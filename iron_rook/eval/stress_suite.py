"""Stress test evaluation suite for finding breaking points.

This suite is designed to push the agents to their limits and find:
- Edge cases that break the system
- False positive rates
- Subtle issue detection capability
- Resource limit handling
- Context awareness

Usage:
    from iron_rook.eval.stress_suite import STRESS_EVAL_SUITE

    runner = ReviewEvalRunner()
    summary = await runner.run_suite(STRESS_EVAL_SUITE)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ash_hawk.types import (
    EvalSuite,
    EvalTask,
    EvalAgentConfig,
    GraderSpec,
)

RUBRICS_DIR = Path(__file__).parent / "rubrics"
STRESS_DIR = Path(__file__).parent / "fixtures" / "stress"


def _get_settings():
    from dawn_kestrel.core.settings import get_settings

    return get_settings()


def _get_judge_config() -> dict[str, str]:
    settings = _get_settings()
    default_account = settings.get_default_account()

    if default_account:
        return {
            "judge_provider": default_account.provider_id.value,
            "judge_model": default_account.model,
        }

    return {
        "judge_provider": settings.provider_default,
        "judge_model": settings.model_default,
    }


_JUDGE_CONFIG = _get_judge_config()


def _make_agent_config(reviewer_name: str) -> EvalAgentConfig:
    settings = _get_settings()
    account = settings.get_default_account()

    if account:
        provider = account.provider_id.value
        model = account.model
    else:
        provider = settings.provider_default
        model = settings.model_default

    return EvalAgentConfig.model_validate(
        {
            "name": reviewer_name,
            "provider": provider,
            "model": model,
            "class": "iron_rook.eval.agent_runner:IronRookRunner",
            "kwargs": {"reviewer": reviewer_name},
        }
    )


def _make_stress_grader(
    expected_findings: list[str],
    should_not_flag: list[str] | None = None,
    pass_threshold: float = 0.5,
) -> list[GraderSpec]:
    graders = [
        GraderSpec(
            grader_type="llm_judge",
            config={
                "rubric": "custom",
                "custom_prompt": f"""You are evaluating a code review agent's response to a stress test case.

Expected findings (agent SHOULD mention these):
{chr(10).join(f"- {f}" for f in expected_findings)}

{f"False positives to AVOID (agent should NOT flag these):{chr(10)}{chr(10).join(f"- {f}" for f in should_not_flag)}" if should_not_flag else ""}

Score based on:
1. How many expected findings were caught (0.5 weight)
2. How many false positives were avoided (0.3 weight)
3. Quality of explanations (0.2 weight)

