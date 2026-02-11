"""Performance & Reliability Review Subagent."""

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


class PerformanceReliabilityReviewer(BaseReviewerAgent):
    """Reviewer agent for performance and reliability checks.

    Checks for:
    - Code complexity (nested loops, deep nesting, cyclomatic complexity)
    - IO amplification (N+1 database queries, excessive API calls in loops)
    - Retry logic (exponential backoff, proper retry policies)
    - Concurrency issues (race conditions, missing locks, shared state)
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
        return "performance"

    def get_system_prompt(self) -> str:
        """Return the system prompt for this reviewer."""
        return f"""You are the Performance & Reliability Review Subagent.

Use this shared behavior:
- If changed_files or diff are missing, request them.
- Focus on hot paths, IO amplification, retries, timeouts, concurrency hazards.
- Propose minimal checks first; escalate if core systems changed.

Specialize in:
- complexity regressions (O(n^2), unbounded loops)
- IO amplification (extra queries/reads)
- retry/backoff/timeouts correctness
- concurrency hazards (async misuse, shared mutable state)
- memory/cpu hot paths, caching correctness
- failure modes and graceful degradation

Relevant changes:
- loops, batching, pagination, retries
- network clients, DB access, file IO
- orchestration changes, parallelism, caching

Checks you may request:
- targeted benchmarks (if repo has them)
- profiling hooks or smoke run command
- unit tests for retry/timeout behavior

Blocking:
- infinite/unbounded retry risk
- missing timeouts on network calls in critical paths
- concurrency bugs with shared mutable state

{get_review_output_schema()}

Your agent name is "performance"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this reviewer is relevant to."""
        return [
            "**/*.py",
            "**/*.rs",
            "**/*.go",
            "**/*.js",
            "**/*.ts",
            "**/*.tsx",
            "**/config/**",
            "**/database/**",
            "**/db/**",
            "**/network/**",
            "**/api/**",
            "**/services/**",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for performance review checks."""
        return ["git", "grep", "python", "pytest", "pytest-benchmark"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform performance review on given context using SimpleReviewAgentRunner.

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
