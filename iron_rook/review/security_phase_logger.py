"""Phase-specific logging infrastructure for security reviewer.

Provides structured, colored logging for security review FSM phases including
thinking output and state transitions.
"""

from __future__ import annotations

import logging
from typing import Literal

from rich.console import Console
from rich.text import Text

from iron_rook.review.contracts import ThinkingFrame, ThinkingStep
from iron_rook.review.llm_audit_logger import (
    get_trace_id,
    get_span_id,
    TraceContext,
    SpanContext,
)


class SecurityPhaseFormatter(logging.Formatter):
    """Formatter that includes trace/span IDs without duplicating log level."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = get_trace_id()
        span_id = get_span_id()

        record.trace_id = trace_id if trace_id else "-"
        record.span_id = span_id if span_id else "-"

        if trace_id and span_id:
            record.trace_info = f"[trace={trace_id} span={span_id}] "
        else:
            record.trace_info = ""

        return super().format(record)


class SecurityPhaseLogger:
    """Logger for security review phase-specific output with colored formatting.

    Provides methods for logging thinking output during phase execution and
    FSM state transitions with phase-specific colors for easy visual tracking.
    """

    PHASE_COLORS: dict[str, str] = {
        "INTAKE": "bold cyan",
        "PLAN_TODOS": "bold green",
        "ACT": "bold yellow",
        "COLLECT": "bold magenta",
        "CONSOLIDATE": "bold blue",
        "EVALUATE": "bold red",
        "DONE": "bold white",
        "STOPPED_BUDGET": "bold orange3",
        "STOPPED_HUMAN": "bold orange3",
        "TRANSITION": "bold gray",
    }

    def __init__(self, enable_color: bool = True) -> None:
        self._enable_color = enable_color
        self._console = Console(force_terminal=enable_color)
        self._logger = logging.getLogger("security.phase")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        if not self._logger.handlers:
            import sys

            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            formatter = SecurityPhaseFormatter(
                fmt="%(asctime)s %(levelname)s %(trace_info)s%(message)s",
                datefmt="%H:%M:%S",
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def log_thinking(self, phase: str, message: str) -> None:
        phase_key = phase.upper()
        color = self.PHASE_COLORS.get(phase_key, "white")

        if self._enable_color:
            phase_text = Text(f"[{phase}] ", style=color)
            message_text = Text(message)
            self._console.print(phase_text + message_text)
        else:
            self._logger.debug("[%s] %s", phase, message)

    def log_transition(self, from_state: str, to_state: str) -> None:
        if self._enable_color:
            arrow = Text(" → ", style="bold dim")
            from_text = Text(from_state, style="dim")
            to_text = Text(to_state, style="bold")
            label = Text("[TRANSITION] ", style=self.PHASE_COLORS["TRANSITION"])

            self._console.print(label + from_text + arrow + to_text)
        else:
            self._logger.info("[TRANSITION] %s → %s", from_state, to_state)

    def log_thinking_frame(self, frame: ThinkingFrame) -> None:
        if self._enable_color:
            phase_key = frame.state.upper()
            color = self.PHASE_COLORS.get(phase_key, "white")

            state_header = Text(f"== {frame.state.upper()} ==", style=f"bold {color}")
            self._console.print(state_header)

            if frame.goals:
                goals_label = Text("Goals:", style="bold")
                self._console.print(goals_label)
                for goal in frame.goals:
                    goal_text = Text(f"  • {goal}", style="dim")
                    self._console.print(goal_text)

            if frame.checks:
                checks_label = Text("Checks:", style="bold")
                self._console.print(checks_label)
                for check in frame.checks:
                    check_text = Text(f"  • {check}", style="dim")
                    self._console.print(check_text)

            if frame.risks:
                risks_label = Text("Risks:", style="bold")
                self._console.print(risks_label)
                for risk in frame.risks:
                    risk_text = Text(f"  • {risk}", style="red")
                    self._console.print(risk_text)

            for i, step in enumerate(frame.steps, 1):
                step_header = Text(f"Step {i} ({step.kind}):", style="bold")
                self._console.print(step_header)

                why_text = Text(f"  Why: {step.why}", style="dim")
                self._console.print(why_text)

                if step.evidence:
                    evidence_text = Text(f"  Evidence: {', '.join(step.evidence)}", style="dim")
                    self._console.print(evidence_text)

                if step.next:
                    next_text = Text(f"  Next: {step.next}", style="dim")
                    self._console.print(next_text)

                confidence_text = Text(f"  Confidence: {step.confidence}", style="dim")
                self._console.print(confidence_text)

            decision_text = Text(f"Decision: {frame.decision}", style="bold")
            self._console.print(decision_text)
        else:
            self._logger.info(
                "[%s] ThinkingFrame: goals=%d, checks=%d, risks=%d, steps=%d, decision=%s",
                frame.state,
                len(frame.goals),
                len(frame.checks),
                len(frame.risks),
                len(frame.steps),
                frame.decision,
            )

    def get_phase_color(self, phase: str) -> str:
        phase_key = phase.upper()
        return self.PHASE_COLORS.get(phase_key, "white")

    def get_valid_phases(self) -> list[str]:
        return list(self.PHASE_COLORS.keys())
