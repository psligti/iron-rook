"""TelemetryMetricsReviewer - checks for logging quality and observability coverage."""

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


class TelemetryMetricsReviewer(BaseReviewerAgent):
    """Telemetry reviewer agent that checks for logging quality and observability coverage.

    This agent specializes in detecting:
    - Logging quality (proper log levels, structured logging)
    - Error reporting (exceptions raised with context)
    - Observability coverage (metrics, traces, distributed tracing)
    - Silent failures (swallowed exceptions)
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
        return "telemetry"

    def get_system_prompt(self) -> str:
        """Get the system prompt for the telemetry reviewer."""
        return f"""You are the Telemetry & Metrics Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to observability.
- Propose minimal targeted checks; escalate when failure modes are introduced.
- If changed_files or diff are missing, request them.
- Discover repo conventions (logging frameworks, metrics libs, tracing setup).

You specialize in:
- logging quality (structured logs, levels, correlation IDs)
- tracing spans / propagation (if applicable)
- metrics: counters/gauges/histograms, cardinality control
- error reporting: meaningful errors, no sensitive data
- observability coverage of new workflows and failure modes
- performance signals: timing, retries, rate limits, backoff

Relevant changes:
- new workflows, background jobs, pipelines, orchestration
- network calls, IO boundaries, retry logic, timeouts
- error handling changes, exception mapping

Checks you may request:
- log format checks (if repo has them)
- smoke run command to ensure logs/metrics emitted (if available)
- grep for logger usage & secrets leakage

Blocking:
- secrets/PII likely logged
- critical path introduced with no error logging/metrics
- retry loops without visibility or limits (runaway risk)
- high-cardinality metric labels introduced

{get_review_output_schema()}

Your agent name is "telemetry"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns relevant to telemetry review."""
        return [
            "**/*.py",
            "**/logging/**",
            "**/observability/**",
            "**/metrics/**",
            "**/tracing/**",
            "**/monitoring/**",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for telemetry review checks."""
        return ["git", "grep", "ast-grep", "python", "pytest"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform telemetry review on given context using SimpleReviewAgentRunner.

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
