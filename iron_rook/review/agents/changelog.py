"""Release & Changelog Review Subagent.

Reviews code changes for release hygiene including:
- CHANGELOG updates for new features
- Version bumps (major, minor, patch)
- Breaking changes documentation
- Migration guides
"""

from __future__ import annotations
from typing import List
import logging

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
)


logger = logging.getLogger(__name__)


class ReleaseChangelogReviewer(BaseReviewerAgent):
    """Reviewer agent for release hygiene and changelog compliance."""

    def __init__(self) -> None:
        self.agent_name = "release_changelog"

    def get_agent_name(self) -> str:
        return self.agent_name

    def get_system_prompt(self) -> str:
        return f"""You are the Release & Changelog Review Subagent.

Use this shared behavior:
- If user-visible behavior changes, ensure release hygiene artifacts are updated.
- If no changelog/versioning policy exists, note it and adjust severity.

Goal:
Ensure user-visible changes are communicated and release hygiene is maintained.

Relevant:
- CLI flags changed
- outputs changed (schemas, logs users rely on)
- breaking changes
- version bump / changelog / migration docs

Checks you may request:
- CHANGELOG presence/update
- version bump policy checks
- help text / docs updated

Severity:
- warning for missing changelog entry
- critical for breaking change without migration note

{get_review_output_schema()}

Your agent name is "release_changelog"."""

    def get_relevant_file_patterns(self) -> List[str]:
        return [
            "CHANGELOG*",
            "CHANGES*",
            "HISTORY*",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "**/__init__.py",
            "**/*.py",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for changelog review checks."""
        return ["git", "grep", "python"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform changelog review on given context using SimpleReviewAgentRunner.

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
