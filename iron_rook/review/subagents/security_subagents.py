"""Security subagents for specialized security analysis.

This module provides specialized security subagents that inherit from BaseSubagent
and use the LoopFSM pattern for execution. Each subagent focuses on a specific
security domain:
- AuthSecuritySubagent: Authentication and authorization patterns
- InjectionScannerSubagent: SQL, command, template injection patterns
- SecretScannerSubagent: Hardcoded secrets and credentials
- DependencyAuditSubagent: Dependency security and vulnerability analysis
"""

from __future__ import annotations
from typing import List
import logging
import asyncio

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    get_review_output_schema,
    Scope,
    MergeGate,
    Finding,
)
from iron_rook.fsm.loop_fsm import LoopFSM
from iron_rook.fsm.loop_state import LoopState
from iron_rook.fsm.todo import Todo

from dawn_kestrel.core.harness import SimpleReviewAgentRunner

logger = logging.getLogger(__name__)


class BaseSubagent(BaseReviewerAgent):
    """Base class for all security subagents.

    Provides FSM loop execution using LoopFSM with the following phases:
    - INTAKE: Initial phase, gathering and validating inputs
    - PLAN: Planning phase, determining execution strategy
    - ACT: Execution phase, running planned actions
    - SYNTHESIZE: Synthesis phase, combining and processing results
    - DONE: Loop completed successfully

    Subclasses must implement:
    - get_agent_name(): Return the agent identifier
    - get_system_prompt(): Return the system prompt for LLM
    - get_relevant_file_patterns(): Return file patterns this subagent is relevant to
    - get_allowed_tools(): Return allowed tool/command prefixes
    - review(): Perform review and return ReviewOutput
    """

    def __init__(
        self,
        verifier: object | None = None,
        max_retries: int = 3,
        agent_runtime: object | None = None,
    ) -> None:
        """Initialize base subagent with LoopFSM.

        Args:
            verifier: FindingsVerifier strategy instance.
            max_retries: Maximum number of retry attempts for failed operations.
            agent_runtime: Optional AgentRuntime for executing sub-loops.
        """
        super().__init__(verifier=verifier, max_retries=max_retries, agent_runtime=agent_runtime)

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform review using FSM loop execution.

        Orchestrates the review using the LoopFSM pattern:
        1. INTAKE: Validate context and inputs
        2. PLAN: Determine analysis strategy
        3. ACT: Execute security analysis
        4. SYNTHESIZE: Combine findings into ReviewOutput
        5. DONE: Return final ReviewOutput

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with findings, severity, and merge gate decision
        """
        logger.info(f"[{self.__class__.__name__}] Starting FSM loop execution")

        # Build context for FSM
        fsm_context = {
            "agent_name": self.get_agent_name(),
            "changed_files": context.changed_files,
            "diff": context.diff,
            "repo_root": context.repo_root,
            "base_ref": context.base_ref,
            "head_ref": context.head_ref,
            "pr_title": context.pr_title,
            "pr_description": context.pr_description,
        }

        try:
            # Execute FSM loop synchronously
            # The LoopFSM run_loop() handles all transitions internally
            self._fsm.run_loop(fsm_context)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] FSM loop failed: {e}")
            # Return a ReviewOutput indicating failure
            return ReviewOutput(
                agent=self.get_agent_name(),
                summary=f"Security review failed: {str(e)}",
                severity="critical",
                scope=Scope(
                    relevant_files=context.changed_files,
                    ignored_files=[],
                    reasoning="Review execution failed during FSM loop",
                ),
                findings=[],
                merge_gate=MergeGate(
                    decision="needs_changes",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[
                        f"Review failed due to error: {str(e)}",
                        "Please retry or investigate the error",
                    ],
                ),
            )

        # After FSM completes, generate ReviewOutput from findings
        # For now, use the parent class method with SimpleReviewAgentRunner
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=True,
            no_relevance_summary=f"No {self.get_agent_name()}-relevant files changed. Review not applicable.",
        )

    def _execute_action_subagent(self) -> None:
        """Execute the action for the ACT phase.

        This method is called by LoopFSM during the ACT phase.
        Subclasses can override this to implement specific analysis logic.

        Raises:
            RuntimeError: If action execution fails.
        """
        # Base implementation does nothing
        # Subclasses should override with specific analysis logic
        logger.debug(f"[{self.__class__.__name__}] _execute_action_subagent called")


class AuthSecuritySubagent(BaseSubagent):
    """Security subagent focused on authentication and authorization patterns.

    Checks for:
    - JWT implementation patterns
    - Session management
    - Authentication middleware
    - Authorization checks
    - RBAC implementation
    """

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform authentication security review.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with auth security findings
        """
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=True,
            no_relevance_summary="No authentication-relevant files changed. Auth security review not applicable.",
        )

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "auth_security"

    def get_system_prompt(self) -> str:
        """Return system prompt for auth security analysis."""
        return f"""You are the Authentication Security Subagent.

You specialize in reviewing authentication and authorization patterns:

Focus areas:
- JWT implementation (token signing, validation, expiration)
- Session management (secure cookie handling, session fixation)
- Authentication middleware (proper implementation, not bypassable)
- Authorization checks (RBAC, permission verification)
- Password handling (hashing, storage, strength requirements)
- OAuth/OpenID Connect flows (proper implementation, token security)
- Multi-factor authentication (MFA) implementation

Security risks to identify:
- Weak password policies or hashing algorithms
- Insecure session token generation or storage
- Missing or bypassable authorization checks
- Hardcoded credentials or API keys
- Insecure JWT configuration (weak secrets, no expiration)
- Session fixation vulnerabilities
- Missing CSRF protection

Scoping heuristics:
- Relevant when changes include: authentication logic, session handling,
  authorization checks, password management, JWT/OAuth code, login endpoints.
- Often ignore: UI-only changes, documentation, static content.

{get_review_output_schema()}"""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this subagent is relevant to."""
        return [
            "**/*auth*.py",
            "**/*session*.py",
            "**/*jwt*.py",
            "**/*token*.py",
            "**/*login*.py",
            "**/*password*.py",
            "**/*oauth*.py",
            "**/*oidc*.py",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Return allowed tool/command prefixes for this subagent."""
        return [
            "grep",
            "ripgrep",
            "python",
            "pytest",
            "bandit",
            "semgrep",
        ]


