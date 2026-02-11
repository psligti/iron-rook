"""Tests for AgentState and AgentStateMachine.

Tests state machine lifecycle, transition validation, and Result pattern integration.
"""

import pytest
from typing import cast

from dawn_kestrel.agents.state import AgentState, AgentStateMachine, FSM_TRANSITIONS
from dawn_kestrel.core.result import Err, Ok, Result


class TestAgentStateEnum:
    """Test AgentState enum properties."""

    def test_enum_values_lowercase(self):
        """Verify all enum values are lowercase strings."""
        expected_values = {
            "idle",
            "initializing",
            "ready",
            "running",
            "paused",
            "completed",
            "failed",
        }
        actual_values = {state.value for state in AgentState}
        assert actual_values == expected_values

    def test_all_states_defined(self):
        """Verify all required states are defined."""
        required_states = {
            AgentState.IDLE,
            AgentState.INITIALIZING,
            AgentState.READY,
            AgentState.RUNNING,
            AgentState.PAUSED,
            AgentState.COMPLETED,
            AgentState.FAILED,
        }
        assert set(AgentState) == required_states


class TestAgentStateMachine:
    """Test AgentStateMachine initialization and basic operations."""

    def test_initializes_to_idle(self):
        """Verify state machine initializes to IDLE by default."""
        fsm = AgentStateMachine()
        assert fsm.current_state == AgentState.IDLE

    def test_can_omit_transitions_param(self):
        """Verify transitions parameter is optional."""
        fsm = AgentStateMachine()
        assert fsm.transitions is not None

    def test_can_provide_custom_transitions(self):
        """Verify custom transition maps can be provided."""
        custom_transitions = {AgentState.IDLE: {AgentState.READY}}
        fsm = AgentStateMachine(transitions=custom_transitions)
        assert fsm.transitions == custom_transitions

    def test_repr_formatting(self):
        """Verify string representation is informative."""
        fsm = AgentStateMachine()
        assert "AgentStateMachine" in repr(fsm)
        assert "idle" in repr(fsm)


