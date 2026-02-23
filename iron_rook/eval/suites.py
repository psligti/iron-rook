"""Pre-built evaluation suites for PR review testing."""

from __future__ import annotations

from typing import Any

from ash_hawk.types import (
    EvalSuite,
    EvalTask,
    GraderSpec,
)


def create_review_suite(
    name: str,
    tasks: list[dict[str, Any]],
    grader_specs: list[GraderSpec] | None = None,
    tags: list[str] | None = None,
) -> EvalSuite:
    """Create a custom evaluation suite for PR review.

    Args:
        name: Suite name (used as ID).
        tasks: List of task definitions with repo_root, base_ref, head_ref, agent.
        grader_specs: Optional grader configurations.
        tags: Optional tags for categorization.

    Returns:
        EvalSuite ready for execution.
    """
    eval_tasks = []
    for i, task_def in enumerate(tasks):
        task = EvalTask(
            id=task_def.get("id", f"task-{i:03d}"),
            description=task_def.get("description", ""),
            input={
                "repo_root": task_def["repo_root"],
                "base_ref": task_def.get("base_ref", "main"),
                "head_ref": task_def.get("head_ref", "HEAD"),
                "agent": task_def.get("agent", "security"),
            },
            expected_output=task_def.get("expected_output"),
            grader_specs=grader_specs or [],
            tags=task_def.get("tags", []),
            fixtures=task_def.get("fixtures", {}),
        )
        eval_tasks.append(task)

    return EvalSuite(
        id=name.lower().replace(" ", "-"),
        name=name,
        tasks=eval_tasks,
        tags=tags or [],
    )


def create_security_suite() -> EvalSuite:
    """Create a basic security review evaluation suite.

    Tests security reviewer on common vulnerability patterns:
    - SQL injection
    - XSS
    - Hardcoded secrets
    - Insecure dependencies

    Returns:
        EvalSuite for security review testing.
    """
    grader = GraderSpec(
        grader_type="llm_judge",
        config={
            "rubric": "security_review",
            "criteria": [
                "detects_vulnerabilities",
                "accurate_severity",
                "actionable_fix",
            ],
            "pass_threshold": 0.7,
        },
        weight=1.0,
        required=True,
    )

    tasks = [
        {
            "id": "sql-injection-detection",
            "description": "Detect SQL injection in user input handling",
            "repo_root": "./fixtures/sql-injection",
            "agent": "security",
            "expected_output": "Should detect SQL injection vulnerability",
            "tags": ["security", "injection"],
        },
        {
            "id": "xss-detection",
            "description": "Detect XSS in template rendering",
            "repo_root": "./fixtures/xss",
            "agent": "security",
            "expected_output": "Should detect XSS vulnerability",
            "tags": ["security", "injection"],
        },
        {
            "id": "hardcoded-secrets",
            "description": "Detect hardcoded API keys and passwords",
            "repo_root": "./fixtures/secrets",
            "agent": "security",
            "expected_output": "Should detect hardcoded secrets",
            "tags": ["security", "secrets"],
        },
    ]

    return create_review_suite(
        name="Security Review Basic",
        tasks=tasks,
        grader_specs=[grader],
        tags=["security", "review", "basic"],
    )


def create_full_review_suite() -> EvalSuite:
    """Create a full PR review evaluation suite.

    Tests all reviewers on various code change patterns.

    Returns:
        EvalSuite for full review testing.
    """
    grader = GraderSpec(
        grader_type="composite",
        config={
            "graders": [
                {
                    "grader_type": "llm_judge",
                    "config": {"rubric": "review_quality", "pass_threshold": 0.6},
                    "weight": 0.5,
                },
                {
                    "grader_type": "string_match",
                    "config": {"mode": "contains", "expected": "verdict"},
                    "weight": 0.5,
                },
            ]
        },
        weight=1.0,
    )

    tasks = []
    reviewers = [
        "security",
        "architecture",
        "performance",
        "documentation",
        "linting",
        "unit_tests",
    ]

    for reviewer in reviewers:
        tasks.append(
            {
                "id": f"{reviewer}-basic",
                "description": f"Test {reviewer} reviewer on basic changes",
                "repo_root": f"./fixtures/{reviewer}",
                "agent": reviewer,
                "tags": [reviewer, "review"],
            }
        )

    return create_review_suite(
        name="Full PR Review",
        tasks=tasks,
        grader_specs=[grader],
        tags=["review", "full", "all-agents"],
    )
