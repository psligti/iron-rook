"""LoopFSM: Finite state machine for review loop orchestration.

This module provides LoopFSM class for managing the state of a review loop
in the FSM-based orchestrator, following the dawn_kestrel AgentStateMachine pattern.
"""

import asyncio
import threading
from typing import Dict, Optional, List, Any, Literal

from dawn_kestrel.core.result import Err, Ok, Result

from iron_rook.fsm.loop_state import LoopState
from iron_rook.fsm.todo import Todo


# Default transition map: defines valid state transitions for review loop
FSM_TRANSITIONS: Dict[LoopState, set[LoopState]] = {
    LoopState.INTAKE: {LoopState.PLAN},
    LoopState.PLAN: {LoopState.ACT},
    LoopState.ACT: {
        LoopState.SYNTHESIZE,
        LoopState.DONE,
    },  # ACT can go to SYNTHESIZE (loop) or DONE (single-pass)
    LoopState.SYNTHESIZE: {LoopState.PLAN, LoopState.DONE},
    LoopState.DONE: set(),  # Terminal state
    LoopState.FAILED: set(),  # Terminal state
    LoopState.STOPPED: set(),  # Terminal state
}


class LoopFSM:
    """Finite state machine for review loop orchestration.

    Manages state transitions for a review loop with validation against
    a transition map. Uses Result pattern for explicit error handling of
    invalid transitions.

    Locking Strategy:
        - Uses threading.RLock for reentrant-safe state mutation protection
        - All state mutations (transitions, todo updates, reset) are protected by _state_lock
        - Read operations (property getters) do NOT acquire locks for performance
        - Each LoopFSM instance has its own lock instance (shared lock pattern not used)
        - RLock ensures same thread can reacquire lock without deadlock

    Attributes:
        current_state: The current LoopState of the machine.
        max_retries: Maximum number of retry attempts for failed operations.
        agent_runtime: Optional AgentRuntime for executing sub-loops.
        todos: List of Todo items tracking tasks in the loop.
        iteration_count: Number of loop iterations executed.
        transitions: Transition map defining valid state changes.

    Example:
        >>> fsm = LoopFSM(max_retries=3, agent_runtime=None)
        >>> fsm.current_state
        <LoopState.INTAKE: 'intake'>
        >>> result = fsm.transition_to(LoopState.PLAN)
        >>> result.is_ok()
        True
        >>> fsm.current_state
        <LoopState.PLAN: 'plan'>
    """

    # Maximum number of iterations to prevent infinite loops
    MAX_ITERATIONS = 10

    def __init__(
        self,
        max_retries: int = 3,
        agent_runtime: Optional[Any] = None,
        transitions: Optional[Dict[LoopState, set[LoopState]]] = None,
    ):
        """Initialize loop state machine.

        Args:
            max_retries: Maximum number of retry attempts (default: 3).
            agent_runtime: Optional AgentRuntime for executing sub-loops.
            transitions: Optional custom transition map. Defaults to FSM_TRANSITIONS.
        """
        self._max_retries = max_retries
        self._agent_runtime = agent_runtime
        self._current_state = LoopState.INTAKE
        self._todos: List[Todo] = []
        self._iteration_count = 0
        self._transitions = transitions if transitions is not None else FSM_TRANSITIONS
        self._context: Dict[str, Any] = {}
        self._retry_count = 0
        self._last_error: Optional[str] = None
        self._state_lock = threading.RLock()  # RLock for reentrant-safe state mutations

    @property
    def current_state(self) -> LoopState:
        """Get the current state (read-only)."""
        return self._current_state

    @property
    def max_retries(self) -> int:
        """Get the maximum retry count (read-only)."""
        return self._max_retries

    @property
    def agent_runtime(self) -> Optional[Any]:
        """Get the agent runtime (read-only)."""
        return self._agent_runtime

    @property
    def todos(self) -> List[Todo]:
        """Get the list of todos (read-only)."""
        return self._todos

    @property
    def iteration_count(self) -> int:
        """Get the iteration count (read-only)."""
        return self._iteration_count

    @property
    def transitions(self) -> Dict[LoopState, set[LoopState]]:
        """Get the transition map (read-only)."""
        return self._transitions

    @property
    def context(self) -> Dict[str, Any]:
        """Get the context data (read-only)."""
        return self._context

    @property
    def retry_count(self) -> int:
        """Get the current retry count (read-only)."""
        return self._retry_count

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message (read-only)."""
        return self._last_error

    @property
    def state_lock(self) -> threading.RLock:
        """Get the state lock for protecting transitions (read-only)."""
        return self._state_lock

    def transition_to(self, next_state: LoopState) -> Result[LoopState]:
        """Attempt to transition to a new state.

        Validates the transition against the transition map. Returns:
        - Ok(next_state): Transition was successful, state changed
        - Err(error): Invalid transition, state unchanged

        State transitions are serialized using _state_lock to prevent concurrent mutations.

        Args:
            next_state: The target state to transition to.

        Returns:
            Result[LoopState]: Ok with new state, or Err with error message.

        Example:
            >>> fsm = LoopFSM()
            >>> result = fsm.transition_to(LoopState.PLAN)
            >>> result.is_ok()
            True
            >>> bad_result = fsm.transition_to(LoopState.DONE)
            >>> bad_result.is_err()
            True
        """
        with self._state_lock:
            if self._is_valid_transition(self._current_state, next_state):
                self._current_state = next_state
                return Ok(next_state)

            error_msg = (
                f"Invalid transition: {self._current_state.value} -> {next_state.value}. "
                f"Valid transitions from {self._current_state.value}: "
                f"{[s.value for s in self._transitions.get(self._current_state, set())]}"
            )
            return Err(error=error_msg, code="INVALID_TRANSITION")

    def _is_valid_transition(self, from_state: LoopState, to_state: LoopState) -> bool:
        """Check if a transition is valid according to the transition map.

        Args:
            from_state: Source state.
            to_state: Target state.

        Returns:
            True if transition is valid, False otherwise.
        """
        valid_targets = self._transitions.get(from_state, set())
        return to_state in valid_targets

    def can_transition_to(self, next_state: LoopState) -> bool:
        """Check if a transition would be valid without changing state.

        Useful for preflight validation or UI state checking.

        Args:
            next_state: The target state to check.

        Returns:
            True if transition would be valid, False otherwise.
        """
        return self._is_valid_transition(self._current_state, next_state)

    def reset(self) -> None:
        """Reset the state machine to INTAKE state.

        This is a convenience method for testing or recovery scenarios.
        Clears iteration count, retry count, todo list, and error state
        while preserving max_retries and agent_runtime settings.
        State mutations are serialized using _state_lock.
        """
        with self._state_lock:
            self._current_state = LoopState.INTAKE
            self._todos = []
            self._iteration_count = 0
            self._context = {}
            self._retry_count = 0
            self._last_error = None

    def add_todo(self, description: str, priority: int = 5) -> Todo:
        """Add a new todo item to loop.

        State mutations are serialized using _state_lock.

        Args:
            description: Description of todo item.
            priority: Numeric priority (higher values = higher priority). Default: 5.

        Returns:
            The newly created Todo object.
        """
        import uuid

        todo = Todo(
            id=str(uuid.uuid4())[:8],
            description=description,
            priority=priority,
            status="pending",
        )
        with self._state_lock:
            self._todos.append(todo)
        return todo

    def update_todo_status(
        self, todo: Todo, status: Literal["pending", "in_progress", "done", "failed"]
    ) -> None:
        """Update the status of an existing todo item.

        State mutations are serialized using _state_lock.

        Args:
            todo: The Todo object to update.
            status: The new status value ("pending", "in_progress", "done", or "failed").
        """
        with self._state_lock:
            todo.status = status

    def clear_todos(self) -> None:
        """Remove all todo items from the loop.

        State mutations are serialized using _state_lock.
        """
        with self._state_lock:
            self._todos = []

    def _execute_action(self) -> None:
        """Execute the action for the current ACT phase.

        This method should be overridden in subclasses to implement actual
        action execution logic. It can raise exceptions to indicate tool failures.

        Raises:
            RuntimeError: If action execution fails.
        """
        # Placeholder for action execution logic
        # In a real implementation, this would:
        # - Execute planned tools/actions
        # - Update context with results
        # - Raise exceptions on tool failures
        pass

    def check_goal_achievement(self) -> bool:
        """Check if the loop goal has been achieved.

        Uses LLM to evaluate current progress and determine if the original goal
        has been achieved. Considers todo status and context data.

        Returns:
            True if goal is achieved, False otherwise.
        """
        import logging
        import asyncio

        logger = logging.getLogger(__name__)

        # Build prompt with todos status and context
        todos_summary = self._build_todos_summary()
        context_summary = self._build_context_summary()

        system_prompt = """You are a goal evaluation assistant. Determine if a task goal has been achieved.

