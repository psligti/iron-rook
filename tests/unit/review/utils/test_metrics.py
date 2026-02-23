import time

import pytest

from iron_rook.review.contracts import TokenMetrics, TokenReport
from iron_rook.review.utils.metrics import MetricsAggregator


class TestMetricsAggregator:
    def test_init_empty(self):
        aggregator = MetricsAggregator()
        report = aggregator.generate_report()
        assert report.total.total_tokens == 0
        assert report.total.call_count == 0
        assert len(report.by_agent) == 0
        assert len(report.by_phase) == 0
        assert len(report.efficiency_flags) == 0

    def test_record_single_call(self):
        aggregator = MetricsAggregator()
        aggregator.record_call(
            agent_name="security",
            phase="intake",
            prompt_tokens=500,
            completion_tokens=200,
            findings_count=3,
        )
        report = aggregator.generate_report()
        assert report.total.prompt_tokens == 500
        assert report.total.completion_tokens == 200
        assert report.total.total_tokens == 700
        assert report.total.call_count == 1
        assert report.total.findings_yielded == 3
        assert "security" in report.by_agent
        assert report.by_agent["security"].prompt_tokens == 500
        assert "intake" in report.by_phase

    def test_record_multiple_calls_same_agent(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 500, 200, 2)
        aggregator.record_call("security", "plan", 300, 150, 1)
        report = aggregator.generate_report()
        assert report.total.call_count == 2
        assert report.total.total_tokens == 1150
        assert report.total.findings_yielded == 3
        assert report.by_agent["security"].call_count == 2
        assert len(report.by_phase) == 2

    def test_record_calls_different_agents(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 500, 200, 3)
        aggregator.record_call("linting", "check", 100, 50, 5)
        report = aggregator.generate_report()
        assert len(report.by_agent) == 2
        assert report.by_agent["security"].findings_yielded == 3
        assert report.by_agent["linting"].findings_yielded == 5
        assert report.total.findings_yielded == 8

    def test_phase_metrics_aggregation(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0)
        aggregator.record_call("linting", "intake", 200, 100, 0)
        aggregator.record_call("docs", "intake", 150, 75, 0)
        report = aggregator.generate_report()
        assert report.by_phase["intake"].prompt_tokens == 450
        assert report.by_phase["intake"].completion_tokens == 225
        assert report.by_phase["intake"].call_count == 3

    def test_low_yield_flag_triggered(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 5000, 2000, 0)
        report = aggregator.generate_report()
        low_yield_flags = [f for f in report.efficiency_flags if "LOW_YIELD" in f]
        assert len(low_yield_flags) == 1
        assert "security" in low_yield_flags[0]

    def test_low_yield_not_flagged_with_findings(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 5000, 2000, 10)
        report = aggregator.generate_report()
        low_yield_flags = [f for f in report.efficiency_flags if "LOW_YIELD" in f]
        assert len(low_yield_flags) == 0

    def test_low_yield_flagged_for_zero_findings(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0)
        report = aggregator.generate_report()
        low_yield_flags = [f for f in report.efficiency_flags if "LOW_YIELD" in f]
        assert len(low_yield_flags) == 1
        assert "security" in low_yield_flags[0]

    def test_redundant_call_detection_within_60s(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0, prompt_hash="hash123")
        aggregator.record_call("security", "plan", 100, 50, 0, prompt_hash="hash123")
        report = aggregator.generate_report()
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(redundant_flags) == 1
        assert "1 duplicate" in redundant_flags[0]

    def test_no_redundant_flag_different_hashes(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0, prompt_hash="hash1")
        aggregator.record_call("security", "plan", 100, 50, 0, prompt_hash="hash2")
        report = aggregator.generate_report()
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(redundant_flags) == 0

    def test_no_redundant_flag_empty_hash(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0)
        aggregator.record_call("security", "plan", 100, 50, 0)
        report = aggregator.generate_report()
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(redundant_flags) == 0

    def test_redundant_call_after_60s_not_flagged(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0, prompt_hash="hash123")
        aggregator._call_hashes["hash123"] = time.monotonic() - 61
        aggregator.record_call("security", "plan", 100, 50, 0, prompt_hash="hash123")
        report = aggregator.generate_report()
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(redundant_flags) == 0

    def test_multiple_redundant_calls(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0, prompt_hash="hash1")
        aggregator.record_call("security", "plan", 100, 50, 0, prompt_hash="hash1")
        aggregator.record_call("linting", "check", 100, 50, 0, prompt_hash="hash1")
        report = aggregator.generate_report()
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(redundant_flags) == 1
        assert "2 duplicate" in redundant_flags[0]

    def test_report_generated_at_timestamp(self):
        aggregator = MetricsAggregator()
        report = aggregator.generate_report()
        assert report.generated_at != ""
        assert "T" in report.generated_at

    def test_report_returns_copies(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0)
        report1 = aggregator.generate_report()
        aggregator.record_call("linting", "check", 200, 100, 0)
        report2 = aggregator.generate_report()
        assert len(report1.by_agent) == 1
        assert len(report2.by_agent) == 2

    def test_default_findings_count_zero(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50)
        report = aggregator.generate_report()
        assert report.total.findings_yielded == 0

    def test_default_prompt_hash_empty(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 100, 50, 0)
        report = aggregator.generate_report()
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(redundant_flags) == 0

    def test_combined_flags(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 5000, 2000, 0, prompt_hash="hash1")
        aggregator.record_call("security", "plan", 5000, 2000, 0, prompt_hash="hash1")
        report = aggregator.generate_report()
        low_yield_flags = [f for f in report.efficiency_flags if "LOW_YIELD" in f]
        redundant_flags = [f for f in report.efficiency_flags if "REDUNDANT_CALLS" in f]
        assert len(low_yield_flags) == 1
        assert len(redundant_flags) == 1
        assert len(report.efficiency_flags) == 2

    def test_token_metrics_findings_per_1k_tokens(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 500, 500, 5)
        report = aggregator.generate_report()
        assert report.by_agent["security"].findings_per_1k_tokens == 5.0

    def test_zero_tokens_findings_per_1k(self):
        aggregator = MetricsAggregator()
        aggregator.record_call("security", "intake", 0, 0, 0)
        report = aggregator.generate_report()
        assert report.by_agent["security"].findings_per_1k_tokens == 0.0
