"""Tests for FSM Security Orchestrator flow and phase transitions."""

import pytest
from unittest.mock import MagicMock
from iron_rook.review.contracts import (
    PullRequestChangeList,
)
from iron_rook.review.fsm_security_orchestrator import SecurityReviewOrchestrator
from typing import Any, Dict, List


class MockAgentResponse:
    """Mock response from agent execution."""

    content = '{"phase": "intake", "data": {}, "next_phase_request": "plan_todos"}'


class MockLLMResponse:
    """Mock LLM response from direct LLM calls."""

    def __init__(self: "MockLLMResponse", text: str) -> None:
        self.text = text


class MockAgentRuntime:
    """Mock dawn-kestrel AgentRuntime for testing."""

    def __init__(self: "MockAgentRuntime") -> None:
        self.sessions: Dict[str, object] = {}
        self.execute_calls: List[Dict[str, object]] = []

    async def get_session(self, session_id: str) -> object:
        """Get or create a mock session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = MagicMock()
        return self.sessions[session_id]

    async def release_session(self, session_id: str) -> None:
        """Release a mock session."""
        if session_id in self.sessions:
            self.sessions[session_id] = None

    async def execute_agent(
        self, agent_name: str, session_id: str, user_message: str, **kwargs: object
    ) -> object:
        """Mock execute_agent - store calls for validation."""
        self.execute_calls.append(
            {
                "agent_name": agent_name,
                "session_id": session_id,
                "user_message": user_message,
            }
        )

        # Return appropriate response based on call count to simulate FSM phases
        call_count = len(self.execute_calls)
        responses = [
            '{"phase": "intake", "data": {"findings": []}, "next_phase_request": "plan_todos"}',
            '{"phase": "plan_todos", "data": {"todos": []}, "next_phase_request": "delegate"}',
            '{"phase": "delegate", "data": {"delegated": []}, "next_phase_request": "collect"}',
            '{"phase": "collect", "data": {"collected": []}, "next_phase_request": "consolidate"}',
            '{"phase": "consolidate", "data": {}, "next_phase_request": "evaluate"}',
            '{"phase": "evaluate", "data": {"overall": "low"}, "next_phase_request": "done"}',
        ]
        response_content = responses[min(call_count - 1, len(responses) - 1)]
        return MagicMock(content=response_content)


@pytest.fixture
def mock_agent_runtime() -> MockAgentRuntime:
    """Fixture providing mocked AgentRuntime."""
    return MockAgentRuntime()


@pytest.fixture
def mock_session_manager() -> Any:  # type: ignore[no-any]
    """Fixture providing mocked SessionManager."""

    # Make release_session awaitable
    async def mock_release_session(session_id: str) -> None:
        """Mock async release_session."""
        pass

    async def mock_get_session(session_id: str) -> object:
        """Mock async get_session."""
        session_mock = MagicMock(
            id=session_id,
            list_messages=MagicMock(return_value=[]),
            add_message=MagicMock(),
            add_part=MagicMock(),
            release_session=mock_release_session,
        )
        return session_mock

    manager = MagicMock()
    manager.get_session = mock_get_session
    return manager  # type: ignore[return-type]


@pytest.fixture
def sample_pr_input() -> PullRequestChangeList:
    """Fixture providing sample PR input for testing."""
    from iron_rook.review.contracts import PullRequestMetadata, PRChange, PRMetadata, PRConstraints

    return PullRequestChangeList(
        pr=PullRequestMetadata(
            id="1234",
            title="Test PR",
            base_branch="main",
            head_branch="feature/test",
            author="alice",
        ),
        changes=[
            PRChange(
                path="src/auth/jwt.py",
                change_type="modified",
                diff_summary="JWT verification updates",
                risk_hints=["auth", "crypto"],
            )
        ],
        metadata=PRMetadata(
            repo="testrepo",
            commit_range="abc567..def890",
            created_at="2026-02-09T18:00:00Z",
        ),
        constraints=PRConstraints(
            tool_budget=25,
            max_subagents=5,
            max_iterations=4,
        ),
    )


class TestSecurityReviewOrchestrator:
    """Test SecurityReviewOrchestrator FSM lifecycle."""

    @pytest.mark.asyncio
    async def test_run_full_review_success(
        self: "TestSecurityReviewOrchestrator",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test successful full review run through all phases."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,  # type: ignore[arg-type]
            prompt_path=None,
        )

        result = await orchestrator.run_review(sample_pr_input)

        assert result.fsm.phase == "done"
        assert result.fsm.stop_reason is None
        assert result.fsm.iterations == 2
        assert result.fsm.tool_calls_used == 0
        assert result.fsm.subagents_used == 3
        assert len(result.findings["medium"]) == 1
        assert result.risk_assessment.overall == "medium"
        assert result.confidence > 0.7

    @pytest.mark.asyncio
    async def test_budget_exceeded_during_review(
        self: "TestSecurityReviewOrchestrator",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test budget enforcement stops execution."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from iron_rook.review.fsm_security_orchestrator import BudgetExceededError

        with pytest.raises(BudgetExceededError) as exc_info:
            await orchestrator.run_review(sample_pr_input)

        assert "Maximum iterations" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_phase_transition_validation(
        self: "TestSecurityReviewOrchestrator",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test invalid phase transitions are caught."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from iron_rook.review.fsm_security_orchestrator import FSMPhaseError

        with pytest.raises(FSMPhaseError) as exc_info:
            await orchestrator.run_review(sample_pr_input)

        assert "Invalid transition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_session_management(
        self: "TestSecurityReviewOrchestrator",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test sessions are properly created and released."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        await orchestrator.run_review(sample_pr_input)

        session_id = mock_agent_runtime.execute_calls[0]["session_id"]
        mock_session_manager.get_session.assert_called_once_with(session_id)
        mock_session_manager.get_session.return_value.release_session.assert_called_once_with(
            session_id
        )

    @pytest.mark.asyncio
    async def test_agent_runtime_integration(
        self: "TestSecurityReviewOrchestrator",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test agent_runtime.execute_agent is called correctly."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=mock_agent_runtime,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        await orchestrator.run_review(sample_pr_input)

        execute_calls = mock_agent_runtime.execute_calls

        assert len(execute_calls) >= 4

        expected_phases = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]

        for i, call in enumerate(execute_calls):
            assert call["agent_name"] == "security_review_fsm"
            session_id = call["session_id"]

            # Verify user message contains expected fields (JSON format, not "phase: N" format)
            assert '"pr"' in str(call["user_message"])
            assert '"changes"' in str(call["user_message"])

            # Later phases include additional context fields
            if i >= 1:  # After intake, includes intake_output
                assert '"intake_output"' in str(call["user_message"])

        mock_session_manager.get_session.assert_called()
        mock_session_manager.get_session.return_value.list_messages.assert_called_once()
        mock_session_manager.get_session.return_value.release_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_subagent_dispatch(
        self: "TestSecurityReviewOrchestrator",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test subagent is dispatched and results collected."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=mock_agent_runtime,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        result = await orchestrator.run_review(sample_pr_input)

        assert result.fsm.subagents_used == 3

        subagent_sessions = [
            call
            for call in mock_agent_runtime.execute_calls
            if str(call["agent_name"]) != "security_review_fsm"
        ]

        assert len(subagent_sessions) == 3

        for call in subagent_sessions:
            assert str(call["agent_name"]) in [
                "auth_security",
                "injection_security",
                "crypto_security",
            ]

        mock_session_manager.get_session.return_value.release_session.assert_called()
        mock_session_manager.get_session.return_value.release_session.assert_called_once_with(
            "subagent_SEC-001"
        )
        mock_session_manager.get_session.return_value.release_session.assert_called_once_with(
            "subagent_SEC-002"
        )
        mock_session_manager.get_session.return_value.release_session.assert_called_once_with(
            "subagent_SEC-003"
        )


class TestFSMReliabilityRedBaseline:
    """RED baseline tests for FSM reliability regressions."""

    @pytest.mark.asyncio
    async def test_invalid_transition_request_fails_deterministically(
        self: "TestFSMReliabilityRedBaseline",
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that invalid phase transitions fail deterministically with explicit error.

        RED: This test expects the orchestrator to validate transitions against FSM_TRANSITIONS
        and raise FSMPhaseError for invalid transitions. Currently, the orchestrator does
        not validate transitions and may silently accept invalid transitions or fail with unclear errors.
        """
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from iron_rook.review.fsm_security_orchestrator import FSMPhaseError

        # Mock the direct LLM response with invalid transition
        import json
        import sys

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            """Mock that returns invalid transition from intake."""
            if args and len(args) > 1 and "messages" in str(args[1]):
                if "phase: 1" in str(args[1]):
                    # Return invalid transition from intake (should go to plan_todos, not evaluate)
                    from unittest.mock import MagicMock

                    response = MagicMock()
                    response.text = (
                        '{"phase": "intake", "data": {}, "next_phase_request": "evaluate"}'
                    )
                    return response
            # Default response for other phases
            from unittest.mock import MagicMock

            response = MagicMock()
            response.text = '{"phase": "done", "data": {}}'
            return response

        # Monkey-patch the LLMClient
        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            # The orchestrator should reject invalid transition intake -> evaluate
            # Currently it does NOT validate, so this will NOT raise FSMPhaseError (RED state)
            result = await orchestrator.run_review(sample_pr_input)

            # RED: If we reach here without raising FSMPhaseError, validation is not enforced
            # The orchestrator should have rejected the invalid transition
            assert result.fsm.stop_reason is not None
            assert "failed" in result.fsm.stop_reason.lower() or result.fsm.phase != "evaluate"
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_missing_required_phase_fields_do_not_silently_continue(
        self: "TestFSMReliabilityRedBaseline",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that missing required phase fields fail explicitly instead of silent continuation.

        RED: This test expects the orchestrator to validate required fields before phase
        transitions. Currently, missing fields may cause silent failures or partial reports
        without clear indication of what went wrong.
        """
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        # Mock a response missing required 'phase' field
        from unittest.mock import MagicMock

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            """Mock that returns output missing required phase field."""
            response = MagicMock()
            response.text = '{"data": {}, "next_phase_request": "plan_todos"}'
            return response

        # Monkey-patch the LLMClient
        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            # Should fail explicitly with validation error or partial report with explicit reason
            result = await orchestrator.run_review(sample_pr_input)

            # Either validation failed (partial report) or explicit error raised
            # The test expects explicit stop reason, not silent continuation
            assert result.fsm.stop_reason is not None
            assert (
                "validation" in result.fsm.stop_reason.lower()
                or "failed" in result.fsm.stop_reason.lower()
            )
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_malformed_json_returns_partial_report_or_explicit_error(
        self: "TestFSMReliabilityRedBaseline",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that malformed JSON returns partial report or explicit error path.

        RED: This test expects the orchestrator to handle JSON parsing errors gracefully
        and return a partial report with explicit error reason instead of crashing or
        returning None.
        """
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        # Mock a response with malformed JSON
        from unittest.mock import MagicMock

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            """Mock that returns malformed JSON."""
            response = MagicMock()
            response.text = '{"phase": "intake", "data": invalid json here}'
            return response

        # Monkey-patch the LLMClient
        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            # Should return partial report with explicit error reason
            result = await orchestrator.run_review(sample_pr_input)

            assert result is not None
            assert result.fsm.stop_reason is not None
            assert (
                "failed" in result.fsm.stop_reason.lower()
                or "intake" in result.fsm.stop_reason.lower()
            )
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_non_continuation_paths_terminate_with_explicit_stop_reason(
        self: "TestFSMReliabilityRedBaseline",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that non-continuation/stall paths terminate with explicit stop reason.

        RED: This test expects the orchestrator to handle stop gates (stopped_budget,
        stopped_human) and other non-continuation paths by terminating with explicit
        stop_reason instead of hanging or ambiguous state.
        """
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        # Mock responses that trigger a stop gate
        from unittest.mock import MagicMock

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            """Mock that triggers a stop gate."""
            response = MagicMock()
            response.text = (
                '{"phase": "intake", "data": {}, "next_phase_request": "stopped_budget"}'
            )
            return response

        # Monkey-patch the LLMClient
        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            # Should return partial report with explicit stop reason
            result = await orchestrator.run_review(sample_pr_input)

            assert result is not None
            # RED: The orchestrator should transition to stopped_budget phase
            # Currently it may not properly handle stop gates
            assert result.fsm.stop_reason is not None
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_transition_validation_actually_enforces_fsm_transitions(
        self: "TestFSMReliabilityRedBaseline",
        mock_agent_runtime: MockAgentRuntime,
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that _validate_phase_transition actually enforces FSM_TRANSITIONS.

        RED: This test verifies that the transition validator exists and works correctly.
        The orchestrator may currently bypass this validation.
        """
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from iron_rook.review.fsm_security_orchestrator import FSMPhaseError

        # Test direct call to _validate_phase_transition with invalid transition
        # This should be called during phase transitions
        try:
            orchestrator._validate_phase_transition("intake", {"next_phase_request": "evaluate"})
            # If we reach here, validation is NOT enforced (RED state)
            pytest.fail("Expected FSMPhaseError for invalid transition intake -> evaluate")
        except FSMPhaseError as e:
            # This is the expected behavior - validation enforced
            assert "Invalid transition" in str(e)
            assert "evaluate" in str(e)


class TestPhasePromptLoading:
    """Test _load_phase_prompt() robustness and error handling."""

    @pytest.fixture
    def minimal_prompt_file(self, tmp_path: Any) -> str:
        """Create a minimal prompt file with known phase sections."""
        prompt_file = tmp_path / "minimal_prompt.md"
        content = """# Test Prompt

### INTAKE

This is intake phase content.

---

### PLAN_TODOS

This is plan_todos phase content.

---

"""
        prompt_file.write_text(content)
        return str(prompt_file)

    @pytest.fixture
    def missing_phase_prompt_file(self, tmp_path: Any) -> str:
        """Create a prompt file missing the PLAN_TODOS phase."""
        prompt_file = tmp_path / "missing_phase_prompt.md"
        content = """# Test Prompt

### INTAKE

This is intake phase content.

---

### DELEGATE

This is delegate phase content.

---

"""
        prompt_file.write_text(content)
        return str(prompt_file)

    def test_load_phase_prompt_valid_phase(
        self,
        mock_session_manager: object,
        minimal_prompt_file: str,
    ) -> None:
        """Test loading a valid phase prompt returns expected content."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=MockAgentRuntime(),
            session_manager=mock_session_manager,
            prompt_path=minimal_prompt_file,
        )

        intake_prompt = orchestrator._load_phase_prompt("intake")
        assert "### INTAKE" in intake_prompt
        assert "This is intake phase content." in intake_prompt

        plan_todos_prompt = orchestrator._load_phase_prompt("plan_todos")
        assert "### PLAN_TODOS" in plan_todos_prompt
        assert "This is plan_todos phase content." in plan_todos_prompt

    def test_load_phase_prompt_missing_phase_raises_error(
        self,
        mock_session_manager: object,
        missing_phase_prompt_file: str,
    ) -> None:
        """Test loading a missing phase raises MissingPhasePromptError."""
        from iron_rook.review.fsm_security_orchestrator import MissingPhasePromptError

        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=MockAgentRuntime(),
            session_manager=mock_session_manager,
            prompt_path=missing_phase_prompt_file,
        )

        with pytest.raises(MissingPhasePromptError) as exc_info:
            orchestrator._load_phase_prompt("plan_todos")

        error_message = str(exc_info.value)
        assert "PLAN_TODOS" in error_message
        assert "not found" in error_message.lower()
        assert "### PLAN_TODOS" in error_message

    def test_load_phase_prompt_all_phases_from_security_review_agent(
        self,
        mock_session_manager: object,
    ) -> None:
        """Test all 6 phase sections can be loaded from security_review_agent.md."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,  # type: ignore
            prompt_path=None,
        )

        phases = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]

        for phase in phases:
            prompt = orchestrator._load_phase_prompt(phase)
            assert prompt, f"Phase {phase} should return non-empty prompt"
            assert f"### {phase.upper()}" in prompt, f"Phase {phase} should contain header"


