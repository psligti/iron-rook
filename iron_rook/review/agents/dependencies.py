"""Dependency & License Review Subagent implementation."""

from __future__ import annotations

from typing import List
from iron_rook.review.contracts import AgentState

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
)


DEPENDENCY_SYSTEM_PROMPT = f"""You are the Dependency & License Review Subagent.

Use this shared behavior:
- If dependency changes are present but file contents are missing, request dependency files and lockfiles.
- Evaluate reproducibility and audit readiness.

Focus:
- new deps added, version bumps, loosened pins
- supply chain risk signals (typosquatting, untrusted packages)
- license compatibility (if enforced)
- build reproducibility (lockfile consistency)

Relevant files:
- pyproject.toml, requirements*.txt, poetry.lock, uv.lock
- CI dependency steps

Checks you may request:
- pip-audit / poetry audit / uv audit
- license checker if repo uses it
- lockfile diff sanity checks

Severity:
- critical/blocking for risky dependency introduced without justification
- critical if pins loosened causing non-repro builds
- warning for safe bumps but missing notes

{get_review_output_schema()}

Your agent name is "dependencies"."""


class DependencyLicenseReviewer(BaseReviewerAgent):
    """Reviewer agent for dependency and license compliance."""

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
        return "dependencies"

    def get_system_prompt(self) -> str:
        """Return the system prompt for the dependency reviewer."""
        return DEPENDENCY_SYSTEM_PROMPT

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns relevant to dependency review."""
        return [
            "pyproject.toml",
            "requirements*.txt",
            "requirements.txt",
            "setup.py",
            "Pipfile",
            "poetry.lock",
            "uv.lock",
            "setup.cfg",
            "tox.ini",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for dependency review checks."""
        return ["git", "grep", "python", "pip", "pip-audit", "uv", "poetry"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform dependencies review on given context using SimpleReviewAgentRunner.

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
            no_relevance_summary="No dependency files changed. Dependency review not applicable.",
        )