Return a JSON object with:
- "score": float between 0 and 1
- "findings_caught": list of expected findings that were mentioned
- "false_positives": list of things incorrectly flagged
- "reasoning": explanation of the score
""",
                "pass_threshold": pass_threshold,
                **_JUDGE_CONFIG,
            },
            weight=0.6,
            required=True,
        ),
        GraderSpec(
            grader_type="schema",
            config={
                "required_fields": ["agent", "summary", "findings"],
                "allow_extra_fields": True,
            },
            weight=0.1,
            required=True,
        ),
        GraderSpec(
            grader_type="transcript",
            config={
                "max_turns": 100,
                "min_turns": 1,
                "require_no_errors": False,
            },
            weight=0.1,
            required=False,
        ),
    ]

    if should_not_flag:
        graders.append(
            GraderSpec(
                grader_type="string_match",
                config={
                    "mode": "not_contains",
                    "not_contains": should_not_flag,
                },
                weight=0.2,
                required=False,
            )
        )

    return graders


STRESS_EVAL_SUITE = EvalSuite(
    id="stress-test-v1",
    name="Stress Test Suite",
    description="Push agents to their limits to find breaking points",
    version="1.0.0",
    tags=["stress", "edge-case", "breaking-point"],
    tasks=[
        EvalTask(
            id="stress-empty-file",
            description="Handle empty/minimal file gracefully",
            input={
                "repo_root": "$fixtures/stress/empty_file.py",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should not crash, should not report false positives",
            grader_specs=_make_stress_grader(
                expected_findings=["no code to review", "empty file handled"],
                should_not_flag=["vulnerability", "security issue", "injection"],
                pass_threshold=0.7,
            ),
            tags=["edge-case", "empty"],
            fixtures={"fixtures": "./fixtures/stress/empty_file.py"},
            timeout_seconds=60,
        ),
        EvalTask(
            id="stress-massive-file",
            description="Handle large file without timeout",
            input={
                "repo_root": "$fixtures/stress/massive_file.py",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should process or gracefully truncate without hanging",
            grader_specs=_make_stress_grader(
                expected_findings=["hardcoded", "api_key", "password", "token"],
                pass_threshold=0.5,
            ),
            tags=["edge-case", "scale"],
            fixtures={"fixtures": "./fixtures/stress/massive_file.py"},
            timeout_seconds=120,
        ),
        EvalTask(
            id="stress-deep-nesting",
            description="Handle deeply nested code",
            input={
                "repo_root": "$fixtures/stress/deep_nesting.py",
                "agent": "architecture",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect complexity issues without crashing",
            grader_specs=_make_stress_grader(
                expected_findings=[
                    "complexity",
                    "nesting",
                    "refactor",
                    "cyclomatic",
                    "cognitive",
                ],
                pass_threshold=0.6,
            ),
            tags=["edge-case", "complexity"],
            fixtures={"fixtures": "./fixtures/stress/deep_nesting.py"},
            timeout_seconds=90,
        ),
        EvalTask(
            id="stress-unicode",
            description="Handle unicode and special characters",
            input={
                "repo_root": "$fixtures/stress/unicode_chaos.py",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should handle unicode, detect homoglyphs/RTL issues",
            grader_specs=_make_stress_grader(
                expected_findings=[
                    "unicode",
                    "homoglyph",
                    "RTL",
                    "zero-width",
                    "security concern",
                ],
                pass_threshold=0.5,
            ),
            tags=["edge-case", "unicode"],
            fixtures={"fixtures": "./fixtures/stress/unicode_chaos.py"},
            timeout_seconds=90,
        ),
        EvalTask(
            id="stress-false-positives",
            description="Avoid false positives on safe code",
            input={
                "repo_root": "$fixtures/stress/false_positive_trap.py",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should NOT flag documentation/examples/tests as issues",
            grader_specs=_make_stress_grader(
                expected_findings=[],
                should_not_flag=[
                    "hardcoded password",
                    "sql injection",
                    "xss vulnerability",
                    "eval injection",
                    "api key exposed",
                ],
                pass_threshold=0.8,
            ),
            tags=["edge-case", "false-positive"],
            fixtures={"fixtures": "./fixtures/stress/false_positive_trap.py"},
            timeout_seconds=90,
        ),
        EvalTask(
            id="stress-subtle-issues",
            description="Detect subtle hard-to-find issues",
            input={
                "repo_root": "$fixtures/stress/subtle_issues.py",
                "agent": "unit_tests",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect at least some subtle issues",
            grader_specs=_make_stress_grader(
                expected_findings=[
                    "thread",
                    "closure",
                    "mutable default",
                    "resource leak",
                    "hash consistency",
                    "finally return",
                    "class attribute",
                ],
                pass_threshold=0.4,
            ),
            tags=["edge-case", "subtle"],
            fixtures={"fixtures": "./fixtures/stress/subtle_issues.py"},
            timeout_seconds=90,
        ),
        EvalTask(
            id="stress-mixed-languages",
            description="Handle multi-language content appropriately",
            input={
                "repo_root": "$fixtures/stress/mixed_languages.py",
                "agent": "security",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should flag real SQL injection, not string literals",
            grader_specs=_make_stress_grader(
                expected_findings=["get_user_unsafe", "SQL injection", "f-string"],
                should_not_flag=[
                    "JAVASCRIPT_CODE",
                    "BASH_CODE",
                    "YAML_CODE",
                ],
                pass_threshold=0.6,
            ),
            tags=["edge-case", "multi-language"],
            fixtures={"fixtures": "./fixtures/stress/mixed_languages.py"},
            timeout_seconds=90,
        ),
        EvalTask(
            id="stress-resource-exhaustion",
            description="Detect resource exhaustion patterns",
            input={
                "repo_root": "$fixtures/stress/resource_exhaustion.py",
                "agent": "performance",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should detect infinite loops, memory issues, deadlocks",
            grader_specs=_make_stress_grader(
                expected_findings=[
                    "infinite",
                    "memory",
                    "deadlock",
                    "timeout",
                    "exponential",
                    "busy wait",
                ],
                pass_threshold=0.5,
            ),
            tags=["edge-case", "performance"],
            fixtures={"fixtures": "./fixtures/stress/resource_exhaustion.py"},
            timeout_seconds=90,
        ),
        EvalTask(
            id="stress-ambiguous",
            description="Handle ambiguous code appropriately",
            input={
                "repo_root": "$fixtures/stress/ambiguous_code.py",
                "agent": "architecture",
                "base_ref": "main",
                "head_ref": "HEAD",
            },
            expected_output="Should acknowledge tradeoffs, not over-flag opinions",
            grader_specs=_make_stress_grader(
                expected_findings=[
                    "tradeoff",
                    "consider",
                    "GodObject",
                    "over-engineering",
                ],
                should_not_flag=[
                    "must",
                    "never",
                    "always",
                    "required",
                ],
                pass_threshold=0.5,
            ),
            tags=["edge-case", "ambiguous"],
            fixtures={"fixtures": "./fixtures/stress/ambiguous_code.py"},
            timeout_seconds=90,
        ),
    ],
    agent=_make_agent_config("security"),
)


def get_stress_suite() -> EvalSuite:
    return STRESS_EVAL_SUITE
