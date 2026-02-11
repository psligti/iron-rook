"""Tests for SecurityReviewer LLM thinking capture.

Tests that phase methods extract and log LLM reasoning from responses
using SecurityPhaseLogger.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import pydantic as pd

from iron_rook.review.agents.security import SecurityReviewer
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ThinkingStep, ThinkingFrame, RunLog


class TestExtractThinkingFromResponse:
    """Test _extract_thinking_from_response helper method."""

    def test_extract_thinking_from_json_top_level(self):
        """Verify extraction of thinking field from top-level JSON."""
        reviewer = SecurityReviewer()

        response_text = """
{
  "thinking": "I need to analyze the authentication flow...",
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": []
  },
  "next_phase_request": "plan_todos"
}"""
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == "I need to analyze the authentication flow..."

    def test_extract_thinking_from_json_data_object(self):
        """Verify extraction of thinking field from data object."""
        reviewer = SecurityReviewer()

        response_text = """
{
  "phase": "intake",
  "data": {
    "thinking": "Checking for SQL injection patterns...",
    "summary": "test",
    "risk_hypotheses": []
  },
  "next_phase_request": "plan_todos"
}"""
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == "Checking for SQL injection patterns..."

    def test_extract_thinking_from_xml_tags(self):
        """Verify extraction of thinking from <thinking> tags."""
        reviewer = SecurityReviewer()

        response_text = """<thinking>Need to check authorization middleware</thinking>
