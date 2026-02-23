"""Tests for CircuitBreaker implementation."""

import asyncio
import pytest

from iron_rook.review.contracts import CircuitBreakerConfig, CircuitState
from iron_rook.review.utils.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    """Test suite for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self):
        cb = CircuitBreaker()
        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_transitions_to_open_after_threshold(self):
        config = CircuitBreakerConfig(failure_threshold=3, window_seconds=60.0)
        cb = CircuitBreaker(config)

        for _ in range(3):
            await cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        config = CircuitBreakerConfig(
            failure_threshold=1, reset_timeout_seconds=0.01, window_seconds=60.0
        )
        cb = CircuitBreaker(config)

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.02)

        assert await cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_after_successes(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            reset_timeout_seconds=0.01,
            window_seconds=60.0,
        )
        cb = CircuitBreaker(config)

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.02)
        await cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self):
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            reset_timeout_seconds=0.01,
            window_seconds=60.0,
        )
        cb = CircuitBreaker(config)

        await cb.record_failure()
        await asyncio.sleep(0.02)
        await cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_sliding_window_excludes_old_failures(self):
        config = CircuitBreakerConfig(
            failure_threshold=3, reset_timeout_seconds=0.01, window_seconds=0.05
        )
        cb = CircuitBreaker(config)

        await cb.record_failure()
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.06)
        assert await cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_record_success_ignored_when_closed(self):
        config = CircuitBreakerConfig(success_threshold=1)
        cb = CircuitBreaker(config)

        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_uses_default_config_when_none_provided(self):
        cb = CircuitBreaker(None)
        assert cb.config.failure_threshold == 10
        assert cb.config.success_threshold == 3
        assert cb.config.reset_timeout_seconds == 300.0
        assert cb.config.window_seconds == 300.0