Analyze the provided progress information and respond with exactly one word:
- "True" if the goal has been achieved
- "False" if the goal has not been achieved

Consider:
- Are all todos completed?
- Has the stated goal in the context been accomplished?
- Is there remaining work to be done?"""

        # Use SimpleReviewAgentRunner for LLM call (wrap async call)
        try:
            from dawn_kestrel.core.harness import SimpleReviewAgentRunner

            async def _make_llm_call() -> str:
                runner = SimpleReviewAgentRunner(
                    agent_name="goal_evaluator",
                    allowed_tools=[],
                )
                return await runner.run_with_retry(system_prompt, context_summary)

            response_text = asyncio.run(_make_llm_call())
            logger.info(f"Goal achievement check response: {response_text.strip()}")

            # Parse response for boolean
            return self._parse_goal_response(response_text)

        except Exception as e:
            logger.error(f"LLM call failed during goal achievement check: {e}")
            # Treat LLM errors as "goal not achieved"
            return False

    def _build_todos_summary(self) -> str:
        """Build a summary of todos status.

        Returns:
            Formatted string showing todos and their status.
        """
        if not self._todos:
            return "No todos defined."

        summary_parts = []
        for todo in self._todos:
            summary_parts.append(f"- {todo.description} (status: {todo.status})")

        return "\n".join(summary_parts)

    def _build_context_summary(self) -> str:
        """Build a summary of context data.

        Returns:
            Formatted string showing key context information.
        """
        if not self._context:
            return "No context data available."

        summary_parts = []
        for key, value in self._context.items():
            summary_parts.append(f"- {key}: {value}")

        return "\n".join(summary_parts)

    def _parse_goal_response(self, response_text: str) -> bool:
        """Parse LLM response to extract boolean.

        Args:
            response_text: The LLM response text.

        Returns:
            True if response indicates goal achieved, False otherwise.
        """
        response_lower = response_text.strip().lower()

        # Direct boolean matches
        if response_lower == "true":
            return True
        if response_lower == "false":
            return False

        # Look for patterns indicating achievement
        goal_achieved_patterns = [
            "yes",
            "achieved",
            "complete",
            "completed",
            "done",
            "success",
            "successful",
        ]

        goal_not_achieved_patterns = [
            "no",
            "not achieved",
            "incomplete",
            "not complete",
            "pending",
            "in progress",
            "more work",
        ]

        for pattern in goal_achieved_patterns:
            if pattern in response_lower:
                return True

        for pattern in goal_not_achieved_patterns:
            if pattern in response_lower:
                return False

        # Default: if unclear, assume not achieved
        return False

    def run_loop(self, context: Dict[str, Any]) -> None:
        """Run the main loop that orchestrates PLAN → ACT → SYNTHESIZE cycle.

        Executes the loop until the goal is achieved or MAX_ITERATIONS is reached.
        Context is stored across iterations and can be accessed via the context property.

        Args:
            context: Initial context dictionary containing loop data.

        Raises:
            RuntimeError: If iteration_count exceeds MAX_ITERATIONS (infinite loop prevention).
            RuntimeError: If state transition fails during loop execution.

        Example:
            >>> fsm = LoopFSM()
            >>> fsm.run_loop({"goal": "review changes", "files": ["src/main.py"]})
            >>> fsm.current_state
            <LoopState.DONE: 'done'>
            >>> fsm.iteration_count
            2
        """
        # Store initial context
        self._context = context

        # Start loop: transition from INTAKE to PLAN
        result = self.transition_to(LoopState.PLAN)
        if result.is_err():
            err: Err[LoopState] = result  # type: ignore[assignment]
            raise RuntimeError(f"Failed to transition to PLAN: {err.error}")

        # Main loop: PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
        while True:
            # Increment iteration count at start of each cycle
            self._iteration_count += 1

            # Infinite loop prevention
            if self._iteration_count > self.MAX_ITERATIONS:
                raise RuntimeError(
                    f"Infinite loop prevention: iteration_count ({self._iteration_count}) "
                    f"exceeds MAX_ITERATIONS ({self.MAX_ITERATIONS})"
                )

            # Execute PLAN → ACT → SYNTHESIZE cycle
            # PLAN → ACT
            result = self.transition_to(LoopState.ACT)
            if result.is_err():
                err: Err[LoopState] = result  # type: ignore[assignment]
                raise RuntimeError(f"Failed to transition to ACT: {err.error}")

            # Execute action with retry logic
            action_success = False
            while self._retry_count <= self._max_retries:
                try:
                    self._execute_action()
                    action_success = True
                    self._retry_count = 0  # Reset retry count on success
                    break
                except Exception as e:
                    self._retry_count += 1
                    self._last_error = str(e)

                    if self._retry_count >= self._max_retries:
                        # Max retries exceeded, need to transition to FAILED
                        # Since ACT -> FAILED is not a valid transition, we must go:
                        # ACT -> SYNTHESIZE -> FAILED
                        break  # Break retry loop to proceed to SYNTHESIZE

            # ACT → SYNTHESIZE (always transition after action phase)
            result = self.transition_to(LoopState.SYNTHESIZE)
            if result.is_err():
                err: Err[LoopState] = result  # type: ignore[assignment]
                raise RuntimeError(f"Failed to transition to SYNTHESIZE: {err.error}")

            # Check if max retries was exceeded during action execution
            if self._retry_count >= self._max_retries:
                # Transition to FAILED state
                # Since SYNTHESIZE -> FAILED is not in transition map, just raise error
                raise RuntimeError(
                    f"Action failed after {self._max_retries} retries. "
                    f"Last error: {self._last_error}"
                )

            # After SYNTHESIZE, check if goal is achieved
            # If achieved, transition to DONE; otherwise, loop back to PLAN
            if self.check_goal_achievement():
                result = self.transition_to(LoopState.DONE)
                if result.is_err():
                    err: Err[LoopState] = result  # type: ignore[assignment]
                    raise RuntimeError(f"Failed to transition to DONE: {err.error}")
                break  # Exit loop when goal is achieved
            else:
                result = self.transition_to(LoopState.PLAN)
                if result.is_err():
                    err: Err[LoopState] = result  # type: ignore[assignment]
                    raise RuntimeError(f"Failed to transition to PLAN: {err.error}")
                continue  # Continue loop for next iteration

    async def run_loop_async(self, context: Dict[str, Any]) -> LoopState:
        """Run the main loop asynchronously.

        This is an async version of run_loop() that allows for async tool execution
        within the ACT phase while maintaining state consistency via locking.

        State transitions are serialized using _state_lock, but parallel tool execution
        within the ACT phase is allowed.

        Args:
            context: Initial context dictionary containing loop data.

        Returns:
            LoopState: The final state (DONE, FAILED, or STOPPED).

        Raises:
            RuntimeError: If iteration_count exceeds MAX_ITERATIONS (infinite loop prevention).
            RuntimeError: If state transition fails during loop execution.

        Example:
            >>> import asyncio
            >>> fsm = LoopFSM()
            >>> result = asyncio.run(fsm.run_loop_async({"goal": "review changes"}))
            >>> result
            <LoopState.DONE: 'done'>
        """
        # Store initial context
        self._context = context

        # Start loop: transition from INTAKE to PLAN
        result = self.transition_to(LoopState.PLAN)
        if result.is_err():
            err: Err[LoopState] = result  # type: ignore[assignment]
            raise RuntimeError(f"Failed to transition to PLAN: {err.error}")

        # Main loop: PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
        while True:
            # Increment iteration count at start of each cycle
            with self._state_lock:
                self._iteration_count += 1

            # Infinite loop prevention
            if self._iteration_count > self.MAX_ITERATIONS:
                raise RuntimeError(
                    f"Infinite loop prevention: iteration_count ({self._iteration_count}) "
                    f"exceeds MAX_ITERATIONS ({self.MAX_ITERATIONS})"
                )

            # Execute PLAN → ACT → SYNTHESIZE cycle
            # PLAN → ACT
            result = self.transition_to(LoopState.ACT)
            if result.is_err():
                err: Err[LoopState] = result  # type: ignore[assignment]
                raise RuntimeError(f"Failed to transition to ACT: {err.error}")

            # Execute action with retry logic
            # Note: Action execution can be parallelized here if AgentRuntime supports it
            # State mutations are still protected by _state_lock
            action_success = False
            while self._retry_count <= self._max_retries:
                try:
                    await self._execute_action_async()
                    action_success = True
                    with self._state_lock:
                        self._retry_count = 0  # Reset retry count on success
                    break
                except Exception as e:
                    with self._state_lock:
                        self._retry_count += 1
                        self._last_error = str(e)

                    if self._retry_count >= self._max_retries:
                        # Max retries exceeded, need to transition to FAILED
                        # Since ACT -> FAILED is not a valid transition, we must go:
                        # ACT -> SYNTHESIZE -> FAILED
                        break  # Break retry loop to proceed to SYNTHESIZE

            # ACT → SYNTHESIZE (always transition after action phase)
            result = self.transition_to(LoopState.SYNTHESIZE)
            if result.is_err():
                err: Err[LoopState] = result  # type: ignore[assignment]
                raise RuntimeError(f"Failed to transition to SYNTHESIZE: {err.error}")

            # Check if max retries was exceeded during action execution
            if self._retry_count >= self._max_retries:
                # Transition to FAILED state
                # Since SYNTHESIZE -> FAILED is not in transition map, just raise error
                raise RuntimeError(
                    f"Action failed after {self._max_retries} retries. "
                    f"Last error: {self._last_error}"
                )

            # After SYNTHESIZE, check if goal is achieved
            # If achieved, transition to DONE; otherwise, loop back to PLAN
            if await self.check_goal_achievement_async():
                result = self.transition_to(LoopState.DONE)
                if result.is_err():
                    err: Err[LoopState] = result  # type: ignore[assignment]
                    raise RuntimeError(f"Failed to transition to DONE: {err.error}")
                break  # Exit loop when goal is achieved
            else:
                result = self.transition_to(LoopState.PLAN)
                if result.is_err():
                    err: Err[LoopState] = result  # type: ignore[assignment]
                    raise RuntimeError(f"Failed to transition to PLAN: {err.error}")
                continue  # Continue loop for next iteration

        return self._current_state

    async def _execute_action_async(self) -> None:
        """Execute the action for the current ACT phase asynchronously.

        This method should be overridden in subclasses to implement actual
        async action execution logic. It can raise exceptions to indicate tool failures.

        Raises:
            RuntimeError: If action execution fails.
        """
        # Placeholder for async action execution logic
        # In a real implementation, this would:
        # - Execute planned tools/actions asynchronously
        # - Allow parallel tool execution via asyncio.gather()
        # - Update context with results
        # - Raise exceptions on tool failures
        pass

    async def check_goal_achievement_async(self) -> bool:
        """Check if the loop goal has been achieved asynchronously.

        Uses LLM to evaluate current progress and determine if the original goal
        has been achieved. Considers todo status and context data.

        Returns:
            True if goal is achieved, False otherwise.
        """
        # For now, delegate to sync version
        # In a real implementation, this would use async LLM calls
        return self.check_goal_achievement()

    def __repr__(self) -> str:
        """String representation showing current state."""
        return (
            f"LoopFSM(current_state={self._current_state.value}, "
            f"iteration_count={self._iteration_count}, "
            f"todos_count={len(self._todos)})"
        )
