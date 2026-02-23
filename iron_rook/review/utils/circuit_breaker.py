"""Circuit breaker implementation for resilience patterns.

This module provides a circuit breaker that protects services from cascading
failures by temporarily blocking requests when failure thresholds are exceeded.

CRITICAL: Uses asyncio.Lock (not threading.Lock) for async safety.
CRITICAL: Uses time.monotonic (not datetime.now) for reliable timing.
"""

import asyncio
import time
from typing import List

from iron_rook.review.contracts import CircuitBreakerConfig, CircuitState


class CircuitBreaker:
    """Circuit breaker with sliding window failure counting.

    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Circuit tripped, requests are blocked
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    The circuit breaker uses a sliding window to count failures within
    a configurable time window, rather than fixed buckets.
    """

    def __init__(self, config: CircuitBreakerConfig | None = None):
        """Initialize the circuit breaker.

        Args:
            config: Configuration for circuit breaker behavior. Uses defaults if None.
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()  # CRITICAL: asyncio.Lock, not threading.Lock
        self._failures: List[float] = []  # timestamps for sliding window
        self._successes: int = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Return the current circuit breaker state."""
        return self._state

    async def can_execute(self) -> bool:
        """Check if execution is allowed based on circuit state.

        Returns:
            True if execution is allowed, False if circuit is open.

        State transitions:
        - CLOSED: Always returns True
        - OPEN: Returns False until reset_timeout elapsed, then transitions to HALF_OPEN
        - HALF_OPEN: Returns True (allows sampling)
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.config.reset_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._successes = 0
                    return True
                return False
            return True  # HALF_OPEN allows sampling

    async def record_success(self) -> None:
        """Record a successful operation.

        In HALF_OPEN state, counts toward success_threshold to transition to CLOSED.
        """
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._successes += 1
                if self._successes >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failures.clear()
                    self._successes = 0

    async def record_failure(self) -> None:
        """Record a failed operation.

        Implements sliding window by storing failure timestamps and filtering
        out those outside the window_seconds.

        State transitions:
        - HALF_OPEN: Immediately transitions back to OPEN
        - CLOSED: Transitions to OPEN if failure_threshold exceeded in window
        """
        async with self._lock:
            now = time.monotonic()  # CRITICAL: monotonic, not datetime
            self._failures.append(now)
            # Sliding window: keep only failures in last window_seconds
            cutoff = now - self.config.window_seconds
            self._failures = [t for t in self._failures if t > cutoff]

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._successes = 0
            elif len(self._failures) >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                self._last_failure_time = now
