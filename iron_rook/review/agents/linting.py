"""Linting and Style Review Subagent."""

from __future__ import annotations
from typing import List
import logging

from iron_rook.review.contracts import AgentState

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
)

logger = logging.getLogger(__name__)


class LintingReviewer(BaseReviewerAgent):
    """Reviewer agent for linting, formatting, and code quality checks.

    This agent uses LLM-based analysis to detect:
    - Formatting issues (indentation, line length)
    - Lint adherence (PEP8 violations, style issues)
    - Type hints coverage (missing type annotations)
    - Code quality smells (unused imports, dead code)
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
        return "linting"

    def get_system_prompt(self) -> str:
        """Return the system prompt for this reviewer."""
        return f"""You are the Linting & Style Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to lint/style.
- Propose minimal changed-files-only lint commands first.
- If changed_files or diff are missing, request them.
- Discover repo conventions (ruff/black/flake8/isort, format settings in pyproject).

You specialize in:
- formatting and lint adherence
- import hygiene, unused vars, dead code
- type hints sanity (quality, not architecture)
- consistency with repo conventions
- correctness smells (shadowing, mutable defaults)

Relevant changes:
- any Python source changes (*.py)
- lint config changes (pyproject.toml, ruff.toml, etc.)

Checks you may request:
- ruff check <changed_files>
- ruff format <changed_files>
- formatter/linter commands used by the repo
- type check if enforced (only when relevant)

Severity:
- warning: minor style issues
- critical: new lint violations likely failing CI
- blocking: syntax errors, obvious correctness issues, format prevents CI merge

{get_review_output_schema()}

Your agent name is "linting"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this reviewer is relevant to."""
        return [
            "**/*.py",
            "*.json",
            "*.toml",
            "*.yaml",
            "*.yml",
            "pyproject.toml",
            "ruff.toml",
            ".flake8",
            "setup.cfg",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for linting review checks."""
        return ["git", "grep", "python", "ruff", "black", "isort", "mypy"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform linting review on given context using SimpleReviewAgentRunner.

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
            early_return_on_no_relevance=True,
            no_relevance_summary="No Python or lint config files changed. Linting review not applicable.",
        )
