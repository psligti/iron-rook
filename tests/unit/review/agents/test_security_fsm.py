"""Tests for SecurityReviewer 6-phase FSM implementation.

Tests FSM transitions, phase execution, SecurityPhaseLogger integration,
and ReviewOutput generation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from iron_rook.review.agents.security import SecurityReviewer, SECURITY_FSM_TRANSITIONS
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput


class TestSecurityFSMInitialization:
    """Test SecurityReviewer FSM initialization."""

    def test_security_reviewer_initializes_with_fsm(self):
        """Verify SecurityReviewer initializes with LoopFSM."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_fsm")
        assert hasattr(reviewer, "_phase_logger")
        assert hasattr(reviewer, "_phase_outputs")
        assert hasattr(reviewer, "_current_security_phase")

    def test_security_reviewer_phase_transitions_defined(self):
        """Verify SECURITY_FSM_TRANSITIONS are correctly defined."""
        assert SECURITY_FSM_TRANSITIONS == {
            "intake": ["plan_todos"],
            "plan_todos": ["delegate"],
            "delegate": ["collect", "consolidate", "evaluate", "done"],
            "collect": ["consolidate"],
            "consolidate": ["evaluate"],
            "evaluate": ["done"],
        }

    def test_security_reviewer_initial_phase_is_intake(self):
        """Verify initial security phase is 'intake'."""
        reviewer = SecurityReviewer()
        assert reviewer.state == "intake"

    def test_security_reviewer_get_agent_name_returns_security_fsm(self):
        """Verify get_agent_name returns 'security_fsm'."""
        reviewer = SecurityReviewer()
        assert reviewer.get_agent_name() == "security_fsm"

    def test_security_reviewer_phase_logger_initialized(self):
        """Verify SecurityPhaseLogger is initialized."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_phase_logger")
        assert reviewer._phase_logger is not None


class TestSecurityFSMTransitions:
    """Test security FSM state transitions."""

    def test_valid_transition_intake_to_plan_todos(self):
        """Verify intake -> plan_todos is a valid transition."""
        reviewer = SecurityReviewer()
        valid_transitions = SECURITY_FSM_TRANSITIONS.get("intake", [])
        assert "plan_todos" in valid_transitions

    def test_valid_transition_plan_todos_to_delegate(self):
        """Verify plan_todos -> delegate is a valid transition."""
        reviewer = SecurityReviewer()
        valid_transitions = SECURITY_FSM_TRANSITIONS.get("plan_todos", [])
        assert "delegate" in valid_transitions

    def test_valid_transition_delegate_to_collect(self):
        """Verify delegate -> collect is a valid transition."""
        reviewer = SecurityReviewer()
        valid_transitions = SECURITY_FSM_TRANSITIONS.get("delegate", [])
        assert "collect" in valid_transitions

    def test_valid_transition_collect_to_consolidate(self):
        """Verify collect -> consolidate is a valid transition."""
        reviewer = SecurityReviewer()
        valid_transitions = SECURITY_FSM_TRANSITIONS.get("collect", [])
        assert "consolidate" in valid_transitions

    def test_valid_transition_consolidate_to_evaluate(self):
        """Verify consolidate -> evaluate is a valid transition."""
        reviewer = SecurityReviewer()
        valid_transitions = SECURITY_FSM_TRANSITIONS.get("consolidate", [])
        assert "evaluate" in valid_transitions

    def test_valid_transition_evaluate_to_done(self):
        """Verify evaluate -> done is a valid transition."""
        reviewer = SecurityReviewer()
        valid_transitions = SECURITY_FSM_TRANSITIONS.get("evaluate", [])
        assert "done" in valid_transitions


class TestSecurityPhaseMethods:
    """Test security phase methods implementation."""

    @pytest.mark.asyncio
    async def test_run_intake_method_exists(self):
        """Verify _run_intake method exists."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_run_intake")

    @pytest.mark.asyncio
    async def test_run_plan_todos_method_exists(self):
        """Verify _run_plan_todos method exists."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_run_plan_todos")

    @pytest.mark.asyncio
    async def test_run_delegate_method_exists(self):
        """Verify _run_delegate method exists."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_run_delegate")

    @pytest.mark.asyncio
    async def test_run_collect_method_exists(self):
        """Verify _run_collect method exists."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_run_collect")

    @pytest.mark.asyncio
    async def test_run_consolidate_method_exists(self):
        """Verify _run_consolidate method exists."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_run_consolidate")

    @pytest.mark.asyncio
    async def test_run_evaluate_method_exists(self):
        """Verify _run_evaluate method exists."""
        reviewer = SecurityReviewer()
        assert hasattr(reviewer, "_run_evaluate")


