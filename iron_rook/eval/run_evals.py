#!/usr/bin/env python
"""Run iron-rook agent evaluations using ash-hawk.

This script demonstrates running the evaluation suites against
iron-rook reviewer agents and judging the results.

Usage:
    uv run python iron_rook/eval/run_evals.py --suite security --limit 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from ash_hawk.types import (
    EvalSuite,
    EvalTask,
    EvalTranscript,
    EvalOutcome,
    EvalStatus,
    FailureMode,
    TokenUsage,
    GraderSpec,
    GraderResult,
    TrialResult,
    EvalRunSummary,
    RunEnvelope,
    ToolSurfacePolicy,
)
from ash_hawk.storage import FileStorage
from ash_hawk.graders import get_default_registry
from ash_hawk.execution.trial import TrialExecutor
from ash_hawk.execution.runner import EvalRunner
from ash_hawk.config import EvalConfig


STORAGE_PATH = Path(__file__).parent.parent.parent / ".iron-rook-evals"


def _get_judge_config() -> dict[str, str]:
    from dawn_kestrel.core.settings import get_settings

    settings = get_settings()
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


def make_security_suite() -> EvalSuite:
    judge_config = _get_judge_config()

    return EvalSuite(
        id="security-eval-demo",
        name="Security Review Demo",
        description="Demo evaluation for security reviewer",
        version="1.0.0",
        tags=["security", "demo"],
        tasks=[
            EvalTask(
                id="demo-sql-injection",
                description="Detect SQL injection",
                input={
                    "code": """
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    """,
                    "expected_findings": ["SQL injection", "f-string in query"],
                },
                expected_output="Should detect SQL injection vulnerability with critical severity",
                grader_specs=[
                    GraderSpec(
                        grader_type="llm_judge",
                        config={
                            "rubric": "correctness",
                            "pass_threshold": 0.6,
                            **judge_config,
                        },
                        weight=0.7,
                        required=True,
                    ),
                    GraderSpec(
                        grader_type="string_match",
                        config={
                            "contains": ["injection", "SQL", "vulnerability"],
                        },
                        weight=0.3,
                        required=False,
                    ),
                ],
                tags=["sql", "injection"],
            ),
            EvalTask(
                id="demo-hardcoded-secret",
                description="Detect hardcoded secret",
                input={
                    "code": """
