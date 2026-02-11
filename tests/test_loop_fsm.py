"""Tests for LoopFSM async execution support.

Tests state locking, async loop execution, and parallel tool execution
within the ACT phase while maintaining state consistency.
"""

import asyncio
import pytest

from iron_rook.fsm.loop_fsm import LoopFSM
from iron_rook.fsm.loop_state import LoopState
from iron_rook.fsm.todo import Todo


class TestStateLocking:
    """Test state locking prevents concurrent state mutations."""

    def test_state_lock_exists_and_is_initialized(self):
        """Verify _state_lock exists and is initialized."""
        fsm = LoopFSM()
        assert hasattr(fsm, "_state_lock")
        assert fsm.state_lock is not None

    def test_state_lock_is_threading_rlock(self):
        """Verify state lock is threading.RLock (reentrant-safe)."""
        import _thread
        import threading

        fsm = LoopFSM()
        # threading.RLock() returns _thread.RLock instance
        assert isinstance(fsm._state_lock, _thread.RLock)

    def test_concurrent_transitions_are_serialized(self):
        """Verify concurrent transitions are serialized by lock."""
        fsm = LoopFSM()

        async def transition_multiple():
            tasks = [asyncio.to_thread(fsm.transition_to, LoopState.PLAN) for _ in range(3)]
            await asyncio.gather(*tasks)

        asyncio.run(transition_multiple())

        # Only one transition should have succeeded
        # State should be PLAN (the first valid transition from INTAKE)
        assert fsm.current_state == LoopState.PLAN

    def test_state_mutations_protected_by_lock(self):
        """Verify state mutations are protected by lock."""
        fsm = LoopFSM()
        original_state = fsm.current_state

        # Transition using lock
        result = fsm.transition_to(LoopState.PLAN)
        assert result.is_ok()
        assert fsm.current_state != original_state

    def test_reset_protected_by_lock(self):
        """Verify reset() is protected by lock."""
        fsm = LoopFSM()
        fsm.transition_to(LoopState.PLAN)
        fsm.transition_to(LoopState.ACT)

        # Reset should be safe even if called from multiple threads
        fsm.reset()
        assert fsm.current_state == LoopState.INTAKE
        assert fsm.iteration_count == 0
        assert fsm.retry_count == 0


class TestRunLoopAsync:
    """Test run_loop_async() method."""

    def test_run_loop_async_exists(self):
        """Verify run_loop_async() method exists."""
        fsm = LoopFSM()
        assert hasattr(fsm, "run_loop_async")
        assert asyncio.iscoroutinefunction(fsm.run_loop_async)

    def test_run_loop_async_is_awaitable(self):
        """Verify run_loop_async() returns awaitable."""
        fsm = LoopFSM()

        # Override _execute_action_async to not raise exceptions
        async def mock_execute_action():
            pass

        fsm._execute_action_async = mock_execute_action

        # Override check_goal_achievement_async to return True immediately
        async def mock_check_goal():
            return True

        fsm.check_goal_achievement_async = mock_check_goal

        result = asyncio.run(fsm.run_loop_async({"goal": "test"}))
        assert result == LoopState.DONE

    def test_run_loop_async_transitions_through_states(self):
        """Verify run_loop_async transitions through states correctly."""
        fsm = LoopFSM()

        # Override methods to avoid blocking
        async def mock_execute_action():
            pass

        fsm._execute_action_async = mock_execute_action

        async def mock_check_goal():
            return True

        fsm.check_goal_achievement_async = mock_check_goal

        final_state = asyncio.run(fsm.run_loop_async({"goal": "test"}))

        # Should have gone: INTAKE -> PLAN -> ACT -> SYNTHESIZE -> DONE
        assert final_state == LoopState.DONE
        assert fsm.iteration_count == 1

    def test_run_loop_async_respects_max_iterations(self):
        """Verify run_loop_async respects MAX_ITERATIONS."""
        fsm = LoopFSM()

        # Override to always return False for goal check
        async def mock_execute_action():
            pass

        fsm._execute_action_async = mock_execute_action

        async def mock_check_goal():
            return False

        fsm.check_goal_achievement_async = mock_check_goal

        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(fsm.run_loop_async({"goal": "test"}))

        assert "Infinite loop prevention" in str(exc_info.value)
        assert "exceeds MAX_ITERATIONS" in str(exc_info.value)


