"""Tests for state transition logging in SecurityReviewer FSM.

Verifies that SecurityPhaseLogger.log_transition() is called before each
phase transition, with proper phase names and timing.
"""

import pytest
from unittest.mock import Mock, patch, call
from iron_rook.review.agents.security import SecurityReviewer
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import Scope, MergeGate, Finding


class TestTransitionLogging:
    """Test state transition logging behavior in SecurityReviewer."""

    def test_security_reviewer_has_phase_logger_initialized(self):
        """Verify SecurityReviewer initializes with SecurityPhaseLogger."""
        reviewer = SecurityReviewer()
        assert reviewer._phase_logger is not None

    def test_log_transition_called_on_intake_to_plan(self):
        reviewer = SecurityReviewer()
        reviewer._phase_logger = Mock()

        reviewer._current_phase = "intake"
        reviewer._transition_to_phase("plan")

        reviewer._phase_logger.log_transition.assert_called_once_with("intake", "plan")

    @patch.object(SecurityReviewer, "_execute_llm")
    def test_log_transition_called_for_all_valid_transitions(self, mock_execute_llm):
        valid_transitions = [
            ("intake", "plan"),
            ("plan", "act"),
            ("act", "synthesize"),
            ("synthesize", "check"),
            ("check", "done"),
        ]

        reviewer = SecurityReviewer()
        reviewer._phase_logger = Mock()

        for from_state, to_state in valid_transitions:
            reviewer._current_phase = from_state
            reviewer._transition_to_phase(to_state)
            reviewer._phase_logger.log_transition.assert_called_with(from_state, to_state)
            reviewer._phase_logger.reset_mock()

    @patch.object(SecurityReviewer, "_execute_llm")
    def test_transition_logging_occurs_before_phase_update(self, mock_execute_llm):
        """Verify log_transition() is called BEFORE _current_security_phase is updated."""
        reviewer = SecurityReviewer()

        call_order = []
        original_log = reviewer._phase_logger.log_transition

        def side_effect_log(from_state, to_state):
            call_order.append(("log", reviewer._current_security_phase, to_state))
            original_log(from_state, to_state)

        reviewer._phase_logger.log_transition = side_effect_log
        reviewer._current_phase = "intake"
        reviewer._transition_to_phase("plan")

        assert call_order[0][0] == "log"
        assert call_order[0][1] == "intake"
        assert call_order[0][2] == "plan"
        assert reviewer._current_security_phase == "plan"

    def test_invalid_transition_raises_value_error_without_logging(self):
        """Verify invalid transitions raise ValueError and don't call log_transition()."""
        reviewer = SecurityReviewer()
        reviewer._phase_logger = Mock()
        reviewer._current_phase = "intake"

        with pytest.raises(ValueError) as exc_info:
            reviewer._transition_to_phase("synthesize")

        assert "Invalid transition" in str(exc_info.value)
        assert "Valid transitions: {'plan'}" in str(exc_info.value)
        reviewer._phase_logger.log_transition.assert_not_called()

    @patch.object(SecurityReviewer, "_execute_llm")
    def test_act_to_synthesize_transition_logged(self, mock_execute_llm):
        """Verify log_transition() is called for act -> synthesize (multiple allowed)."""
        reviewer = SecurityReviewer()
        reviewer._current_phase = "act"
        reviewer._phase_logger = Mock()

        reviewer._transition_to_phase("synthesize")
        reviewer._phase_logger.log_transition.assert_called_once_with("act", "synthesize")

    @patch.object(SecurityReviewer, "_execute_llm")
    def test_all_act_alternative_transitions_logged(self, mock_execute_llm):
        reviewer = SecurityReviewer()
        reviewer._phase_logger = Mock()

        reviewer._current_phase = "act"
        reviewer._transition_to_phase("synthesize")
        reviewer._phase_logger.log_transition.assert_called_once_with("act", "synthesize")

    @patch.object(SecurityReviewer, "_execute_llm")
    def test_phase_logger_is_security_phase_logger_instance(self, mock_execute_llm):
        """Verify _phase_logger is actually a SecurityPhaseLogger instance."""
        from iron_rook.review.security_phase_logger import SecurityPhaseLogger

        reviewer = SecurityReviewer()
        assert isinstance(reviewer._phase_logger, SecurityPhaseLogger)

    @patch.object(SecurityReviewer, "_execute_llm")
    def test_transition_states_match_fsm_transitions_dict(self, mock_execute_llm):
        # Use SecurityReviewer's actual VALID_TRANSITIONS, not the generic WORKFLOW_FSM_TRANSITIONS
        reviewer = SecurityReviewer()
        reviewer._phase_logger = Mock()

        for from_state, allowed_to_states in SecurityReviewer.VALID_TRANSITIONS.items():
            for to_state in allowed_to_states:
                reviewer._current_phase = from_state
                reviewer._phase_logger.reset_mock()
                reviewer._transition_to_phase(to_state)
                reviewer._phase_logger.log_transition.assert_called_once_with(from_state, to_state)
