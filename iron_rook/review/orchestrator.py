"""Orchestrator for parallel PR review agent execution."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Callable

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from dawn_kestrel.agents.runtime import AgentRuntime
from dawn_kestrel.core.agent_types import SessionManagerLike
from dawn_kestrel.agents.registry import AgentRegistry
from iron_rook.review.contracts import (
    Finding,
    MergeGate,
    MergePolicy,
    OrchestratorOutput,
    parse_delegation_requests,
    PriorityMergePolicy,
    ReviewInputs,
    ReviewOutput,
    Scope,
    ToolPlan,
    BudgetConfig,
    BudgetTracker,
    ALLOWLISTED_DELEGATION_AGENTS,
)
from iron_rook.review.context_builder import ContextBuilder, DefaultContextBuilder
from iron_rook.review.discovery import EntryPointDiscovery
from iron_rook.review.streaming import ReviewStreamManager
from iron_rook.review.utils.executor import (
    CommandExecutor,
    ExecutionResult,
)
from iron_rook.review.utils.session_helper import (
    create_review_session,
)
from iron_rook.review.utils.result_transformers import (
    agent_result_to_review_output,
)
from dawn_kestrel.tools import create_builtin_registry
from dawn_kestrel.tools.framework import ToolRegistry

logger = logging.getLogger(__name__)


class PRReviewOrchestrator:
    def __init__(
        self,
        subagents: List[BaseReviewerAgent],
        command_executor: CommandExecutor | None = None,
        stream_manager: ReviewStreamManager | None = None,
        discovery: EntryPointDiscovery | None = None,
        context_builder: ContextBuilder | None = None,
        merge_policy: MergePolicy | None = None,
        budget_config: BudgetConfig | None = None,
        use_agent_runtime: bool = False,
        agent_runtime: AgentRuntime | None = None,
        session_manager: SessionManagerLike | None = None,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        self.subagents = subagents
        self.command_executor = command_executor or CommandExecutor()
        self.stream_manager = stream_manager or ReviewStreamManager()
        # Entry point discovery module for intelligent context filtering
        self.discovery = discovery or EntryPointDiscovery()
        self.context_builder = context_builder or DefaultContextBuilder(self.discovery)
        self.merge_policy = merge_policy or PriorityMergePolicy()
        self.budget_config = budget_config or BudgetConfig()
        self.budget_tracker = BudgetTracker(self.budget_config)
        # Feature flag for using AgentRuntime execution path
        self.use_agent_runtime = use_agent_runtime
        # AgentRuntime dependencies (optional, only used when use_agent_runtime=True)
        self.agent_runtime = agent_runtime
        self.session_manager = session_manager
        self.agent_registry = agent_registry

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
        await self.stream_manager.start_stream()

        initial_results = await self.run_subagents_parallel(inputs, stream_callback)

        all_findings = [finding for result in initial_results for finding in result.findings]
        deduped_findings = self.dedupe_findings(all_findings)

        second_wave_results = await self.second_wave_delegated_followups(
            initial_results, inputs, stream_callback
        )

        second_wave_findings = [
            finding for result in second_wave_results for finding in result.findings
        ]

        all_findings.extend(second_wave_findings)
        deduped_findings = self.dedupe_findings(all_findings)

        merge_decision = self.compute_merge_decision(initial_results + second_wave_results)
        tool_plan = self.generate_tool_plan(initial_results + second_wave_results)

        summary = (
            f"Review completed by {len(initial_results)} initial agents and "
            f"{len(second_wave_results)} delegated follow-ups with "
            f"{len(deduped_findings)} total findings"
        )

        return OrchestratorOutput(
            merge_decision=merge_decision,
            findings=deduped_findings,
            tool_plan=tool_plan,
            subagent_results=initial_results + second_wave_results,
            summary=summary,
            total_findings=len(deduped_findings),
        )

    async def run_subagents_parallel(
        self, inputs: ReviewInputs, stream_callback: Callable | None = None
    ) -> List[ReviewOutput]:
        import logging

        logger = logging.getLogger(__name__)
        verbose_logging = logger.isEnabledFor(logging.DEBUG)

        tasks = []
        semaphore = asyncio.Semaphore(4)
        logger.info(
            f"Starting parallel review with {len(self.subagents)} agents, max 4 concurrent, timeout={inputs.timeout_seconds}s"
        )

        if verbose_logging:
            logger.info("[VERBOSE] Subagent Details:")
            for idx, agent in enumerate(self.subagents):
                agent_name = agent.get_agent_name()
                logger.info(f"[VERBOSE]   Agent #{idx + 1}: {agent_name}")

        for idx, agent in enumerate(self.subagents):

            async def run_with_timeout(
                current_agent: BaseReviewerAgent = agent,
            ) -> ReviewOutput | None:
                async with semaphore:
                    agent_name = current_agent.get_agent_name()
                    logger.info(
                        f"[{agent_name}] Starting agent (timeout: {inputs.timeout_seconds}s)"
                    )

                    if verbose_logging:
                        logger.info(
                            f"[VERBOSE] [{agent_name}] Agent class: {current_agent.__class__.__name__}"
                        )
                        logger.info(
                            f"[VERBOSE] [{agent_name}] Allowed tools: {current_agent.get_allowed_tools()}"
                        )
                        logger.info(
                            f"[VERBOSE] [{agent_name}] Relevant patterns: {current_agent.get_relevant_file_patterns()}"
                        )

                    try:
                        if stream_callback:
                            await self.stream_manager.emit_progress(agent_name, "started", {})

                        logger.info(f"[{agent_name}] Building context...")
                        context = await self._build_context(inputs, current_agent)
                        logger.info(
                            f"[{agent_name}] Context built: {len(context.changed_files)} files, {len(context.diff)} chars diff"
                        )
                        logger.debug(
                            f"[{agent_name}] Changed files: {', '.join(context.changed_files[:10])}"
                        )

                        if verbose_logging:
                            logger.info(f"[VERBOSE] [{agent_name}] Context details:")
                            logger.info(
                                f"[VERBOSE] [{agent_name}]   Repo root: {context.repo_root}"
                            )
                            logger.info(f"[VERBOSE] [{agent_name}]   Base ref: {context.base_ref}")
                            logger.info(f"[VERBOSE] [{agent_name}]   Head ref: {context.head_ref}")
                            logger.info(f"[VERBOSE] [{agent_name}]   PR title: {context.pr_title}")

                        prefers_direct_review = (
                            hasattr(current_agent, "prefers_direct_review")
                            and current_agent.prefers_direct_review()
                        )

                        if self.use_agent_runtime and not prefers_direct_review:
                            logger.info(f"[{agent_name}] Using AgentRuntime execution path")
                            result = await asyncio.wait_for(
                                self._execute_via_agent_runtime(agent_name, context),
                                timeout=inputs.timeout_seconds,
                            )
                        else:
                            logger.info(
                                f"[{agent_name}] Calling agent review method (direct path)..."
                            )
                            result = await asyncio.wait_for(
                                current_agent.review(context), timeout=inputs.timeout_seconds
                            )

                        logger.info(
                            f"[{agent_name}] LLM response received: {len(result.findings)} findings"
                        )
                        if verbose_logging:
                            logger.info(f"[VERBOSE] [{agent_name}] Result summary:")
                            logger.info(f"[VERBOSE] [{agent_name}]   Agent: {result.agent}")
                            logger.info(f"[VERBOSE] [{agent_name}]   Severity: {result.severity}")
                            logger.info(
                                f"[VERBOSE] [{agent_name}]   Summary: {result.summary[:200]}{'...' if len(result.summary) > 200 else ''}"
                            )
                            logger.info(
                                f"[VERBOSE] [{agent_name}]   Findings: {len(result.findings)}"
                            )
                            logger.info(f"[VERBOSE] [{agent_name}]   Checks: {len(result.checks)}")
                            logger.info(f"[VERBOSE] [{agent_name}]   Skips: {len(result.skips)}")
                            logger.info(
                                f"[VERBOSE] [{agent_name}]   Merge gate decision: {result.merge_gate.decision}"
                            )
                            logger.info(
                                f"[VERBOSE] [{agent_name}]   Scope reasoning: {result.scope.reasoning[:200]}{'...' if len(result.scope.reasoning) > 200 else ''}"
                            )

                        if stream_callback:
                            await self.stream_manager.emit_result(agent_name, result)

                        return result

                    except RuntimeError as e:
                        if self.use_agent_runtime:
                            raise
                        error_msg = f"Agent {agent_name} failed: {str(e)}"
                        logger.error(f"[{agent_name}] {error_msg}", exc_info=True)
                        if stream_callback:
                            await self.stream_manager.emit_error(agent_name, error_msg)

                        return ReviewOutput(
                            agent=agent_name,
                            summary="Agent failed with exception",
                            severity="critical",
                            scope=Scope(relevant_files=[], ignored_files=[], reasoning="Exception"),
                            checks=[],
                            skips=[],
                            findings=[],
                            merge_gate=MergeGate(
                                decision="needs_changes",
                                must_fix=[],
                                should_fix=[],
                                notes_for_coding_agent=[],
                            ),
                        )

                    except asyncio.TimeoutError:
                        error_msg = f"Agent {agent_name} timed out after {inputs.timeout_seconds}s"
                        logger.error(f"[{agent_name}] {error_msg}")
                        if stream_callback:
                            await self.stream_manager.emit_error(agent_name, error_msg)

                        return ReviewOutput(
                            agent=agent_name,
                            summary="Agent timed out",
                            severity="critical",
                            scope=Scope(relevant_files=[], ignored_files=[], reasoning="Timeout"),
                            checks=[],
                            skips=[],
                            findings=[],
                            merge_gate=MergeGate(
                                decision="needs_changes",
                                must_fix=[],
                                should_fix=[],
                                notes_for_coding_agent=[],
                            ),
                        )

                    except Exception as e:
                        error_msg = f"Agent {agent_name} failed: {str(e)}"
                        logger.error(f"[{agent_name}] {error_msg}", exc_info=True)
                        if stream_callback:
                            await self.stream_manager.emit_error(agent_name, error_msg)

                        return ReviewOutput(
                            agent=agent_name,
                            summary="Agent failed with exception",
                            severity="critical",
                            scope=Scope(relevant_files=[], ignored_files=[], reasoning="Exception"),
                            checks=[],
                            skips=[],
                            findings=[],
                            merge_gate=MergeGate(
                                decision="needs_changes",
                                must_fix=[],
                                should_fix=[],
                                notes_for_coding_agent=[],
                            ),
                        )

            tasks.append(run_with_timeout())

        logger.info(f"Gathering results from {len(tasks)} parallel agents...")
        results = await asyncio.gather(*tasks)
        logger.info(
            f"All agents completed: {len([r for r in results if r.summary != 'Agent timed out' and r.summary != 'Agent failed with exception'])} successful"
        )

        return results

    async def execute_command(self, command: str, timeout: int = 30) -> ExecutionResult:
        """Execute a command via CommandExecutor.

        Args:
            command: Command string to execute
            timeout: Maximum execution time in seconds

        Returns:
            ExecutionResult with command output and metadata
        """
        return await self.command_executor.execute(command, timeout=timeout)

    def compute_merge_decision(self, results: List[ReviewOutput]) -> MergeGate:
        """Compute merge decision using injected policy.

        Args:
            results: List of ReviewOutput from subagents

        Returns:
            MergeGate with decision and fix lists
        """
        return self.merge_policy.compute_merge_decision(results)

    def dedupe_findings(self, all_findings: List[Finding]) -> List[Finding]:
        """De-duplicate findings by grouping.

        Args:
            all_findings: List of all findings from subagents

        Returns:
            List of unique findings
        """
        seen = set()
        unique = []

        for finding in all_findings:
            key = (finding.id, finding.title, finding.severity)

            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique

    def generate_tool_plan(self, results: List[ReviewOutput]) -> ToolPlan:
        """Generate tool plan with proposed commands.

        Args:
            results: List of ReviewOutput from subagents

        Returns:
            ToolPlan with proposed commands and execution summary
        """
        proposed_commands = []
        auto_fix_available = False

        for result in results:
            for check in result.checks:
                if check.required:
                    proposed_commands.extend(check.commands)

        if proposed_commands:
            auto_fix_available = any(
                cmd.startswith("ruff") or cmd.startswith("black") for cmd in proposed_commands
            )

        summary = f"Generated tool plan with {len(proposed_commands)} commands"

        return ToolPlan(
            proposed_commands=list(set(proposed_commands)),
            auto_fix_available=auto_fix_available,
            execution_summary=summary,
        )

    async def _build_context(self, inputs: ReviewInputs, agent: BaseReviewerAgent) -> ReviewContext:
        return await self.context_builder.build(inputs, agent)

    async def _execute_via_agent_runtime(
        self, agent_name: str, context: ReviewContext
    ) -> ReviewOutput:
        """Execute agent via AgentRuntime framework.

        This method:
        1. Creates ephemeral session for agent execution
        2. Creates filtered tool registry based on agent's allowed tools
        3. Calls AgentRuntime.execute_agent()
        4. Transforms AgentResult to ReviewOutput

        Args:
            agent_name: Name of agent to execute
            context: ReviewContext with PR information

        Returns:
            ReviewOutput with findings, severity, and merge gate decision

        Raises:
            RuntimeError: If AgentRuntime dependencies not configured
            ValueError: If agent not found in AgentRegistry
        """
        if not self.agent_runtime:
            raise RuntimeError(
                "AgentRuntime not configured. Set agent_runtime parameter when "
                "use_agent_runtime=True"
            )
        if not self.session_manager:
            raise RuntimeError(
                "SessionManager not configured. Set session_manager parameter when "
                "use_agent_runtime=True"
            )
        if not self.agent_registry:
            raise RuntimeError(
                "AgentRegistry not configured. Set agent_registry parameter when "
                "use_agent_runtime=True"
            )

        logger.info(f"[{agent_name}] Executing via AgentRuntime with ephemeral session")

        session = create_review_session(context.repo_root, context)
        logger.debug(f"[{agent_name}] Created session: {session.id}")

        user_message_parts = [
            "## Review Context",
            "",
            f"**Repository Root**: {context.repo_root}",
            "",
            "### Changed Files",
        ]
        for file_path in context.changed_files:
            user_message_parts.append(f"- {file_path}")

        if context.base_ref and context.head_ref:
            user_message_parts.append("")
            user_message_parts.append("### Git Diff")
            user_message_parts.append(f"**Base Ref**: {context.base_ref}")
            user_message_parts.append(f"**Head Ref**: {context.head_ref}")

        user_message_parts.append("")
        user_message_parts.append("### Diff Content")
        user_message_parts.append("```diff")
        user_message_parts.append(context.diff)
        user_message_parts.append("```")

        if context.pr_title:
            user_message_parts.append("")
            user_message_parts.append("### Pull Request")
            user_message_parts.append(f"**Title**: {context.pr_title}")
            if context.pr_description:
                user_message_parts.append(f"**Description**:\n{context.pr_description}")

        user_message = "\n".join(user_message_parts)
        logger.debug(f"[{agent_name}] Formatted user message: {len(user_message)} chars")

        agent_tools = self._get_agent_allowed_tools(agent_name)
        logger.debug(f"[{agent_name}] Agent allowed tools: {agent_tools}")

        tools_registry = create_builtin_registry()
        filtered_tools = {
            tool_id: tool_def
            for tool_id, tool_def in tools_registry.tools.items()
            if tool_id in agent_tools
        }

        filtered_registry = ToolRegistry()
        for tool_id, tool_def in filtered_tools.items():
            await filtered_registry.register(tool_def, tool_id=tool_id)

        logger.debug(f"[{agent_name}] Filtered tool registry: {len(filtered_registry.tools)} tools")

        agent_result = await self.agent_runtime.execute_agent(
            agent_name=agent_name,
            session_id=session.id,
            user_message=user_message,
            session_manager=self.session_manager,
            tools=filtered_registry,
            skills=[],
        )

        logger.info(
            f"[{agent_name}] AgentRuntime execution complete in {agent_result.duration:.2f}s"
        )

        output = agent_result_to_review_output(agent_result, context)
        logger.info(f"[{agent_name}] Transformed AgentResult to ReviewOutput")

        return output

    def _get_agent_allowed_tools(self, agent_name: str) -> List[str]:
        """Get allowed tools list for agent from its allowed tools method.

        Args:
            agent_name: Name of the agent

        Returns:
            List of allowed tool names
        """
        for agent in self.subagents:
            if agent.get_agent_name() == agent_name:
                return agent.get_allowed_tools()

        logger.warning(f"Agent {agent_name} not found in subagents, returning empty allowed tools")
        return []

    async def second_wave_delegated_followups(
        self,
        initial_results: List[ReviewOutput],
        inputs: ReviewInputs,
        stream_callback: Callable | None = None,
    ) -> List[ReviewOutput]:
        from iron_rook.review.registry import ReviewerRegistry

        import logging

        logger = logging.getLogger(__name__)
        verbose_logging = logger.isEnabledFor(logging.DEBUG)

        logger.info("Starting second-wave delegation follow-ups")

        delegation_result = parse_delegation_requests(
            initial_results, allowed_agents=ALLOWLISTED_DELEGATION_AGENTS
        )

        if not delegation_result.valid:
            logger.warning(f"Skipping second-wave delegation: {delegation_result.skip_reason}")
            return []

        if not delegation_result.requests:
            logger.info("No delegation requests found in initial results")
            return []

        logger.info(
            f"Found {len(delegation_result.requests)} delegation requests, "
            f"budget allows max {self.budget_config.max_delegated_actions} actions"
        )

        filter_requests = []
        skip_reasons = []

        for request in delegation_result.requests:
            if not self.budget_tracker.can_delegate_action():
                skip_reasons.append(
                    f"Delegation to '{request.agent}' skipped: budget exceeded "
                    f"({self.budget_tracker.delegated_action_count}/{self.budget_config.max_delegated_actions} actions used)"
                )
                continue

            if request.agent not in ReviewerRegistry.get_all_names():
                skip_reasons.append(
                    f"Delegation to '{request.agent}' skipped: agent not registered"
                )
                continue

            filter_requests.append(request)
            self.budget_tracker.record_delegated_action()

        if skip_reasons:
            logger.warning(f"Skipped {len(skip_reasons)} delegation requests")
            for reason in skip_reasons:
                logger.warning(f"  - {reason}")

        if not filter_requests:
            logger.info("No valid delegation requests remaining after filtering")
            return []

        logger.info(
            f"Executing {len(filter_requests)} delegated follow-ups with "
            f"concurrency limit {self.budget_config.max_concurrency}"
        )

        if verbose_logging:
            logger.info("")
            logger.info("[VERBOSE] ===== SECOND-WAVE DELEGATION =====")
            logger.info(f"[VERBOSE] Delegated agents: {[req.agent for req in filter_requests]}")
            for req in filter_requests:
                logger.info(f"[VERBOSE]   {req.agent}: {req.reason}")
            logger.info("[VERBOSE] ===== END SECOND-WAVE DELEGATION =====")
            logger.info("")

        second_wave_results = []
        tasks = []
        semaphore = asyncio.Semaphore(self.budget_config.max_concurrency)

        for request in filter_requests:

            async def run_delegated_agent(req: DelegationRequest = request) -> ReviewOutput | None:
                async with semaphore:
                    if not self.budget_tracker.can_execute_command():
                        logger.warning(f"Concurrency limit reached for {req.agent}, skipping")
                        return None

                    self.budget_tracker.add_active_command()

                    try:
                        if stream_callback:
                            await self.stream_manager.emit_progress(req.agent, "started", {})

                        logger.info(
                            f"[second-wave] Starting delegated agent {req.agent}: {req.reason}"
                        )

                        agent_class = ReviewerRegistry.get_reviewer(req.agent)
                        agent = agent_class()

                        context = await self._build_context(inputs, agent)
                        result = await asyncio.wait_for(
                            agent.review(context), timeout=self.budget_config.timeout_seconds
                        )

                        logger.info(
                            f"[second-wave] Agent {req.agent} completed: "
                            f"{len(result.findings)} findings"
                        )

                        if stream_callback:
                            await self.stream_manager.emit_result(req.agent, result)

                        return result

                    except asyncio.TimeoutError:
                        error_msg = (
                            f"Second-wave agent {req.agent} timed out after "
                            f"{self.budget_config.timeout_seconds}s"
                        )
                        logger.error(f"[{req.agent}] {error_msg}")
                        if stream_callback:
                            await self.stream_manager.emit_error(req.agent, error_msg)

                        return ReviewOutput(
                            agent=req.agent,
                            summary="Second-wave agent timed out",
                            severity="critical",
                            scope=Scope(relevant_files=[], ignored_files=[], reasoning="Timeout"),
                            checks=[],
                            skips=[],
                            findings=[],
                            merge_gate=MergeGate(
                                decision="needs_changes",
                                must_fix=[],
                                should_fix=[],
                                notes_for_coding_agent=[],
                            ),
                        )

                    except Exception as e:
                        error_msg = f"Second-wave agent {req.agent} failed: {str(e)}"
                        logger.error(f"[{req.agent}] {error_msg}", exc_info=True)
                        if stream_callback:
                            await self.stream_manager.emit_error(req.agent, error_msg)

                        return ReviewOutput(
                            agent=req.agent,
                            summary="Second-wave agent failed with exception",
                            severity="critical",
                            scope=Scope(relevant_files=[], ignored_files=[], reasoning="Exception"),
                            checks=[],
                            skips=[],
                            findings=[],
                            merge_gate=MergeGate(
                                decision="needs_changes",
                                must_fix=[],
                                should_fix=[],
                                notes_for_coding_agent=[],
                            ),
                        )

                    finally:
                        self.budget_tracker.remove_active_command()

            tasks.append(run_delegated_agent())

        if tasks:
            results = await asyncio.gather(*tasks)
            second_wave_results = [r for r in results if r is not None]

        logger.info(
            f"Second-wave delegation completed: {len(second_wave_results)} agents returned results"
        )

        return second_wave_results
