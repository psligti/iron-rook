"""SecurityReviewer wrapper that integrates with AgentRuntime.

This wrapper adapts the SecurityReviewer agent to work with AgentRuntime
execution framework, providing:
- Early return on no relevance
- Tool policy injection
- AgentRuntime execution
- AgentResult → ReviewOutput transformation
- Findings verification
"""

from __future__ import annotations

import logging
from typing import Optional

from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput
from iron_rook.review.utils.agent_runtime_bridge import (
    agent_result_to_review_output,
)
from iron_rook.review.utils.session_helper import create_review_session
from iron_rook.review.verifier import FindingsVerifier
from dawn_kestrel.agents.runtime import AgentRuntime
from dawn_kestrel.core.agent_types import SessionManagerLike
from dawn_kestrel.tools import create_builtin_registry

logger = logging.getLogger(__name__)


class SecurityReviewerAgentRuntimeWrapper:
    """Wrapper for SecurityReviewer that uses AgentRuntime for execution.

    This wrapper provides a bridge between review agent interface and
    AgentRuntime execution framework, handling session management,
    tool filtering, and result transformation.

    Args:
        agent_runtime: AgentRuntime instance for agent execution
        session_manager: SessionManager for session lifecycle management
        verifier: Optional FindingsVerifier for findings verification

    Example:
        >>> from dawn_kestrel.agents.runtime import AgentRuntime
        >>> from dawn_kestrel.storage.store import SessionStorage
        >>> from dawn_kestrel.core.session import SessionManager
        >>> from pathlib import Path
        >>>
        >>> storage = SessionStorage(base_dir=Path("/tmp"))
        >>> session_manager = SessionManager(storage=storage, project_dir=Path("/repo"))
        >>> runtime = AgentRuntime(agent_registry, Path("/repo"))
        >>>
        >>> wrapper = SecurityReviewerAgentRuntimeWrapper(
        ...     agent_runtime=runtime,
        ...     session_manager=session_manager
        ... )
        >>> output = await wrapper.review(context)
    """

    def __init__(
        self,
        agent_runtime: Optional[AgentRuntime],
        session_manager: Optional[SessionManagerLike],
        verifier: Optional[FindingsVerifier] = None,
    ):
        """Initialize wrapper with dependencies."""
        from iron_rook.review.verifier import GrepFindingsVerifier

        self._agent_runtime = agent_runtime
        self._session_manager = session_manager
        self._verifier = verifier or GrepFindingsVerifier()

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform security review using AgentRuntime.

        This method:
        1. Checks relevance and returns early if no relevant files changed
        2. Creates an ephemeral review session
        3. Formats ReviewContext as user message
        4. Injects tool policy into system prompt
        5. Calls AgentRuntime.execute_agent()
        6. Transforms AgentResult to ReviewOutput
        7. Calls verify_findings() on result
        8. Handles errors appropriately

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with security findings, severity, and merge gate decision

        Raises:
            TimeoutError: If LLM request times out
            Exception: For other API-related errors (returns critical ReviewOutput)
        """
        logger.info(f"[SecurityReviewerAgentRuntimeWrapper] review() called")
        logger.info(f"[SecurityReviewerAgentRuntimeWrapper]   repo_root: {context.repo_root}")
        logger.info(
            f"[SecurityReviewerAgentRuntimeWrapper]   changed_files: {len(context.changed_files)}"
        )
        logger.info(f"[SecurityReviewerAgentRuntimeWrapper]   diff_size: {len(context.diff)} chars")

        # Early return if no relevant files
        if not self._is_relevant_to_changes(context.changed_files):
            logger.info(f"[SecurityReviewerAgentRuntimeWrapper] No relevant files, returning early")
            return self._create_no_relevance_output(context)

        # Create ephemeral session
        session = create_review_session(context.repo_root, context)
        logger.info(f"[SecurityReviewerAgentRuntimeWrapper] Created session: {session.id}")

        # Format user message from ReviewContext
        user_message = self._format_user_message(context)

        # Get system prompt from inner reviewer
        system_prompt = self._get_system_prompt()

        # Inject tool policy into system prompt
        system_prompt = self._inject_tool_policy(system_prompt)

        # Create tool registry with allowed tools
        tools = await self._create_tool_registry()

        # Call AgentRuntime.execute_agent
        try:
            logger.info(
                f"[SecurityReviewerAgentRuntimeWrapper] Calling AgentRuntime.execute_agent()"
            )
            agent_result = await self._agent_runtime.execute_agent(
                agent_name="security",
                session_id=session.id,
                user_message=user_message,
                session_manager=self._session_manager,
                tools=tools,
                skills=[],
            )
            logger.info(
                f"[SecurityReviewerAgentRuntimeWrapper] Agent execution complete in {agent_result.duration:.2f}s"
            )
        except TimeoutError as e:
            logger.error(f"[SecurityReviewerAgentRuntimeWrapper] TimeoutError: {e}")
            raise
        except Exception as e:
            logger.error(f"[SecurityReviewerAgentRuntimeWrapper] Error: {e}")
            # Return critical ReviewOutput for other errors
            return self._create_error_output(context, str(e))

        # Transform AgentResult to ReviewOutput
        output = agent_result_to_review_output(agent_result, context)

        # Verify findings using verifier directly
        verification_results = self._verifier.verify(
            findings=output.findings,
            changed_files=context.changed_files,
            repo_root=context.repo_root,
        )

        if verification_results:
            logger.info(
                f"[SecurityReviewerAgentRuntimeWrapper] Verified findings: {len(verification_results)} evidence entries"
            )

        logger.info(f"[SecurityReviewerAgentRuntimeWrapper] review() returning")
        return output

    def _is_relevant_to_changes(self, changed_files: list[str]) -> bool:
        """Check if changed files are relevant to security review."""
        patterns = self._get_relevant_file_patterns()
        if not patterns:
            return False

        for file_path in changed_files:
            for pattern in patterns:
                from fnmatch import fnmatch

                if fnmatch(file_path, pattern):
                    return True
        return False

    def _get_relevant_file_patterns(self) -> list[str]:
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

    def _get_system_prompt(self) -> str:
        """Get system prompt for security reviewer."""
        return """You are Security Review Subagent.

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
- recommendations must be actionable, least-disruptive, and tied to observed risk

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

