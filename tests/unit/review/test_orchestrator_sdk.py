"""Tests for migrated PRReviewOrchestrator using dawn-kestrel SDK.

Tests verify that the orchestrator correctly:
- Integrates with OpenCodeAsyncClient
- Executes agents in parallel
- Aggregates results correctly
- Handles errors gracefully
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

from iron_rook.review.orchestrator import PRReviewOrchestrator
from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    Scope,
    MergeGate,
    Finding,
    ReviewInputs,
)
from iron_rook.review.sdk_adapter import (
    create_reviewer_agent_from_base,
    review_context_to_user_message,
    agent_result_to_review_output,
    create_error_review_output,
)


class MockReviewerAgent(BaseReviewerAgent):
    """Mock reviewer agent for testing."""

    def __init__(self, name: str = "mock_reviewer"):
        super().__init__()
        self._name = name

    def get_agent_name(self) -> str:
        return self._name

    def get_system_prompt(self) -> str:
        return f"You are a {self._name} reviewer."

    def get_relevant_file_patterns(self) -> list[str]:
        return ["*.py", "**/*.py"]

    def get_allowed_tools(self) -> list[str]:
        return ["grep", "read"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        return ReviewOutput(
            agent=self._name,
            summary=f"Mock review by {self._name}",
            severity="low",
            scope=Scope(
                relevant_files=context.changed_files,
                ignored_files=[],
                reasoning="Mock review reasoning",
            ),
            findings=[],
            checks=[],
            skips=[],
            merge_gate=MergeGate(
                decision="approve",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=[],
            ),
        )


class TestSDKAdapter:
    """Test SDK adapter functions."""

    def test_create_reviewer_agent_from_base(self):
        """Verify BaseReviewerAgent can be converted to Agent dataclass."""
        agent = MockReviewerAgent("test_agent")
        sdk_agent = create_reviewer_agent_from_base(agent)

        assert sdk_agent.name == "test_agent"
        assert sdk_agent.mode == "subagent"
        assert len(sdk_agent.permission) > 0
        assert any(p["permission"] == "read" for p in sdk_agent.permission)

    def test_review_context_to_user_message(self):
        """Verify ReviewContext can be converted to user message."""
        context = ReviewContext(
            changed_files=["src/file1.py", "src/file2.py"],
            diff="diff content",
            repo_root="/test/repo",
            base_ref="main",
            head_ref="feature",
            pr_title="Test PR",
            pr_description="Test description",
        )

        system_prompt = "Test system prompt"
        user_message = review_context_to_user_message(context, system_prompt)

        assert system_prompt in user_message
        assert "src/file1.py" in user_message
        assert "src/file2.py" in user_message
        assert "diff content" in user_message
        assert "main" in user_message
        assert "feature" in user_message
        assert "Test PR" in user_message
        assert "Test description" in user_message

    def test_agent_result_to_review_output(self):
        """Verify AgentResult can be converted to ReviewOutput."""
        agent_name = "test_agent"
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        mock_agent_result = Mock()
        mock_agent_result.response = """{
            "agent": "test_agent",
            "summary": "Test review",
            "severity": "low",
            "scope": {
                "relevant_files": ["src/test.py"],
                "ignored_files": [],
                "reasoning": "Test reasoning"
            },
            "findings": [],
            "checks": [],
            "skips": [],
            "merge_gate": {
                "decision": "approve",
                "must_fix": [],
                "should_fix": [],
                "notes_for_coding_agent": []
            }
        }"""

        output = agent_result_to_review_output(agent_name, mock_agent_result, context)

        assert output.agent == "test_agent"
        assert output.summary == "Test review"
        assert output.severity == "low"
        assert len(output.findings) == 0

    def test_create_error_review_output(self):
        """Verify error ReviewOutput is created correctly."""
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        output = create_error_review_output("test_agent", "Test error", context)

        assert output.agent == "test_agent"
        assert output.severity == "blocking"
        assert "Test error" in output.summary
        assert output.merge_gate.decision == "block"


class TestPRReviewOrchestratorWithSDK:
    """Test PRReviewOrchestrator with SDK integration."""

    @pytest.fixture
    def mock_sdk_client(self):
        """Create mock SDK client."""
        client = AsyncMock()
        client.register_agent = AsyncMock()
        client.create_session = AsyncMock()
        client.execute_agent = AsyncMock()
        return client

    @pytest.fixture
    def sample_inputs(self):
        """Create sample review inputs."""
        return ReviewInputs(
            repo_root="/test/repo",
            base_ref="main",
            head_ref="feature",
            pr_title="Test PR",
            pr_description="Test description",
        )

    def test_orchestrator_initialization_with_sdk_client(self, mock_sdk_client):
        """Verify orchestrator can be initialized with SDK client."""
        subagents = [MockReviewerAgent("agent1"), MockReviewerAgent("agent2")]
        orchestrator = PRReviewOrchestrator(
            subagents=subagents,
            sdk_client=mock_sdk_client,
            project_dir=Path("/test"),
        )

        assert len(orchestrator.subagents) == 2
        assert orchestrator.sdk_client == mock_sdk_client
        assert orchestrator.project_dir == Path("/test")

    def test_orchestrator_initialization_without_sdk_client(self):
        """Verify orchestrator can be initialized without SDK client (creates own)."""
        subagents = [MockReviewerAgent("agent1")]
        orchestrator = PRReviewOrchestrator(subagents=subagents)

        assert len(orchestrator.subagents) == 1
        assert orchestrator.sdk_client is None
        assert orchestrator.project_dir == Path.cwd()

    @pytest.mark.asyncio
    async def test_parallel_execution_with_sdk(self, mock_sdk_client, sample_inputs, tmp_path):
        """Verify agents are executed in parallel using SDK."""
        subagents = [
            MockReviewerAgent("agent1"),
            MockReviewerAgent("agent2"),
            MockReviewerAgent("agent3"),
        ]

        # Mock session creation
        mock_session = Mock()
        mock_session.id = "test_session_id"
        mock_sdk_client.create_session.return_value = Mock(
            is_ok=lambda: True, unwrap=lambda: mock_session
        )

        # Mock agent execution - return JSON that can be parsed as ReviewOutput
        mock_sdk_client.register_agent.return_value = Mock(is_ok=lambda: True)
        mock_sdk_client.execute_agent.return_value = Mock(
            is_ok=lambda: True,
            unwrap=lambda: Mock(
                response="""{
                    "agent": "agent1",
                    "summary": "Test review",
                    "severity": "low",
                    "scope": {
                        "relevant_files": ["src/test.py"],
                        "ignored_files": [],
                        "reasoning": "Test"
                    },
                    "findings": [],
                    "checks": [],
                    "skips": [],
                    "merge_gate": {
                        "decision": "approve",
                        "must_fix": [],
                        "should_fix": [],
                        "notes_for_coding_agent": []
                    }
                }"""
            ),
        )

        orchestrator = PRReviewOrchestrator(
            subagents=subagents,
            sdk_client=mock_sdk_client,
            project_dir=tmp_path,
        )

        with (
            patch("iron_rook.review.orchestrator.get_changed_files") as mock_get_files,
            patch("iron_rook.review.orchestrator.get_diff") as mock_get_diff,
        ):
            mock_get_files.return_value = ["src/test.py"]
            mock_get_diff.return_value = "test diff"

            results = await orchestrator.run_subagents_parallel(sample_inputs)

            assert len(results) == 3
            assert all(r is not None for r in results)
            assert mock_sdk_client.register_agent.call_count == 3
            assert mock_sdk_client.create_session.call_count == 3
            assert mock_sdk_client.execute_agent.call_count == 3

    @pytest.mark.asyncio
    async def test_result_aggregation_unchanged(self):
        """Verify result aggregation logic is unchanged."""
        subagents = [MockReviewerAgent("agent1"), MockReviewerAgent("agent2")]

        # Create mock results
        result1 = ReviewOutput(
            agent="agent1",
            summary="Review 1",
            severity="low",
            scope=Scope(
                relevant_files=["src/file1.py"],
                ignored_files=[],
                reasoning="Reasoning 1",
            ),
            findings=[
                Finding(
                    title="Finding 1",
                    severity="warning",
                    owner="team1",
                    estimate="1h",
                    evidence="Evidence 1",
                    risk="Low",
                    recommendation="Fix 1",
                ),
            ],
            checks=[],
            skips=[],
            merge_gate=MergeGate(
                decision="approve",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=[],
            ),
        )

        result2 = ReviewOutput(
            agent="agent2",
            summary="Review 2",
            severity="critical",
            scope=Scope(
                relevant_files=["src/file2.py"],
                ignored_files=[],
                reasoning="Reasoning 2",
            ),
            findings=[
                Finding(
                    title="Finding 2",
                    severity="critical",
                    owner="team2",
                    estimate="2h",
                    evidence="Evidence 2",
                    risk="High",
                    recommendation="Fix 2",
                ),
            ],
            checks=[],
            skips=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=["Fix 2"],
                should_fix=[],
                notes_for_coding_agent=[],
            ),
        )

        orchestrator = PRReviewOrchestrator(subagents=subagents)

        # Test deduplication
        all_findings = [result1.findings[0], result2.findings[0], result1.findings[0]]
        deduped = orchestrator.dedupe_findings(all_findings)

        assert len(deduped) == 2  # Should dedupe duplicate finding

        # Test merge decision
        merge_decision = orchestrator.compute_merge_decision([result1, result2])
        assert merge_decision.decision == "needs_changes"  # Highest severity wins

    @pytest.mark.asyncio
    async def test_error_handling_during_execution(self, mock_sdk_client, sample_inputs):
        """Verify errors during agent execution are handled gracefully."""
        subagents = [MockReviewerAgent("agent1")]

        # Mock agent execution to return error
        mock_sdk_client.register_agent.return_value = Mock(is_ok=lambda: True)
        mock_sdk_client.create_session.return_value = Mock(
            is_ok=lambda: True, unwrap=lambda: Mock(id="test_session")
        )
        mock_sdk_client.execute_agent.return_value = Mock(
            is_ok=lambda: False, error="Test execution error"
        )

        orchestrator = PRReviewOrchestrator(
            subagents=subagents,
            sdk_client=mock_sdk_client,
        )

        with (
            patch("iron_rook.review.orchestrator.get_changed_files") as mock_get_files,
            patch("iron_rook.review.orchestrator.get_diff") as mock_get_diff,
        ):
            mock_get_files.return_value = ["src/test.py"]
            mock_get_diff.return_value = "test diff"

            results = await orchestrator.run_subagents_parallel(sample_inputs)

            assert len(results) == 1
            result = results[0]
            assert result.severity == "blocking"
            assert "execution failed" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_full_review_workflow(self, mock_sdk_client, sample_inputs, tmp_path):
        """Verify full review workflow with SDK integration."""
        subagents = [MockReviewerAgent("agent1"), MockReviewerAgent("agent2")]

        # Mock SDK responses
        mock_session = Mock()
        mock_session.id = "session_id"
        mock_sdk_client.create_session.return_value = Mock(
            is_ok=lambda: True, unwrap=lambda: mock_session
        )
        mock_sdk_client.register_agent.return_value = Mock(is_ok=lambda: True)
        mock_sdk_client.execute_agent.return_value = Mock(
            is_ok=lambda: True,
            unwrap=lambda: Mock(
                response="""{
                    "agent": "agent1",
                    "summary": "Test",
                    "severity": "low",
                    "scope": {"relevant_files": [], "ignored_files": [], "reasoning": "Test"},
                    "findings": [],
                    "checks": [],
                    "skips": [],
                    "merge_gate": {
                        "decision": "approve",
                        "must_fix": [],
                        "should_fix": [],
                        "notes_for_coding_agent": []
                    }
                }"""
            ),
        )

        orchestrator = PRReviewOrchestrator(
            subagents=subagents,
            sdk_client=mock_sdk_client,
            project_dir=tmp_path,
        )

        with (
            patch("iron_rook.review.orchestrator.get_changed_files") as mock_get_files,
            patch("iron_rook.review.orchestrator.get_diff") as mock_get_diff,
        ):
            mock_get_files.return_value = ["src/test.py"]
            mock_get_diff.return_value = "test diff"

            output = await orchestrator.run_review(sample_inputs)

            assert output.merge_decision is not None
            assert output.total_findings >= 0
            assert len(output.subagent_results) == 2
            assert output.tool_plan is not None