class InjectionScannerSubagent(BaseSubagent):
    """Security subagent focused on injection vulnerabilities.

    Checks for:
    - SQL injection patterns
    - Command injection patterns
    - Template injection patterns
    - XSS (cross-site scripting) vectors
    - LDAP injection patterns
    """

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform injection vulnerability review.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with injection security findings
        """
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=True,
            no_relevance_summary="No injection-relevant files changed. Injection scan not applicable.",
        )

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "injection_scanner"

    def get_system_prompt(self) -> str:
        """Return system prompt for injection vulnerability analysis."""
        return f"""You are the Injection Vulnerability Scanner Subagent.

You specialize in detecting injection vulnerabilities:

Focus areas:
- SQL injection (unsafe query construction, missing parameterization)
- Command injection (subprocess/shell calls with user input)
- Template injection (unsafe template rendering)
- Cross-site scripting (XSS) vectors (unsafe HTML/JS rendering)
- LDAP injection (unsafe LDAP query construction)
- NoSQL injection (unsafe document database queries)
- Path traversal (unsafe file path handling)
- Code injection (unsafe eval/exec usage)

Security risks to identify:
- String concatenation in SQL queries without parameterization
- User input passed to subprocess/shell commands
- Unsafe template rendering with user data
- Unescaped HTML/JavaScript in output
- Missing input validation and sanitization
- Unsafe use of eval(), exec(), or similar functions
- Direct file path access with user input

Scoping heuristics:
- Relevant when changes include: database queries, user input handling,
  command execution, template rendering, file operations, API endpoints.
- Often ignore: pure business logic, data structures, configuration.

