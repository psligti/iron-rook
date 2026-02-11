"""Unit Tests Reviewer agent for checking test quality and adequacy."""

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


class UnitTestsReviewer(BaseReviewerAgent):
    """Reviewer agent specialized in unit test quality and adequacy.

    Checks for:
    - Test adequacy (cover changed behavior)
    - Test correctness (assertions, mocking)
    - Edge case coverage (boundary values, error conditions)
    - Determinism (randomness, time dependencies, state leakage)
    """

    FSM_TRANSITIONS: dict[AgentState, set[AgentState]] = {
        AgentState.IDLE: {AgentState.INITIALIZING},
        AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
        AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
        AgentState.RUNNING: {AgentState.COMPLETED, AgentState.FAILED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: set(),
    }

    def get_system_prompt(self) -> str:
        """Return the system prompt for this reviewer agent."""
        return f"""You are the Unit Test Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to unit tests.
- Propose minimal targeted test selection first; escalate if risk is high.
- If changed_files or diff are missing, request them.
- Discover repo conventions (pytest, nox/tox, uv run, test layout).

You specialize in:
- adequacy of tests for changed behavior
- correctness of tests (assertions, determinism, fixtures)
- edge case and failure mode coverage
- avoiding brittle tests (time, randomness, network)
- selecting minimal test runs to validate change

Relevant changes:
- behavior changes in code
- new modules/functions/classes
- bug fixes (prefer regression tests)
- changes to test/fixture utilities, CI test steps

Checks you may request:
- pytest -q <test_file>
- pytest -q -k "<keyword>"
- pytest -q tests/unit/...
- coverage on changed modules only (if available)

Severity:
- warning: tests exist but miss an edge case
- critical: behavior changed with no tests and moderate risk
- blocking: high-risk change with no tests; broken/flaky tests introduced

{get_review_output_schema()}

Your agent name is "unit_tests"."""

    def get_agent_name(self) -> str:
        """Return the agent name."""
        return "unit_tests"

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this reviewer is relevant to."""
        return ["**/*.py"]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for unit test review checks."""
        return ["git", "grep", "python", "pytest", "coverage"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform unit test review on given context using SimpleReviewAgentRunner.

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