class TestParallelToolExecution:
    """Test parallel tool execution within ACT phase."""

    def test_parallel_action_execution_allowed(self):
        """Verify parallel tool execution within ACT phase works correctly."""
        fsm = LoopFSM()

        # Track execution order
        execution_log = []

        async def mock_parallel_execute():
            # Simulate parallel tool execution
            tasks = [asyncio.sleep(0.01) for _ in range(3)]
            await asyncio.gather(*tasks)
            execution_log.append("parallel_executed")

        fsm._execute_action_async = mock_parallel_execute

        async def mock_check_goal():
            return True

        fsm.check_goal_achievement_async = mock_check_goal

        asyncio.run(fsm.run_loop_async({"goal": "test"}))

        # Parallel execution should have happened
        assert "parallel_executed" in execution_log

    def test_state_consistency_during_parallel_execution(self):
        """Verify state remains consistent during parallel tool execution."""
        fsm = LoopFSM()

        # Track if state was mutated during parallel execution
        state_check = {"consistent": True}

        async def mock_parallel_execute():
            # Check that state is ACT during execution
            if fsm.current_state != LoopState.ACT:
                state_check["consistent"] = False

            # Simulate parallel operations
            tasks = [asyncio.sleep(0.01) for _ in range(3)]
            await asyncio.gather(*tasks)

            # Check state again
            if fsm.current_state != LoopState.ACT:
                state_check["consistent"] = False

        fsm._execute_action_async = mock_parallel_execute

        async def mock_check_goal():
            return True

        fsm.check_goal_achievement_async = mock_check_goal

        asyncio.run(fsm.run_loop_async({"goal": "test"}))

        # State should have been consistent
        assert state_check["consistent"]

    def test_state_transitions_still_serialized_with_parallel_execution(self):
        """Verify state transitions are serialized even with parallel tool execution."""
        fsm = LoopFSM()

        async def mock_parallel_execute():
            # Simulate parallel tool execution
            tasks = [asyncio.sleep(0.01) for _ in range(2)]
            await asyncio.gather(*tasks)

        fsm._execute_action_async = mock_parallel_execute

        async def mock_check_goal():
            # Goal achieved after 2 iterations
            return fsm.iteration_count >= 2

        fsm.check_goal_achievement_async = mock_check_goal

        asyncio.run(fsm.run_loop_async({"goal": "test"}))

        # Should have executed 2 full cycles
        assert fsm.iteration_count == 2
        assert fsm.current_state == LoopState.DONE


class TestAsyncErrorHandling:
    """Test async error handling with state locking."""

    def test_action_failure_triggers_retry_in_async(self):
        """Verify action failure triggers retry in async execution."""
        fsm = LoopFSM(max_retries=2)

        fail_count = {"count": 0}

        async def mock_failing_action():
            fail_count["count"] += 1
            if fail_count["count"] < 2:
                raise RuntimeError("Tool failure")

        fsm._execute_action_async = mock_failing_action

        async def mock_check_goal():
            return True

        fsm.check_goal_achievement_async = mock_check_goal

        asyncio.run(fsm.run_loop_async({"goal": "test"}))

        # Should have retried and succeeded
        assert fail_count["count"] == 2
        assert fsm.current_state == LoopState.DONE
        assert fsm.retry_count == 0  # Reset on success

    def test_max_retries_exceeded_in_async(self):
        """Verify max retries exceeded in async execution raises error."""
        fsm = LoopFSM(max_retries=1)

        async def mock_failing_action():
            raise RuntimeError("Persistent tool failure")

        fsm._execute_action_async = mock_failing_action

        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(fsm.run_loop_async({"goal": "test"}))

        assert "failed after 1 retries" in str(exc_info.value)
        # FSM stays in SYNTHESIZE state (doesn't transition to FAILED since
        # SYNTHESIZE -> FAILED is not a valid transition)
        assert fsm.last_error is not None
        assert "Persistent tool failure" in fsm.last_error
