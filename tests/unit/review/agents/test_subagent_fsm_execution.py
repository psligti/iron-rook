"""Tests for subagent FSM loop execution.

Tests verify that each security subagent (AuthSecuritySubagent, InjectionScannerSubagent,
SecretScannerSubagent, DependencyAuditSubagent) properly:
- Inherits from BaseSubagent
- Implements required methods (get_agent_name, get_system_prompt, get_relevant_file_patterns, get_allowed_tools)
- review() method returns ReviewOutput

Note: Subagents no longer use LoopFSM directly - they use SimpleReviewAgentRunner.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from iron_rook.review.subagents.security_subagents import (
    AuthSecuritySubagent,
    InjectionScannerSubagent,
    SecretScannerSubagent,
    DependencyAuditSubagent,
    BaseSubagent,
)
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput


class TestAuthSecuritySubagent:
    """Test AuthSecuritySubagent initialization and execution."""

    def test_auth_security_subagent_inherits_from_base_subagent(self):
        """Verify AuthSecuritySubagent inherits from BaseSubagent."""
        agent = AuthSecuritySubagent()
        assert isinstance(agent, BaseSubagent)

    def test_auth_security_subagent_has_fsm_attribute(self):
        """Verify AuthSecuritySubagent has _fsm attribute (now None)."""
        agent = AuthSecuritySubagent()
        assert hasattr(agent, "_fsm")
        assert agent._fsm is None

    def test_auth_security_subagent_implements_get_agent_name(self):
        """Verify get_agent_name() method exists and returns correct value."""
        agent = AuthSecuritySubagent()
        assert hasattr(agent, "get_agent_name")
        assert agent.get_agent_name() == "auth_security"

    def test_auth_security_subagent_implements_get_system_prompt(self):
        """Verify get_system_prompt() method exists and returns non-empty string."""
        agent = AuthSecuritySubagent()
        assert hasattr(agent, "get_system_prompt")
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Authentication Security Subagent" in prompt

    def test_auth_security_subagent_implements_get_relevant_file_patterns(self):
        """Verify get_relevant_file_patterns() method exists and returns correct patterns."""
        agent = AuthSecuritySubagent()
        assert hasattr(agent, "get_relevant_file_patterns")
        patterns = agent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        # Verify auth-related patterns
        assert "**/*auth*.py" in patterns
        assert "**/*session*.py" in patterns
        assert "**/*jwt*.py" in patterns

    def test_auth_security_subagent_implements_get_allowed_tools(self):
        """Verify get_allowed_tools() method exists and returns security tools."""
        agent = AuthSecuritySubagent()
        assert hasattr(agent, "get_allowed_tools")
        tools = agent.get_allowed_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Verify security tools
        assert "grep" in tools
        assert "ripgrep" in tools
        assert "bandit" in tools

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_auth_security_subagent_review_returns_review_output(self, mock_runner_class):
        """Verify review() method returns ReviewOutput."""
        agent = AuthSecuritySubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "auth_security",\n  "summary": "No auth security issues found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No auth-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_auth_security_subagent_fsm_executes_full_cycle(self, mock_runner_class):
        """Verify FSM executes through INTAKE -> PLAN -> ACT -> SYNTHESIZE -> DONE cycle."""
        agent = AuthSecuritySubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "auth_security",\n  "summary": "No auth security issues found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No auth-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)


class TestInjectionScannerSubagent:
    """Test InjectionScannerSubagent initialization and execution."""

    def test_injection_scanner_subagent_inherits_from_base_subagent(self):
        """Verify InjectionScannerSubagent inherits from BaseSubagent."""
        agent = InjectionScannerSubagent()
        assert isinstance(agent, BaseSubagent)

    def test_injection_scanner_subagent_has_fsm_attribute(self):
        """Verify InjectionScannerSubagent has _fsm attribute (now None)."""
        agent = InjectionScannerSubagent()
        assert hasattr(agent, "_fsm")
        assert agent._fsm is None

    def test_injection_scanner_subagent_implements_get_agent_name(self):
        """Verify get_agent_name() method exists and returns correct value."""
        agent = InjectionScannerSubagent()
        assert hasattr(agent, "get_agent_name")
        assert agent.get_agent_name() == "injection_scanner"

    def test_injection_scanner_subagent_implements_get_system_prompt(self):
        """Verify get_system_prompt() method exists and returns non-empty string."""
        agent = InjectionScannerSubagent()
        assert hasattr(agent, "get_system_prompt")
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Injection Vulnerability Scanner Subagent" in prompt

    def test_injection_scanner_subagent_implements_get_relevant_file_patterns(self):
        """Verify get_relevant_file_patterns() method exists and returns correct patterns."""
        agent = InjectionScannerSubagent()
        assert hasattr(agent, "get_relevant_file_patterns")
        patterns = agent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        # Verify injection-relevant patterns
        assert "**/*.py" in patterns
        assert "**/*.js" in patterns
        assert "**/*.ts" in patterns

    def test_injection_scanner_subagent_implements_get_allowed_tools(self):
        """Verify get_allowed_tools() method exists and returns security tools."""
        agent = InjectionScannerSubagent()
        assert hasattr(agent, "get_allowed_tools")
        tools = agent.get_allowed_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Verify security tools
        assert "grep" in tools
        assert "ripgrep" in tools
        assert "bandit" in tools

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_injection_scanner_subagent_review_returns_review_output(self, mock_runner_class):
        """Verify review() method returns ReviewOutput."""
        agent = InjectionScannerSubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "injection_scanner",\n  "summary": "No injection vulnerabilities found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No injection-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_injection_scanner_subagent_fsm_executes_full_cycle(self, mock_runner_class):
        """Verify FSM executes through INTAKE -> PLAN -> ACT -> SYNTHESIZE -> DONE cycle."""
        agent = InjectionScannerSubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "injection_scanner",\n  "summary": "No injection vulnerabilities found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No injection-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)


class TestSecretScannerSubagent:
    """Test SecretScannerSubagent FSM initialization and execution."""

    def test_secret_scanner_subagent_inherits_from_base_subagent(self):
        """Verify SecretScannerSubagent inherits from BaseSubagent."""
        agent = SecretScannerSubagent()
        assert isinstance(agent, BaseSubagent)

    def test_secret_scanner_subagent_has_fsm_attribute(self):
        """Verify SecretScannerSubagent has _fsm attribute (now None)."""
        agent = SecretScannerSubagent()
        assert hasattr(agent, "_fsm")
        assert agent._fsm is None

    def test_secret_scanner_subagent_implements_get_agent_name(self):
        """Verify get_agent_name() method exists and returns correct value."""
        agent = SecretScannerSubagent()
        assert hasattr(agent, "get_agent_name")
        assert agent.get_agent_name() == "secret_scanner"

    def test_secret_scanner_subagent_implements_get_system_prompt(self):
        """Verify get_system_prompt() method exists and returns non-empty string."""
        agent = SecretScannerSubagent()
        assert hasattr(agent, "get_system_prompt")
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Secrets Scanner Subagent" in prompt

    def test_secret_scanner_subagent_implements_get_relevant_file_patterns(self):
        """Verify get_relevant_file_patterns() method exists and returns correct patterns."""
        agent = SecretScannerSubagent()
        assert hasattr(agent, "get_relevant_file_patterns")
        patterns = agent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        # Verify secret-relevant patterns
        assert "**/*.py" in patterns
        assert "**/*.yaml" in patterns
        assert "**/*.env*" in patterns

    def test_secret_scanner_subagent_implements_get_allowed_tools(self):
        """Verify get_allowed_tools() method exists and returns security tools."""
        agent = SecretScannerSubagent()
        assert hasattr(agent, "get_allowed_tools")
        tools = agent.get_allowed_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Verify security tools
        assert "grep" in tools
        assert "ripgrep" in tools
        assert "trufflehog" in tools

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_secret_scanner_subagent_review_returns_review_output(self, mock_runner_class):
        """Verify review() method returns ReviewOutput."""
        agent = SecretScannerSubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "secret_scanner",\n  "summary": "No secrets found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No secrets-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_secret_scanner_subagent_fsm_executes_full_cycle(self, mock_runner_class):
        """Verify FSM executes through INTAKE -> PLAN -> ACT -> SYNTHESIZE -> DONE cycle."""
        agent = SecretScannerSubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "secret_scanner",\n  "summary": "No secrets found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No secrets-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)


class TestDependencyAuditSubagent:
    """Test DependencyAuditSubagent FSM initialization and execution."""

    def test_dependency_audit_subagent_inherits_from_base_subagent(self):
        """Verify DependencyAuditSubagent inherits from BaseSubagent."""
        agent = DependencyAuditSubagent()
        assert isinstance(agent, BaseSubagent)

    def test_dependency_audit_subagent_has_fsm_attribute(self):
        """Verify DependencyAuditSubagent has _fsm attribute (now None)."""
        agent = DependencyAuditSubagent()
        assert hasattr(agent, "_fsm")
        assert agent._fsm is None

    def test_dependency_audit_subagent_implements_get_agent_name(self):
        """Verify get_agent_name() method exists and returns correct value."""
        agent = DependencyAuditSubagent()
        assert hasattr(agent, "get_agent_name")
        assert agent.get_agent_name() == "dependency_audit"

    def test_dependency_audit_subagent_implements_get_system_prompt(self):
        """Verify get_system_prompt() method exists and returns non-empty string."""
        agent = DependencyAuditSubagent()
        assert hasattr(agent, "get_system_prompt")
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Dependency Security Audit Subagent" in prompt

    def test_dependency_audit_subagent_implements_get_relevant_file_patterns(self):
        """Verify get_relevant_file_patterns() method exists and returns correct patterns."""
        agent = DependencyAuditSubagent()
        assert hasattr(agent, "get_relevant_file_patterns")
        patterns = agent.get_relevant_file_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        # Verify dependency-relevant patterns
        assert "**/requirements*.txt" in patterns
        assert "**/pyproject.toml" in patterns
        assert "**/package.json" in patterns

    def test_dependency_audit_subagent_implements_get_allowed_tools(self):
        """Verify get_allowed_tools() method exists and returns security tools."""
        agent = DependencyAuditSubagent()
        assert hasattr(agent, "get_allowed_tools")
        tools = agent.get_allowed_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Verify security tools
        assert "grep" in tools
        assert "ripgrep" in tools
        assert "pip-audit" in tools

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_dependency_audit_subagent_review_returns_review_output(self, mock_runner_class):
        """Verify review() method returns ReviewOutput."""
        agent = DependencyAuditSubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "dependency_audit",\n  "summary": "No dependency issues found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No dependency files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)

    @patch("iron_rook.review.subagents.security_subagents.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_auth_security_subagent_fsm_executes_full_cycle(self, mock_runner_class):
        """Verify FSM executes through INTAKE -> PLAN -> ACT -> SYNTHESIZE -> DONE cycle."""
        agent = AuthSecuritySubagent()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "agent": "auth_security",\n  "summary": "No auth security issues found",\n  "severity": "low",\n  "scope": {\n    "relevant_files": [],\n    "ignored_files": [],\n    "reasoning": "No auth-relevant files changed"\n  },\n  "findings": [],\n  "merge_gate": {\n    "decision": "approve",\n    "must_fix": [],\n    "should_fix": [],\n    "notes_for_coding_agent": []\n  }\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await agent.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)
