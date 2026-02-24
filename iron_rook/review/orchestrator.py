"""Orchestrator for parallel PR review execution."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Callable, Optional, cast, Any
from pathlib import Path

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    BudgetConfig,
    BudgetSnapshot,
    CheckpointData,
    CircuitBreakerConfig,
    CircuitState,
    Finding,
    MergeGate,
    MergePolicy,
    OrchestratorOutput,
    PriorityMergePolicy,
    ReviewInputs,
    ReviewOutput,
    Scope,
    TokenReport,
    ToolPlan,
)
from iron_rook.review.utils.circuit_breaker import CircuitBreaker
from iron_rook.review.utils.checkpoint import CheckpointManager
from iron_rook.review.utils.budget_tracker import BudgetTracker
from iron_rook.review.utils.metrics import MetricsAggregator
from iron_rook.review.utils.executor import (
    CommandExecutor,
    ExecutionResult,
)
from iron_rook.review.sdk_adapter import (
    create_reviewer_agent_from_base,
    review_context_to_user_message,
    agent_result_to_review_output,
    create_error_review_output,
)
from dawn_kestrel.sdk.client import OpenCodeAsyncClient
from dawn_kestrel.core.config import SDKConfig
from dawn_kestrel.agents.execution_queue import AgentExecutionJob, InMemoryAgentExecutionQueue

logger = logging.getLogger(__name__)


class PRReviewOrchestrator:
    def __init__(
        self,
        subagents: List[BaseReviewerAgent],
        command_executor: CommandExecutor | None = None,
        merge_policy: MergePolicy | None = None,
        sdk_client: OpenCodeAsyncClient | None = None,
        project_dir: Optional[Path] = None,
        sequential: bool = False,
        max_retries: int = 3,
        max_parallel_workers: int = 2,
        parallel_queue_timeout_seconds: float = 300.0,
        budget_config: Optional[BudgetConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        enable_checkpoints: bool = True,
        enable_metrics: bool = True,
    ) -> None:
        """Initialize PR review orchestrator.

        Args:
            subagents: List of reviewer agent instances
            command_executor: Optional command executor for running checks
            merge_policy: Optional merge policy for decision making
            sdk_client: Optional OpenCodeAsyncClient for agent execution
            project_dir: Optional project directory for SDK configuration
            sequential: Run agents sequentially instead of parallel (for rate limits)
            max_retries: Max retries on rate limit errors (429)
            max_parallel_workers: Max number of parallel agent workers when sequential=False
            parallel_queue_timeout_seconds: Timeout for parallel queue completion
            budget_config: Optional budget configuration for token/time limits
            circuit_breaker_config: Optional circuit breaker configuration
            enable_checkpoints: Enable checkpoint persistence for resume support
            enable_metrics: Enable token metrics aggregation
        """
        self.subagents = subagents
        self.command_executor = command_executor or CommandExecutor()
        self.merge_policy = merge_policy or PriorityMergePolicy()
        self.sdk_client = sdk_client
        self.project_dir = project_dir or Path.cwd()
        self.sequential = sequential
        self.max_retries = max_retries
        self._parallel_executor = InMemoryAgentExecutionQueue(
            max_workers=max_parallel_workers,
            timeout_seconds=parallel_queue_timeout_seconds,
        )
        self._registered_agents: dict[str, str] = {}

        # Resilience features
        self._circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._budget_config = budget_config
        self._budget_tracker: Optional[BudgetTracker] = None
        self._checkpoint_manager: Optional[CheckpointManager] = None
        self._metrics_aggregator: Optional[MetricsAggregator] = None
        self._enable_checkpoints = enable_checkpoints
        self._enable_metrics = enable_metrics
        self._trace_id: str = ""

        # Initialize per-agent circuit breakers
        for agent in subagents:
            agent_name = agent.get_agent_name()
            self._circuit_breakers[agent_name] = CircuitBreaker(self._circuit_breaker_config)

    async def run_review(
        self, inputs: ReviewInputs, stream_callback: Callable | None = None
    ) -> OrchestratorOutput:
        """Run full review with all subagents in parallel.

        Args:
            inputs: ReviewInputs containing repo details and PR metadata
            stream_callback: Optional callback for streaming progress events

        Returns:
            OrchestratorOutput with merged findings, decision, and tool plan
        """
        from iron_rook.review.utils.git import get_changed_files, get_diff

        self._trace_id = uuid.uuid4().hex[:16]

        if self._budget_config:
            self._budget_tracker = BudgetTracker(self._budget_config)

        if self._enable_metrics:
            self._metrics_aggregator = MetricsAggregator()
            from iron_rook.review.llm_audit_logger import LLMAuditLogger

            LLMAuditLogger.get().set_metrics_aggregator(self._metrics_aggregator)

        if self._enable_checkpoints:
            self._checkpoint_manager = CheckpointManager(Path(inputs.repo_root))

        all_changed_files = await get_changed_files(
            inputs.repo_root, inputs.base_ref, inputs.head_ref
        )
        diff = await get_diff(inputs.repo_root, inputs.base_ref, inputs.head_ref)
        inputs_hash = ""
        if self._checkpoint_manager:
            inputs_hash = self._checkpoint_manager.compute_inputs_hash(all_changed_files, diff)

        try:
            initial_results = await self.run_subagents_parallel(inputs, stream_callback)
        except KeyboardInterrupt:
            if self._checkpoint_manager and inputs_hash:
                checkpoint = CheckpointData(
                    trace_id=self._trace_id,
                    timestamp=datetime.now().isoformat(),
                    repo_root=inputs.repo_root,
                    base_ref=inputs.base_ref,
                    head_ref=inputs.head_ref,
                    inputs_hash=inputs_hash,
                    budget_snapshot=self._budget_tracker.get_snapshot()
                    if self._budget_tracker
                    else None,
                )
                self._checkpoint_manager.save(checkpoint)
                logger.warning("Review interrupted - checkpoint saved for resume")
            raise

        initial_results = [r for r in initial_results if r is not None]

        all_findings = [
            finding for result in initial_results if result for finding in result.findings
        ]
        deduped_findings = self.dedupe_findings(all_findings)

        merge_decision = self.compute_merge_decision(initial_results)
        tool_plan = self.generate_tool_plan(initial_results)

        summary = (
            f"Review completed by {len(initial_results)} agents with "
            f"{len(deduped_findings)} total findings"
        )

        token_metrics: Optional[TokenReport] = None
        if self._metrics_aggregator:
            token_metrics = self._metrics_aggregator.generate_report()

        budget_snapshot: Optional[BudgetSnapshot] = None
        if self._budget_tracker:
            budget_snapshot = self._budget_tracker.get_snapshot()

        # Cleanup checkpoint on successful completion
        if self._checkpoint_manager and inputs_hash:
            self._checkpoint_manager.delete(inputs_hash)
            logger.debug(f"Checkpoint deleted after successful completion: {inputs_hash}")

        return OrchestratorOutput(
            merge_decision=merge_decision,
            findings=deduped_findings,
            tool_plan=tool_plan,
            subagent_results=initial_results,
            summary=summary,
            total_findings=len(deduped_findings),
            token_metrics=token_metrics,
            budget_snapshot=budget_snapshot,
        )

    async def run_subagents_parallel(
        self, inputs: ReviewInputs, stream_callback: Callable | None = None
    ) -> List[ReviewOutput]:
        """Run all subagents in parallel or sequentially based on configuration.

        Args:
            inputs: ReviewInputs with repo details
            stream_callback: Optional progress callback

        Returns:
            List of ReviewOutput from all subagents
        """
        if self.sequential:
            return await self._run_subagents_sequential(inputs, stream_callback)
        return await self._run_subagents_parallel(inputs, stream_callback)

    async def _run_subagents_sequential(
        self, inputs: ReviewInputs, stream_callback: Callable | None = None
    ) -> List[ReviewOutput]:
        """Run all subagents one at a time (for strict rate limits).

        Args:
            inputs: ReviewInputs with repo details
            stream_callback: Optional progress callback

        Returns:
            List of ReviewOutput from all subagents
        """
        from iron_rook.review.utils.git import get_changed_files, get_diff

        verbose_logging = logger.isEnabledFor(logging.DEBUG)
        results: List[ReviewOutput] = []
        completed_agents: Dict[str, Any] = {}
        failed_agents: List[str] = []

        logger.info(f"Starting sequential review with {len(self.subagents)} agents")

        all_changed_files = await get_changed_files(
            inputs.repo_root, inputs.base_ref, inputs.head_ref
        )
        diff = await get_diff(inputs.repo_root, inputs.base_ref, inputs.head_ref)

        inputs_hash = ""
        if self._checkpoint_manager:
            inputs_hash = self._checkpoint_manager.compute_inputs_hash(all_changed_files, diff)

        for idx, agent in enumerate(self.subagents):
            agent_name = agent.get_agent_name()
            logger.info(f"[{agent_name}] Starting agent ({idx + 1}/{len(self.subagents)})")

            result = await self._execute_single_agent(
                agent=agent,
                agent_name=agent_name,
                inputs=inputs,
                all_changed_files=all_changed_files,
                diff=diff,
                stream_callback=stream_callback,
                verbose_logging=verbose_logging,
            )
            results.append(result)

            if result and result.findings or (result and result.severity != "blocking"):
                completed_agents[agent_name] = result.model_dump()
            elif result is None or (result and result.severity == "blocking"):
                failed_agents.append(agent_name)

            if self._checkpoint_manager and inputs_hash:
                self._save_checkpoint(
                    inputs=inputs,
                    inputs_hash=inputs_hash,
                    completed_agents=completed_agents,
                    failed_agents=failed_agents,
                    current_agent=agent_name,
                )

        return results

    async def _run_subagents_parallel(
        self, inputs: ReviewInputs, stream_callback: Callable | None = None
    ) -> List[ReviewOutput]:
        """Run all subagents in parallel using in-memory queue workers.

        Args:
            inputs: ReviewInputs with repo details
            stream_callback: Optional progress callback

        Returns:
            List of ReviewOutput from all subagents
        """
        from iron_rook.review.utils.git import get_changed_files, get_diff

        verbose_logging = logger.isEnabledFor(logging.DEBUG)

        logger.info(
            f"Starting parallel review with {len(self.subagents)} agents, "
            f"max {self._parallel_executor.max_workers} concurrent"
        )

        all_changed_files = await get_changed_files(
            inputs.repo_root, inputs.base_ref, inputs.head_ref
        )
        diff = await get_diff(inputs.repo_root, inputs.base_ref, inputs.head_ref)

        results_by_index: list[ReviewOutput | None] = [None] * len(self.subagents)
        results_lock = asyncio.Lock()

        if verbose_logging:
            logger.info("[VERBOSE] Subagent Details:")
            for idx, agent in enumerate(self.subagents):
                agent_name = agent.get_agent_name()
                logger.info(f"[VERBOSE]   Agent #{idx + 1}: {agent_name}")

        jobs = [
            AgentExecutionJob(index=i, task_id=f"review_{self.subagents[i].get_agent_name()}_{i}")
            for i in range(len(self.subagents))
        ]

        async def execute_parallel_job(job: AgentExecutionJob) -> str:
            idx = job.index
            agent = self.subagents[idx]
            agent_name = agent.get_agent_name()

            result = await self._execute_single_agent(
                agent=agent,
                agent_name=agent_name,
                inputs=inputs,
                all_changed_files=all_changed_files,
                diff=diff,
                stream_callback=stream_callback,
                verbose_logging=verbose_logging,
            )

            async with results_lock:
                results_by_index[idx] = result
            return job.task_id

        batch_result = await self._parallel_executor.run_jobs(
            jobs=jobs, execute=execute_parallel_job
        )

        for index, error in batch_result.errors_by_index.items():
            agent_name = self.subagents[index].get_agent_name()
            logger.error(f"[{agent_name}] Parallel worker failed: {error}")

            if results_by_index[index] is None:
                fallback_context = ReviewContext(
                    changed_files=[],
                    diff="",
                    repo_root=inputs.repo_root,
                    base_ref=inputs.base_ref,
                    head_ref=inputs.head_ref,
                )
                results_by_index[index] = create_error_review_output(
                    agent_name, error, fallback_context
                )

        return [
            result
            if result is not None
            else create_error_review_output(
                self.subagents[index].get_agent_name(),
                "Parallel execution did not return a result",
                ReviewContext(
                    changed_files=[],
                    diff="",
                    repo_root=inputs.repo_root,
                    base_ref=inputs.base_ref,
                    head_ref=inputs.head_ref,
                ),
            )
            for index, result in enumerate(results_by_index)
        ]

    async def _execute_single_agent(
        self,
        agent: BaseReviewerAgent,
        agent_name: str,
        inputs: ReviewInputs,
        all_changed_files: List[str],
        diff: str,
        stream_callback: Callable | None = None,
        verbose_logging: bool = False,
    ) -> ReviewOutput:
        """Execute a single agent with retry logic for rate limits.

        Args:
            agent: BaseReviewerAgent instance to execute
            agent_name: Name of the agent for logging
            inputs: ReviewInputs with repo details
            all_changed_files: List of changed files
            diff: Git diff string
            stream_callback: Optional progress callback
            verbose_logging: Whether to log verbose output

        Returns:
            ReviewOutput from agent execution
        """
        import random

        circuit = self._circuit_breakers.get(agent_name)
        if circuit and not await circuit.can_execute():
            logger.warning(f"[{agent_name}] Circuit breaker OPEN, skipping execution")
            return self._create_circuit_open_output(agent_name, inputs)

        if self._budget_tracker and self._budget_tracker.is_exhausted():
            logger.warning(f"[{agent_name}] Budget exhausted, stopping review")
            return create_error_review_output(
                agent_name,
                "Budget exhausted",
                ReviewContext(
                    changed_files=[],
                    diff="",
                    repo_root=inputs.repo_root,
                    base_ref=inputs.base_ref,
                    head_ref=inputs.head_ref,
                ),
            )

        if agent.is_relevant_to_changes(all_changed_files):
            changed_files = all_changed_files
        else:
            changed_files = []
            logger.info(f"[{agent_name}] Agent not relevant to changes, skipping review")

        context = ReviewContext(
            changed_files=changed_files,
            diff=diff,
            repo_root=inputs.repo_root,
            base_ref=inputs.base_ref,
            head_ref=inputs.head_ref,
            pr_title=inputs.pr_title,
            pr_description=inputs.pr_description,
        )

        logger.info(
            f"[{agent_name}] Context built: {len(context.changed_files)} files, {len(context.diff)} chars diff"
        )

        if verbose_logging:
            logger.info(f"[VERBOSE] [{agent_name}] Context details:")
            logger.info(f"[VERBOSE] [{agent_name}]   Repo root: {context.repo_root}")
            logger.info(f"[VERBOSE] [{agent_name}]   Base ref: {context.base_ref}")
            logger.info(f"[VERBOSE] [{agent_name}]   Head ref: {context.head_ref}")

        context_or_fallback = context

        for attempt in range(self.max_retries + 1):
            try:
                if stream_callback:
                    await stream_callback(agent_name, "started", {})

                if agent.prefers_direct_review():
                    if verbose_logging:
                        logger.info(f"[VERBOSE] [{agent_name}] Using direct review (agent has FSM)")
                    result = await agent.review(context)
                else:
                    result = await self._execute_agent_via_sdk(
                        agent, context, agent_name, verbose_logging
                    )

                logger.info(f"[{agent_name}] Review completed")
                if result:
                    logger.info(
                        f"[{agent_name}] Result: {result.severity} severity, {len(result.findings)} findings"
                    )

                if circuit:
                    await circuit.record_success()

                if stream_callback:
                    await stream_callback(agent_name, "completed", {}, result=result)

                return result

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = self._is_rate_limit_error(error_msg)

                if is_rate_limit and attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"[{agent_name}] Rate limit hit (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {backoff:.1f}s..."
                    )
                    await asyncio.sleep(backoff)
                    continue

                logger.error(f"[{agent_name}] Error: {error_msg}", exc_info=True)

                if circuit:
                    await circuit.record_failure()

                if stream_callback:
                    await stream_callback(agent_name, "error", {"error": error_msg})

                return create_error_review_output(agent_name, error_msg, context_or_fallback)

        if circuit:
            await circuit.record_failure()

        return create_error_review_output(agent_name, "Max retries exceeded", context_or_fallback)

    def _save_checkpoint(
        self,
        inputs: ReviewInputs,
        inputs_hash: str,
        completed_agents: Dict[str, Any],
        failed_agents: List[str],
        current_agent: str,
    ) -> None:
        """Save a checkpoint after each agent completes.

        Args:
            inputs: ReviewInputs for context
            inputs_hash: Hash of the inputs for validation
            completed_agents: Dict of agent_name -> ReviewOutput for completed agents
            failed_agents: List of agents that failed
            current_agent: Currently executing agent
        """
        if not self._checkpoint_manager:
            return

        checkpoint = CheckpointData(
            trace_id=self._trace_id,
            timestamp=datetime.now().isoformat(),
            repo_root=inputs.repo_root,
            base_ref=inputs.base_ref,
            head_ref=inputs.head_ref,
            inputs_hash=inputs_hash,
            completed_agents=completed_agents,
            failed_agents=failed_agents,
            current_agent=current_agent,
            budget_snapshot=self._budget_tracker.get_snapshot() if self._budget_tracker else None,
        )
        self._checkpoint_manager.save(checkpoint)
        logger.debug(f"Checkpoint saved after {current_agent}")

    def _create_circuit_open_output(self, agent_name: str, inputs: ReviewInputs) -> ReviewOutput:
        """Create an error output when circuit breaker is open.

        Args:
            agent_name: Name of the agent
            inputs: ReviewInputs for context

        Returns:
            ReviewOutput indicating circuit breaker blocked execution
        """
        return create_error_review_output(
            agent_name,
            "Circuit breaker open - too many recent failures",
            ReviewContext(
                changed_files=[],
                diff="",
                repo_root=inputs.repo_root,
                base_ref=inputs.base_ref,
                head_ref=inputs.head_ref,
            ),
        )

    def _is_rate_limit_error(self, error_msg: str) -> bool:
        """Check if error is a rate limit error.

        Args:
            error_msg: Error message string

        Returns:
            True if this is a rate limit error
        """
        rate_limit_indicators = [
            "429",
            "rate limit",
            "rate_limit",
            "rateLimit",
            "too many requests",
            "1302",
            "1303",
            "1305",
            "1308",
            "1310",
            "high concurrency",
            "high frequency",
            "usage limit",
        ]
        error_lower = error_msg.lower()
        return any(indicator in error_lower for indicator in rate_limit_indicators)

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Backoff time in seconds
        """
        import random

        base_delay = 2.0
        max_delay = 60.0
        jitter = random.uniform(0, 0.5)
        delay = min(base_delay * (2**attempt) + jitter, max_delay)
        return delay

    async def _execute_agent_via_sdk(
        self,
        agent: BaseReviewerAgent,
        context: ReviewContext,
        agent_name: str,
        verbose_logging: bool,
    ) -> ReviewOutput:
        """Execute agent via dawn-kestrel SDK.

        Args:
            agent: BaseReviewerAgent instance to execute
            context: ReviewContext with PR details
            agent_name: Name of the agent for logging
            verbose_logging: Whether to log verbose output

        Returns:
            ReviewOutput from agent execution
        """
        config = SDKConfig(project_dir=self.project_dir)
        client = self.sdk_client or OpenCodeAsyncClient(config=config)

        system_prompt = agent.get_system_prompt()
        user_message = review_context_to_user_message(context, system_prompt)

        if verbose_logging:
            logger.info(f"[VERBOSE] [{agent_name}] Using SDK for execution")
            logger.info(
                f"[VERBOSE] [{agent_name}]   User message length: {len(user_message)} chars"
            )

        register_result = await client.register_agent(create_reviewer_agent_from_base(agent))
        if register_result.is_err():
            err = cast(Any, register_result)
            error_msg = err.error
            logger.error(f"[{agent_name}] Failed to register agent: {error_msg}")
            return create_error_review_output(
                agent_name, f"Agent registration failed: {error_msg}", context
            )

        session_result = await client.create_session(title=f"PR Review: {agent_name}")
        if session_result.is_err():
            err = cast(Any, session_result)
            error_msg = err.error
            logger.error(f"[{agent_name}] Failed to create session: {error_msg}")
            return create_error_review_output(
                agent_name, f"Session creation failed: {error_msg}", context
            )

        session = session_result.unwrap()
        logger.info(f"[{agent_name}] Created session: {session.id}")

        execute_result = await client.execute_agent(
            agent_name=agent_name,
            session_id=session.id,
            user_message=user_message,
        )

        if execute_result.is_err():
            err = cast(Any, execute_result)
            error_msg = err.error
            logger.error(f"[{agent_name}] Agent execution failed: {error_msg}")
            return create_error_review_output(agent_name, f"Execution failed: {error_msg}", context)

        agent_result = execute_result.unwrap()
        return agent_result_to_review_output(agent_name, agent_result, context)

    def compute_merge_decision(self, results: List[ReviewOutput]) -> MergeGate:
        """Compute merge decision from all agent results using merge policy.

        Args:
            results: List of ReviewOutput from all agents

        Returns:
            MergeGate with final decision
        """
        return self.merge_policy.compute_merge_decision(results)

    def dedupe_findings(self, all_findings: List[Finding]) -> List[Finding]:
        """Deduplicate findings based on title and severity.

        Args:
            all_findings: List of all findings from all agents

        Returns:
            Deduplicated list of findings
        """
        seen = set()
        deduped = []

        for finding in all_findings:
            key = (finding.title, finding.severity)
            if key not in seen:
                seen.add(key)
                deduped.append(finding)

        return deduped

    def generate_tool_plan(self, results: List[ReviewOutput]) -> ToolPlan:
        """Generate tool plan from all agent results.

        Args:
            results: List of ReviewOutput from all agents

        Returns:
            ToolPlan with proposed commands
        """
        commands = []

        for result in results:
            if not result:
                continue
            for check in result.checks:
                commands.extend(check.commands)

        return ToolPlan(
            proposed_commands=commands,
        )

    async def execute_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """Execute a shell command and return result.

        Args:
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            ExecutionResult with stdout, stderr, and return code
        """
        return await self.command_executor.execute(command, timeout)