class TestJSONEnvelopeCompliance:
    """Test PhaseOutput schema enforces JSON envelope structure."""

    def test_phase_output_extra_fields_forbidden(self) -> None:
        """Test PhaseOutput rejects extra fields at top level."""
        from iron_rook.review.contracts import PhaseOutput
        import pydantic as pd

        # Extra field at top level should fail with extra="forbid"
        invalid_dict = {
            "phase": "intake",
            "data": {},
            "next_phase_request": "plan_todos",
            "extra_field": "not_allowed",
        }
        with pytest.raises(pd.ValidationError) as exc_info:
            PhaseOutput(**invalid_dict)
        assert "extra" in str(exc_info.value).lower()

    def test_phase_output_valid_intake_output(self) -> None:
        """Test valid INTAKE phase output passes validation."""
        from iron_rook.review.contracts import PhaseOutput

        valid_output = PhaseOutput(
            phase="intake",
            data={
                "summary": "Summary of changes",
                "risk_hypotheses": ["hypothesis 1", "hypothesis 2"],
                "questions": ["question 1"],
            },
            next_phase_request="plan_todos",
        )

        assert valid_output.phase == "intake"
        assert valid_output.next_phase_request == "plan_todos"
        assert valid_output.data["summary"] == "Summary of changes"

    def test_phase_output_valid_evaluate_output(self) -> None:
        """Test valid EVALUATE phase output passes validation."""
        from iron_rook.review.contracts import PhaseOutput

        valid_output = PhaseOutput(
            phase="evaluate",
            data={
                "findings": {
                    "critical": [],
                    "high": [],
                    "medium": [],
                    "low": [],
                },
                "risk_assessment": {
                    "overall": "low",
                    "rationale": "No issues found",
                    "areas_touched": [],
                },
                "confidence": 0.9,
            },
            next_phase_request="done",
        )

        assert valid_output.phase == "evaluate"
        assert valid_output.next_phase_request == "done"
        assert valid_output.data["confidence"] == 0.9


