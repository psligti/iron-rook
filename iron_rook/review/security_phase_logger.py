"""Phase-specific logging infrastructure for security reviewer.

Provides structured, colored logging for security review FSM phases including
thinking output and state transitions.
"""

from __future__ import annotations

import logging
from typing import Literal

from rich.console import Console
from rich.text import Text


class SecurityPhaseLogger:
    """Logger for security review phase-specific output with colored formatting.

    Provides methods for logging thinking output during phase execution and
    FSM state transitions with phase-specific colors for easy visual tracking.

    Example:
        >>> logger = SecurityPhaseLogger()
        >>> logger.log_thinking("INTAKE", "Analyzing PR changes")
        [INTAKE] Analyzing PR changes
        >>> logger.log_transition("intake", "plan_todos")
        [TRANSITION] intake → plan_todos
    """

    PHASE_COLORS: dict[str, str] = {
        "INTAKE": "bold cyan",
        "PLAN_TODOS": "bold green",
        "DELEGATE": "bold yellow",
        "COLLECT": "bold magenta",
        "CONSOLIDATE": "bold blue",
        "EVALUATE": "bold red",
        "DONE": "bold white",
        "STOPPED_BUDGET": "bold orange3",
        "STOPPED_HUMAN": "bold orange3",
        "TRANSITION": "bold gray",
    }

    def __init__(self, enable_color: bool = True) -> None:
        """Initialize the phase logger.

        Args:
            enable_color: Enable colored console output using Rich. Default: True.
        """
        self._enable_color = enable_color
        self._console = Console(force_terminal=enable_color)
        self._logger = logging.getLogger("security.thinking")
        self._logger.setLevel(logging.DEBUG)

    def log_thinking(self, phase: str, message: str) -> None:
        """Log thinking output for a specific phase with phase-specific formatting.

        Args:
            phase: The phase name (e.g., "INTAKE", "PLAN_TODOS"). Used for color selection.
            message: The thinking message to log.

        Example:
            >>> logger = SecurityPhaseLogger()
            >>> logger.log_thinking("INTAKE", "Analyzing PR changes for security surfaces")
            [INTAKE] Analyzing PR changes for security surfaces
        """
        phase_key = phase.upper()
        color = self.PHASE_COLORS.get(phase_key, "white")

        if self._enable_color:
            phase_text = Text(f"[{phase}] ", style=color)
            message_text = Text(message)
            self._console.print(phase_text + message_text)

            self._logger.debug("[%s] %s", phase, message)
        else:
            self._logger.info("[%s] %s", phase, message)

    def log_transition(self, from_state: str, to_state: str) -> None:
        """Log FSM state transition with clear visual formatting.

        Args:
            from_state: The source state (e.g., "intake", "plan_todos").
            to_state: The target state (e.g., "plan_todos", "delegate").

        Example:
            >>> logger = SecurityPhaseLogger()
            >>> logger.log_transition("intake", "plan_todos")
            [TRANSITION] intake → plan_todos
        """
        if self._enable_color:
            arrow = Text(" → ", style="bold dim")
            from_text = Text(from_state, style="dim")
            to_text = Text(to_state, style="bold")
            label = Text("[TRANSITION] ", style=self.PHASE_COLORS["TRANSITION"])

            self._console.print(label + from_text + arrow + to_text)

            self._logger.info("[TRANSITION] %s → %s", from_state, to_state)
        else:
            self._logger.info("[TRANSITION] %s → %s", from_state, to_state)

    def get_phase_color(self, phase: str) -> str:
        """Get the color style for a given phase.

        Args:
            phase: The phase name (e.g., "INTAKE", "PLAN_TODOS").

        Returns:
            The Rich color style string for the phase.

        Example:
            >>> logger = SecurityPhaseLogger()
            >>> color = logger.get_phase_color("INTAKE")
            >>> color
            'bold cyan'
        """
        phase_key = phase.upper()
        return self.PHASE_COLORS.get(phase_key, "white")

    def get_valid_phases(self) -> list[str]:
        """Get list of valid phase names with their color styles.

        Returns:
            List of phase names recognized by the logger.

        Example:
            >>> logger = SecurityPhaseLogger()
            >>> phases = logger.get_valid_phases()
            >>> 'INTAKE' in phases
            True
        """
        return list(self.PHASE_COLORS.keys())