class TestValidTransitions:
    """Test valid state transitions."""

    def test_idle_to_initializing(self):
        """Verify IDLE -> INITIALIZING is valid."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.INITIALIZING)

        assert result.is_ok()
        assert fsm.current_state == AgentState.INITIALIZING

    def test_initializing_to_ready(self):
        """Verify INITIALIZING -> READY is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        result = fsm.transition_to(AgentState.READY)

        assert result.is_ok()
        assert fsm.current_state == AgentState.READY

    def test_ready_to_running(self):
        """Verify READY -> RUNNING is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        result = fsm.transition_to(AgentState.RUNNING)

        assert result.is_ok()
        assert fsm.current_state == AgentState.RUNNING

    def test_running_to_paused(self):
        """Verify RUNNING -> PAUSED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        result = fsm.transition_to(AgentState.PAUSED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.PAUSED

    def test_paused_to_running(self):
        """Verify PAUSED -> RUNNING is valid (resume)."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        fsm.transition_to(AgentState.PAUSED)
        result = fsm.transition_to(AgentState.RUNNING)

        assert result.is_ok()
        assert fsm.current_state == AgentState.RUNNING

    def test_running_to_completed(self):
        """Verify RUNNING -> COMPLETED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.COMPLETED

    def test_running_to_failed(self):
        """Verify RUNNING -> FAILED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        result = fsm.transition_to(AgentState.FAILED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.FAILED

    def test_paused_to_completed(self):
        """Verify PAUSED -> COMPLETED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        fsm.transition_to(AgentState.PAUSED)
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.COMPLETED

    def test_paused_to_failed(self):
        """Verify PAUSED -> FAILED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        fsm.transition_to(AgentState.PAUSED)
        result = fsm.transition_to(AgentState.FAILED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.FAILED

    def test_initializing_to_failed(self):
        """Verify INITIALIZING -> FAILED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        result = fsm.transition_to(AgentState.FAILED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.FAILED

    def test_ready_to_failed(self):
        """Verify READY -> FAILED is valid."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        result = fsm.transition_to(AgentState.FAILED)

        assert result.is_ok()
        assert fsm.current_state == AgentState.FAILED


class TestInvalidTransitions:
    """Test invalid state transitions."""

    def test_idle_to_completed_is_invalid(self):
        """Verify IDLE -> COMPLETED is invalid."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert fsm.current_state == AgentState.IDLE  # State unchanged

    def test_idle_to_failed_is_invalid(self):
        """Verify IDLE -> FAILED is invalid."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.FAILED)

        assert result.is_err()
        assert fsm.current_state == AgentState.IDLE

    def test_completed_to_any_is_invalid(self):
        """Verify COMPLETED is terminal state."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        fsm.transition_to(AgentState.COMPLETED)

        # Try to transition from COMPLETED
        result = fsm.transition_to(AgentState.RUNNING)
        assert result.is_err()
        assert fsm.current_state == AgentState.COMPLETED

    def test_failed_to_any_is_invalid(self):
        """Verify FAILED is terminal state."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.FAILED)

        # Try to transition from FAILED
        result = fsm.transition_to(AgentState.READY)
        assert result.is_err()
        assert fsm.current_state == AgentState.FAILED

    def test_invalid_transition_preserves_state(self):
        """Verify invalid transition does not change current state."""
        fsm = AgentStateMachine()
        initial_state = fsm.current_state

        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert fsm.current_state == initial_state


class TestTransitionResult:
    """Test Result pattern return values from transition_to()."""

    def test_valid_transition_returns_ok(self):
        """Verify valid transition returns Ok with new state."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.INITIALIZING)

        assert isinstance(result, Ok)
        assert result.unwrap() == AgentState.INITIALIZING

    def test_invalid_transition_returns_err(self):
        """Verify invalid transition returns Err with error details."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert isinstance(result, Err)
        err = cast(Err[AgentState], result)
        assert err.error is not None
        assert "Invalid transition" in err.error
        assert "idle -> completed" in err.error
        assert err.code == "INVALID_TRANSITION"

    def test_err_result_has_retryable_false(self):
        """Verify Err result indicates transition is not retryable."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert isinstance(result, Err)
        err = cast(Err[AgentState], result)
        assert err.retryable is False


class TestCanTransitionTo:
    """Test can_transition_to() method for preflight validation."""

    def test_can_check_valid_transition_without_changing_state(self):
        """Verify can_transition_to() checks without mutating state."""
        fsm = AgentStateMachine()
        initial_state = fsm.current_state

        can_transition = fsm.can_transition_to(AgentState.INITIALIZING)

        assert can_transition is True
        assert fsm.current_state == initial_state

    def test_can_check_invalid_transition_without_changing_state(self):
        """Verify can_transition_to() returns False for invalid transitions."""
        fsm = AgentStateMachine()
        initial_state = fsm.current_state

        can_transition = fsm.can_transition_to(AgentState.COMPLETED)

        assert can_transition is False
        assert fsm.current_state == initial_state

    def test_can_transition_from_various_states(self):
        """Verify can_transition_to() works from various states."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        assert fsm.can_transition_to(AgentState.READY)

        fsm.transition_to(AgentState.READY)
        assert fsm.can_transition_to(AgentState.RUNNING)

        fsm.transition_to(AgentState.RUNNING)
        assert fsm.can_transition_to(AgentState.PAUSED)


class TestReset:
    """Test reset() method for state machine reset."""

    def test_reset_returns_to_idle(self):
        """Verify reset() returns state machine to IDLE."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)

        fsm.reset()

        assert fsm.current_state == AgentState.IDLE

    def test_reset_from_completed_state(self):
        """Verify reset() works from terminal state."""
        fsm = AgentStateMachine()
        fsm.transition_to(AgentState.INITIALIZING)
        fsm.transition_to(AgentState.READY)
        fsm.transition_to(AgentState.RUNNING)
        fsm.transition_to(AgentState.COMPLETED)

        fsm.reset()

        assert fsm.current_state == AgentState.IDLE


class TestCustomTransitionMaps:
    """Test state machine with custom transition maps."""

    def test_custom_map_overrides_default(self):
        """Verify custom transition map overrides default."""
        custom_transitions = {
            AgentState.IDLE: {AgentState.RUNNING},
            AgentState.RUNNING: {AgentState.COMPLETED},
            AgentState.COMPLETED: set(),
            AgentState.FAILED: set(),
        }
        fsm = AgentStateMachine(transitions=custom_transitions)

        # IDLE -> RUNNING should be valid
        result = fsm.transition_to(AgentState.RUNNING)
        assert result.is_ok()
        assert fsm.current_state == AgentState.RUNNING

        # RUNNING -> COMPLETED should be valid
        result = fsm.transition_to(AgentState.COMPLETED)
        assert result.is_ok()
        assert fsm.current_state == AgentState.COMPLETED

    def test_custom_map_invalidates_default_transitions(self):
        """Verify custom map invalidates default transitions."""
        custom_transitions = {AgentState.IDLE: {AgentState.RUNNING}}
        fsm = AgentStateMachine(transitions=custom_transitions)

        # IDLE -> INITIALIZING should be invalid (default map removed)
        result = fsm.transition_to(AgentState.INITIALIZING)
        assert result.is_err()
        assert fsm.current_state == AgentState.IDLE


class TestFSMTransitionsDefault:
    """Test default FSM_TRANSITIONS constant."""

    def test_fsm_transitions_is_complete(self):
        """Verify FSM_TRANSITIONS includes all states."""
        assert set(FSM_TRANSITIONS.keys()) == set(AgentState)

    def test_fsm_transitions_terminal_states_empty(self):
        """Verify terminal states have empty transition sets."""
        assert FSM_TRANSITIONS[AgentState.COMPLETED] == set()
        assert FSM_TRANSITIONS[AgentState.FAILED] == set()

    def test_fsm_transitions_idle_has_initializing(self):
        """Verify IDLE state has INITIALIZING as only valid transition."""
        assert FSM_TRANSITIONS[AgentState.IDLE] == {AgentState.INITIALIZING}


class TestTransitionToReturnsOkValue:
    """Test what transition_to() returns in Ok result (per requirements)."""

    def test_ok_value_is_target_state(self):
        """Verify Ok result contains the target state."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.INITIALIZING)

        assert result.is_ok()
        assert result.unwrap() == AgentState.INITIALIZING

    def test_ok_value_matches_current_state(self):
        """Verify Ok value matches the new current state."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.INITIALIZING)

        assert result.is_ok()
        assert result.unwrap() == fsm.current_state


class TestInvalidTransitionErrEncoding:
    """Test how invalid transitions are encoded in Err (per requirements)."""

    def test_err_has_message(self):
        """Verify Err contains error message."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert isinstance(result, Err)
        err = cast(Err[AgentState], result)
        assert err.error is not None

    def test_err_message_includes_both_states(self):
        """Verify Err message includes from and to states."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert isinstance(result, Err)
        err = cast(Err[AgentState], result)
        assert "idle -> completed" in err.error

    def test_err_message_includes_valid_transitions(self):
        """Verify Err message lists valid transitions."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert isinstance(result, Err)
        err = cast(Err[AgentState], result)
        assert "Valid transitions" in err.error
        assert "initializing" in err.error

    def test_err_has_code(self):
        """Verify Err contains error code."""
        fsm = AgentStateMachine()
        result = fsm.transition_to(AgentState.COMPLETED)

        assert result.is_err()
        assert isinstance(result, Err)
        err = cast(Err[AgentState], result)
        assert err.code == "INVALID_TRANSITION"
