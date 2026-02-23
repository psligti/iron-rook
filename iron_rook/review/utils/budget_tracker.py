"""Budget tracking for review agent execution."""

import time
import logging
from typing import Optional, Callable, List

from iron_rook.review.contracts import BudgetConfig, BudgetSnapshot

logger = logging.getLogger(__name__)


class BudgetTracker:
    """Tracks token usage and time budgets during review execution.

    Monitors resource consumption and fires warning callbacks when
    usage crosses configured thresholds (default: 50%, 75%, 90%).

    Example:
        >>> config = BudgetConfig(max_total_tokens=1000, max_wall_time_seconds=60)
        >>> tracker = BudgetTracker(config)
        >>> tracker.add_warning_callback(lambda msg, pct: print(f"Warning: {msg}"))
        >>> tracker.record_tokens(500)  # Fires 50% warning
        >>> tracker.is_exhausted()
        False
        >>> tracker.can_afford(600)
        False
    """

    def __init__(self, config: Optional[BudgetConfig] = None):
        """Initialize budget tracker.

        Args:
            config: Budget configuration. Defaults to BudgetConfig() if not provided.
        """
        self.config = config or BudgetConfig()
        self._tokens_used = 0
        self._start_time = time.monotonic()
        self._last_warning_threshold: Optional[float] = None
        self._warning_callbacks: List[Callable[[str, float], None]] = []

    def add_warning_callback(self, callback: Callable[[str, float], None]) -> None:
        """Add a callback to be invoked when budget thresholds are crossed.

        Callbacks receive (message: str, threshold: float) where threshold
        is the decimal percentage (e.g., 0.5 for 50%).

        Args:
            callback: Function to call on threshold crossing.
        """
        self._warning_callbacks.append(callback)

    def record_tokens(self, count: int) -> None:
        """Record token usage and check for threshold warnings.

        Args:
            count: Number of tokens to record.
        """
        self._tokens_used += count
        self._check_warnings()

    def get_snapshot(self) -> BudgetSnapshot:
        """Get current budget usage snapshot.

        Returns:
            BudgetSnapshot with current usage statistics.
        """
        elapsed = time.monotonic() - self._start_time
        remaining_time = max(0, self.config.max_wall_time_seconds - elapsed)
        remaining_tokens = max(0, self.config.max_total_tokens - self._tokens_used)

        return BudgetSnapshot(
            tokens_used=self._tokens_used,
            tokens_remaining=remaining_tokens,
            time_elapsed_seconds=elapsed,
            time_remaining_seconds=remaining_time,
            last_warning_threshold=self._last_warning_threshold,
        )

    def is_exhausted(self) -> bool:
        """Check if budget is exhausted (tokens or time).

        Returns:
            True if tokens or time budget is depleted, False otherwise.
        """
        snapshot = self.get_snapshot()
        return snapshot.tokens_remaining <= 0 or snapshot.time_remaining_seconds <= 0

    def _check_warnings(self) -> None:
        """Check and fire warning callbacks if thresholds are crossed."""
        snapshot = self.get_snapshot()
        for threshold in sorted(self.config.warning_thresholds):
            if snapshot.percent_used >= threshold:
                if self._last_warning_threshold is None or threshold > self._last_warning_threshold:
                    self._last_warning_threshold = threshold
                    msg = f"Budget warning: {threshold * 100:.0f}% used ({self._tokens_used}/{self.config.max_total_tokens} tokens)"
                    logger.warning(msg)
                    for callback in self._warning_callbacks:
                        try:
                            callback(msg, threshold)
                        except Exception:
                            # Do not block on callback errors
                            logger.exception("Warning callback failed")

    def can_afford(self, estimated_tokens: int) -> bool:
        """Check if estimated tokens can be afforded within budget.

        Args:
            estimated_tokens: Estimated tokens needed.

        Returns:
            True if tokens can be afforded, False otherwise.
        """
        return (self._tokens_used + estimated_tokens) <= self.config.max_total_tokens
