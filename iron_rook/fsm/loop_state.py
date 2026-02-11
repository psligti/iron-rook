"""Loop state enumeration for FSM-based orchestration.

This module provides LoopState enum for tracking the state of a review loop
in the FSM-based orchestrator.
"""

from enum import Enum


class LoopState(Enum):
    """Review loop states for FSM-based orchestrator.

    States represent the phases of a review loop execution:
    - INTAKE: Initial phase, gathering and validating inputs
    - PLAN: Planning phase, determining execution strategy
    - ACT: Execution phase, running the planned actions
    - SYNTHESIZE: Synthesis phase, combining and processing results
    - DONE: Loop completed successfully
    - FAILED: Loop encountered an error
    - STOPPED: Loop was stopped externally

    Enum values are lowercase strings for consistency with dawn-kestrel conventions.
    """

    INTAKE = "intake"
    PLAN = "plan"
    ACT = "act"
    SYNTHESIZE = "synthesize"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"