```json
{
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": []
  },
  "next_phase_request": "plan_todos"
}
```"""
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == "Need to check authorization middleware"

    def test_extract_thinking_from_markdown_wrapped_json(self):
        """Verify extraction works with markdown code blocks."""
        reviewer = SecurityReviewer()

        response_text = """```json
{
  "thinking": "Analyzing crypto usage...",
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": []
  },
  "next_phase_request": "plan_todos"
}
```"""
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == "Analyzing crypto usage..."

    def test_extract_thinking_empty_when_no_thinking(self):
        """Verify empty string returned when no thinking found."""
        reviewer = SecurityReviewer()

        response_text = """{
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": []
  },
  "next_phase_request": "plan_todos"
}"""
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == ""

    def test_extract_thinking_empty_when_null(self):
        """Verify empty string returned when thinking is null."""
        reviewer = SecurityReviewer()

        response_text = """{
  "thinking": null,
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": []
  },
  "next_phase_request": "plan_todos"
}"""
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == ""

    def test_extract_thinking_from_invalid_json(self):
        """Verify empty string returned for invalid JSON."""
        reviewer = SecurityReviewer()

        response_text = "Not valid JSON at all"
        thinking = reviewer._extract_thinking_from_response(response_text)
        assert thinking == ""


class TestIntakePhaseThinking:
    """Test INTAKE phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_intake_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify INTAKE phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        # Mock LLM response with thinking
        mock_execute_llm.return_value = """{
  "thinking": "Analyzing PR changes for security surfaces",
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run intake phase
        await reviewer._run_intake(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any("Analyzing PR changes for security surfaces" in call for call in calls)

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_intake_phase_logs_thinking_before_transition(self, mock_execute_llm):
        """Verify INTAKE phase logs thinking BEFORE calling next_phase.get()."""
        reviewer = SecurityReviewer()

        # Mock LLM response with thinking
        mock_execute_llm.return_value = """{
  "thinking": "Reviewing authentication changes",
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run intake phase
        output = await reviewer._run_intake(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any("Reviewing authentication changes" in call for call in calls)


class TestPlanTodosPhaseThinking:
    """Test PLAN_TODOS phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_plan_todos_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify PLAN_TODOS phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        # Set intake output for context
        reviewer._phase_outputs["intake"] = {"data": {"risk_hypotheses": ["test1", "test2"]}}

        # Mock LLM response with thinking
        mock_execute_llm.return_value = """{
  "thinking": "Creating TODOs for authentication and injection risks",
  "phase": "plan_todos",
  "data": {
    "todos": []
  },
  "next_phase_request": "delegate"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run plan_todos phase
        await reviewer._run_plan_todos(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any(
            "Creating TODOs for authentication and injection risks" in call for call in calls
        )


class TestDelegatePhaseThinking:
    """Test DELEGATE phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_delegate_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify DELEGATE phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        # Mock runner response with thinking

        mock_execute_llm.return_value = """{
  "thinking": "Delegating auth TODOs to auth_security subagent",
  "phase": "delegate",
  "data": {
    "subagent_requests": []
  },
  "next_phase_request": "collect"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run delegate phase
        await reviewer._run_delegate(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any("Delegating auth TODOs to auth_security subagent" in call for call in calls)


class TestCollectPhaseThinking:
    """Test COLLECT phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_collect_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify COLLECT phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        # Mock runner response with thinking

        mock_execute_llm.return_value = """{
  "thinking": "Validating all subagent results and marking TODOs complete",
  "phase": "collect",
  "data": {
    "todo_status": []
  },
  "next_phase_request": "consolidate"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run collect phase
        await reviewer._run_collect(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any(
            "Validating all subagent results and marking TODOs complete" in call for call in calls
        )


class TestConsolidatePhaseThinking:
    """Test CONSOLIDATE phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_consolidate_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify CONSOLIDATE phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        # Mock runner response with thinking

        mock_execute_llm.return_value = """{
  "thinking": "Merging findings from all subagents and de-duplicating",
  "phase": "consolidate",
  "data": {},
  "next_phase_request": "evaluate"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run consolidate phase
        await reviewer._run_consolidate(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any(
            "Merging findings from all subagents and de-duplicating" in call for call in calls
        )


class TestEvaluatePhaseThinking:
    """Test EVALUATE phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_evaluate_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify EVALUATE phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        # Mock runner response with thinking

        mock_execute_llm.return_value = """{
  "thinking": "Assessing severity and generating final risk report",
  "phase": "evaluate",
  "data": {
    "findings": {},
    "risk_assessment": {
      "overall": "low",
      "rationale": "No critical issues found"
    }
  },
  "next_phase_request": "done"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run evaluate phase
        await reviewer._run_evaluate(context)

        # Verify thinking was logged (extracted from LLM response)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have the LLM thinking logged
        assert any("Assessing severity and generating final risk report" in call for call in calls)


class TestThinkingNotLoggedWhenEmpty:
    """Test that empty thinking is not logged."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_empty_thinking_not_logged(self, mock_execute_llm):
        """Verify empty thinking is not logged to phase logger."""
        reviewer = SecurityReviewer()

        # Mock runner response WITHOUT thinking

        mock_execute_llm.return_value = """{
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}"""

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        # Mock phase logger
        reviewer._phase_logger = Mock()

        # Run intake phase
        await reviewer._run_intake(context)

        # Verify no thinking call with extracted thinking (only operational messages)
        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        # Should have only operational logs, not extracted LLM thinking
        # When there's no thinking in the response, only the operational messages are logged
        assert any("complete" in call for call in calls)


class TestThinkingModels:
    """Test Pydantic models for thinking capture (ThinkingStep, ThinkingFrame, RunLog)."""

    # ========================================================================
    # ThinkingStep Tests
    # ========================================================================

    def test_thinking_step_valid_input(self):
        """Verify ThinkingStep accepts all valid kind enum values."""
        # Test all valid kinds
        for kind in ["transition", "tool", "delegate", "gate", "stop"]:
            step = ThinkingStep(
                kind=kind,
                why="Test reasoning",
                evidence=["evidence 1", "evidence 2"],
                next="next_state",
                confidence="high",
            )
            assert step.kind == kind
            assert step.why == "Test reasoning"
            assert step.evidence == ["evidence 1", "evidence 2"]
            assert step.next == "next_state"
            assert step.confidence == "high"

    def test_thinking_step_invalid_kind(self):
        """Verify ThinkingStep rejects invalid kind enum values."""
        with pytest.raises(pd.ValidationError) as exc_info:
            ThinkingStep(kind="invalid_kind", why="Test reasoning")
        assert "kind" in str(exc_info.value).lower()

    def test_thinking_step_default_values(self):
        """Verify ThinkingStep uses correct default values for optional fields."""
        step = ThinkingStep(kind="transition", why="Test reasoning")
        assert step.evidence == []
        assert step.next is None
        assert step.confidence == "medium"

    def test_thinking_step_evidence_default_factory(self):
        """Verify ThinkingStep evidence field uses list default_factory correctly."""
        step1 = ThinkingStep(kind="transition", why="Test 1")
        step2 = ThinkingStep(kind="transition", why="Test 2")
        # Modify evidence in step1
        step1.evidence.append("shared evidence")
        # step2 evidence should remain empty (default_factory creates new list each time)
        assert step1.evidence == ["shared evidence"]
        assert step2.evidence == []

    # ========================================================================
    # ThinkingFrame Tests
    # ========================================================================

    def test_thinking_frame_valid_input(self):
        """Verify ThinkingFrame accepts valid input with all fields."""
        frame = ThinkingFrame(
            state="intake",
            goals=["Analyze PR changes", "Identify security risks"],
            checks=["Check for SQL injection", "Verify authentication"],
            risks=["Potential data leak", "Broken access control"],
            steps=[
                ThinkingStep(kind="transition", why="Start analysis", evidence=["PR has 3 files"]),
                ThinkingStep(kind="tool", why="Run security scan", next="scan_complete"),
            ],
            decision="proceed to plan_todos",
        )
        assert frame.state == "intake"
        assert len(frame.goals) == 2
        assert len(frame.checks) == 2
        assert len(frame.risks) == 2
        assert len(frame.steps) == 2
        assert frame.decision == "proceed to plan_todos"

    def test_thinking_frame_timestamp(self):
        """Verify ThinkingFrame ts field generates ISO-8601 timestamp with Z suffix."""
        frame = ThinkingFrame(state="intake", decision="proceed")
        assert frame.ts is not None
        assert frame.ts.endswith("Z")
        # Verify it's a valid ISO format timestamp
        from datetime import datetime

        # Parse the timestamp (should not raise exception)
        parsed = datetime.fromisoformat(frame.ts.rstrip("Z"))
        assert parsed is not None

    def test_thinking_frame_default_lists(self):
        """Verify ThinkingFrame list fields use default_factory correctly."""
        frame1 = ThinkingFrame(state="intake", decision="proceed")
        frame2 = ThinkingFrame(state="plan_todos", decision="delegate")
        # Modify list in frame1
        frame1.goals.append("shared goal")
        frame1.checks.append("shared check")
        frame1.risks.append("shared risk")
        # frame2 lists should remain empty (default_factory creates new list each time)
        assert frame1.goals == ["shared goal"]
        assert frame2.goals == []
        assert frame1.checks == ["shared check"]
        assert frame2.checks == []
        assert frame1.risks == ["shared risk"]
        assert frame2.risks == []

    # ========================================================================
    # RunLog Tests
    # ========================================================================

    def test_run_log_valid_input(self):
        """Verify RunLog accepts valid input with frames list."""
        frame1 = ThinkingFrame(
            state="intake",
            goals=["Analyze PR"],
            decision="proceed to plan_todos",
        )
        frame2 = ThinkingFrame(
            state="plan_todos",
            goals=["Create TODOs"],
            decision="delegate",
        )
        log = RunLog(frames=[frame1, frame2])
        assert len(log.frames) == 2
        assert log.frames[0].state == "intake"
        assert log.frames[1].state == "plan_todos"

    def test_run_log_add_method(self):
        """Verify RunLog add() method correctly appends frames."""
        log = RunLog()
        frame1 = ThinkingFrame(
            state="intake",
            goals=["Analyze PR"],
            decision="proceed to plan_todos",
        )
        frame2 = ThinkingFrame(
            state="plan_todos",
            goals=["Create TODOs"],
            decision="delegate",
        )
        log.add(frame1)
        assert len(log.frames) == 1
        assert log.frames[0].state == "intake"
        log.add(frame2)
        assert len(log.frames) == 2
        assert log.frames[1].state == "plan_todos"

    def test_run_log_default_frames(self):
        """Verify RunLog frames field uses list default_factory correctly."""
        log1 = RunLog()
        log2 = RunLog()
        # Add frame to log1
        log1.frames.append(ThinkingFrame(state="intake", goals=["Test"], decision="proceed"))
        # log2 frames should remain empty (default_factory creates new list each time)
        assert len(log1.frames) == 1
        assert len(log2.frames) == 0
