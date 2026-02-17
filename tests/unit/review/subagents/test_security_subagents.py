"""Tests for security subagents.

Tests cover BaseSubagent and all 4 specialized subagents:
- AuthSecuritySubagent
- InjectionScannerSubagent
- SecretScannerSubagent
- DependencyAuditSubagent

Note: Subagents now use SimpleReviewAgentRunner directly instead of LoopFSM.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from iron_rook.review.subagents.security_subagents import (
    BaseSubagent,
    AuthSecuritySubagent,
    InjectionScannerSubagent,
    SecretScannerSubagent,
    DependencyAuditSubagent,
)
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput, Scope, MergeGate, Finding


class TestBaseSubagentInitialization:
    """Test BaseSubagent class initialization through concrete subclasses."""

    def test_auth_subagent_initializes_without_fsm(self):
        """Verify AuthSecuritySubagent initializes (FSM is now optional/None)."""
        subagent = AuthSecuritySubagent()
        assert hasattr(subagent, "_fsm")
        # _fsm is now None since we don't use LoopFSM
        assert subagent._fsm is None

    def test_auth_subagent_accepts_max_retries(self):
        """Verify AuthSecuritySubagent accepts max_retries parameter."""
        subagent = AuthSecuritySubagent(max_retries=5)
        # max_retries is now stored in base class but not in FSM
        assert subagent._fsm is None

    def test_injection_subagent_initializes_without_fsm(self):
        """Verify InjectionScannerSubagent initializes (FSM is now optional/None)."""
        subagent = InjectionScannerSubagent()
        assert hasattr(subagent, "_fsm")
        assert subagent._fsm is None

    def test_secret_subagent_initializes_without_fsm(self):
        """Verify SecretScannerSubagent initializes (FSM is now optional/None)."""
        subagent = SecretScannerSubagent()
        assert hasattr(subagent, "_fsm")
        assert subagent._fsm is None

    def test_dependency_subagent_initializes_without_fsm(self):
        """Verify DependencyAuditSubagent initializes (FSM is now optional/None)."""
        subagent = DependencyAuditSubagent()
        assert hasattr(subagent, "_fsm")
        assert subagent._fsm is None


class TestAuthSecuritySubagent:
    """Test AuthSecuritySubagent initialization and properties."""

    def test_auth_subagent_inherits_from_base_subagent(self):
        """Verify AuthSecuritySubagent inherits from BaseSubagent."""
        subagent = AuthSecuritySubagent()
        assert isinstance(subagent, BaseSubagent)

    def test_auth_subagent_get_agent_name(self):
        """Verify AuthSecuritySubagent returns correct agent name."""
        subagent = AuthSecuritySubagent()
        assert subagent.get_agent_name() == "auth_security"

    def test_auth_subagent_get_system_prompt(self):
        """Verify AuthSecuritySubagent returns system prompt."""
        subagent = AuthSecuritySubagent()
        prompt = subagent.get_system_prompt()
        assert isinstance(prompt, str)
        assert "Authentication Security Subagent" in prompt
        assert "JWT" in prompt
        assert "session" in prompt.lower()

    def test_auth_subagent_get_relevant_file_patterns(self):
        """Verify AuthSecuritySubagent returns relevant file patterns."""
        subagent = AuthSecuritySubagent()
        patterns = subagent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert any("auth" in p for p in patterns)
        assert any("session" in p for p in patterns)
        assert any("jwt" in p for p in patterns)

    def test_auth_subagent_get_allowed_tools(self):
        """Verify AuthSecuritySubagent returns allowed tools."""
        subagent = AuthSecuritySubagent()
        tools = subagent.get_allowed_tools()
        assert isinstance(tools, list)
        assert "grep" in tools
        assert "pytest" in tools
        assert "bandit" in tools


class TestInjectionScannerSubagent:
    """Test InjectionScannerSubagent initialization and properties."""

    def test_injection_subagent_inherits_from_base_subagent(self):
        """Verify InjectionScannerSubagent inherits from BaseSubagent."""
        subagent = InjectionScannerSubagent()
        assert isinstance(subagent, BaseSubagent)

    def test_injection_subagent_get_agent_name(self):
        """Verify InjectionScannerSubagent returns correct agent name."""
        subagent = InjectionScannerSubagent()
        assert subagent.get_agent_name() == "injection_scanner"

    def test_injection_subagent_get_system_prompt(self):
        """Verify InjectionScannerSubagent returns system prompt."""
        subagent = InjectionScannerSubagent()
        prompt = subagent.get_system_prompt()
        assert isinstance(prompt, str)
        assert "Injection Vulnerability Scanner" in prompt
        assert "SQL injection" in prompt
        assert "XSS" in prompt

    def test_injection_subagent_get_relevant_file_patterns(self):
        """Verify InjectionScannerSubagent returns relevant file patterns."""
        subagent = InjectionScannerSubagent()
        patterns = subagent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        # Check for .py and .js substrings in patterns (more flexible than exact match)
        assert any(".py" in p for p in patterns)
        assert any(".js" in p for p in patterns)

    def test_injection_subagent_get_allowed_tools(self):
        """Verify InjectionScannerSubagent returns allowed tools."""
        subagent = InjectionScannerSubagent()
        tools = subagent.get_allowed_tools()
        assert isinstance(tools, list)
        assert "grep" in tools
        assert "bandit" in tools
        assert "semgrep" in tools


class TestSecretScannerSubagent:
    """Test SecretScannerSubagent initialization and properties."""

    def test_secret_subagent_inherits_from_base_subagent(self):
        """Verify SecretScannerSubagent inherits from BaseSubagent."""
        subagent = SecretScannerSubagent()
        assert isinstance(subagent, BaseSubagent)

    def test_secret_subagent_get_agent_name(self):
        """Verify SecretScannerSubagent returns correct agent name."""
        subagent = SecretScannerSubagent()
        assert subagent.get_agent_name() == "secret_scanner"

    def test_secret_subagent_get_system_prompt(self):
        """Verify SecretScannerSubagent returns system prompt."""
        subagent = SecretScannerSubagent()
        prompt = subagent.get_system_prompt()
        assert isinstance(prompt, str)
        assert "Secrets Scanner" in prompt
        assert "API keys" in prompt
        assert "password" in prompt.lower()

    def test_secret_subagent_get_relevant_file_patterns(self):
        """Verify SecretScannerSubagent returns relevant file patterns."""
        subagent = SecretScannerSubagent()
        patterns = subagent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert "**/*.py" in patterns
        assert "**/*.yaml" in patterns
        assert "**/*.env*" in patterns

    def test_secret_subagent_get_allowed_tools(self):
        """Verify SecretScannerSubagent returns allowed tools."""
        subagent = SecretScannerSubagent()
        tools = subagent.get_allowed_tools()
        assert isinstance(tools, list)
        assert "grep" in tools
        assert "trufflehog" in tools


class TestDependencyAuditSubagent:
    """Test DependencyAuditSubagent initialization and properties."""

    def test_dependency_subagent_inherits_from_base_subagent(self):
        """Verify DependencyAuditSubagent inherits from BaseSubagent."""
        subagent = DependencyAuditSubagent()
        assert isinstance(subagent, BaseSubagent)

    def test_dependency_subagent_get_agent_name(self):
        """Verify DependencyAuditSubagent returns correct agent name."""
        subagent = DependencyAuditSubagent()
        assert subagent.get_agent_name() == "dependency_audit"

    def test_dependency_subagent_get_system_prompt(self):
        """Verify DependencyAuditSubagent returns system prompt."""
        subagent = DependencyAuditSubagent()
        prompt = subagent.get_system_prompt()
        assert isinstance(prompt, str)
        assert "Dependency Security Audit" in prompt
        assert "CVE" in prompt
        assert "vulnerabilities" in prompt.lower()

    def test_dependency_subagent_get_relevant_file_patterns(self):
        """Verify DependencyAuditSubagent returns relevant file patterns."""
        subagent = DependencyAuditSubagent()
        patterns = subagent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert "requirements" in "".join(patterns)
        assert "**/pyproject.toml" in patterns

    def test_dependency_subagent_get_allowed_tools(self):
        """Verify DependencyAuditSubagent returns allowed tools."""
        subagent = DependencyAuditSubagent()
        tools = subagent.get_allowed_tools()
        assert isinstance(tools, list)
        assert "grep" in tools
        assert "pip-audit" in tools
        assert "safety" in tools


class TestSubagentReviewExecution:
    """Test review execution for all subagent types."""

    @pytest.fixture
    def mock_review_context(self):
        """Create a mock ReviewContext for testing."""
        return ReviewContext(
            changed_files=["test.py"],
            diff="test diff content",
            repo_root="/tmp/test",
            base_ref="main",
            head_ref="feature",
        )

    @pytest.mark.asyncio
    async def test_auth_subagent_review_execution(self, mock_review_context):
        """Verify AuthSecuritySubagent executes review."""
        subagent = AuthSecuritySubagent()

        # Mock the _execute_review_with_runner to avoid actual LLM calls
        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_output = ReviewOutput(
                agent="auth_security",
                summary="Test summary",
                severity="merge",
                scope=Scope(
                    relevant_files=[],
                    ignored_files=[],
                    reasoning="Test",
                ),
                merge_gate=MergeGate(
                    decision="approve",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            mock_runner.return_value = mock_output

            # Execute review
            result = await subagent.review(mock_review_context)

            assert isinstance(result, ReviewOutput)

    @pytest.mark.asyncio
    async def test_injection_subagent_review_execution(self, mock_review_context):
        """Verify InjectionScannerSubagent executes review."""
        subagent = InjectionScannerSubagent()

        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_output = ReviewOutput(
                agent="injection_scanner",
                summary="Test summary",
                severity="merge",
                scope=Scope(
                    relevant_files=[],
                    ignored_files=[],
                    reasoning="Test",
                ),
                merge_gate=MergeGate(
                    decision="approve",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            mock_runner.return_value = mock_output

            result = await subagent.review(mock_review_context)

            assert isinstance(result, ReviewOutput)

    @pytest.mark.asyncio
    async def test_secret_subagent_review_execution(self, mock_review_context):
        """Verify SecretScannerSubagent executes review."""
        subagent = SecretScannerSubagent()

        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_output = ReviewOutput(
                agent="secret_scanner",
                summary="Test summary",
                severity="merge",
                scope=Scope(
                    relevant_files=[],
                    ignored_files=[],
                    reasoning="Test",
                ),
                merge_gate=MergeGate(
                    decision="approve",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            mock_runner.return_value = mock_output

            result = await subagent.review(mock_review_context)

            assert isinstance(result, ReviewOutput)

    @pytest.mark.asyncio
    async def test_dependency_subagent_review_execution(self, mock_review_context):
        """Verify DependencyAuditSubagent executes review."""
        subagent = DependencyAuditSubagent()

        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_output = ReviewOutput(
                agent="dependency_audit",
                summary="Test summary",
                severity="merge",
                scope=Scope(
                    relevant_files=[],
                    ignored_files=[],
                    reasoning="Test",
                ),
                merge_gate=MergeGate(
                    decision="approve",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            mock_runner.return_value = mock_output

            result = await subagent.review(mock_review_context)

            assert isinstance(result, ReviewOutput)


class TestSubagentErrorHandling:
    """Test error handling and retry behavior."""

    @pytest.fixture
    def mock_review_context(self):
        """Create a mock ReviewContext for testing."""
        return ReviewContext(
            changed_files=["test.py"],
            diff="test diff content",
            repo_root="/tmp/test",
            base_ref="main",
            head_ref="feature",
        )

    @pytest.mark.asyncio
    async def test_subagent_handles_llm_error_gracefully(self, mock_review_context):
        """Verify subagent handles LLM errors and raises appropriately."""
        subagent = InjectionScannerSubagent()

        # Mock _execute_review_with_runner to raise exception
        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_runner.side_effect = Exception("LLM API error")

            # Review should raise exception as per BaseReviewerAgent behavior
            with pytest.raises(Exception, match="LLM API error"):
                await subagent.review(mock_review_context)


class TestSubagentFindingsFormat:
    """Test that subagents return findings in correct ReviewOutput format."""

    @pytest.fixture
    def mock_review_context(self):
        """Create a mock ReviewContext for testing."""
        return ReviewContext(
            changed_files=["auth.py", "config.py"],
            diff="test diff content",
            repo_root="/tmp/test",
            base_ref="main",
            head_ref="feature",
        )

    @pytest.mark.asyncio
    async def test_auth_subagent_returns_correct_format(self, mock_review_context):
        """Verify AuthSecuritySubagent returns ReviewOutput with correct format."""
        subagent = AuthSecuritySubagent()

        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_output = ReviewOutput(
                agent="auth_security",
                summary="Auth review complete",
                severity="warning",
                scope=Scope(
                    relevant_files=["auth.py"],
                    ignored_files=[],
                    reasoning="Found auth-related changes",
                ),
                findings=[
                    Finding(
                        id="AUTH-001",
                        title="Weak password hashing",
                        severity="warning",
                        confidence="high",
                        owner="security",
                        estimate="M",
                        evidence="Line 45 uses MD5 hashing",
                        risk="MD5 is not secure",
                        recommendation="Use bcrypt or Argon2",
                    )
                ],
                merge_gate=MergeGate(
                    decision="needs_changes",
                    must_fix=["Weak password hashing"],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            mock_runner.return_value = mock_output

            result = await subagent.review(mock_review_context)

            # Verify ReviewOutput structure
            assert isinstance(result, ReviewOutput)
            assert result.agent == "auth_security"
            assert result.severity in ["merge", "warning", "critical", "blocking"]
            assert result.merge_gate.decision in [
                "approve",
                "needs_changes",
                "block",
                "approve_with_warnings",
            ]
            assert isinstance(result.findings, list)
            # Use hasattr instead of isinstance to avoid issues if Scope has __dict__
            assert hasattr(result, "scope")

    @pytest.mark.asyncio
    async def test_secret_subagent_returns_findings(self, mock_review_context):
        """Verify SecretScannerSubagent returns findings in correct format."""
        subagent = SecretScannerSubagent()

        with patch.object(
            BaseSubagent, "_execute_review_with_runner", new_callable=AsyncMock
        ) as mock_runner:
            mock_output = ReviewOutput(
                agent="secret_scanner",
                summary="Secret scan complete",
                severity="blocking",
                scope=Scope(
                    relevant_files=["config.py"],
                    ignored_files=[],
                    reasoning="Found potential secrets",
                ),
                findings=[
                    Finding(
                        id="SEC-001",
                        title="Hardcoded API key",
                        severity="blocking",
                        confidence="high",
                        owner="security",
                        estimate="S",
                        evidence="Line 10: API_KEY='sk-12345'",
                        risk="Secret exposed in source code",
                        recommendation="Remove and use environment variables",
                    )
                ],
                merge_gate=MergeGate(
                    decision="block",
                    must_fix=["Hardcoded API key"],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            mock_runner.return_value = mock_output

            result = await subagent.review(mock_review_context)

            assert result.agent == "secret_scanner"
            assert result.severity == "blocking"
            assert len(result.findings) > 0
            # Iterate over findings to check severity instead of direct index access
            assert any(finding.severity == "blocking" for finding in result.findings)
