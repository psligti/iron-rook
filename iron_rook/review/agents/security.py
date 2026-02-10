"""Security Review Subagent - LLM-driven orchestrator.

The SecurityReviewer is a high-level orchestrator that:
1. Evaluates PR changes for security vulnerabilities
2. Dynamically creates todos for different security checks
3. Uses tools (grep, ast-grep, file reading) to investigate
4. Optionally delegates to specialized analysis
5. Aggregates findings and makes a merge decision

Note: This is the OLD simple agent. Use the FSM-based agent
via CLI: iron-rook --agent security-fsm
"""

import warnings
from typing import List

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import ReviewOutput, Scope, MergeGate
from iron_rook.review.verifier import FindingsVerifier


class SecurityReviewer(BaseReviewerAgent):
    """Deprecated: Security Reviewer using simple LLM agent.

    This agent is deprecated in favor of the FSM-based security reviewer.
    Use 'security-fsm' agent via CLI: iron-rook --agent security-fsm
    """

    def __init__(self, verifier: FindingsVerifier | None = None) -> None:
        """Initialize deprecated SecurityReviewer."""
        warnings.warn(
            "SecurityReviewer is deprecated. Use the FSM-based security reviewer instead: "
            "iron-rook --agent security-fsm",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(verifier)

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform security review (deprecated).

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with security findings, severity, and merge gate decision
        """
        # Simple stub implementation for backward compatibility
        return ReviewOutput(
            agent="security",
            summary="Security reviewer is deprecated. Use security-fsm agent instead.",
            severity="merge",
            scope=Scope(
                relevant_files=context.changed_files,
                ignored_files=[],
                reasoning="Security reviewer is deprecated; use security-fsm agent",
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="approve",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=[
                    "The SecurityReviewer is deprecated. Please use the FSM-based security "
                    "reviewer instead via: iron-rook --agent security-fsm"
                ],
            ),
        )

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "security"

    def get_system_prompt(self) -> str:
        """Get system prompt (deprecated)."""
        return "Security review is deprecated. Use security-fsm agent."

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns this reviewer is relevant to."""
        return [
            "*.py",
            "*.js",
            "*.ts",
            "*.tsx",
            "*.go",
            "*.java",
            "*.rb",
            "*.php",
            "*.cs",
            "*.cpp",
            "*.c",
            "*.h",
            "*.sh",
            "*.yaml",
            "*.yml",
            "*.json",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tool/command prefixes for this reviewer."""
        return [
            "grep",
            "rg",
            "ast-grep",
            "read",
            "file",
            "git",
        ]
