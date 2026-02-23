"""Calibration types for LLM judge evaluation.

These types provide calibration support for iron-rook evals.
They are compatible with ash-hawk's calibration types when available.

When ash-hawk adds calibration support (CalibrationSample, CalibrationCurve,
CalibrationResult), these will be used as a fallback.
"""

from __future__ import annotations

import pydantic as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ash_hawk.types import EvalTrial


class CalibrationSample(pd.BaseModel):
    predicted: float = pd.Field(ge=0.0, le=1.0)
    actual: bool
    trial_id: str | None = None

    @classmethod
    def from_trial(
        cls, trial: EvalTrial, grader_type: str = "llm_judge"
    ) -> CalibrationSample | None:
        llm_result = None
        if hasattr(trial, "result") and hasattr(trial.result, "grader_results"):
            for gr in trial.result.grader_results:
                if gr.grader_type == grader_type:
                    llm_result = gr
                    break

        if llm_result is None:
            return None

        return cls(
            predicted=llm_result.score,
            actual=trial.aggregate_score >= 0.7,
            trial_id=trial.task_id,
        )


class CalibrationCurve(pd.BaseModel):
    samples: list[CalibrationSample]
    ece: float = pd.Field(ge=0.0)
    brier_score: float = pd.Field(ge=0.0)

    @classmethod
    def compute(cls, samples: list[CalibrationSample]) -> CalibrationCurve:
        if not samples:
            return cls(samples=[], ece=0.0, brier_score=0.0)

        n_bins = 10
        bin_size = 1.0 / n_bins
        ece_sum = 0.0
        brier_sum = 0.0

        for i in range(n_bins):
            bin_low = i * bin_size
            bin_high = (i + 1) * bin_size
            bin_samples = [s for s in samples if bin_low <= s.predicted < bin_high]

            if not bin_samples:
                continue

            avg_confidence = sum(s.predicted for s in bin_samples) / len(bin_samples)
            avg_accuracy = sum(1.0 for s in bin_samples if s.actual) / len(bin_samples)
            ece_sum += abs(avg_confidence - avg_accuracy) * len(bin_samples)

        for s in samples:
            brier_sum += (s.predicted - float(s.actual)) ** 2

        ece = ece_sum / len(samples) if samples else 0.0
        brier = brier_sum / len(samples) if samples else 0.0

        return cls(samples=samples, ece=ece, brier_score=brier)


class CalibrationResult(pd.BaseModel):
    curve: CalibrationCurve
    recommended_threshold: float = pd.Field(ge=0.0, le=1.0)
    rationale: str


class DisagreementReport(pd.BaseModel):
    flagged_trial_ids: list[str]
    reasons: dict[str, str]
    low_score_threshold: float
    high_variance_threshold: float


def detect_disagreements(
    trials: list,
    low_score_threshold: float = 0.7,
    high_variance_threshold: float = 0.2,
) -> DisagreementReport:
    flagged: list[str] = []
    reasons: dict[str, str] = {}

    for trial in trials:
        trial_id = getattr(trial, "task_id", str(id(trial)))
        score = getattr(trial, "aggregate_score", 1.0)

        if score < low_score_threshold:
            flagged.append(trial_id)
            reasons[trial_id] = f"Low aggregate score: {score:.2f} < {low_score_threshold}"
            continue

        if hasattr(trial, "result") and hasattr(trial.result, "grader_results"):
            scores = [gr.score for gr in trial.result.grader_results if hasattr(gr, "score")]
            if len(scores) >= 2:
                mean = sum(scores) / len(scores)
                variance = sum((s - mean) ** 2 for s in scores) / len(scores)
                if variance > high_variance_threshold:
                    flagged.append(trial_id)
                    reasons[trial_id] = f"High variance between judges: {variance:.2f}"

    return DisagreementReport(
        flagged_trial_ids=flagged,
        reasons=reasons,
        low_score_threshold=low_score_threshold,
        high_variance_threshold=high_variance_threshold,
    )


def try_import_ash_hawk_calibration():
    try:
        from ash_hawk.types import CalibrationSample as AshCalibrationSample
        from ash_hawk.types import CalibrationCurve as AshCalibrationCurve
        from ash_hawk.types import CalibrationResult as AshCalibrationResult

        return {
            "CalibrationSample": AshCalibrationSample,
            "CalibrationCurve": AshCalibrationCurve,
            "CalibrationResult": AshCalibrationResult,
        }
    except ImportError:
        return {
            "CalibrationSample": CalibrationSample,
            "CalibrationCurve": CalibrationCurve,
            "CalibrationResult": CalibrationResult,
        }


CALIBRATION_TYPES = try_import_ash_hawk_calibration()
