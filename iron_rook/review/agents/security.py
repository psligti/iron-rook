"""Security Review Subagent - checks for security vulnerabilities."""

from __future__ import annotations
from typing import List, Optional
import asyncio
import logging

from dawn_kestrel.agents.builtin import Agent
from dawn_kestrel.agents.registry import AgentRegistry
from iron_rook.review.base import BaseReviewerAgent, ReviewContext


from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
)
from iron_rook.review.verifier import FindingsVerifier
from iron_rook.review.utils.agent_runtime_bridge import (
    SecurityReviewerAgentRuntimeWrapper,
)
from dawn_kestrel.agents.runtime import AgentRuntime
from dawn_kestrel.core.agent_types import SessionManagerLike

logger = logging.getLogger(__name__)


SECURITY_REVIEWER_AGENT = Agent(
    name="security",
    description="Security reviewer with tool execution support",
    mode="subagent",
    native=False,
    permission=[
        {"permission": "todowrite", "pattern": "*", "action": "allow"},
        {"permission": "todoread", "pattern": "*", "action": "allow"},
        {"permission": "*", "pattern": "*", "action": "deny"},
    ],
)


def _register_agent_sync() -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(AgentRegistry().register_agent(SECURITY_REVIEWER_AGENT))


_register_agent_sync()


