"""Documentation Review Subagent.

Reviews code changes for documentation coverage including:
- Docstrings for public functions/classes
- README updates for new features
- Configuration documentation
- Usage examples
"""

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


class DocumentationReviewer(BaseReviewerAgent):
    """Documentation reviewer agent that checks for documentation coverage.

    This agent specializes in detecting:
    - Missing docstrings for public functions/classes
    - Outdated or missing README documentation
    - Missing configuration documentation
    - Missing usage examples
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
        """Return the agent identifier."""
        return "documentation"

    def get_system_prompt(self) -> str:
        """Get the system prompt for the documentation reviewer."""
        return f"""You are the Documentation Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to documentation.
- Propose minimal checks; request doc build checks only if relevant.
- If changed_files or diff are missing, request them.
- Discover repo conventions (README, docs toolchain) to propose correct commands.

You specialize in:
- docstrings for public functions/classes
- module-level docs explaining purpose and contracts
- README / usage updates when behavior changes
- configuration documentation (env vars, settings, CLI flags)
- examples and edge case documentation

Relevant changes:
- new public APIs, new commands/tools/skills/agents
- changes to behavior, defaults, outputs, error handling
- renamed modules, moved files, breaking interface changes

Checks you may request:
- docs build/check (mkdocs/sphinx) if repo has it
- docstring linting if configured
- ensure examples match CLI/help output if changed

Documentation review must answer:
1) Would a new engineer understand how to use the changed parts?
2) Are contracts described (inputs/outputs/errors)?
3) Are sharp edges warned?
4) Is terminology consistent?

Severity guidance:
- warning: missing docstring or minor README mismatch
- critical: behavior changed but docs claim old behavior; config/env changes undocumented
- blocking: public interface changed with no documentation and high risk of misuse

{get_review_output_schema()}

Your agent name is "documentation"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns relevant to documentation review."""
        return [
            "**/*.py",
            "README*",
            "docs/**",
            "*.md",
            "pyproject.toml",
            "setup.cfg",
            ".env.example",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for documentation review checks."""
        return ["git", "grep", "python", "markdownlint", "mkdocs"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform documentation review on given context using SimpleReviewAgentRunner.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with documentation findings, severity, and merge gate decision

        Raises:
            ValueError: If API key is missing or invalid
            TimeoutError: If LLM request times out
            Exception: For other API-related errors
        """
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=False,
        )
