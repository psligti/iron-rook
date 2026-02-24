"""Review evaluation runner using ash-hawk harness.

Supports:
- Calibration against ground truth labels
- Disagreement detection for low-confidence judgments
- Confidence tracking in grader results
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ash_hawk.types import (
        EvalSuite,
        EvalTask,
        EvalTranscript,
        EvalOutcome,
        RunEnvelope,
        EvalRunSummary,
        ToolSurfacePolicy,
    )


class ReviewEvalRunner:
    """Runner for evaluating PR review agent quality.

    Integrates iron-rook reviewers with ash-hawk evaluation harness
    to measure reviewer accuracy on known test cases.

    Example:
        >>> from iron_rook.eval import ReviewEvalRunner
        >>> from iron_rook.eval.suites import create_security_suite
        >>>
        >>> runner = ReviewEvalRunner(
        ...     provider="z.ai",
        ...     model="glm-4.7",
        ... )
        >>> suite = create_security_suite()
        >>> summary = await runner.run_suite(suite)
        >>> print(f"Pass rate: {summary.metrics.pass_rate:.1%}")
    """

    def __init__(
        self,
        provider: str = "z.ai",
        model: str = "glm-4.7",
        storage_path: Path | None = None,
        policy: ToolSurfacePolicy | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._storage_path = storage_path or Path(".iron-rook-evals")
        self._policy = policy

    def _get_default_policy(self) -> ToolSurfacePolicy:
        from ash_hawk.types import ToolSurfacePolicy

        return ToolSurfacePolicy(
            allowed_tools=["read", "glob", "ripgrep", "bash"],
            allowed_roots=["."],
            timeout_seconds=300.0,
        )

    def _create_run_envelope(self, suite: EvalSuite) -> RunEnvelope:
        from ash_hawk.types import RunEnvelope
        import sys
        import platform

        return RunEnvelope(
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            suite_id=suite.id,
            suite_hash=self._hash_suite(suite),
            harness_version="0.1.0",
            git_commit=None,
            agent_name="iron-rook-reviewer",
            agent_version="0.1.0",
            provider=self._provider,
            model=self._model,
            model_params={},
            seed=None,
            tool_policy_hash="default",
            python_version=sys.version.split()[0],
            os_info=platform.platform(),
            created_at=datetime.now(UTC).isoformat(),
        )

    def _hash_suite(self, suite: EvalSuite) -> str:
        import hashlib
        import json

        content = json.dumps(suite.model_dump(mode="json"), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _execute_review_task(
        self,
        task: EvalTask,
        policy: ToolSurfacePolicy,
    ) -> tuple[EvalTranscript, EvalOutcome]:
        from ash_hawk.types import (
            EvalTranscript,
            EvalOutcome,
            FailureMode,
            TokenUsage,
        )
        from iron_rook.review.contracts import ReviewInputs
        from iron_rook.review.orchestrator import PRReviewOrchestrator
        from iron_rook.review.registry import ReviewerRegistry

        start_time = time.time()

        try:
            task_input = task.input
            if isinstance(task_input, dict):
                repo_root = task_input.get("repo_root", ".")
                base_ref = task_input.get("base_ref", "main")
                head_ref = task_input.get("head_ref", "HEAD")
                agent_name = task_input.get("agent", "security")
            else:
                return (
                    EvalTranscript(
                        error_trace="Task input must be a dict",
                        duration_seconds=time.time() - start_time,
                    ),
                    EvalOutcome.failure(FailureMode.VALIDATION_ERROR, "Task input must be a dict"),
                )

            reviewer = ReviewerRegistry.get_reviewer(agent_name)
            if not reviewer:
                return (
                    EvalTranscript(
                        error_trace=f"Unknown reviewer: {agent_name}",
                        duration_seconds=time.time() - start_time,
                    ),
                    EvalOutcome.failure(
                        FailureMode.VALIDATION_ERROR, f"Unknown reviewer: {agent_name}"
                    ),
                )

            inputs = ReviewInputs(
                repo_root=str(repo_root),
                base_ref=base_ref,
                head_ref=head_ref,
            )

            orchestrator = PRReviewOrchestrator(subagents=[reviewer])
            result = await orchestrator.run_review(inputs)

            duration = time.time() - start_time

            transcript = EvalTranscript(
                messages=[{"role": "user", "content": str(task_input)}],
                tool_calls=[],
                token_usage=TokenUsage(),
                cost_usd=0.0,
                duration_seconds=duration,
                agent_response=result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else str(result),
            )

            return transcript, EvalOutcome.success()

        except Exception as e:
            import traceback

            duration = time.time() - start_time
            return (
                EvalTranscript(
                    error_trace="".join(traceback.format_exception(type(e), e, e.__traceback__)),
                    duration_seconds=duration,
                ),
                EvalOutcome.failure(FailureMode.AGENT_ERROR, str(e)),
            )

    async def run_suite(self, suite: EvalSuite) -> EvalRunSummary:
        from ash_hawk.storage import FileStorage
        from ash_hawk.execution import TrialExecutor
        from ash_hawk.execution.runner import EvalRunner
        from ash_hawk.config import EvalConfig
        from ash_hawk.types import TrialResult, GraderResult

        storage = FileStorage(base_path=str(self._storage_path))
        policy = self._policy or self._get_default_policy()
        config = EvalConfig(parallelism=1)

        async def review_agent_runner(
            task: EvalTask,
            policy_enforcer: Any,
            agent_config: dict[str, Any],
        ) -> tuple[EvalTranscript, EvalOutcome]:
            return await self._execute_review_task(task, policy)

        trial_executor = TrialExecutor(
            storage=storage,
            policy=policy,
            agent_runner=review_agent_runner,
        )

        runner = EvalRunner(config, storage, trial_executor)
        envelope = self._create_run_envelope(suite)

        agent_config = {
            "provider": self._provider,
            "model": self._model,
        }

        return await runner.run_suite(suite, agent_config, envelope)

    def calibrate_from_run(
        self,
        run_id: str,
        grader_type: str = "llm_judge",
    ):
        from iron_rook.eval.calibration_types import (
            CalibrationSample,
            CalibrationCurve,
            CalibrationResult,
        )
        from iron_rook.eval.calibration import GROUND_TRUTH_LABELS
        from ash_hawk.storage import FileStorage

        storage = FileStorage(base_path=str(self._storage_path))
        summary = storage.load_summary(run_id)

        if not summary:
            raise ValueError(f"Run not found: {run_id}")

        samples: list[CalibrationSample] = []
        for trial in summary.trials:
            trial_id = trial.task_id
            if trial_id not in GROUND_TRUTH_LABELS:
                continue

            actual = GROUND_TRUTH_LABELS[trial_id]
            predicted = trial.aggregate_score

            sample = CalibrationSample(
                predicted=predicted,
                actual=actual,
                trial_id=trial_id,
            )
            samples.append(sample)

        if not samples:
            raise ValueError(f"No matching samples for calibration from run {run_id}")

        curve = CalibrationCurve.compute(samples)
        recommended_threshold = self._compute_optimal_threshold(samples)
        rationale = self._generate_calibration_rationale(curve, recommended_threshold)

        return CalibrationResult(
            curve=curve,
            recommended_threshold=recommended_threshold,
            rationale=rationale,
        )

    def detect_disagreements_from_run(
        self,
        run_id: str,
        low_score_threshold: float = 0.65,
        high_variance_threshold: float = 0.20,
        agent_type: str | None = None,
    ) -> dict[str, Any]:
        from iron_rook.eval.calibration_types import detect_disagreements
        from iron_rook.eval.calibration import get_disagreement_config
        from ash_hawk.storage import FileStorage

        if agent_type:
            config = get_disagreement_config(agent_type)
            low_score_threshold = config["low_score_threshold"]
            high_variance_threshold = config["high_variance_threshold"]

        storage = FileStorage(base_path=str(self._storage_path))
        summary = storage.load_summary(run_id)

        if not summary:
            raise ValueError(f"Run not found: {run_id}")

        report = detect_disagreements(
            summary.trials,
            low_score_threshold=low_score_threshold,
            high_variance_threshold=high_variance_threshold,
        )

        return {
            "flagged_trial_ids": report.flagged_trial_ids,
            "reasons": report.reasons,
            "low_score_threshold": low_score_threshold,
            "high_variance_threshold": high_variance_threshold,
            "agent_type": agent_type,
            "summary": {
                "total_trials": len(summary.trials),
                "flagged_count": len(report.flagged_trial_ids),
                "flagged_percentage": len(report.flagged_trial_ids) / len(summary.trials) * 100
                if summary.trials
                else 0,
            },
        }

    def _compute_optimal_threshold(self, samples: list) -> float:
        best_threshold = 0.5
        best_accuracy = 0.0

        for threshold in [i / 100 for i in range(40, 90, 5)]:
            correct = sum(1 for s in samples if (s.predicted >= threshold) == s.actual)
            accuracy = correct / len(samples) if samples else 0

            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_threshold = threshold

        return best_threshold

    def _generate_calibration_rationale(
        self,
        curve,
        recommended_threshold: float,
    ) -> str:
        ece = curve.ece
        brier = curve.brier_score

        if ece < 0.05:
            calibration_quality = "excellent"
        elif ece < 0.10:
            calibration_quality = "good"
        elif ece < 0.15:
            calibration_quality = "moderate"
        else:
            calibration_quality = "poor"

        return (
            f"Judge calibration is {calibration_quality} (ECE: {ece:.4f}, Brier: {brier:.4f}). "
            f"Recommended pass threshold: {recommended_threshold:.2f} "
            f"to maximize accuracy while catching critical issues."
        )
