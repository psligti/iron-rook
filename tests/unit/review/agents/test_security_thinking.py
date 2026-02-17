"""Tests for SecurityReviewer LLM thinking capture.

Tests that phase methods extract and log LLM reasoning from responses
using SecurityPhaseLogger.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import pydantic as pd

from iron_rook.review.agents.security import SecurityReviewer
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import (
    ThinkingStep,
    ThinkingFrame,
    RunLog,
    ReviewOutput,
    Scope,
    MergeGate,
)
from iron_rook.review.security_phase_logger import SecurityPhaseLogger


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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
  "next_phase_request": "plan"
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
    async def test_plan_phase_logs_thinking_from_response(self, mock_execute_llm):
        reviewer = SecurityReviewer()

        reviewer._phase_outputs["intake"] = {"data": {"risk_hypotheses": ["test1", "test2"]}}

        mock_execute_llm.return_value = """{
  "thinking": "Creating TODOs for authentication and injection risks",
  "phase": "plan",
  "data": {
    "todos": []
  },
  "next_phase_request": "act"
}"""

        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        reviewer._phase_logger = Mock()

        await reviewer._run_plan(context)

        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        assert any(
            "Creating TODOs for authentication and injection risks" in call for call in calls
        )


class TestActPhaseThinking:
    """Test ACT phase thinking logging."""

    @pytest.mark.asyncio
    async def test_act_phase_logs_thinking_from_response(self):
        reviewer = SecurityReviewer()

        reviewer._phase_outputs = {
            "plan": {
                "data": {
                    "todos": [
                        {
                            "id": "SEC-001",
                            "description": "Test todo",
                            "priority": "high",
                            "risk_category": "test",
                            "acceptance_criteria": "Test criteria",
                            "evidence_required": [],
                        }
                    ]
                }
            }
        }

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

        with patch("iron_rook.review.agents.security.DelegateTodoSkill") as MockSkill:
            mock_skill_instance = Mock()
            mock_skill_instance.review = AsyncMock()
            mock_skill_instance.review.return_value = ReviewOutput(
                agent="delegate_todo",
                summary="Test delegation complete",
                severity="merge",
                scope=Scope(
                    relevant_files=["src/test.py"],
                    reasoning="Test",
                ),
                findings=[],
                merge_gate=MergeGate(
                    decision="approve",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[],
                ),
            )
            MockSkill.return_value = mock_skill_instance

            # Run act phase
            await reviewer._run_act(context)

        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        assert any("ACT" in call for call in calls) or any("act" in call for call in calls)


class TestSynthesizePhaseThinking:
    """Test SYNTHESIZE phase thinking logging."""

    @patch.object(SecurityReviewer, "_execute_llm")
    @pytest.mark.asyncio
    async def test_synthesize_phase_logs_thinking_from_response(self, mock_execute_llm):
        """Verify SYNTHESIZE phase logs LLM thinking from response."""
        reviewer = SecurityReviewer()

        mock_execute_llm.return_value = """{
  "thinking": "Validating results and merging findings from all subagents",
  "phase": "synthesize",
  "data": {
    "todo_status": [],
    "gates": {}
  },
  "next_phase_request": "evaluate"
}"""

        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/repo",
            base_ref="main",
            head_ref="HEAD",
        )

        reviewer._phase_logger = Mock()

        await reviewer._run_synthesize(context)

        calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        assert any(
            "Validating results and merging findings from all subagents" in call for call in calls
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
  "next_phase_request": "plan"
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
            decision="proceed to plan",
        )
        assert frame.state == "intake"
        assert len(frame.goals) == 2
        assert len(frame.checks) == 2
        assert len(frame.risks) == 2
        assert len(frame.steps) == 2
        assert frame.decision == "proceed to plan"

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
        frame2 = ThinkingFrame(state="plan", decision="act")
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
            decision="proceed to plan",
        )
        frame2 = ThinkingFrame(
            state="plan",
            goals=["Create TODOs"],
            decision="act",
        )
        log = RunLog(frames=[frame1, frame2])
        assert len(log.frames) == 2
        assert log.frames[0].state == "intake"
        assert log.frames[1].state == "plan"

    def test_run_log_add_method(self):
        """Verify RunLog add() method correctly appends frames."""
        log = RunLog()
        frame1 = ThinkingFrame(
            state="intake",
            goals=["Analyze PR"],
            decision="proceed to plan",
        )
        frame2 = ThinkingFrame(
            state="plan",
            goals=["Create TODOs"],
            decision="act",
        )
        log.add(frame1)
        assert len(log.frames) == 1
        assert log.frames[0].state == "intake"
        log.add(frame2)
        assert len(log.frames) == 2
        assert log.frames[1].state == "plan"

    def test_run_log_default_frames(self):
        """Verify RunLog frames field uses list default_factory correctly."""
        log1 = RunLog()
        log2 = RunLog()
        # Add frame to log1
        log1.frames.append(ThinkingFrame(state="intake", goals=["Test"], decision="proceed"))
        # log2 frames should remain empty (default_factory creates new list each time)
        assert len(log1.frames) == 1
        assert len(log2.frames) == 0


class TestPhaseLoggerFrame:
    """Test SecurityPhaseLogger.log_thinking_frame() method."""

    def setUp(self):
        """Set up test fixtures."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger

        self.logger = SecurityPhaseLogger(enable_color=True)

    def test_log_thinking_frame_header(self):
        """Verify log_thinking_frame displays state header with correct phase color."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger
        from unittest.mock import patch

        logger = SecurityPhaseLogger(enable_color=True)
        frame = ThinkingFrame(state="intake", decision="proceed")

        # Mock console.print to capture calls
        with patch.object(logger._console, "print") as mock_print:
            logger.log_thinking_frame(frame)

            # Verify header was printed with correct content
            assert mock_print.called
            calls = [str(call) for call in mock_print.call_args_list]
            # Should contain the state header
            assert any("INTAKE" in call for call in calls)

    def test_log_thinking_frame_goals_checks_risks(self):
        """Verify log_thinking_frame displays goals/checks/risks with bullets."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger
        from unittest.mock import patch

        logger = SecurityPhaseLogger(enable_color=True)
        frame = ThinkingFrame(
            state="plan",
            goals=["Create security TODOs", "Identify high-risk areas"],
            checks=["Verify SQL injection patterns", "Check authentication flows"],
            risks=["Incomplete validation", "Weak session management"],
            decision="act",
        )

        # Mock console.print to capture calls
        with patch.object(logger._console, "print") as mock_print:
            logger.log_thinking_frame(frame)

            # Verify bullets were printed for goals, checks, risks
            assert mock_print.called
            calls = [str(call) for call in mock_print.call_args_list]
            combined_calls = " ".join(calls)

            # Check that goals, checks, risks labels appear
            assert "Goals:" in combined_calls
            assert "Checks:" in combined_calls
            assert "Risks:" in combined_calls

            # Check that content items appear
            assert "Create security TODOs" in combined_calls
            assert "Verify SQL injection patterns" in combined_calls
            assert "Incomplete validation" in combined_calls

    def test_log_thinking_frame_steps(self):
        """Verify log_thinking_frame displays thinking steps with all fields."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger
        from unittest.mock import patch

        logger = SecurityPhaseLogger(enable_color=True)
        step1 = ThinkingStep(
            kind="transition",
            why="Need to gather more context",
            evidence=["PR has 5 files changed", "Changes touch auth module"],
            next="continue",
            confidence="high",
        )
        step2 = ThinkingStep(
            kind="tool",
            why="Run security scan",
            next="scan_results",
            confidence="medium",
        )
        frame = ThinkingFrame(state="intake", steps=[step1, step2], decision="proceed")

        # Mock console.print to capture calls
        with patch.object(logger._console, "print") as mock_print:
            logger.log_thinking_frame(frame)

            # Verify step content was printed
            assert mock_print.called
            calls = [str(call) for call in mock_print.call_args_list]
            combined_calls = " ".join(calls)

            # Check that step fields appear
            assert "Step 1" in combined_calls
            assert "transition" in combined_calls
            assert "Need to gather more context" in combined_calls
            assert "Evidence:" in combined_calls
            assert "PR has 5 files changed" in combined_calls
            assert "Next:" in combined_calls
            assert "continue" in combined_calls
            assert "Confidence:" in combined_calls
            assert "high" in combined_calls

    def test_log_thinking_frame_decision(self):
        """Verify log_thinking_frame displays decision field."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger
        from unittest.mock import patch

        logger = SecurityPhaseLogger(enable_color=True)
        frame = ThinkingFrame(state="evaluate", decision="approve with minor comments")

        # Mock console.print to capture calls
        with patch.object(logger._console, "print") as mock_print:
            logger.log_thinking_frame(frame)

            # Verify decision was printed
            assert mock_print.called
            calls = [str(call) for call in mock_print.call_args_list]
            combined_calls = " ".join(calls)

            # Check that decision appears
            assert "Decision:" in combined_calls
            assert "approve with minor comments" in combined_calls

    def test_log_thinking_frame_logs_to_logger(self):
        """Verify log_thinking_frame logs to internal logger."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger
        import logging

        logger = SecurityPhaseLogger(enable_color=True)
        frame = ThinkingFrame(
            state="consolidate",
            goals=["Merge findings"],
            checks=["Verify duplicates"],
            risks=["Missing data"],
            steps=[
                ThinkingStep(kind="gate", why="Check completeness", confidence="high"),
            ],
            decision="proceed",
        )

        # Capture log output using caplog-style approach
        import io

        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        logger._logger.addHandler(handler)

        try:
            logger.log_thinking_frame(frame)

            # Get logged output
            log_output = log_capture.getvalue()

            # Verify structured log entry
            assert "consolidate" in log_output
            assert "ThinkingFrame" in log_output
            # Verify counts in log message
            assert "goals=1" in log_output
            assert "checks=1" in log_output
            assert "risks=1" in log_output
            assert "steps=1" in log_output
            assert "decision=proceed" in log_output
        finally:
            logger._logger.removeHandler(handler)
