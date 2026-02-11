"""Agent state enumeration for review agents.

This module provides AgentState enum for tracking the lifecycle state
of review agents, following dawn-kestrel conventions with lowercase
string values.
"""

from enum import Enum


class AgentState(Enum):
    """Review agent lifecycle states.

    States represent the execution phase of a review agent:
    - IDLE: Agent is initialized and ready
    - INITIALIZING: Agent is preparing for execution (setting up state, loading prompts)
    - RUNNING: Agent is actively executing its review logic
    - READY: Agent has completed execution and has results ready
    - COMPLETED: Agent has finished successfully and returned results
    - FAILED: Agent encountered an error during execution

    Enum values are lowercase strings for consistency with dawn-kestrel conventions.
    """

    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    READY = "ready"
    COMPLETED = "completed"
    FAILED = "failed"
