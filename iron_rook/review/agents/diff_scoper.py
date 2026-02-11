"""Diff Scoper Subagent - pre-pass reviewer for diff risk classification and routing."""

from __future__ import annotations
from typing import List
import logging

from iron_rook.fsm.state import AgentState

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
)


logger = logging.getLogger(__name__)


class DiffScoperReviewer(BaseReviewerAgent):
    """Pre-pass reviewer that classifies diff risk and routes attention to appropriate subagents.

    This agent runs early in review pipeline to:
    1. Analyze git diff to identify scope and magnitude of changes
    2. Classify risk level (high/medium/low) based on multiple factors
    3. Route attention findings to appropriate specialized reviewers
    4. Suggest minimal checks to run first for quick feedback
    """

    FSM_TRANSITIONS: dict[AgentState, set[AgentState]] = {
        AgentState.IDLE: {AgentState.INITIALIZING},
        AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
        AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
        AgentState.RUNNING: {AgentState.COMPLETED, AgentState.FAILED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: set(),
    }

    def get_agent_name(self) -> str:
        """Return the agent name."""
        return "diff_scoper"

    def get_system_prompt(self) -> str:
        """Return the system prompt for this reviewer agent."""
        return f"""You are the Diff Scoper Subagent.

Use this shared behavior:
- If changed_files or diff are missing, request them.
- Summarize change intent and classify risk.
- Route attention to which other subagents matter most.
- Propose minimal checks to run first.

Goal:
- Summarize what changed in 5-10 bullets.
- Classify risk: low/medium/high.
- Produce a routing table: which subagents are most relevant and why.
- Propose minimal set of checks to run first.

{get_review_output_schema()}

Your agent name is "diff_scoper".

IMPORTANT: In merge_gate.notes_for_coding_agent, include:
- "routing": {{"architecture": "...", "security": "...", ...}}
- "risk rationale"

These are notes for the orchestrator, not blocking issues."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this reviewer is relevant to.

        Diff scoper is relevant to all files since it analyzes overall change scope.
        """
        return ["**/*"]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for diff scoping checks."""
        return ["git", "grep", "ast-grep", "python"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform diff_scoper review on given context using SimpleReviewAgentRunner.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with findings, severity, and merge gate decision

        Raises:
            ValueError: If API key is missing or invalid
            TimeoutError: If LLM request times out
            Exception: For other API-related errors
        """
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=False,
        )
