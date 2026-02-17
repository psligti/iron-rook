"""Requirements reviewer subagent for comparing implementation to ticket/PR description."""

from __future__ import annotations
from typing import List
import logging

from iron_rook.review.contracts import AgentState

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import ReviewOutput


logger = logging.getLogger(__name__)


REQUIREMENTS_SYSTEM_PROMPT = """You are the Requirements Review Subagent.

Use this shared behavior:
- If diff is missing, request it.
- If no ticket/pr description is provided, request it OR proceed by extracting implied requirements from code changes and mark confidence lower.
- Compare stated requirements and acceptance criteria to what was implemented.

Goal:
Confirm the change matches stated requirements and acceptance criteria.

Inputs may include:
- ticket_description or pr_description
- acceptance_criteria
- changed_files
- diff

What to do:
1) Extract explicit/implied requirements from description/criteria.
2) Check the diff implements them.
3) Identify gaps, scope creep, ambiguous behavior.
4) Ensure error cases and edge cases are covered or flagged.

Severity:
- warning: minor mismatch or missing note
- critical: core requirement not met or contradicts requirement
- blocking: change does the wrong thing / breaks a requirement / unsafe default

Return JSON with agent="requirements" using the standard schema.
Return JSON only."""


class RequirementsReviewer(BaseReviewerAgent):
    """Reviewer agent that compares implementation to ticket/PR description."""

    FSM_TRANSITIONS: dict[AgentState, set[AgentState]] = {
        AgentState.IDLE: {AgentState.INITIALIZING},
        AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
        AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
        AgentState.RUNNING: {AgentState.COMPLETED, AgentState.FAILED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: set(),
    }

    def get_agent_name(self) -> str:
        """Return the name of this reviewer agent."""
        return "requirements"

    def get_system_prompt(self) -> str:
        """Get the system prompt for this reviewer agent."""
        return REQUIREMENTS_SYSTEM_PROMPT

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns this reviewer is relevant to."""
        return ["**/*"]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for requirements review checks."""
        return ["git", "grep", "python"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform requirements review on given context using SimpleReviewAgentRunner.

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