{get_review_output_schema()}"""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this subagent is relevant to."""
        return [
            "**/*.py",
            "**/*.js",
            "**/*.ts",
            "**/*.sql",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Return allowed tool/command prefixes for this subagent."""
        return [
            "grep",
            "ripgrep",
            "bandit",
            "semgrep",
            "safety",
        ]


class SecretScannerSubagent(BaseSubagent):
    """Security subagent focused on secrets and credential detection.

    Checks for:
    - Hardcoded API keys
    - Passwords in code
    - JWT secrets
    - Database credentials
    - Cloud provider keys (AWS, GCP, Azure)
    - SSH keys
    """

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform secrets detection review.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with secrets detection findings
        """
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=True,
            no_relevance_summary="No secrets-relevant files changed. Secret scan not applicable.",
        )

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "secret_scanner"

    def get_system_prompt(self) -> str:
        """Return system prompt for secrets detection analysis."""
        return f"""You are the Secrets Scanner Subagent.

You specialize in detecting hardcoded secrets and credentials:

Focus areas:
- API keys and tokens
- Database passwords and connection strings
- JWT signing secrets
- Cloud provider credentials (AWS, GCP, Azure)
- SSH private keys
- OAuth tokens
- Third-party API credentials
- Certificates and private keys

Security risks to identify:
- Hardcoded API keys (AWS, GitHub, Stripe, etc.)
- Database passwords in code
- JWT secrets exposed
- Cloud access keys in configuration
- SSH private keys committed to repo
- OAuth tokens in code
- Base64-encoded secrets
- Comments containing credentials

Secret patterns to detect:
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
- GOOGLE_APPLICATION_CREDENTIALS
- AZURE_CLIENT_SECRET
- API_KEY=, api_key=, apiKey=
- password=, passwd=, pwd=
- JWT_SECRET, jwt_secret
- PRIVATE KEY, -----BEGIN PRIVATE KEY-----

Scoping heuristics:
- Relevant when changes include: configuration files, environment variable handling,
  credential management, authentication code, deployment scripts.
- Often ignore: documentation, test fixtures with obvious fake credentials.

{get_review_output_schema()}"""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this subagent is relevant to."""
        return [
            "**/*.py",
            "**/*.yaml",
            "**/*.yml",
            "**/*.json",
            "**/*.env*",
            "**/*.toml",
            "**/*.ini",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Return allowed tool/command prefixes for this subagent."""
        return [
            "grep",
            "ripgrep",
            "trufflehog",
            "git-secrets",
        ]


class DependencyAuditSubagent(BaseSubagent):
    """Security subagent focused on dependency vulnerability analysis.

    Checks for:
    - Outdated dependencies
    - Known vulnerabilities (CVEs)
    - Dependency license issues
    - Supply chain risks
    - New or removed dependencies
    """

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform dependency security audit.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with dependency security findings
        """
        return await self._execute_review_with_runner(
            context,
            early_return_on_no_relevance=True,
            no_relevance_summary="No dependency files changed. Dependency audit not applicable.",
        )

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "dependency_audit"

    def get_system_prompt(self) -> str:
        """Return system prompt for dependency security analysis."""
        return f"""You are the Dependency Security Audit Subagent.

You specialize in reviewing dependency security:

Focus areas:
- Known vulnerabilities (CVEs) in dependencies
- Outdated packages with security fixes
- Dependency license compliance
- Supply chain risk signals
- New or removed dependencies in changes
- Dependency version pinning issues
- Malicious package indicators

Security risks to identify:
- Dependencies with known CVEs
- Outdated packages with available security patches
- Loosened version constraints (e.g., changing from == to >=)
- New dependencies without security review
- Dependencies with few maintainers or suspicious activity
- License conflicts with project requirements
- Transitive dependencies with security issues

Common dependency files to check:
- Python: requirements.txt, pyproject.toml, setup.py, poetry.lock
- Node.js: package.json, package-lock.json, yarn.lock
- Java: pom.xml, build.gradle
- Go: go.mod, go.sum

Scoping heuristics:
- Relevant when changes include: dependency files, package management,
  build configuration, lock files.
- Often ignore: source code changes without dependency updates.

{get_review_output_schema()}"""

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this subagent is relevant to."""
        return [
            "**/requirements*.txt",
            "**/pyproject.toml",
            "**/setup.py",
            "**/poetry.lock",
            "**/Pipfile*",
            "**/package.json",
            "**/package-lock.json",
            "**/yarn.lock",
            "**/pom.xml",
            "**/build.gradle",
            "**/go.mod",
            "**/go.sum",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Return allowed tool/command prefixes for this subagent."""
        return [
            "grep",
            "ripgrep",
            "pip-audit",
            "safety",
            "snyk",
            "npm audit",
        ]
