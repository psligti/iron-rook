"""Real-time streaming infrastructure for PR review progress updates."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncGenerator, Any, Dict, List, Optional, Literal

import pydantic as pd

from iron_rook.review.contracts import ReviewOutput


logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """Types of stream events."""

    AGENT_STARTED = "agent_started"
    AGENT_PROGRESS = "agent_progress"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    REVIEW_COMPLETE = "review_complete"


class StreamEvent(pd.BaseModel):
    """Base event for streaming updates."""

    event_type: StreamEventType
    agent_name: str
    timestamp: datetime = pd.Field(default_factory=datetime.now)
    data: Dict[str, Any] = pd.Field(default_factory=dict)

    model_config = pd.ConfigDict(extra="forbid")


class ProgressEvent(StreamEvent):
    """Event for agent progress updates."""

    event_type: Literal[StreamEventType.AGENT_PROGRESS] = StreamEventType.AGENT_PROGRESS
    data: Dict[str, Any] = pd.Field(
        default_factory=lambda: {
            "percent_complete": 0,
            "current_step": "",
            "total_steps": 0,
        }
    )


class ResultEvent(StreamEvent):
    """Event for agent completion with result."""

    event_type: Literal[StreamEventType.AGENT_COMPLETED] = StreamEventType.AGENT_COMPLETED
    result: ReviewOutput


class ErrorEvent(StreamEvent):
    """Event for agent errors."""

    event_type: Literal[StreamEventType.AGENT_ERROR] = StreamEventType.AGENT_ERROR
    error: str


def calculate_progress(
    completed: int, total: int, started_at: datetime
) -> Dict[str, Any]:
    """Calculate progress metadata.

    Args:
        completed: Number of completed agents
        total: Total number of agents
        started_at: When the review started

    Returns:
        Dict with percent_complete, agents_completed, total_agents, eta_seconds
    """
    percent_complete = (completed / total) * 100 if total > 0 else 0
    elapsed = datetime.now() - started_at

    if completed > 0 and total > completed:
        avg_time_per_agent = elapsed.total_seconds() / completed
        eta_seconds = avg_time_per_agent * (total - completed)
    elif completed == total and total > 0:
        eta_seconds = 0.0
    else:
        eta_seconds = None

    return {
        "percent_complete": round(percent_complete, 2),
        "agents_completed": completed,
        "total_agents": total,
        "eta_seconds": eta_seconds,
    }


@dataclass
class StreamHandle:
    """Handle for managing an active stream."""

    manager: "ReviewStreamManager"
    _closed: bool = field(default=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


class ReviewStreamManager:
    """Manages real-time streaming of PR review progress."""

    def __init__(self, buffer_size: int = 1000) -> None:
        """Initialize stream manager.

        Args:
            buffer_size: Maximum number of events to buffer
        """
        self._buffer_size = buffer_size
        self._queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=buffer_size)
        self._consumers: List[asyncio.Queue[StreamEvent]] = []
        self._total_agents: int = 0
        self._completed_agents: int = 0
        self._started_at: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def start_stream(self) -> StreamHandle:
        """Start a new stream and return a handle.

        Returns:
            StreamHandle for managing the stream lifecycle
        """
        async with self._lock:
            self._total_agents = 0
            self._completed_agents = 0
            self._started_at = datetime.now()

        return StreamHandle(manager=self)

    async def emit_progress(
        self, agent_name: str, status: str, data: dict
    ) -> None:
        """Emit a progress event for an agent.

        Args:
            agent_name: Name of the agent
            status: Current status message
            data: Additional progress data
        """
        event = ProgressEvent(agent_name=agent_name, data={"status": status, **data})
        await self._broadcast(event)

    async def emit_result(
        self, agent_name: str, result: ReviewOutput
    ) -> None:
        """Emit a result event when an agent completes.

        Args:
            agent_name: Name of the agent
            result: ReviewOutput from the agent
        """
        async with self._lock:
            self._completed_agents += 1

        event = ResultEvent(agent_name=agent_name, result=result)
        await self._broadcast(event)

    async def emit_error(self, agent_name: str, error: str) -> None:
        """Emit an error event when an agent fails.

        Args:
            agent_name: Name of the agent
            error: Error message
        """
        event = ErrorEvent(agent_name=agent_name, error=error)
        await self._broadcast(event)

    async def subscribe(self) -> AsyncGenerator[StreamEvent, None]:
        """Subscribe to stream events as an async generator.

        Yields:
            StreamEvent objects as they are emitted

        Example:
            async for event in manager.subscribe():
                print(f"{event.agent_name}: {event.event_type}")
        """
        consumer_queue: asyncio.Queue[StreamEvent] = asyncio.Queue()

        async with self._lock:
            self._consumers.append(consumer_queue)
            while not self._queue.empty():
                try:
                    buffered_event = self._queue.get_nowait()
                    consumer_queue.put_nowait(buffered_event)
                except asyncio.QueueEmpty:
                    break

        try:
            while True:
                event = await consumer_queue.get()
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            raise
        finally:
            async with self._lock:
                if consumer_queue in self._consumers:
                    self._consumers.remove(consumer_queue)

    async def _broadcast(self, event: StreamEvent) -> None:
        """Broadcast event to all consumers.

        Args:
            event: Event to broadcast
        """
        if not self._consumers:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                oldest = self._queue.get_nowait()
                logger.warning(
                    f"Buffer full, dropped oldest event: {oldest.event_type} from {oldest.agent_name}"
                )
                self._queue.put_nowait(event)
            return

        for consumer_queue in self._consumers:
            try:
                consumer_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    f"Consumer queue full, dropped event: {event.event_type} from {event.agent_name}"
                )
