"""Security FSM reviewer agent.

This agent wraps the SecurityReviewOrchestrator to provide
a unified agent interface for the FSM-based security review path.
"""

from __future__ import annotations

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    PullRequestChangeList,
    PullRequestMetadata,
    PRChange,
    PRMetadata,
    PRConstraints,
    ReviewOutput,
    Scope,
    SecurityReviewReport,
    MergeGate,
)
from iron_rook.review.fsm_security_orchestrator import SecurityReviewOrchestrator
from iron_rook.review.utils.session_helper import (
    SessionManagerLike,
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
        session_manager: SessionManagerLike | None = None,
        prompt_path: str | None = None,
    ) -> None:
        """Initialize Security FSM reviewer agent.

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

    def get_allowed_tools(self) -> list[str]:
        """Return allowed tools for this reviewer.

        The FSM orchestrator manages its own tool usage internally,
        so this agent doesn't need to declare tools at this level.
        """
        return []

    def get_system_prompt(self) -> str:
        """Return system prompt for this reviewer.

        The FSM orchestrator manages its own prompts internally,
        so this agent doesn't need a system prompt at this level.
        """
        return ""

    async def review(
        self,
        context: ReviewContext,
    ) -> ReviewOutput:
        """Run the security review using the FSM orchestrator.

        Args:
            context: Review context containing changed files, diff, and metadata

        Returns:
            ReviewOutput with security findings and merge gate decision
        """
        pr_input = self._build_pr_input(context)

        session_mgr = (
            self.session_manager if self.session_manager is not None else EphemeralSessionManager()
        )
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=session_mgr,
            prompt_path=self.prompt_path,
        )

        # Run the FSM security review
        security_report = await orchestrator.run_review(pr_input)

        # Convert SecurityReviewReport to ReviewOutput
        return self._convert_to_review_output(security_report, context)

    def _build_pr_input(self, context: ReviewContext) -> PullRequestChangeList:
        """Build PullRequestChangeList from ReviewContext.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            PullRequestChangeList for the FSM orchestrator
        """
        # Create PR changes from diff
        changes = [
            PRChange(
                path=file_path,
                change_type="modified",  # Default to modified for simplicity
                diff_summary=f"Changed in {file_path}",
            )
            for file_path in context.changed_files
        ]

        # Create PR metadata
        pr = PullRequestMetadata(
            id="unknown",
            title=context.pr_title or "Security Review",
            base_branch=context.base_ref or "main",
            head_branch=context.head_ref or "feature",
            author="unknown",
        )

        # Create PR metadata
        metadata = PRMetadata(
            repo=context.repo_root,
            commit_range=f"{context.base_ref or ''}...{context.head_ref or ''}",
            created_at="unknown",
        )

        return PullRequestChangeList(
            pr=pr,
            changes=changes,
            metadata=metadata,
            constraints=PRConstraints(),
        )

    def _convert_to_review_output(
        self,
        security_report: SecurityReviewReport,
        context: ReviewContext,
    ) -> ReviewOutput:
        """Convert SecurityReviewReport to ReviewOutput.

        Args:
            security_report: SecurityReviewReport from FSM orchestrator
            context: Original ReviewContext

        Returns:
            ReviewOutput for the orchestrator
        """
        from iron_rook.review.contracts import Finding

        # Flatten all findings from all severity levels
        all_findings = []
        for severity, findings in security_report.findings.items():
            for finding in findings:
                # Map severity levels appropriately
                finding_severity = "critical"
                if severity == "critical":
                    finding_severity = "critical"
                elif severity == "high":
                    finding_severity = "critical"
                elif severity == "medium":
                    finding_severity = "critical"
                elif severity == "low":
                    finding_severity = "warning"
                else:
                    finding_severity = "warning"

                all_findings.append(
                    Finding(
                        id=f"sec-{len(all_findings)}",
                        title=finding.title,
                        severity=finding_severity,
                        confidence="medium",
                        owner="security",
                        estimate="M",
                        evidence=", ".join(str(e) for e in finding.evidence),
                        risk=severity,
                        recommendation=finding.recommendations[0]
                        if finding.recommendations
                        else "Review and fix",
                    )
                )

        # Determine merge decision based on findings
        decision = "approve"
        must_fix = []
        should_fix = []

        overall_severity = "merge"
        if any(f.severity == "blocking" for f in all_findings):
            overall_severity = "blocking"
        elif any(f.severity == "critical" for f in all_findings):
            overall_severity = "critical"
        elif any(f.severity == "warning" for f in all_findings):
            overall_severity = "warning"

        for finding in all_findings:
            if finding.severity == "blocking":
                decision = "block"
                must_fix.append(f"{finding.title}: {finding.recommendation}")
            elif finding.severity == "critical":
                if decision == "approve":
                    decision = "needs_changes"
                must_fix.append(f"{finding.title}: {finding.recommendation}")
            elif finding.severity == "warning":
                if decision == "approve":
                    decision = "approve_with_warnings"
                should_fix.append(f"{finding.title}: {finding.recommendation}")

        return ReviewOutput(
            agent="security-fsm",
            summary=security_report.risk_assessment.rationale,
            severity=overall_severity,
            scope=Scope(
                relevant_files=context.changed_files,
                ignored_files=[],
                reasoning=f"FSM-based security review with {len(all_findings)} findings",
            ),
            findings=all_findings,
            merge_gate=MergeGate(
                decision=decision,
                must_fix=must_fix,
                should_fix=should_fix,
                notes_for_coding_agent=[
                    f"FSM execution completed with confidence: {security_report.confidence:.2f}",
                    f"Security review completed {security_report.fsm.phase} phase",
                ],
            ),
        )

    def prefers_direct_review(self) -> bool:
        """Return True to use direct review path.

        The FSM orchestrator has its own AgentRuntime-first logic
        and direct-LLM fallback, so it doesn't need the orchestrator's
        AgentRuntime wrapper.
        """
        return True
