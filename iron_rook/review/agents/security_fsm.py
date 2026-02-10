"""Security FSM reviewer agent.

This agent wraps the SecurityReviewOrchestrator to provide
a unified agent interface for the FSM-based security review path.
"""

from __future__ import annotations

from iron_rook.review.base import BaseReviewerAgent
from iron_rook.review.contracts import (
    PullRequestChangeList,
    SecurityReviewReport,
    ReviewInputs,
)
from iron_rook.review.fsm_security_orchestrator import SecurityReviewOrchestrator
from iron_rook.review.utils.session_helper import (
    EphemeralSessionManager,
)


class SecurityFSMReviewer(BaseReviewerAgent):
    """FSM-based security review agent.

    This agent wraps the SecurityReviewOrchestrator to provide a
    unified agent interface for the FSM-based security review path.

    The orchestrator implements:
    - Deterministic transition validation against FSM_TRANSITIONS
    - Required-field validation before phase execution
    - AgentRuntime-first execution path with tested direct-LLM fallback
    - Bounded retry policy (max 3) for transient failures
    - Fail-fast for structural errors
    - Session lifecycle guarantees
    """

    def __init__(
        self,
        session_manager: EphemeralSessionManager | None = None,
        prompt_path: str | None = None,
    ) -> None:
        """Initialize the Security FSM reviewer agent.

        Args:
            session_manager: Optional session manager for agent runtime execution
            prompt_path: Optional path to security_review_agent.md prompts
        """
        self.session_manager = session_manager
        self.prompt_path = prompt_path

    def get_agent_name(self) -> str:
        """Return the agent name."""
        return "security-fsm"

    def get_relevant_file_patterns(self) -> list[str]:
        """Return file patterns relevant to this agent."""
        return ["**/*.py", "**/*.md", "requirements/*.txt", "*.toml"]

    async def review(
        self,
        context: ReviewInputs,
    ) -> SecurityReviewReport:
        """Run the security review using the FSM orchestrator.

        Args:
            context: Review context containing PR inputs and constraints

        Returns:
            SecurityReviewReport with consolidated findings
        """
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=self.session_manager,
            prompt_path=self.prompt_path,
        )

        return await orchestrator.run_review(context.pr_input)

    def prefers_direct_review(self) -> bool:
        """Return False to use AgentRuntime path.

        The FSM orchestrator has its own AgentRuntime-first logic
        and direct-LLM fallback, so it doesn't need the orchestrator's
        direct review path.
        """
        return False