Your agent name is "security".
"""

    def _inject_tool_policy(self, system_prompt: str) -> str:
        """Inject tool policy into system prompt."""
        tool_policy = """

Tool Policy:
- todowrite and todoread: ALLOWED for todo list management
- All other tools: CHECK ONLY (do not execute)
- For security checks, use grep/bandit/semgrep as checks only
- Do NOT execute write/edit tools beyond todowrite
"""
        return system_prompt + tool_policy

    async def _create_tool_registry(self):
        """Create tool registry with allowed tools for security review."""
        allowed_tools = [
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

        registry = create_builtin_registry()

        # Filter to allowed tools
        filtered_tools = {
            tool_id: tool_def
            for tool_id, tool_def in registry.tools.items()
            if tool_id in allowed_tools
        }

        from dawn_kestrel.tools.framework import ToolRegistry

        filtered_registry = ToolRegistry()
        for tool_id, tool_def in filtered_tools.items():
            await filtered_registry.register(tool_def, tool_id=tool_id)

        logger.debug(
            f"[SecurityReviewerAgentRuntimeWrapper] Tool registry: {len(filtered_registry.tools)} tools available"
        )

        return filtered_registry

    def _format_user_message(self, context: ReviewContext) -> str:
        """Format ReviewContext as user message for AgentRuntime."""
        parts = [
            "## Review Context",
            "",
            f"**Repository Root**: {context.repo_root}",
            "",
            "### Changed Files",
        ]

        for file_path in context.changed_files:
            parts.append(f"- {file_path}")

        if context.base_ref and context.head_ref:
            parts.append("")
            parts.append("### Git Diff")
            parts.append(f"**Base Ref**: {context.base_ref}")
            parts.append(f"**Head Ref**: {context.head_ref}")

        parts.append("")
        parts.append("### Diff Content")
        parts.append("```diff")
        parts.append(context.diff)
        parts.append("```")

        if context.pr_title:
            parts.append("")
            parts.append("### Pull Request")
            parts.append(f"**Title**: {context.pr_title}")
            if context.pr_description:
                parts.append(f"**Description**:\n{context.pr_description}")

        return "\n".join(parts)

    def _create_no_relevance_output(self, context: ReviewContext) -> ReviewOutput:
        """Create ReviewOutput for no relevance case."""
        from iron_rook.review.contracts import Scope, MergeGate

        return ReviewOutput(
            agent="security",
            summary="No security-relevant files changed. Security review not applicable.",
            severity="merge",
            scope=Scope(
                relevant_files=[],
                ignored_files=context.changed_files,
                reasoning="No files matched security relevance patterns",
            ),
            checks=[],
            skips=[],
            findings=[],
            merge_gate=MergeGate(
                decision="approve",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=["No security-relevant files were changed."],
            ),
        )

    def _create_error_output(self, context: ReviewContext, error_message: str) -> ReviewOutput:
        """Create ReviewOutput for error case."""
        from iron_rook.review.contracts import Scope, MergeGate

        return ReviewOutput(
            agent="security",
            summary=f"Security review error: {error_message}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                ignored_files=[],
                reasoning="Review failed due to error",
            ),
            checks=[],
            skips=[],
            findings=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[f"Review error: {error_message}"],
                should_fix=[],
                notes_for_coding_agent=["Review failed. Please retry or investigate error."],
            ),
        )