API_KEY = "sk-prod-abc123def456"
DATABASE_URL = "postgres://admin:password123@db.example.com/mydb"
""",
                    "expected_findings": ["hardcoded API key", "hardcoded password"],
                },
                expected_output="Should detect hardcoded secrets with blocking severity",
                grader_specs=[
                    GraderSpec(
                        grader_type="llm_judge",
                        config={
                            "rubric": "correctness",
                            "pass_threshold": 0.6,
                            **judge_config,
                        },
                        weight=0.7,
                        required=True,
                    ),
                    GraderSpec(
                        grader_type="string_match",
                        config={
                            "contains": ["secret", "hardcoded", "credential"],
                        },
                        weight=0.3,
                        required=False,
                    ),
                ],
                tags=["secrets", "credentials"],
            ),
        ],
    )


def mock_agent_runner(
    task: EvalTask,
    policy_enforcer: Any,
    agent_config: dict[str, object],
) -> tuple[EvalTranscript, EvalOutcome]:
    from iron_rook.review.registry import ReviewerRegistry
    from iron_rook.review.contracts import ReviewInputs, ReviewOutput, Finding, Scope, MergeGate
    import time

    start_time = time.time()

    try:
        task_input = task.input
        code = task_input.get("code", "") if isinstance(task_input, dict) else ""
        task_id = task.id

        reviewer_class = ReviewerRegistry.get_reviewer("security")
        reviewer = reviewer_class()

        simulated_response = ReviewOutput(
            agent="security",
            summary=f"Security review for {task_id}",
            severity="critical" if "sql" in task_id.lower() else "blocking",
            scope=Scope(
                relevant_files=["code.py"],
                reasoning="Input code analyzed for security issues",
            ),
            findings=[
                Finding(
                    id="SEC-001",
                    title="SQL Injection Vulnerability"
                    if "sql" in task_id.lower()
                    else "Hardcoded Secrets",
                    severity="critical" if "sql" in task_id.lower() else "blocking",
                    confidence="high",
                    owner="security",
                    estimate="S",
                    evidence=code[:200],
                    risk="Exploitable vulnerability allowing unauthorized data access",
                    recommendation="Use parameterized queries instead of string formatting",
                )
            ],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[
                    "Fix SQL injection" if "sql" in task_id.lower() else "Remove hardcoded secrets"
                ],
                should_fix=[],
            ),
        )

        transcript = EvalTranscript(
            messages=[{"role": "user", "content": str(task_input)}],
            tool_calls=[
                {"tool": "read", "input": {"path": "code.py"}, "output": code[:500]},
            ],
            token_usage=TokenUsage(input=150, output=200),
            cost_usd=0.002,
            duration_seconds=time.time() - start_time,
            agent_response=simulated_response.model_dump(mode="json"),
        )

        return transcript, EvalOutcome(status=EvalStatus.COMPLETED)

    except Exception as e:
        import traceback

        return (
            EvalTranscript(
                error_trace="".join(traceback.format_exception(type(e), e, e.__traceback__)),
                duration_seconds=time.time() - start_time,
            ),
            EvalOutcome(
                status=EvalStatus.ERROR, failure_mode=FailureMode.AGENT_ERROR, error_message=str(e)
            ),
        )


async def run_suite_with_grading(suite: EvalSuite, storage_path: Path) -> EvalRunSummary:
    storage = FileStorage(base_path=str(storage_path))
    policy = ToolSurfacePolicy(
        allowed_tools=["read", "grep", "bash"],
        allowed_roots=["."],
        timeout_seconds=60.0,
    )
    config = EvalConfig(parallelism=2)

    trial_executor = TrialExecutor(
        storage=storage,
        policy=policy,
        agent_runner=mock_agent_runner,
    )

    runner = EvalRunner(config, storage, trial_executor)

    import sys
    import platform
    import uuid
    from datetime import UTC, datetime

    envelope = RunEnvelope(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        suite_id=suite.id,
        suite_hash=str(hash(suite.id) % 10000),
        harness_version="0.1.0",
        git_commit=None,
        agent_name="iron-rook-security",
        agent_version="0.1.0",
        provider="z.ai",
        model="glm-4.7",
        model_params={},
        seed=None,
        tool_policy_hash="default",
        python_version=sys.version.split()[0],
        os_info=platform.platform(),
        created_at=datetime.now(UTC).isoformat(),
    )

    agent_config = {"provider": "z.ai", "model": "glm-4.7"}

    return await runner.run_suite(suite, agent_config, envelope)


async def grade_results(
    suite: EvalSuite, summary: EvalRunSummary, storage: FileStorage
) -> list[dict]:
    results = []

    for trial in summary.trials:
        if trial.result is None:
            results.append(
                {
                    "task_id": trial.task_id,
                    "status": "no_result",
                    "passed": False,
                }
            )
            continue

        transcript = trial.result.transcript
        agent_response = transcript.agent_response if transcript else None

        task = next((t for t in suite.tasks if t.id == trial.task_id), None)
        if task is None:
            continue

        task_results = {
            "task_id": trial.task_id,
            "description": task.description,
            "agent_response": agent_response,
            "grader_results": [],
        }

        registry = get_default_registry()
        for grader_spec in task.grader_specs:
            try:
                grader = registry.get(grader_spec.grader_type)
                if grader is None:
                    continue

                grader_result = await grader.grade(
                    trial=trial,
                    transcript=transcript,
                    spec=grader_spec,
                )

                task_results["grader_results"].append(
                    {
                        "grader_type": grader_spec.grader_type,
                        "score": grader_result.score,
                        "passed": grader_result.passed,
                        "details": grader_result.details,
                    }
                )

            except Exception as e:
                task_results["grader_results"].append(
                    {
                        "grader_type": grader_spec.grader_type,
                        "error": str(e),
                        "passed": False,
                    }
                )

        results.append(task_results)

    return results


def print_results(results: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)

    for task_result in results:
        print(f"\n## Task: {task_result['task_id']}")
        print(f"   Description: {task_result['description']}")

        if task_result.get("agent_response"):
            response = task_result["agent_response"]
            if isinstance(response, dict):
                print(f"   Agent: {response.get('agent', 'unknown')}")
                print(f"   Severity: {response.get('severity', 'unknown')}")
                findings = response.get("findings", [])
                print(f"   Findings: {len(findings)}")
                for f in findings[:2]:
                    print(f"     - {f.get('title', 'unknown')} ({f.get('severity', '?')})")

        print("   Grader Results:")
        for gr in task_result.get("grader_results", []):
            status = "✓ PASS" if gr.get("passed") else "✗ FAIL"
            score = gr.get("score", 0)
            print(f"     [{status}] {gr['grader_type']}: score={score:.2f}")
            details = gr.get("details", {})
            if details:
                reason = details.get("reasoning") or details.get("message") or str(details)[:80]
                print(f"             {reason}...")

    total = len(results)
    passed = sum(1 for r in results if any(gr.get("passed") for gr in r.get("grader_results", [])))
    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} tasks passed at least one grader")
    print("=" * 60)


async def main(suite_name: str = "security", limit: int = 2) -> None:
    print(f"Running {suite_name} evaluation suite...")
    print(f"Storage: {STORAGE_PATH}")

    if suite_name == "security":
        suite = make_security_suite()
    else:
        from iron_rook.eval.agent_evals import get_agent_suite

        suite = get_agent_suite(suite_name)
        if suite is None:
            print(f"Unknown suite: {suite_name}")
            return

    if limit:
        suite.tasks = suite.tasks[:limit]

    print(f"Suite: {suite.name} ({len(suite.tasks)} tasks)")

    summary = await run_suite_with_grading(suite, STORAGE_PATH)

    print(f"Run completed: {summary.envelope.run_id}")
    print(f"Total tasks: {summary.metrics.total_tasks}")
    print(f"Completed: {summary.metrics.completed_tasks}")

    storage = FileStorage(base_path=str(STORAGE_PATH))
    graded_results = await grade_results(suite, summary, storage)

    print_results(graded_results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run iron-rook evaluations")
    parser.add_argument("--suite", default="security", help="Suite to run")
    parser.add_argument("--limit", type=int, default=2, help="Max tasks to run")
    args = parser.parse_args()

    asyncio.run(main(args.suite, args.limit))