class TestSecurityPhaseLoggerIntegration:
    """Test SecurityPhaseLogger integration for thinking output."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_intake_phase_logs_thinking(self, mock_runner_class):
        """Verify INTAKE phase uses SecurityPhaseLogger.log_thinking()."""
        reviewer = SecurityReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "phase": "intake",\n  "data": {\n    "summary": "test",\n    "risk_hypotheses": [],\n    "questions": []\n  },\n  "next_phase_request": "plan_todos"\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute phase
        output = await reviewer._run_intake(context)

        # Verify phase is in output
        assert "phase" in output
        assert output["phase"] == "intake"

        # Verify next_phase_request
        assert "next_phase_request" in output
        assert output["next_phase_request"] == "plan_todos"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_plan_todos_phase_logs_thinking(self, mock_runner_class):
        """Verify PLAN_TODOS phase uses SecurityPhaseLogger.log_thinking()."""
        reviewer = SecurityReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "phase": "plan_todos",\n  "data": {\n    "todos": [],\n    "delegation_plan": {},\n    "tools_considered": [],\n    "tools_chosen": [],\n    "why": ""\n  },\n  "next_phase_request": "delegate"\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute phase
        output = await reviewer._run_plan_todos(context)

        # Verify phase is in output
        assert "phase" in output
        assert output["phase"] == "plan_todos"

        # Verify next_phase_request
        assert "next_phase_request" in output
        assert output["next_phase_request"] == "delegate"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_evaluate_phase_logs_thinking(self, mock_runner_class):
        """Verify EVALUATE phase uses SecurityPhaseLogger.log_thinking()."""
        reviewer = SecurityReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "phase": "evaluate",\n  "data": {\n    "findings": {\n      "critical": [],\n      "high": [],\n      "medium": [],\n      "low": []\n    },\n    "risk_assessment": {\n      "overall": "low",\n      "rationale": ""\n    },\n    "evidence_index": [],\n    "actions": {\n      "required": [],\n      "suggested": []\n    },\n    "confidence": 0.9,\n    "missing_information": []\n  },\n  "next_phase_request": "done"\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute phase
        output = await reviewer._run_evaluate(context)

        # Verify phase is in output
        assert "phase" in output
        assert output["phase"] == "evaluate"

        # Verify next_phase_request
        assert "next_phase_request" in output
        assert output["next_phase_request"] == "done"


class TestStateTransitionLogging:
    """Test state transition logging with SecurityPhaseLogger."""

    def test_transition_to_phase_logs_transition(self):
        """Verify _transition_to_phase logs transitions."""
        reviewer = SecurityReviewer()

        # Mock logger
        reviewer._phase_logger.log_transition = Mock()

        # Valid transition
        reviewer._transition_to_phase("plan_todos")

        # Verify log_transition was called
        reviewer._phase_logger.log_transition.assert_called_once_with("intake", "plan_todos")

        # Verify current phase updated
        assert reviewer.state == "plan_todos"

    def test_invalid_transition_raises_error(self):
        """Verify invalid transition raises ValueError."""
        reviewer = SecurityReviewer()

        # Mock logger
        reviewer._phase_logger.log_transition = Mock()

        # Invalid transition: done -> intake (not in SECURITY_FSM_TRANSITIONS)
        with pytest.raises(ValueError) as exc_info:
            reviewer._current_security_phase = "done"
            reviewer._transition_to_phase("intake")

        # Verify error message
        assert "Invalid transition" in str(exc_info.value)
        assert "done -> intake" in str(exc_info.value)

    def test_all_six_phases_have_valid_transitions(self):
        """Verify all 6 phases have at least one valid transition."""
        all_phases = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]
        for phase in all_phases:
            valid_transitions = SECURITY_FSM_TRANSITIONS.get(phase, [])
            assert len(valid_transitions) > 0, f"Phase {phase} has no valid transitions"


class TestReviewOutputGeneration:
    """Test ReviewOutput generation from EVALUATE phase."""

    def test_build_review_output_from_evaluate_creates_valid_output(self):
        """Verify _build_review_output_from_evaluate creates valid ReviewOutput."""
        reviewer = SecurityReviewer()

        # Mock evaluate output
        evaluate_output = {
            "phase": "evaluate",
            "data": {
                "findings": {
                    "critical": [],
                    "high": [],
                    "medium": [
                        {
                            "severity": "medium",
                            "title": "Test finding",
                            "description": "Test description",
                            "evidence": [{"type": "file_ref", "path": "src/test.py"}],
                            "recommendations": ["Fix the issue"],
                        }
                    ],
                    "low": [],
                },
                "risk_assessment": {
                    "overall": "medium",
                    "rationale": "Medium risk finding detected",
                    "areas_touched": ["test"],
                },
                "evidence_index": [],
                "actions": {
                    "required": [],
                    "suggested": [],
                },
                "confidence": 0.8,
                "missing_information": [],
            },
            "next_phase_request": "done",
        }

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Build ReviewOutput
        output = reviewer._build_review_output_from_evaluate(evaluate_output, context)

        # Verify ReviewOutput structure
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"
        assert output.severity == "medium"
        assert len(output.findings) == 1
        assert output.findings[0].severity == "medium"
        assert output.merge_gate.decision == "approve"

    def test_build_error_review_output_creates_critical_output(self):
        """Verify _build_error_review_output creates ReviewOutput with severity 'critical'."""
        reviewer = SecurityReviewer()

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Build error output
        output = reviewer._build_error_review_output(context, "Test error")

        # Verify ReviewOutput structure
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"
        assert output.severity == "critical"
        assert output.summary.startswith("Security review failed")
        assert output.merge_gate.decision == "needs_changes"


class TestSecurityFilePatternsAndTools:
    """Test security reviewer file patterns and tools."""

    def test_get_relevant_file_patterns_returns_security_patterns(self):
        """Verify get_relevant_file_patterns returns security-related patterns."""
        reviewer = SecurityReviewer()
        patterns = reviewer.get_relevant_file_patterns()

        # Verify security-relevant patterns
        assert "**/*.py" in patterns
        assert "**/*.js" in patterns
        assert "**/*.sh" in patterns
        assert "**/*.env*" in patterns
        assert "**/.github/workflows/**" in patterns

    def test_get_allowed_tools_returns_security_tools(self):
        """Verify get_allowed_tools returns security-related tools."""
        reviewer = SecurityReviewer()
        tools = reviewer.get_allowed_tools()

        # Verify security tools
        assert "grep" in tools
        assert "ast-grep" in tools
        assert "bandit" in tools
        assert "semgrep" in tools
        assert "pip-audit" in tools


class TestFullFSMExecutionFlow:
    """Test end-to-end FSM execution flow."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_executes_all_six_phases(self, mock_runner_class):
        """Verify FSM executes through all 6 phases."""
        reviewer = SecurityReviewer()

        # Mock runner responses for all phases
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            # INTAKE response
            '{\n  "phase": "intake",\n  "data": {\n    "summary": "test",\n    "risk_hypotheses": [],\n    "questions": []\n  },\n  "next_phase_request": "plan_todos"\n}',
            # PLAN_TODOS response
            '{\n  "phase": "plan_todos",\n  "data": {\n    "todos": [],\n    "delegation_plan": {},\n    "tools_considered": [],\n    "tools_chosen": [],\n    "why": ""\n  },\n  "next_phase_request": "delegate"\n}',
            # DELEGATE response
            '{\n  "phase": "delegate",\n  "data": {\n    "subagent_requests": [],\n    "self_analysis_plan": []\n  },\n  "next_phase_request": "collect"\n}',
            # COLLECT response
            '{\n  "phase": "collect",\n  "data": {\n    "todo_status": [],\n    "issues_with_results": []\n  },\n  "next_phase_request": "consolidate"\n}',
            # CONSOLIDATE response
            '{\n  "phase": "consolidate",\n  "data": {\n    "gates": {\n      "all_todos_resolved": true,\n      "evidence_present": true,\n      "findings_categorized": true,\n      "confidence_set": true\n    },\n    "missing_information": []\n  },\n  "next_phase_request": "evaluate"\n}',
            # EVALUATE response
            '{\n  "phase": "evaluate",\n  "data": {\n    "findings": {\n      "critical": [],\n      "high": [],\n      "medium": [],\n      "low": []\n    },\n    "risk_assessment": {\n      "overall": "low",\n      "rationale": ""\n    },\n    "evidence_index": [],\n    "actions": {\n      "required": [],\n      "suggested": []\n    },\n    "confidence": 1.0,\n    "missing_information": []\n  },\n  "next_phase_request": "done"\n}',
        ]
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Mock logger
        reviewer._phase_logger.log_thinking = Mock()
        reviewer._phase_logger.log_transition = Mock()

        # Execute review
        output = await reviewer.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"

        # Verify all phases were logged
        assert reviewer._phase_logger.log_thinking.call_count >= 6

        # Verify transitions were logged
        # intake -> plan_todos, plan_todos -> delegate, delegate -> collect, collect -> consolidate, consolidate -> evaluate, evaluate -> done
        assert reviewer._phase_logger.log_transition.call_count >= 6

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_stops_at_done_phase(self, mock_runner_class):
        """Verify FSM stops at DONE phase."""
        reviewer = SecurityReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = '{\n  "phase": "evaluate",\n  "data": {\n    "findings": {\n      "critical": [],\n      "high": [],\n      "medium": [],\n      "low": []\n    },\n    "risk_assessment": {\n      "overall": "low",\n      "rationale": ""\n    },\n    "evidence_index": [],\n    "actions": {\n      "required": [],\n      "suggested": []\n    },\n    "confidence": 1.0,\n    "missing_information": []\n  },\n  "next_phase_request": "done"\n}'
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await reviewer.review(context)

        # Verify final state is "done"
        assert reviewer.state == "done"

        # Verify ReviewOutput is valid
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"