class TestRetryPolicy:
    """Test retry policy - bounded retry for transient, fail-fast for structural."""

    @pytest.mark.asyncio
    async def test_structural_errors_fail_fast_without_retry(
        self: "TestRetryPolicy",
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that structural errors fail immediately without retry."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from iron_rook.review.fsm_security_orchestrator import StructuralError

        # Mock a response that triggers structural error (missing required field)
        from unittest.mock import MagicMock

        call_count = {"count": 0}

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            call_count["count"] += 1
            response = MagicMock()
            # Return output missing 'phase' field (structural error)
            response.text = '{"data": {}, "next_phase_request": "plan_todos"}'
            return response

        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            result = await orchestrator.run_review(sample_pr_input)
            assert result.fsm.phase == "intake"
            assert "failed" in result.fsm.stop_reason.lower()
            # Structural error should fail-fast - only 1 attempt, no retries
            assert call_count["count"] == 1
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_transient_errors_retry_up_to_3_then_stop(
        self: "TestRetryPolicy",
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that transient errors retry up to 3 times, then stop."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        # Mock a response that triggers transient error (runtime/network error)
        from unittest.mock import MagicMock

        call_count = {"count": 0}
        fail_count = 3  # Fail first 3 attempts

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            call_count["count"] += 1
            response = MagicMock()

            if call_count["count"] <= fail_count:
                # Simulate transient network error (ConnectionError is transient)
                raise ConnectionError("Network timeout")
            else:
                # Return valid response after failures
                response.text = '{"phase": "intake", "data": {}, "next_phase_request": "done"}'
                return response

        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            result = await orchestrator.run_review(sample_pr_input)
            # Should stop with stopped_retry_exhausted after max retries
            assert result.fsm.phase == "stopped_retry_exhausted"
            assert (
                "transient" in result.fsm.stop_reason.lower()
                or "retry" in result.fsm.stop_reason.lower()
            )
            # Transient error should retry exactly 4 times (1 initial + 3 retries)
            assert call_count["count"] == 4
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_bounded_retry_no_infinite_continuation(
        self: "TestRetryPolicy",
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that retry is bounded and never continues infinitely."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from unittest.mock import MagicMock

        call_count = {"count": 0}

        async def mock_llm_complete(*args: object, **kwargs: object) -> object:
            call_count["count"] += 1
            # Always fail to test bounded retry prevents infinite loops
            raise TimeoutError("Persistent timeout")

        import dawn_kestrel.llm

        original_complete = dawn_kestrel.llm.LLMClient.complete
        dawn_kestrel.llm.LLMClient.complete = mock_llm_complete

        try:
            result = await orchestrator.run_review(sample_pr_input)
            # Should stop with stopped_retry_exhausted
            assert result.fsm.phase == "stopped_retry_exhausted"
            # Bounded retry: max 4 attempts (1 initial + 3 retries)
            assert call_count["count"] == 4
        finally:
            dawn_kestrel.llm.LLMClient.complete = original_complete

    @pytest.mark.asyncio
    async def test_classify_error_distinguishes_structural_from_transient(
        self: "TestRetryPolicy",
        mock_session_manager: object,
        sample_pr_input: PullRequestChangeList,
    ) -> None:
        """Test that _classify_error correctly distinguishes error types."""
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=None,
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        from iron_rook.review.fsm_security_orchestrator import (
            StructuralError,
            TransientError,
            FSMPhaseError,
        )
        import json

        # Test structural error classification
        structural_error = FSMPhaseError("Invalid transition")
        classified = orchestrator._classify_error(structural_error)
        assert isinstance(classified, StructuralError)
        assert "FSMPhaseError" in str(classified)

        # Test transient error classification
        transient_error = ConnectionError("Network timeout")
        classified = orchestrator._classify_error(transient_error)
        assert isinstance(classified, TransientError)
        assert "ConnectionError" in str(classified)

        # Test ValidationError is structural
        try:
            from iron_rook.review.contracts import PhaseOutput

            PhaseOutput.model_validate({"invalid": "data"})
        except Exception as e:
            classified = orchestrator._classify_error(e)
            assert isinstance(classified, StructuralError)

        # Test JSONDecodeError is structural
        json_error = json.JSONDecodeError("Invalid JSON", "", 0)
        classified = orchestrator._classify_error(json_error)
        assert isinstance(classified, StructuralError)
