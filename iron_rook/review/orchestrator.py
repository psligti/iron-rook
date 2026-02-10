"""Orchestrator for parallel PR review execution."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Callable

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    Finding,
    MergeGate,
    MergePolicy,
    OrchestratorOutput,
    PriorityMergePolicy,
    ReviewInputs,
    ReviewOutput,
    Scope,
    ToolPlan,
)
from iron_rook.review.utils.executor import (
    CommandExecutor,
    ExecutionResult,
)

logger = logging.getLogger(__name__)


class PRReviewOrchestrator:
    def __init__(
        self,
        subagents: List[BaseReviewerAgent],
        command_executor: CommandExecutor | None = None,
        merge_policy: MergePolicy | None = None,
    ) -> None:
        self.subagents = subagents
        self.command_executor = command_executor or CommandExecutor()
        self.merge_policy = merge_policy or PriorityMergePolicy()

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
        initial_results = await self.run_subagents_parallel(inputs, stream_callback)

        all_findings = [finding for result in initial_results for finding in result.findings]
        deduped_findings = self.dedupe_findings(all_findings)

        merge_decision = self.compute_merge_decision(initial_results)
        tool_plan = self.generate_tool_plan(initial_results)

        summary = (
            f"Review completed by {len(initial_results)} agents with "
            f"{len(deduped_findings)} total findings"
        )

        return OrchestratorOutput(
            merge_decision=merge_decision,
            findings=deduped_findings,
            tool_plan=tool_plan,
            subagent_results=initial_results,
            summary=summary,
            total_findings=len(deduped_findings),
        )

    async def run_subagents_parallel(
        self, inputs: ReviewInputs, stream_callback: Callable | None = None
    ) -> List[ReviewOutput]:
        """Run all subagents in parallel with semaphore limiting.

        Args:
            inputs: ReviewInputs with repo details
            stream_callback: Optional progress callback

        Returns:
            List of ReviewOutput from all subagents
        """
        from iron_rook.review.utils.git import get_changed_files, get_diff

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

            async def run_with_timeout(current_agent=agent):
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
                                await stream_callback(agent_name, "started", {})

                            logger.info(f"[{agent_name}] Building context...")
                            all_changed_files = await get_changed_files(
                                inputs.repo_root, inputs.base_ref, inputs.head_ref
                            )
                            diff = await get_diff(
                                inputs.repo_root, inputs.base_ref, inputs.head_ref
                            )

                            # Use agent's relevance filtering
                            if current_agent.is_relevant_to_changes(all_changed_files):
                                changed_files = all_changed_files
                            else:
                                changed_files = []
                                logger.info(
                                    f"[{agent_name}] Agent not relevant to changes, skipping review"
                                )

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
                            logger.debug(
                                f"[{agent_name}] Changed files: {', '.join(context.changed_files[:10])}"
                            )

                            if verbose_logging:
                                logger.info(f"[VERBOSE] [{agent_name}] Context details:")
                                logger.info(
                                    f"[VERBOSE] [{agent_name}]   Repo root: {context.repo_root}"
                                )
                                logger.info(
                                    f"[VERBOSE] [{agent_name}]   Base ref: {context.base_ref}"
                                )
                                logger.info(
                                    f"[VERBOSE] [{agent_name}]   Head ref: {context.head_ref}"
                                )
                                logger.info(
                                    f"[VERBOSE] [{agent_name}]   PR title: {context.pr_title}"
                                )

                            result = await asyncio.wait_for(
                                current_agent.review(context),
                                timeout=inputs.timeout_seconds,
                            )

                            logger.info(f"[{agent_name}] Review completed")
                            logger.info(
                                f"[{agent_name}] Result: {result.severity} severity, {len(result.findings)} findings"
                            )

                            if stream_callback:
                                await stream_callback(agent_name, "completed", {}, result=result)

                            return result

                        except asyncio.TimeoutError:
                            error_msg = f"Agent timed out after {inputs.timeout_seconds}s"
                            logger.error(f"[{agent_name}] {error_msg}")

                            if stream_callback:
                                await stream_callback(agent_name, "error", {"error": error_msg})

                            return ReviewOutput(
                                agent=agent_name,
                                severity="blocking",
                                summary=f"Agent timed out after {inputs.timeout_seconds}s",
                                findings=[],
                                scope=Scope(
                                    relevant_files=[],
                                    ignored_files=[],
                                    reasoning="Agent timed out before completing review",
                                ),
                                checks=[],
                                skips=[],
                                merge_gate=MergeGate(
                                    decision="block",
                                    must_fix=[f"Agent {agent_name} timed out - review incomplete"],
                                    should_fix=[],
                                    notes_for_coding_agent=[],
                                ),
                            )

                        except Exception as e:
                            error_msg = str(e)
                            logger.error(f"[{agent_name}] Error: {error_msg}", exc_info=True)

                            if stream_callback:
                                await stream_callback(agent_name, "error", {"error": error_msg})

                            return ReviewOutput(
                                agent=agent_name,
                                severity="blocking",
                                summary=f"Agent error: {error_msg}",
                                findings=[],
                                scope=Scope(
                                    relevant_files=[],
                                    ignored_files=[],
                                    reasoning=f"Agent encountered error: {error_msg}",
                                ),
                                checks=[],
                                skips=[],
                                merge_gate=MergeGate(
                                    decision="block",
                                    must_fix=[f"Agent {agent_name} failed: {error_msg}"],
                                    should_fix=[],
                                    notes_for_coding_agent=[],
                                ),
                            )

            tasks.append(run_with_timeout())

        results = await asyncio.gather(*tasks, return_exceptions=False)
        return results

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