class SecurityReviewer(BaseReviewerAgent):
    """Security reviewer agent that checks for security vulnerabilities.

    This agent specializes in detecting:
    - Secrets handling (API keys, passwords, tokens)
    - Authentication/authorization issues
    - Injection risks (SQL, XSS, command)
    - CI/CD exposures
    - Unsafe code execution patterns
    """

    def __init__(
        self,
        verifier: Optional[FindingsVerifier] = None,
        use_agent_runtime: bool = False,
        agent_runtime: Optional[AgentRuntime] = None,
        session_manager: Optional[SessionManagerLike] = None,
    ):
        """Initialize SecurityReviewer with optional AgentRuntime wrapper support.

        Args:
            verifier: FindingsVerifier strategy instance. If None, uses
                GrepFindingsVerifier by default.
            use_agent_runtime: If True, uses SecurityReviewerAgentRuntimeWrapper
                for execution. If False (default), uses SimpleReviewAgentRunner.
            agent_runtime: AgentRuntime instance required when use_agent_runtime=True.
            session_manager: SessionManager instance required when use_agent_runtime=True.
        """
        super().__init__(verifier=verifier)
        self._use_agent_runtime = use_agent_runtime
        self._agent_runtime = agent_runtime
        self._session_manager = session_manager

    def get_agent_name(self) -> str:
        """Return agent identifier."""
        return "security"

    def get_system_prompt(self) -> str:
        """Get system prompt for security reviewer."""
        return f"""You are Security Review Subagent.

Todo List Management:
- Use todowrite tool to create and manage a structured todo list at review start
- Use todoread tool to check current todo status before and after each check
- Maintain strict status transitions: pending -> in_progress -> completed (or cancelled)
- Add new todos dynamically when you discover findings requiring deeper analysis
- Prioritize todos by security impact: high (critical vulnerabilities), medium (elevated risk), low (routine checks)

Subagent Delegation for Complex Analysis:
- For complex findings requiring deep analysis, use task tool to delegate to specialized subagents
- Create a tracking todo before delegating, mark in_progress while subagent runs, mark completed after receiving results
- Delegate to: security (deep dive), architecture (trust boundaries), testing (exploitability)
- Monitor delegated subagents and incorporate their findings into your security assessment

Primary goals:
- prevent high-impact security regressions from merging
- focus review effort where trust boundaries, privilege, or sensitive data changed
- produce auditable findings with concrete evidence and clear remediation

Risk triage workflow:
- classify each changed file or diff chunk by risk: critical, elevated, routine, or not-applicable
- prioritize surfaces that introduce or modify trust boundaries, authentication, authorization, or data flow from untrusted input
- start with minimal high-signal checks, then deepen only when risk or uncertainty remains
- if changed_files or diff are missing, request them before issuing conclusions

Evidence standards:
- ground every finding in specific diff evidence (file path, behavior, and risk mechanism)
- explain exploitability and impact, not just rule matches
- avoid speculative claims when evidence is weak; lower confidence or record as a skip with rationale
- recommendations must be actionable, least-disruptive, and tied to the observed risk

Dynamic check selection:
- select checks based on changed technologies, files, and threat model rather than a fixed checklist
- reference available analyzers when useful (for example SAST or dependency audit), but do not prescribe shell command choreography
- prefer checks that either validate exploitability or reduce uncertainty for blocking decisions

You specialize in:
- secrets handling (keys/tokens/passwords), logging of sensitive data
- authn/authz, permission checks, RBAC
- injection risks: SQL injection, command injection, template injection, prompt injection
- SSRF, unsafe network calls, insecure defaults
- dependency/supply chain risk signals (new deps, loosened pins)
- cryptography misuse
- file/path handling, deserialization, eval/exec usage
- CI/CD exposures (tokens, permissions, workflow changes)

Todo Workflow for Security Reviews:

1. START: Create initial todo list using todowrite:
   - "analyze-trust-boundaries" (high priority): Review authentication, authorization, permission changes
   - "check-secrets-handling" (high priority): Scan for hardcoded credentials, token leaks
   - "verify-input-validation" (medium priority): Check for injection vulnerabilities
   - "audit-dependencies" (medium priority): Review new dependencies for supply chain risks
   - "assess-exploitability" (medium priority): Evaluate discovered vulnerabilities for exploit potential
   - "generate-report" (low priority): Synthesize findings into ReviewOutput format

2. DURING REVIEW: Use todoread before starting each check:
   - Mark current todo as "in_progress" before starting analysis
   - Mark completed after finishing check and recording findings
   - Add new todos if analysis uncovers complex issues requiring deeper investigation

3. FOR COMPLEX FINDINGS: Delegate to subagents:
   - Create todo: "deep-dive-<finding-id>" (high priority) before delegating
   - Use task tool with subagent_type appropriate to finding type
   - Example: "task tool, delegate to architecture reviewer to analyze trust boundary design"
   - Mark todo as "completed" when subagent returns findings

4. END: Mark "generate-report" as in_progress, then complete
   - Log final todo status using todoread to verify all todos completed
   - Ensure no high-priority todos remain pending before returning ReviewOutput

High-signal file patterns:
- auth/**, security/**, iam/**, permissions/**, middleware/**
- network clients, webhook handlers, request parsers
- subprocess usage, shell commands
- config files: *.yml, *.yaml (CI), Dockerfile, terraform, deploy scripts
- dependency files: pyproject.toml, requirements*.txt, poetry.lock, uv.lock

Checks you may request (when available and relevant):
- bandit (Python SAST)
- dependency audit (pip-audit / poetry audit / uv audit)
- semgrep ruleset
- grep checks: "password", "token", "secret", "AWS_", "PRIVATE_KEY"

Security review must answer:
1) Did we introduce a new trust boundary or input surface?
2) Are inputs validated and outputs encoded appropriately?
3) Are secrets handled safely (not logged, not committed, not exposed)?
4) Are permissions least-privilege and explicit?

Blocking conditions:
- plaintext secrets committed or leaked into logs
- authz bypass risk or missing permission checks
- code execution risk (eval/exec) without strong sandboxing
- command injection risk via subprocess with untrusted input
- unsafe deserialization of untrusted input

{get_review_output_schema()}

Your agent name is "security"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns relevant to security review."""
        return [
            "**/*.py",
            "**/*.yml",
            "**/*.yaml",
            "**/auth*/**",
            "**/security*/**",
            "**/iam/**",
            "**/permissions/**",
            "**/middleware/**",
            "**/requirements*.txt",
            "**/pyproject.toml",
            "**/poetry.lock",
            "**/uv.lock",
            "**/Dockerfile*",
            "**/*.tf",
            "**/.github/workflows/**",
            "**/.gitlab-ci.yml",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for security review checks."""
        return [
            "git",
            "grep",
            "ast-grep",
            "python",
            "bandit",
            "semgrep",
            "pip-audit",
            "uv",
            "poetry",
            "todowrite",
            "todoread",
        ]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform security review on given context.

        Uses either SecurityReviewerAgentRuntimeWrapper (when use_agent_runtime=True)
        or SimpleReviewAgentRunner via _execute_review_with_runner() (when use_agent_runtime=False).

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with security findings, severity, and merge gate decision

        Raises:
            ValueError: If API key is missing or invalid
            TimeoutError: If LLM request times out
            Exception: For other API-related errors
        """
        logger.info(f"[security] >>> review() called")
        logger.info(f"[security]     repo_root: {context.repo_root}")
        logger.info(f"[security]     base_ref: {context.base_ref}")
        logger.info(f"[security]     head_ref: {context.head_ref}")
        logger.info(f"[security]     changed_files: {len(context.changed_files)}")
        logger.info(f"[security]     diff_size: {len(context.diff)} chars")
        logger.info(f"[security]     pr_title: {context.pr_title}")
        logger.info(
            f"[security]     pr_description: {len(context.pr_description) if context.pr_description else 0} chars"
        )
        logger.info(f"[security]     use_agent_runtime: {self._use_agent_runtime}")

        if self._use_agent_runtime:
            logger.info(f"[security] Using AgentRuntime wrapper path")

            wrapper = SecurityReviewerAgentRuntimeWrapper(
                agent_runtime=self._agent_runtime,
                session_manager=self._session_manager,
                verifier=self._verifier,
            )

            output = await wrapper.review(context)
        else:
            logger.info(
                f"[security] NOTE: Agent will create todo list and track progress via todowrite/todoread"
            )

            output = await self._execute_review_with_runner(
                context,
                early_return_on_no_relevance=True,
                no_relevance_summary="No security-relevant files changed. Security review not applicable.",
            )

        logger.info(f"[security] Parsed ReviewOutput:")
        logger.info(f"[security]   agent: {output.agent}")
        logger.info(
            f"[security]   summary: {output.summary[:100]}{'...' if len(output.summary) > 100 else ''}"
        )
        logger.info(f"[security]   severity: {output.severity}")
        logger.info(f"[security]   findings: {len(output.findings)}")
        logger.info(f"[security]   checks: {len(output.checks)}")
        logger.info(f"[security]   skips: {len(output.skips)}")
        logger.info(
            f"[security] TODO STATUS: Review completed. All security check todos should be marked completed."
        )
        for i, finding in enumerate(output.findings, 1):
            logger.info(f"[security]   Finding #{i}: {finding.title}")
            logger.info(f"[security]     id: {finding.id}")
            logger.info(f"[security]     severity: {finding.severity}")
            logger.info(f"[security]     confidence: {finding.confidence}")
            logger.info(f"[security]     owner: {finding.owner}")
            logger.info(f"[security]     estimate: {finding.estimate}")
            logger.debug(
                f"[security]     evidence: {finding.evidence[:150]}{'...' if len(finding.evidence) > 150 else ''}"
            )
            logger.debug(
                f"[security]     recommendation: {finding.recommendation[:150]}{'...' if len(finding.recommendation) > 150 else ''}"
            )

        logger.info(f"[security] <<< review() returning")
        return output
