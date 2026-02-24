#!/usr/bin/env python
"""Run stress tests and generate gap analysis report.

Usage:
    uv run python iron_rook/eval/run_stress_tests.py

This will:
1. Run all stress test cases
2. Capture failures and timeouts
3. Analyze gaps in agents/skills/tooling/harness
4. Generate a comprehensive report
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class StressTestResult:
    task_id: str
    description: str
    passed: bool
    score: float
    error: str | None = None
    timeout: bool = False
    duration_seconds: float = 0.0
    findings: list[str] = field(default_factory=list)


@dataclass
class GapAnalysis:
    agent_gaps: list[str] = field(default_factory=list)
    skill_gaps: list[str] = field(default_factory=list)
    tool_gaps: list[str] = field(default_factory=list)
    harness_gaps: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


async def run_single_stress_test(
    task_id: str, task_input: dict, timeout_seconds: int = 90
) -> StressTestResult:
    import shutil
    import subprocess
    import tempfile

    from iron_rook.review.contracts import ReviewInputs
    from iron_rook.review.orchestrator import PRReviewOrchestrator
    from iron_rook.review.registry import ReviewerRegistry

    start_time = time.time()
    temp_dir = None

    try:
        agent_name = task_input.get("agent", "security")
        fixture_path = task_input.get("repo_root", ".")
        fixture_path = str(fixture_path).replace("$fixtures/", "iron_rook/eval/fixtures/")

        fixture_file = Path(fixture_path)
        if not fixture_file.exists():
            return StressTestResult(
                task_id=task_id,
                description=f"Fixture not found: {fixture_path}",
                passed=False,
                score=0.0,
                error=f"Fixture not found: {fixture_path}",
                duration_seconds=time.time() - start_time,
            )

        temp_dir = Path(tempfile.mkdtemp(prefix="iron-rook-stress-"))

        subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=temp_dir, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "base"],
            cwd=temp_dir,
            capture_output=True,
            check=True,
        )

        dest_file = temp_dir / fixture_file.name
        shutil.copy(fixture_file, dest_file)

        subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "changes"], cwd=temp_dir, capture_output=True, check=True
        )

        reviewer_class = ReviewerRegistry.get_reviewer(agent_name)
        if not reviewer_class:
            return StressTestResult(
                task_id=task_id,
                description=f"Unknown agent: {agent_name}",
                passed=False,
                score=0.0,
                error=f"Unknown agent: {agent_name}",
                duration_seconds=time.time() - start_time,
            )

        reviewer = reviewer_class()
        inputs = ReviewInputs(
            repo_root=str(temp_dir),
            base_ref="HEAD~1",
            head_ref="HEAD",
        )

        orchestrator = PRReviewOrchestrator(subagents=[reviewer])
        result = await asyncio.wait_for(
            orchestrator.run_review(inputs),
            timeout=timeout_seconds,
        )

        duration = time.time() - start_time
        findings = []
        if hasattr(result, "findings"):
            for f in result.findings:
                if hasattr(f, "description"):
                    findings.append(f.description)
                elif isinstance(f, dict):
                    findings.append(f.get("description", str(f)))
                else:
                    findings.append(str(f))

        return StressTestResult(
            task_id=task_id,
            description=f"Stress test: {task_id}",
            passed=True,
            score=1.0,
            duration_seconds=duration,
            findings=findings,
        )

    except asyncio.TimeoutError:
        return StressTestResult(
            task_id=task_id,
            description=f"Stress test: {task_id}",
            passed=False,
            score=0.0,
            timeout=True,
            error=f"Test timed out after {timeout_seconds} seconds",
            duration_seconds=time.time() - start_time,
        )
    except Exception as e:
        import traceback

        return StressTestResult(
            task_id=task_id,
            description=f"Stress test: {task_id}",
            passed=False,
            score=0.0,
            error=f"{type(e).__name__}: {str(e)}",
            duration_seconds=time.time() - start_time,
        )
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def analyze_gaps(results: list[StressTestResult]) -> GapAnalysis:
    analysis = GapAnalysis()

    for result in results:
        if result.timeout:
            analysis.harness_gaps.append(f"Timeout on {result.task_id}: Agent took too long")

        if result.error and "Unknown agent" in result.error:
            analysis.agent_gaps.append(f"Agent resolution failed: {result.error}")

        if result.error and "import" in result.error.lower():
            analysis.skill_gaps.append(f"Import error in {result.task_id}")

        if "false_positive" in result.task_id and not result.passed:
            analysis.agent_gaps.append(f"High false positive rate: {result.task_id}")

        if "subtle" in result.task_id and result.score < 0.5:
            analysis.agent_gaps.append(f"Subtle issue detection weak: {result.task_id}")

        if "unicode" in result.task_id and result.error:
            analysis.tool_gaps.append(f"Unicode handling issue in {result.task_id}")

        if "massive" in result.task_id and result.timeout:
            analysis.harness_gaps.append("Token limit reached on large files")

    if any(r.timeout for r in results):
        analysis.recommendations.append("Add timeout configuration per task type")

    if any("subtle" in r.task_id and r.score < 0.5 for r in results):
        analysis.recommendations.append("Enhance prompts for subtle issue detection")

    if any("false_positive" in r.task_id and not r.passed for r in results):
        analysis.recommendations.append("Add context-aware filtering")

    if any(r.error and "unicode" in r.task_id.lower() for r in results):
        analysis.recommendations.append("Add robust unicode handling")

    return analysis


def generate_report(results: list[StressTestResult], analysis: GapAnalysis) -> str:
    lines = [
        "# Stress Test Report",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Summary",
        "",
        f"- Total tests: {len(results)}",
        f"- Passed: {sum(1 for r in results if r.passed)}",
        f"- Failed: {sum(1 for r in results if not r.passed)}",
        f"- Timeouts: {sum(1 for r in results if r.timeout)}",
        "",
        "## Test Results",
        "",
    ]

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        if result.timeout:
            status = "TIMEOUT"
        lines.extend(
            [
                f"### {result.task_id}",
                "",
                f"- Status: {status}",
                f"- Duration: {result.duration_seconds:.2f}s",
            ]
        )
        if result.error:
            lines.append(f"- Error: `{result.error[:200]}`")
        if result.findings:
            lines.append(f"- Findings: {len(result.findings)}")
        lines.append("")

    lines.extend(
        [
            "## Gap Analysis",
            "",
            "### Agent Gaps",
            "",
        ]
    )
    lines.extend(f"- {gap}" for gap in analysis.agent_gaps) if analysis.agent_gaps else [
        "No agent gaps."
    ]
    lines.extend(["", "### Skill Gaps", ""])
    lines.extend(f"- {gap}" for gap in analysis.skill_gaps) if analysis.skill_gaps else [
        "No skill gaps."
    ]
    lines.extend(["", "### Tool Gaps", ""])
    lines.extend(f"- {gap}" for gap in analysis.tool_gaps) if analysis.tool_gaps else [
        "No tool gaps."
    ]
    lines.extend(["", "### Harness Gaps", ""])
    lines.extend(f"- {gap}" for gap in analysis.harness_gaps) if analysis.harness_gaps else [
        "No harness gaps."
    ]
    lines.extend(["", "## Recommendations", ""])
    lines.extend(
        f"{i + 1}. {rec}" for i, rec in enumerate(analysis.recommendations)
    ) if analysis.recommendations else ["No recommendations."]

    return "\n".join(lines)


async def main():
    from iron_rook.eval.stress_suite import STRESS_EVAL_SUITE

    print("=" * 60)
    print("IRON-ROOK STRESS TEST SUITE")
    print("=" * 60)
    print()

    results: list[StressTestResult] = []

    for task in STRESS_EVAL_SUITE.tasks:
        print(f"Running: {task.id}...")

        result = await run_single_stress_test(
            task_id=task.id,
            task_input=task.input,
            timeout_seconds=task.timeout_seconds or 90,
        )

        results.append(result)

        status = "OK" if result.passed else "FAIL"
        if result.timeout:
            status = "TIMEOUT"
        print(f"  [{status}] {result.duration_seconds:.2f}s")

        if result.error:
            print(f"  Error: {result.error[:100]}")

    print()
    print("Analyzing gaps...")

    analysis = analyze_gaps(results)
    report = generate_report(results, analysis)

    output_path = Path("iron_rook/eval/stress_test_report.md")
    output_path.write_text(report)

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Passed: {sum(1 for r in results if r.passed)}/{len(results)}")
    print(f"Failed: {sum(1 for r in results if not r.passed)}/{len(results)}")
    print(f"Timeouts: {sum(1 for r in results if r.timeout)}/{len(results)}")
    print()
    print(f"Report saved to: {output_path}")
    print()
    print("GAP SUMMARY:")
    print(f"  Agent gaps: {len(analysis.agent_gaps)}")
    print(f"  Skill gaps: {len(analysis.skill_gaps)}")
    print(f"  Tool gaps: {len(analysis.tool_gaps)}")
    print(f"  Harness gaps: {len(analysis.harness_gaps)}")

    if results and not all(r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
