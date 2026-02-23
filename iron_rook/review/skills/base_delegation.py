"""Base class for delegation skills that dispatch work to subagents.

This module provides BaseDelegationSkill, an abstract base class for skills
that delegate work to subagents for parallel execution.

Key features:
- Abstract methods for subagent class and request building
- Concurrent subagent execution with asyncio.gather()
- Error handling with graceful degradation
- Result aggregation across subagent outputs
"""

from __future__ import annotations

import asyncio
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Type

from iron_rook.review.base import BaseReviewerAgent, ReviewContext

if TYPE_CHECKING:
    from iron_rook.review.contracts import ReviewOutput

logger = logging.getLogger(__name__)


class BaseDelegationSkill(BaseReviewerAgent):
    """Abstract base class for skills that delegate work to subagents.

    Subclasses must implement:
    - get_subagent_class(): Return the subagent class to instantiate
    - build_subagent_request(): Build request dict for each subagent

    Provides:
    - execute_subagents_concurrently(): Run subagents in parallel
    - _aggregate_results(): Combine subagent outputs

    Usage:
        class MyDelegationSkill(BaseDelegationSkill):
            def get_subagent_class(self) -> Type[BaseReviewerAgent]:
                return MySubagent

            def build_subagent_request(self, todo: dict, context: ReviewContext) -> dict:
                return {
                    "todo_id": todo["id"],
                    "title": todo["title"],
                    "scope": {"paths": context.changed_files},
                }

            async def review(self, context: ReviewContext) -> ReviewOutput:
                requests = [self.build_subagent_request(t, context) for t in self._todos]
                results = await self.execute_subagents_concurrently(requests, context)
                return self._build_output_from_results(results, context)
    """

    def __init__(
        self,
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        **kwargs,
    ) -> None:
        """Initialize BaseDelegationSkill.

        Args:
            verifier: Optional findings verifier
            max_retries: Maximum retry attempts for subagent execution
            agent_runtime: Optional agent runtime for execution
            **kwargs: Additional arguments passed to BaseReviewerAgent
        """
        super().__init__(verifier=verifier, max_retries=max_retries, agent_runtime=agent_runtime)
        self._max_retries = max_retries

    @abstractmethod
    def get_subagent_class(self) -> Type[BaseReviewerAgent]:
        """Return the subagent class to instantiate for each request.

        Returns:
            The subagent class (must inherit from BaseReviewerAgent)

        Example:
            def get_subagent_class(self) -> Type[BaseReviewerAgent]:
                return SecuritySubagent
        """
        pass

    @abstractmethod
    def build_subagent_request(
        self, todo: Dict[str, Any], context: ReviewContext
    ) -> Dict[str, Any]:
        """Build a request dict for a subagent.

        Args:
            todo: Todo item to delegate (contains id, title, scope, etc.)
            context: ReviewContext with changed files and metadata

        Returns:
            Request dict that will be passed to subagent constructor

        Example:
            def build_subagent_request(self, todo, context) -> dict:
                return {
                    "todo_id": todo["id"],
                    "title": todo["title"],
                    "scope": {"paths": context.changed_files},
                    "risk_category": todo.get("category", "general"),
                    "acceptance_criteria": todo.get("criteria", []),
                }
        """
        pass

    async def execute_subagents_concurrently(
        self,
        requests: List[Dict[str, Any]],
        context: ReviewContext,
        max_concurrency: int = 2,
    ) -> List[Dict[str, Any]]:
        """Execute subagents concurrently with error handling.

        Creates a subagent instance for each request and runs them in parallel
        using asyncio.gather(). Handles exceptions gracefully, converting them
        to error result dicts.

        Args:
            requests: List of request dicts (from build_subagent_request())
            context: ReviewContext to pass to each subagent
            max_concurrency: Maximum concurrent subagents (default: 4)

        Returns:
            List of result dicts, each containing:
            - todo_id: The todo ID from the request
            - title: The todo title from the request
            - subagent_type: Class name of the subagent
            - status: "done" or "blocked"
            - result: ReviewOutput.model_dump() if successful, None if failed
            - error: Error message if status is "blocked"
        """
        if not requests:
            logger.info(f"[{self.__class__.__name__}] No requests to execute")
            return []

        logger.info(
            f"[{self.__class__.__name__}] Executing {len(requests)} subagent tasks concurrently "
            f"(max {max_concurrency} at a time)"
        )

        subagent_class = self.get_subagent_class()
        subagent_type_name = subagent_class.__name__

        async def execute_single_subagent(request: Dict[str, Any]) -> Dict[str, Any]:
            todo_id = request.get("todo_id", "unknown")
            title = request.get("title", "unknown")

            try:
                subagent = subagent_class(task=request, max_retries=self._max_retries)  # type: ignore[call-arg]

                result = await subagent.review(context)

                logger.info(
                    f"[{self.__class__.__name__}] Subagent task {todo_id} completed: "
                    f"{len(result.findings) if result else 0} findings"
                )

                return {
                    "todo_id": todo_id,
                    "title": title,
                    "subagent_type": subagent_type_name,
                    "status": "done" if result else "blocked",
                    "result": result.model_dump() if result else None,
                }

            except Exception as e:
                logger.error(
                    f"[{self.__class__.__name__}] Subagent task {todo_id} failed: {e}",
                    exc_info=True,
                )
                return {
                    "todo_id": todo_id,
                    "title": title,
                    "subagent_type": subagent_type_name,
                    "status": "blocked",
                    "error": str(e),
                }

        # Use semaphore for concurrency limiting
        semaphore = asyncio.Semaphore(max_concurrency)

        async def execute_with_semaphore(request: Dict[str, Any]) -> Dict[str, Any]:
            """Execute with concurrency limit."""
            async with semaphore:
                return await execute_single_subagent(request)

        # Execute all subagents concurrently
        tasks = [execute_with_semaphore(req) for req in requests]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        results: List[Dict[str, Any]] = []
        for i, item in enumerate(gather_results):
            if isinstance(item, Exception):
                request = requests[i]
                logger.error(
                    f"[{self.__class__.__name__}] Subagent task {request.get('todo_id')} "
                    f"raised exception: {item}",
                    exc_info=True,
                )
                results.append(
                    {
                        "todo_id": request.get("todo_id"),
                        "title": request.get("title"),
                        "subagent_type": subagent_type_name,
                        "status": "blocked",
                        "error": str(item),
                    }
                )
            else:
                results.append(item)  # type: ignore[arg-type]

        # Log summary
        done_count = sum(1 for r in results if r.get("status") == "done")
        blocked_count = sum(1 for r in results if r.get("status") == "blocked")
        logger.info(
            f"[{self.__class__.__name__}] Completed {len(results)} subagent tasks: "
            f"{done_count} done, {blocked_count} blocked"
        )

        return results

    def _aggregate_results(
        self,
        results: List[Dict[str, Any]],
        context: ReviewContext,
    ) -> Dict[str, Any]:
        """Aggregate subagent results into a unified summary.

        Args:
            results: List of subagent result dicts
            context: ReviewContext for reference

        Returns:
            Aggregated dict containing:
            - total_tasks: Total number of subagent tasks
            - completed_tasks: Number of successful tasks
            - blocked_tasks: Number of failed tasks
            - total_findings: Sum of all findings across successful subagents
            - findings_by_severity: Dict mapping severity to count
            - errors: List of error messages from blocked tasks
        """
        total_tasks = len(results)
        completed_tasks = sum(1 for r in results if r.get("status") == "done")
        blocked_tasks = sum(1 for r in results if r.get("status") == "blocked")

        # Collect findings from successful results
        all_findings: List[Dict[str, Any]] = []
        for result in results:
            if result.get("status") != "done":
                continue
            result_data = result.get("result", {})
            if not result_data:
                continue
            subagent_findings = result_data.get("findings", [])
            all_findings.extend(subagent_findings)

        # Count by severity
        findings_by_severity: Dict[str, int] = {}
        for finding in all_findings:
            severity = finding.get("severity", "unknown")
            findings_by_severity[severity] = findings_by_severity.get(severity, 0) + 1

        # Collect errors
        errors = [
            {"todo_id": r.get("todo_id"), "error": r.get("error")}
            for r in results
            if r.get("status") == "blocked" and r.get("error")
        ]

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "blocked_tasks": blocked_tasks,
            "total_findings": len(all_findings),
            "findings_by_severity": findings_by_severity,
            "errors": errors,
        }

    def get_agent_name(self) -> str:
        """Return agent name - subclasses should override."""
        return "base_delegation"

    def get_allowed_tools(self) -> List[str]:
        """Return allowed tools for delegation skills.

        Delegation skills typically don't use tools directly - they
        delegate to subagents that have their own tool sets.
        """
        return ["read", "grep", "file"]

    def get_relevant_file_patterns(self) -> List[str]:
        """Return empty list - delegation skills orchestrate, not review files."""
        return []

    def get_system_prompt(self) -> str:
        """Return system prompt - subclasses should override."""
        return "You are a delegation skill that dispatches work to subagents."

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform review - subclasses must implement their own logic."""
        from iron_rook.review.contracts import MergeGate, ReviewOutput, Scope

        return ReviewOutput(
            agent=self.get_agent_name(),
            summary="BaseDelegationSkill.review() must be overridden by subclass",
            severity="merge",
            scope=Scope(
                relevant_files=[],
                reasoning="Base class does not implement review logic",
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="approve",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=["Override review() in subclass"],
            ),
        )
