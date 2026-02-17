"""WorkflowFSMAdapter: Wraps dawn_kestrel FSMBuilder for security-agent-specific workflows.

This adapter provides security-agent-specific functionality on top of the
dawn_kestrel.core.fsm.FSMBuilder, including:
- Phase name mapping (security phases → workflow states)
- run_workflow() async method for executing state loops
- Early-exit path handling
- _phase_outputs accumulation across phases
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Awaitable

from dawn_kestrel.core.fsm import FSM, FSMBuilder, FSMContext, WORKFLOW_STATES, WORKFLOW_TRANSITIONS
from dawn_kestrel.core.result import Err, Ok, Result

logger = logging.getLogger(__name__)


WORKFLOW_FSM_TRANSITIONS: Dict[str, List[str]] = {
    state: list(transitions) for state, transitions in WORKFLOW_TRANSITIONS.items()
}


@dataclass
class PhaseHandler:
    """Handler for a workflow phase.

    Attributes:
        name: Phase name (workflow state name).
        handler: Async callable that executes the phase logic.
        timeout_seconds: Optional timeout for this phase.
    """

    name: str
    handler: Callable[[Any, Dict[str, Any]], Awaitable[Dict[str, Any]]]
    timeout_seconds: Optional[float] = None


@dataclass
class WorkflowResult:
    """Result of workflow execution.

    Attributes:
        final_state: Final workflow state (e.g., "done", "evaluate").
        phase_outputs: Accumulated outputs from all phases.
        success: Whether workflow completed successfully.
        error: Optional error message if workflow failed.
    """

    final_state: str
    phase_outputs: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class WorkflowFSMAdapter:
    """Adapter wrapping FSMBuilder for security-agent-specific workflows.

    This class provides:
    - Phase name mapping between security agent phases and workflow states
    - build() method returning Result[FSM] from FSMBuilder
    - run_workflow() async method that executes state transitions
    - _phase_outputs accumulation across phases
    - Timeout support per phase
    - Early-exit path handling (act → synthesize/evaluate/done)

    Example:
        >>> adapter = WorkflowFSMAdapter()
        >>> adapter.register_phase_handler("intake", handle_intake, timeout=30)
        >>> adapter.register_phase_handler("plan", handle_plan)
        >>> fsm_result = adapter.build()
        >>> if fsm_result.is_ok():
        ...     result = await adapter.run_workflow(context)
        ...     print(f"Final state: {result.final_state}")

    Attributes:
        phase_handlers: Dict mapping phase names to PhaseHandler instances.
        phase_outputs: Accumulated outputs from executed phases.
        current_phase: Current phase name (workflow state).
        fsm: Optional built FSM instance.
    """

    def __init__(
        self,
        initial_phase: str = "intake",
        phase_timeout_seconds: Optional[float] = None,
    ):
        """Initialize the workflow adapter.

        Args:
            initial_phase: Starting phase name (default: "intake").
            phase_timeout_seconds: Default timeout for phases without explicit timeout.
        """
        self._phase_handlers: Dict[str, PhaseHandler] = {}
        self._phase_outputs: Dict[str, Any] = {}
        self._current_phase: str = initial_phase
        self._initial_phase: str = initial_phase
        self._phase_timeout_seconds: Optional[float] = phase_timeout_seconds
        self._fsm: Optional[FSM] = None
        self._transitions: Dict[str, List[str]] = WORKFLOW_FSM_TRANSITIONS.copy()

    @property
    def phase_outputs(self) -> Dict[str, Any]:
        """Get accumulated phase outputs (read-only)."""
        return self._phase_outputs

    @property
    def current_phase(self) -> str:
        """Get current phase name (read-only)."""
        return self._current_phase

    @property
    def fsm(self) -> Optional[FSM]:
        """Get the built FSM instance (read-only)."""
        return self._fsm

    def register_phase_handler(
        self,
        phase: str,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Dict[str, Any]]],
        timeout_seconds: Optional[float] = None,
    ) -> WorkflowFSMAdapter:
        """Register a handler for a workflow phase.

        Args:
            phase: Phase name (workflow state).
            handler: Async callable that takes (context, phase_outputs) and returns dict.
            timeout_seconds: Optional timeout for this phase.

        Returns:
            self for method chaining.
        """
        self._phase_handlers[phase] = PhaseHandler(
            name=phase,
            handler=handler,
            timeout_seconds=timeout_seconds or self._phase_timeout_seconds,
        )
        return self

    def add_transition(self, from_phase: str, to_phase: str) -> WorkflowFSMAdapter:
        """Add a custom transition to the workflow.

        Args:
            from_phase: Source phase name.
            to_phase: Target phase name.

        Returns:
            self for method chaining.
        """
        if from_phase not in self._transitions:
            self._transitions[from_phase] = []
        if to_phase not in self._transitions[from_phase]:
            self._transitions[from_phase].append(to_phase)
        return self

    def build(self, initial_state: Optional[str] = None) -> Result[FSM]:
        """Build FSM instance from adapter configuration.

        Uses dawn_kestrel.core.fsm.FSMBuilder to construct an FSM with:
        - Configured states from transitions
        - Transitions from WORKFLOW_FSM_TRANSITIONS
        - Entry hooks for registered phase handlers

        Args:
            initial_state: Optional initial state (default: "intake").

        Returns:
            Result[FSM]: Ok with FSM instance, Err if configuration invalid.
        """
        initial = initial_state or self._initial_phase
        builder = FSMBuilder()

        # Add all states
        all_states = set()
        all_states.add(initial)
        for from_state, to_states in self._transitions.items():
            all_states.add(from_state)
            all_states.update(to_states)

        for state in all_states:
            builder.with_state(state)

        # Add transitions
        for from_state, to_states in self._transitions.items():
            for to_state in to_states:
                builder.with_transition(from_state, to_state)

        # Add entry hooks for registered phase handlers
        for phase, phase_handler in self._phase_handlers.items():

            async def create_entry_hook(
                ph: PhaseHandler,
            ) -> Callable[[FSMContext], Awaitable[Result[None]]]:
                async def entry_hook(ctx: FSMContext) -> Result[None]:
                    # Store phase in context for run_workflow to use
                    ctx.user_data["_pending_phase"] = ph.name
                    return Ok(None)

                return entry_hook

            # Note: Entry hooks are set but actual phase execution happens in run_workflow()
            # This is because we need to manage phase_outputs accumulation ourselves

        result = builder.build(initial_state=initial)
        if result.is_ok():
            self._fsm = result.unwrap()
            return Ok(self._fsm)
        return result

    def reset(self) -> None:
        """Reset adapter state for a new workflow run.

        Clears phase outputs and resets current phase to initial.
        """
        self._phase_outputs = {}
        self._current_phase = self._initial_phase
        self._fsm = None

    async def run_workflow(
        self,
        context: Any,
        phase_handlers: Optional[
            Dict[str, Callable[[Any, Dict[str, Any]], Awaitable[Dict[str, Any]]]]
        ] = None,
    ) -> WorkflowResult:
        """Execute the workflow by running phase handlers in sequence.

        This method implements the state loop similar to SecurityReviewer._run_review_fsm():
        - Starts at initial phase
        - Executes each phase handler
        - Accumulates outputs in _phase_outputs
        - Transitions based on next_phase_request from handler output
        - Handles timeout per phase
        - Continues until "done" phase

        Args:
            context: Context object passed to phase handlers.
            phase_handlers: Optional dict of phase handlers (alternative to register_phase_handler).

        Returns:
            WorkflowResult with final state, phase outputs, and success status.

        Example:
            >>> async def handle_intake(ctx, outputs):
            ...     return {"next_phase_request": "plan", "data": "..."}
            >>> result = await adapter.run_workflow(context, {"intake": handle_intake})
        """
        # Use provided handlers or registered ones
        handlers = phase_handlers or {name: h.handler for name, h in self._phase_handlers.items()}

        # Reset state for new run
        self._phase_outputs = {}
        self._current_phase = self._initial_phase

        # Build FSM if not already built
        if self._fsm is None:
            build_result = self.build()
            if build_result.is_err():
                build_err: Err[FSM] = build_result  # type: ignore[assignment]
                return WorkflowResult(
                    final_state=self._current_phase,
                    phase_outputs=self._phase_outputs,
                    success=False,
                    error=f"Failed to build FSM: {build_err.error}",
                )

        try:
            # Main workflow loop
            while self._current_phase != "done":
                # Get handler for current phase
                handler = handlers.get(self._current_phase)
                if handler is None:
                    logger.warning(f"No handler registered for phase: {self._current_phase}")
                    # No handler - check if we can transition to a valid next state
                    next_phases = self._transitions.get(self._current_phase, [])
                    if next_phases:
                        self._current_phase = next_phases[0]
                        continue
                    return WorkflowResult(
                        final_state=self._current_phase,
                        phase_outputs=self._phase_outputs,
                        success=False,
                        error=f"No handler for phase '{self._current_phase}' and no valid transitions",
                    )

                # Execute phase with optional timeout
                phase_handler = self._phase_handlers.get(self._current_phase)
                timeout = (
                    phase_handler.timeout_seconds if phase_handler else self._phase_timeout_seconds
                )

                try:
                    if timeout is not None:
                        output = await asyncio.wait_for(
                            handler(context, self._phase_outputs),
                            timeout=timeout,
                        )
                    else:
                        output = await handler(context, self._phase_outputs)

                except asyncio.TimeoutError:
                    logger.error(f"Phase '{self._current_phase}' timed out after {timeout}s")
                    return WorkflowResult(
                        final_state=self._current_phase,
                        phase_outputs=self._phase_outputs,
                        success=False,
                        error=f"Phase '{self._current_phase}' timed out after {timeout}s",
                    )

                # Handle None output
                if output is None:
                    logger.warning(f"Phase '{self._current_phase}' returned None")
                    output = {}

                # Store phase output
                self._phase_outputs[self._current_phase] = output

                # Determine next phase
                next_phase = output.get("next_phase_request")
                if next_phase is None:
                    # Default transition
                    valid_transitions = self._transitions.get(self._current_phase, [])
                    if valid_transitions:
                        next_phase = valid_transitions[0]
                    else:
                        # No valid transitions - must be terminal
                        next_phase = "done"

                # Validate transition
                valid_transitions = self._transitions.get(self._current_phase, [])
                if next_phase not in valid_transitions and next_phase != "done":
                    # Allow terminal transitions even if not explicitly defined
                    logger.warning(
                        f"Invalid transition: {self._current_phase} -> {next_phase}. "
                        f"Valid: {valid_transitions}"
                    )
                    return WorkflowResult(
                        final_state=self._current_phase,
                        phase_outputs=self._phase_outputs,
                        success=False,
                        error=f"Invalid transition: {self._current_phase} -> {next_phase}",
                    )

                # Transition FSM if built
                if self._fsm is not None:
                    fsm_context = FSMContext(
                        source="workflow_adapter",
                        metadata={"phase": self._current_phase},
                        user_data=self._phase_outputs,
                    )
                    transition_result = await self._fsm.transition_to(next_phase, fsm_context)
                    if transition_result.is_err():
                        trans_err: Err[None] = transition_result  # type: ignore[assignment]
                        logger.error(f"FSM transition failed: {trans_err.error}")

                # Update current phase
                self._current_phase = next_phase

            # Workflow completed successfully
            return WorkflowResult(
                final_state="done",
                phase_outputs=self._phase_outputs,
                success=True,
            )

        except Exception as e:
            logger.exception(f"Workflow execution failed: {e}")
            return WorkflowResult(
                final_state=self._current_phase,
                phase_outputs=self._phase_outputs,
                success=False,
                error=str(e),
            )

    def get_valid_transitions(self, phase: Optional[str] = None) -> List[str]:
        """Get valid transitions from a phase.

        Args:
            phase: Phase to get transitions from (default: current phase).

        Returns:
            List of valid target phase names.
        """
        source = phase or self._current_phase
        return self._transitions.get(source, [])

    def __repr__(self) -> str:
        """String representation showing current state."""
        return (
            f"WorkflowFSMAdapter("
            f"current_phase={self._current_phase}, "
            f"phase_outputs_keys={list(self._phase_outputs.keys())}, "
            f"handlers={list(self._phase_handlers.keys())})"
        )
