"""LLM Audit Logger with trace/span IDs for tracking LLM I/O.

Provides dedicated logging for LLM interactions that can be easily filtered
and correlated across distributed operations using trace and span IDs.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from iron_rook.review.utils.metrics import MetricsAggregator


trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")
span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("span_id", default="")
parent_span_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "parent_span_id", default=""
)


def generate_trace_id() -> str:
    """Generate a new trace ID."""
    return uuid.uuid4().hex[:16]


def generate_span_id() -> str:
    """Generate a new span ID."""
    return uuid.uuid4().hex[:8]


def get_trace_id() -> str:
    """Get current trace ID from context."""
    return trace_id_var.get()


def get_span_id() -> str:
    """Get current span ID from context."""
    return span_id_var.get()


def set_trace_id(trace_id: str) -> contextvars.Token:
    """Set trace ID in context and return token for reset."""
    return trace_id_var.set(trace_id)


def set_span_id(span_id: str) -> contextvars.Token:
    """Set span ID in context and return token for reset."""
    return span_id_var.set(span_id)


def reset_trace_id(token: contextvars.Token) -> None:
    """Reset trace ID using token."""
    trace_id_var.reset(token)


def reset_span_id(token: contextvars.Token) -> None:
    """Reset span ID using token."""
    span_id_var.reset(token)


class TraceContext:
    """Context manager for managing trace/span IDs."""

    def __init__(self, trace_id: Optional[str] = None, span_id: Optional[str] = None):
        self._trace_id = trace_id or generate_trace_id()
        self._span_id = span_id or generate_span_id()
        self._trace_token: Optional[contextvars.Token] = None
        self._span_token: Optional[contextvars.Token] = None

    def __enter__(self) -> "TraceContext":
        self._trace_token = set_trace_id(self._trace_id)
        self._span_token = set_span_id(self._span_id)
        return self

    def __exit__(self, *args) -> None:
        if self._trace_token:
            reset_trace_id(self._trace_token)
        if self._span_token:
            reset_span_id(self._span_token)


class SpanContext:
    """Context manager for creating child spans within a trace."""

    def __init__(self, span_name: str = ""):
        self._span_name = span_name
        self._span_id = generate_span_id()
        self._parent_span_id = get_span_id()
        self._span_token: Optional[contextvars.Token] = None
        self._parent_token: Optional[contextvars.Token] = None

    def __enter__(self) -> "SpanContext":
        self._parent_token = parent_span_id_var.set(self._parent_span_id)
        self._span_token = set_span_id(self._span_id)
        return self

    def __exit__(self, *args) -> None:
        if self._span_token:
            reset_span_id(self._span_token)
        if self._parent_token:
            parent_span_id_var.reset(self._parent_token)


class LLMAuditFormatter(logging.Formatter):
    """Custom formatter that includes trace/span IDs without duplication."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = get_trace_id()
        span_id = get_span_id()

        record.trace_id = trace_id if trace_id else "-"
        record.span_id = span_id if span_id else "-"

        return super().format(record)


