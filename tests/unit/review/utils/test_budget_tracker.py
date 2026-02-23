import time

import pytest

from iron_rook.review.contracts import BudgetConfig
from iron_rook.review.utils.budget_tracker import BudgetTracker


class TestBudgetTracker:
    def test_init_default_config(self):
        tracker = BudgetTracker()
        assert tracker.config.max_total_tokens == 500_000
        assert tracker.config.max_wall_time_seconds == 1800

    def test_init_custom_config(self):
        config = BudgetConfig(max_total_tokens=1000, max_wall_time_seconds=60)
        tracker = BudgetTracker(config)
        assert tracker.config.max_total_tokens == 1000
        assert tracker.config.max_wall_time_seconds == 60

    def test_record_tokens(self):
        config = BudgetConfig(max_total_tokens=1000)
        tracker = BudgetTracker(config)
        tracker.record_tokens(100)
        tracker.record_tokens(50)
        snapshot = tracker.get_snapshot()
        assert snapshot.tokens_used == 150

    def test_get_snapshot(self):
        config = BudgetConfig(max_total_tokens=1000, max_wall_time_seconds=60)
        tracker = BudgetTracker(config)
        tracker.record_tokens(250)
        snapshot = tracker.get_snapshot()
        assert snapshot.tokens_used == 250
        assert snapshot.tokens_remaining == 750
        assert snapshot.time_elapsed_seconds >= 0
        assert snapshot.time_remaining_seconds <= 60

    def test_is_exhausted_tokens(self):
        config = BudgetConfig(max_total_tokens=100)
        tracker = BudgetTracker(config)
        assert not tracker.is_exhausted()
        tracker.record_tokens(100)
        assert tracker.is_exhausted()
        tracker.record_tokens(50)
        assert tracker.is_exhausted()

    def test_is_exhausted_time(self):
        config = BudgetConfig(max_total_tokens=10000, max_wall_time_seconds=0)
        tracker = BudgetTracker(config)
        time.sleep(0.01)
        assert tracker.is_exhausted()

    def test_can_afford(self):
        config = BudgetConfig(max_total_tokens=1000)
        tracker = BudgetTracker(config)
        assert tracker.can_afford(500)
        assert tracker.can_afford(1000)
        assert not tracker.can_afford(1001)
        tracker.record_tokens(600)
        assert tracker.can_afford(400)
        assert not tracker.can_afford(401)

    def test_warning_callbacks_fire_at_thresholds(self):
        warnings = []
        config = BudgetConfig(max_total_tokens=1000, warning_thresholds=[0.5, 0.75, 0.9])
        tracker = BudgetTracker(config)
        tracker.add_warning_callback(lambda msg, pct: warnings.append(pct))
        tracker.record_tokens(500)
        assert 0.5 in warnings
        tracker.record_tokens(250)
        assert 0.75 in warnings
        tracker.record_tokens(150)
        assert 0.9 in warnings

    def test_warning_callback_receives_message_and_threshold(self):
        received = []
        config = BudgetConfig(max_total_tokens=100)
        tracker = BudgetTracker(config)
        tracker.add_warning_callback(lambda msg, pct: received.append((msg, pct)))
        tracker.record_tokens(50)
        assert len(received) == 1
        assert "50%" in received[0][0]
        assert received[0][1] == 0.5

    def test_no_duplicate_warnings_at_same_threshold(self):
        warnings = []
        config = BudgetConfig(max_total_tokens=100)
        tracker = BudgetTracker(config)
        tracker.add_warning_callback(lambda msg, pct: warnings.append(pct))
        tracker.record_tokens(50)
        tracker.record_tokens(10)
        tracker.record_tokens(10)
        assert warnings.count(0.5) == 1

    def test_callback_errors_do_not_block(self):
        warnings = []
        config = BudgetConfig(max_total_tokens=100)
        tracker = BudgetTracker(config)

        def failing_callback(msg, pct):
            raise RuntimeError("Callback failed")

        tracker.add_warning_callback(failing_callback)
        tracker.add_warning_callback(lambda msg, pct: warnings.append(pct))
        tracker.record_tokens(50)
        assert 0.5 in warnings

    def test_multiple_callbacks(self):
        calls = []
        config = BudgetConfig(max_total_tokens=100)
        tracker = BudgetTracker(config)
        tracker.add_warning_callback(lambda msg, pct: calls.append("first"))
        tracker.add_warning_callback(lambda msg, pct: calls.append("second"))
        tracker.record_tokens(50)
        assert len(calls) == 2
        assert "first" in calls
        assert "second" in calls

    def test_last_warning_threshold_tracking(self):
        config = BudgetConfig(max_total_tokens=100, warning_thresholds=[0.5, 0.75, 0.9])
        tracker = BudgetTracker(config)
        assert tracker._last_warning_threshold is None
        tracker.record_tokens(50)
        assert tracker._last_warning_threshold == 0.5
        tracker.record_tokens(25)
        assert tracker._last_warning_threshold == 0.75
        tracker.record_tokens(15)
        assert tracker._last_warning_threshold == 0.9

    def test_percent_used_in_snapshot(self):
        config = BudgetConfig(max_total_tokens=1000)
        tracker = BudgetTracker(config)
        tracker.record_tokens(250)
        snapshot = tracker.get_snapshot()
        assert snapshot.percent_used == 0.25

    def test_zero_token_budget(self):
        config = BudgetConfig(max_total_tokens=0)
        tracker = BudgetTracker(config)
        snapshot = tracker.get_snapshot()
        assert snapshot.percent_used == 0

    def test_can_afford_with_zero_budget(self):
        config = BudgetConfig(max_total_tokens=0)
        tracker = BudgetTracker(config)
        assert not tracker.can_afford(1)
        assert tracker.can_afford(0)
