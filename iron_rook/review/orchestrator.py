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
    PriorityMergePolicy,
    ReviewInputs,
    ReviewOutput,
    Scope,
    ToolPlan,
    BudgetConfig,
    BudgetTracker,
)
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
        merge_policy: MergePolicy | None = None,
    ) -> None:
        self.subagents = subagents
        self.command_executor = command_executor or CommandExecutor()
        self.stream_manager = stream_manager or ReviewStreamManager()
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
        await self.stream_manager.start_stream()

        initial_results = await self.run_subagents_parallel(inputs, stream_callback)

        all_findings = [finding for result in initial_results for finding in result.findings]
        deduped_findings = self.dedupe_findings(all_findings)