@dataclass
class LLMInteraction:
    """Record of a single LLM interaction."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    trace_id: str = field(default_factory=get_trace_id)
    span_id: str = field(default_factory=get_span_id)
    agent_name: str = ""
    phase: str = ""
    direction: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0
    model: str = ""
    prompt_preview: str = ""
    response_preview: str = ""


class LLMAuditLogger:
    """Dedicated logger for LLM I/O with trace/span tracking.

    Logs LLM interactions to a dedicated 'iron_rook.llm_audit' logger
    that can be easily filtered via grep or log aggregation systems.

    Example:
        >>> logger = LLMAuditLogger.get()
        >>> with TraceContext():
        ...     logger.log_request("security", "intake", system_prompt, user_message)
        ...     logger.log_response("security", "intake", response_text, duration_ms=1234)
    """

    _instance: Optional["LLMAuditLogger"] = None

    def __init__(
        self,
        enabled: bool = True,
        metrics_aggregator: Optional["MetricsAggregator"] = None,
    ) -> None:
        self._enabled = enabled
        self._metrics_aggregator = metrics_aggregator
        self._logger = logging.getLogger("iron_rook.llm_audit")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()
        self._logger.propagate = False

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)

        formatter = LLMAuditFormatter(
            fmt="%(asctime)s %(levelname)s [trace_id=%(trace_id)s span_id=%(span_id)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    @classmethod
    def get(
        cls,
        enabled: bool = True,
        metrics_aggregator: Optional["MetricsAggregator"] = None,
    ) -> "LLMAuditLogger":
        """Get or create the singleton LLMAuditLogger instance."""
        if cls._instance is None or cls._instance._enabled != enabled:
            cls._instance = LLMAuditLogger(enabled, metrics_aggregator)
        elif metrics_aggregator is not None:
            cls._instance._metrics_aggregator = metrics_aggregator
        return cls._instance

    def set_metrics_aggregator(self, aggregator: Optional["MetricsAggregator"]) -> None:
        self._metrics_aggregator = aggregator

    @staticmethod
    def compute_prompt_hash(system_prompt: str, user_message: str) -> str:
        """Compute a hash of the prompt for redundant call detection."""
        content = system_prompt + "\n" + user_message
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def log_request(
        self,
        agent_name: str,
        phase: str,
        system_prompt: str,
        user_message: str,
        model: str = "",
    ) -> None:
        """Log an LLM request with prompt details."""
        if not self._enabled:
            return

        trace_id = get_trace_id()
        span_id = get_span_id()

        prompt_preview = user_message[:200] + "..." if len(user_message) > 200 else user_message

        self._logger.debug(
            "[LLM_REQUEST] agent=%s phase=%s model=%s",
            agent_name,
            phase,
            model or "unknown",
        )
        self._logger.debug(
            "[LLM_PROMPT] trace=%s span=%s | system_prompt=%d chars | user_message=%d chars",
            trace_id,
            span_id,
            len(system_prompt),
            len(user_message),
        )
        self._logger.debug(
            "[LLM_PROMPT_PREVIEW] %s",
            prompt_preview.replace("\n", "\\n"),
        )

    def log_response(
        self,
        agent_name: str,
        phase: str,
        response: str,
        duration_ms: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        findings_count: int = 0,
        prompt_hash: str = "",
    ) -> None:
        """Log an LLM response with details."""
        if not self._enabled:
            return

        trace_id = get_trace_id()
        span_id = get_span_id()

        response_preview = response[:300] + "..." if len(response) > 300 else response

        self._logger.debug(
            "[LLM_RESPONSE] agent=%s phase=%s duration=%dms tokens=%d",
            agent_name,
            phase,
            duration_ms,
            prompt_tokens + completion_tokens,
        )
        self._logger.debug(
            "[LLM_RESPONSE_DETAIL] trace=%s span=%s | response=%d chars",
            trace_id,
            span_id,
            len(response),
        )
        self._logger.debug(
            "[LLM_RESPONSE_PREVIEW] %s",
            response_preview.replace("\n", "\\n"),
        )

        if self._metrics_aggregator:
            self._metrics_aggregator.record_call(
                agent_name=agent_name,
                phase=phase,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                findings_count=findings_count,
                prompt_hash=prompt_hash,
            )

    def log_error(
        self,
        agent_name: str,
        phase: str,
        error: Exception,
    ) -> None:
        """Log an LLM error."""
        if not self._enabled:
            return

        trace_id = get_trace_id()
        span_id = get_span_id()

        self._logger.error(
            "[LLM_ERROR] trace=%s span=%s agent=%s phase=%s error=%s: %s",
            trace_id,
            span_id,
            agent_name,
            phase,
            type(error).__name__,
            str(error),
        )

    def is_enabled(self) -> bool:
        """Check if LLM audit logging is enabled."""
        return self._enabled
