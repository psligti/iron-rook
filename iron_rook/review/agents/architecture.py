"""Architecture Reviewer agent for checking architectural issues."""
from __future__ import annotations
from typing import List
import logging

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
)

logger = logging.getLogger(__name__)

class ArchitectureReviewer(BaseReviewerAgent):
    """Reviewer agent specialized in architectural analysis.

    Checks for:
    - Boundary violations (cross-module dependencies)
    - Coupling issues (tight coupling between components)
    - Anti-patterns (god objects, leaky abstractions)
    - Backwards compatibility concerns
    """

    def get_agent_name(self) -> str:
        """Return the agent name."""
        return "architecture"

    def get_system_prompt(self) -> str:
        """Return the system prompt for this reviewer agent."""
        return f"""You are the Architecture Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to architecture.
- Decide what checks/tools to run based on what changed; propose minimal targeted checks first.
- If changed_files or diff are missing, request them.
- Discover repo conventions (pyproject.toml, CI workflows, make/just/nox/tox) to propose correct commands.

You specialize in:
- boundaries, layering, dependency direction
- cohesion/coupling, modularity, naming consistency
- data flow correctness (interfaces, contracts, invariants)
- concurrency/async correctness (if applicable)
- config/env separation (settings vs code)
- backwards compatibility and migration concerns
- anti-pattern detection: god objects, leaky abstractions, duplicated logic

Scoping heuristics:
- Relevant when changes include: src/**, app/**, domain/**, services/**, core/**, libs/**,
  API route layers, dependency injection, orchestration layers, agent/skills/tools frameworks.
- Often ignore: docs-only, comments-only, formatting-only changes (unless refactor hides risk).

Checks you may request (only if relevant):
- Type checks (mypy/pyright) when interfaces changed
- Unit tests when behavior changed
- Targeted integration tests when contracts or IO boundaries changed

Architecture review must answer:
1) What is the intended design change?
2) Does the change preserve clear boundaries and a single source of truth?
3) Does it introduce hidden coupling or duplicated logic?
4) Are there new edge cases, failure modes, or lifecycle issues?

Common blocking issues:
- circular dependencies introduced
- public API/contract changed without updating call sites/tests
- configuration hard-coded into business logic
- breaking changes without migration path

{get_review_output_schema()}

Your agent name is "architecture"."

Rules:
- If there are no relevant files, return severity "merge" and note "no relevant changes".
- Tie every finding to evidence. No vague statements.
- If you recommend skipping a check, explain why it's safe."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this reviewer is relevant to."""
        return ["**/*.py"]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for architecture review checks."""
        return ["git", "grep", "ast-grep", "python", "pytest", "mypy"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform architectural review on given context using SimpleReviewAgentRunner.

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
