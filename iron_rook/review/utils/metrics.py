"""Metrics aggregator for tracking token usage and efficiency."""

import time
from datetime import datetime
from typing import Dict, List

from iron_rook.review.contracts import TokenMetrics, TokenReport


class MetricsAggregator:
    """Aggregates token usage metrics across agents and phases.

    Tracks token consumption, call counts, and findings generated
    to produce efficiency reports and detect redundant/low-yield patterns.

    Example:
        aggregator = MetricsAggregator()
        aggregator.record_call(
            agent_name="security",
            phase="intake",
            prompt_tokens=500,
            completion_tokens=200,
            findings_count=3,
            prompt_hash="abc123"
        )
        report = aggregator.generate_report()
    """

    def __init__(self):
        """Initialize the metrics aggregator."""
        self._by_agent: Dict[str, TokenMetrics] = {}
        self._by_phase: Dict[str, TokenMetrics] = {}
        self._call_hashes: Dict[str, float] = {}  # hash -> timestamp
        self._redundant_calls: List[str] = []

    def record_call(
        self,
        agent_name: str,
        phase: str,
        prompt_tokens: int,
        completion_tokens: int,
        findings_count: int = 0,
        prompt_hash: str = "",
    ) -> None:
        """Record a single agent call's token usage.

        Args:
            agent_name: Name of the agent making the call
            phase: Execution phase (e.g., "intake", "plan", "act")
            prompt_tokens: Number of tokens in the prompt
            completion_tokens: Number of tokens in the completion
            findings_count: Number of findings produced by this call
            prompt_hash: Hash of the prompt for redundant call detection
        """
        # Check for redundant calls (same prompt within 60s)
        if prompt_hash:
            now = time.monotonic()
            if prompt_hash in self._call_hashes:
                if now - self._call_hashes[prompt_hash] < 60:
                    self._redundant_calls.append(f"{agent_name}:{phase}")
            self._call_hashes[prompt_hash] = now

        # Update agent metrics
        if agent_name not in self._by_agent:
            self._by_agent[agent_name] = TokenMetrics()
        agent_metrics = self._by_agent[agent_name]
        agent_metrics.prompt_tokens += prompt_tokens
        agent_metrics.completion_tokens += completion_tokens
        agent_metrics.total_tokens += prompt_tokens + completion_tokens
        agent_metrics.call_count += 1
        agent_metrics.findings_yielded += findings_count

        # Update phase metrics
        if phase not in self._by_phase:
            self._by_phase[phase] = TokenMetrics()
        phase_metrics = self._by_phase[phase]
        phase_metrics.prompt_tokens += prompt_tokens
        phase_metrics.completion_tokens += completion_tokens
        phase_metrics.total_tokens += prompt_tokens + completion_tokens
        phase_metrics.call_count += 1

    def generate_report(self) -> TokenReport:
        """Generate a token usage report with efficiency flags.

        Returns:
            TokenReport with aggregated metrics by agent, phase,
            total, and any efficiency warnings.
        """
        total = TokenMetrics()
        for metrics in self._by_agent.values():
            total.prompt_tokens += metrics.prompt_tokens
            total.completion_tokens += metrics.completion_tokens
            total.total_tokens += metrics.total_tokens
            total.call_count += metrics.call_count
            total.findings_yielded += metrics.findings_yielded

        efficiency_flags: List[str] = []

        # Flag low-yield agents (< 0.5 findings per 1k tokens)
        for agent, metrics in self._by_agent.items():
            if metrics.total_tokens > 0:
                per_1k = metrics.findings_yielded / (metrics.total_tokens / 1000)
                if per_1k < 0.5 and metrics.findings_yielded == 0:
                    efficiency_flags.append(
                        f"LOW_YIELD: {agent} (0 findings, {metrics.total_tokens} tokens)"
                    )

        # Flag redundant calls
        if self._redundant_calls:
            efficiency_flags.append(
                f"REDUNDANT_CALLS: {len(self._redundant_calls)} duplicate prompts"
            )

        return TokenReport(
            by_agent=self._by_agent.copy(),
            by_phase=self._by_phase.copy(),
            total=total,
            efficiency_flags=efficiency_flags,
            generated_at=datetime.now().isoformat(),
        )
