"""Tests for SecurityPhaseLogger.

Tests phase-specific logging including thinking output, state transitions,
and color formatting support.
"""

import logging
import pytest

from iron_rook.review.security_phase_logger import SecurityPhaseLogger


class TestSecurityPhaseLoggerInitialization:
    """Test SecurityPhaseLogger initialization and configuration."""

    def test_logger_initialization_with_color_enabled(self):
        """Verify logger initializes with color enabled by default."""
        logger = SecurityPhaseLogger()
        assert logger._enable_color is True
        assert logger._console is not None
        assert logger._logger is not None
        assert logger._logger.name == "security.thinking"

    def test_logger_initialization_with_color_disabled(self):
        """Verify logger initializes with color disabled when specified."""
        logger = SecurityPhaseLogger(enable_color=False)
        assert logger._enable_color is False

    def test_logger_has_phase_colors_dict(self):
        """Verify logger has PHASE_COLORS dictionary with expected keys."""
        logger = SecurityPhaseLogger()
        expected_phases = [
            "INTAKE",
            "PLAN_TODOS",
            "ACT",
            "COLLECT",
            "CONSOLIDATE",
            "EVALUATE",
            "DONE",
            "STOPPED_BUDGET",
            "STOPPED_HUMAN",
            "TRANSITION",
        ]
        for phase in expected_phases:
            assert phase in logger.PHASE_COLORS


class TestLogThinking:
    """Test log_thinking method for phase-specific output."""

    def test_log_thinking_with_valid_phase(self, caplog):
        """Verify log_thinking works with valid phase name."""
        logger = SecurityPhaseLogger(enable_color=False)
        logger.log_thinking("INTAKE", "Test thinking message")

        assert len(caplog.records) >= 1
        assert any(
            "INTAKE" in record.message and "Test thinking message" in record.message
            for record in caplog.records
        )

    def test_log_thinking_with_lowercase_phase(self, caplog):
        """Verify log_thinking preserves original phase case in log message."""
        logger = SecurityPhaseLogger(enable_color=False)
        logger.log_thinking("intake", "Test message")

        assert any(
            "intake" in record.message and "Test message" in record.message
            for record in caplog.records
        )

    def test_log_thinking_with_unknown_phase(self, caplog):
        """Verify log_thinking handles unknown phase gracefully."""
        logger = SecurityPhaseLogger(enable_color=False)
        logger.log_thinking("UNKNOWN", "Test message")

        assert any(
            "UNKNOWN" in record.message and "Test message" in record.message
            for record in caplog.records
        )


class TestLogTransition:
    """Test log_transition method for FSM state transitions."""

    def test_log_transition_valid_states(self, caplog):
        """Verify log_transition works with valid state names."""
        logger = SecurityPhaseLogger(enable_color=False)
        logger.log_transition("intake", "plan")

        assert any("[TRANSITION]" in record.message for record in caplog.records)
        assert any(
            "intake" in record.message and "plan" in record.message for record in caplog.records
        )

    def test_log_transition_multiple_transitions(self, caplog):
        """Verify multiple transitions are logged correctly."""
        logger = SecurityPhaseLogger(enable_color=False)
        logger.log_transition("intake", "plan")
        logger.log_transition("plan", "act")
        logger.log_transition("act", "synthesize")

        transitions = [r for r in caplog.records if "[TRANSITION]" in r.message]
        assert len(transitions) == 3

    def test_log_transition_with_terminal_state(self, caplog):
        """Verify log_transition handles terminal states."""
        logger = SecurityPhaseLogger(enable_color=False)
        logger.log_transition("evaluate", "done")

        assert any("[TRANSITION]" in record.message for record in caplog.records)
        assert any(
            "evaluate" in record.message and "done" in record.message for record in caplog.records
        )


class TestPhaseColorMethods:
    """Test color-related helper methods."""

    def test_get_phase_color_valid_phase(self):
        """Verify get_phase_color returns color for valid phase."""
        logger = SecurityPhaseLogger()
        color = logger.get_phase_color("INTAKE")
        assert color == "bold cyan"

    def test_get_phase_color_lowercase_input(self):
        """Verify get_phase_color normalizes lowercase phase name."""
        logger = SecurityPhaseLogger()
        color = logger.get_phase_color("intake")
        assert color == "bold cyan"

    def test_get_phase_color_unknown_phase(self):
        """Verify get_phase_color returns default color for unknown phase."""
        logger = SecurityPhaseLogger()
        color = logger.get_phase_color("UNKNOWN")
        assert color == "white"

    def test_get_valid_phases(self):
        """Verify get_valid_phases returns list of all phase names."""
        logger = SecurityPhaseLogger()
        phases = logger.get_valid_phases()

        expected_phases = [
            "INTAKE",
            "PLAN_TODOS",
            "ACT",
            "COLLECT",
            "CONSOLIDATE",
            "EVALUATE",
            "DONE",
            "STOPPED_BUDGET",
            "STOPPED_HUMAN",
            "TRANSITION",
        ]
        for phase in expected_phases:
            assert phase in phases

    def test_get_valid_phases_returns_list(self):
        """Verify get_valid_phases returns a list."""
        logger = SecurityPhaseLogger()
        phases = logger.get_valid_phases()
        assert isinstance(phases, list)
        assert len(phases) > 0
