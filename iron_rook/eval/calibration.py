"""Ground truth labels for eval calibration.

This file provides ground truth labels for calibrating LLM judges
against known correct/incorrect agent responses.

Usage:
    ash-hawk calibrate --ground-truth iron_rook/eval/ground_truth.json --run <run-id>
"""

from __future__ import annotations

# Ground truth labels per task
# true = agent should pass (correctly identifies issues)
# false = agent should fail (misses issues or false positives)
GROUND_TRUTH_LABELS: dict[str, bool] = {
    # Security tasks - all should be detected
    "security-sql-injection": True,
    "security-hardcoded-secrets": True,
    "security-xss": True,
    "security-auth-bypass": True,
    # Architecture tasks - all should be detected
    "arch-boundary-violation": True,
    "arch-circular-deps": True,
    "arch-god-object": True,
    # Documentation tasks
    "doc-missing-docs": True,
    "doc-outdated-readme": True,
    # Unit tests tasks
    "test-missing-tests": True,
    "test-brittle-tests": True,
    # Linting tasks
    "lint-style-violations": True,
    "lint-type-hints": True,
    # Performance tasks
    "perf-n2-complexity": True,
    "perf-io-amplification": True,
    # Dependencies tasks
    "deps-vulnerable-deps": True,
    "deps-license-issues": True,
    # Single-task suites
    "telemetry-missing-metrics": True,
    "req-missing-implementation": True,
    "diff-risk-changes": True,
    "changelog-missing": True,
}

# Calibration thresholds per agent type
# These are expected pass thresholds based on task difficulty
CALIBRATION_THRESHOLDS: dict[str, dict[str, float]] = {
    "security": {
        "expected_ece": 0.08,  # Expected Calibration Error
        "expected_brier": 0.15,  # Brier score
        "recommended_threshold": 0.65,  # Lower for security (catch more)
    },
    "architecture": {
        "expected_ece": 0.10,
        "expected_brier": 0.18,
        "recommended_threshold": 0.65,
    },
    "documentation": {
        "expected_ece": 0.10,
        "expected_brier": 0.20,
        "recommended_threshold": 0.60,
    },
    "unit_tests": {
        "expected_ece": 0.10,
        "expected_brier": 0.18,
        "recommended_threshold": 0.60,
    },
    "linting": {
        "expected_ece": 0.05,  # More deterministic
        "expected_brier": 0.10,
        "recommended_threshold": 0.70,
    },
    "performance": {
        "expected_ece": 0.10,
        "expected_brier": 0.20,
        "recommended_threshold": 0.65,
    },
    "dependencies": {
        "expected_ece": 0.08,
        "expected_brier": 0.15,
        "recommended_threshold": 0.65,
    },
    "telemetry": {
        "expected_ece": 0.12,
        "expected_brier": 0.22,
        "recommended_threshold": 0.60,
    },
    "requirements": {
        "expected_ece": 0.10,
        "expected_brier": 0.18,
        "recommended_threshold": 0.65,
    },
    "diff_scoper": {
        "expected_ece": 0.10,
        "expected_brier": 0.18,
        "recommended_threshold": 0.65,
    },
    "changelog": {
        "expected_ece": 0.10,
        "expected_brier": 0.18,
        "recommended_threshold": 0.60,
    },
}

# Disagreement detection configuration
DISAGREEMENT_CONFIG: dict[str, float] = {
    "low_score_threshold": 0.65,  # Flag if aggregate < 0.65
    "high_variance_threshold": 0.20,  # Flag if variance > 0.20
    "confidence_threshold": 0.70,  # Consider "low confidence" if < 0.70
}


def get_ground_truth_file() -> str:
    """Return path to ground truth JSON file for CLI calibration."""
    from pathlib import Path

    return str(Path(__file__).parent / "ground_truth.json")


def write_ground_truth_json() -> None:
    """Write ground truth labels to JSON file for ash-hawk calibrate CLI."""
    import json
    from pathlib import Path

    output_path = Path(__file__).parent / "ground_truth.json"
    with open(output_path, "w") as f:
        json.dump(GROUND_TRUTH_LABELS, f, indent=2)
    print(f"Written ground truth to {output_path}")


if __name__ == "__main__":
    write_ground_truth_json()
