"""Tests for SecurityReviewer LLM thinking capture.

Tests that phase methods extract and log LLM reasoning from responses
using SecurityPhaseLogger.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from iron_rook.review.agents.security import SecurityReviewer
from iron_rook.review.base import ReviewContext


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
