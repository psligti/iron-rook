"""Shared pytest fixtures for iron-rook tests."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    Scope,
    MergeGate,
    Finding,
    Check,
    Skip,
    RunLog,
)


_PHASE_TEMPLATES = {
    "intake": {
        "phase": "intake",
        "data": {
            "summary": "Mock intake summary",
            "risk_hypotheses": [],
            "questions": [],
        },
        "next_phase_request": "plan",
    },
    "plan": {
        "phase": "plan",
        "data": {
            "todos": [],
            "delegation_plan": {},
            "tools_considered": [],
            "tools_chosen": [],
            "why": "Mock planning rationale",
        },
        "next_phase_request": "act",
    },
    "act": {
        "phase": "act",
        "data": {
            "subagent_requests": [],
            "self_analysis_plan": [],
        },
        "next_phase_request": "synthesize",
    },
    "synthesize": {
        "phase": "synthesize",
        "data": {
            "gates": {
                "all_todos_resolved": True,
                "evidence_present": True,
                "findings_categorized": True,
                "confidence_set": True,
            },
            "missing_information": [],
        },
        "next_phase_request": "check",
    },
    "check": {
        "phase": "check",
        "data": {
            "findings": {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            },
            "risk_assessment": {
                "overall": "low",
                "rationale": "Mock risk assessment",
            },
            "evidence_index": [],
            "actions": {
                "required": [],
                "suggested": [],
            },
            "confidence": 1.0,
            "missing_information": [],
        },
        "next_phase_request": "done",
    },
}


def create_mock_response(phase: str, overrides: dict[str, Any] | None = None) -> str:
    """Create a mock JSON response for a given FSM phase.

    Args:
        phase: The phase name (intake, plan, act, synthesize, check).
        overrides: Optional dict to merge into the default template.
            Use dot notation for nested keys (e.g., "data.summary").

    Returns:
        JSON string of the phase response.

    Example:
        >>> response = create_mock_response("intake", {"data": {"summary": "Custom summary"}})
        >>> json.loads(response)["data"]["summary"]
        'Custom summary'
    """
    if phase not in _PHASE_TEMPLATES:
        raise ValueError(f"Unknown phase: {phase}. Valid phases: {list(_PHASE_TEMPLATES.keys())}")

    response = json.loads(json.dumps(_PHASE_TEMPLATES[phase]))

    if overrides:
        for key, value in overrides.items():
            if "." in key:
                parts = key.split(".")
                current = response
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                response[key] = value

    return json.dumps(response, indent=2)


@pytest.fixture
def mock_phase_responses() -> dict[str, str]:
    """Fixture providing mock JSON responses for all FSM phases.

    Returns:
        Dict mapping phase name to JSON string response.

    Example:
        >>> responses = mock_phase_responses
        >>> json.loads(responses["intake"])["phase"]
        'intake'
    """
    return {
        "intake": create_mock_response("intake"),
        "plan": create_mock_response("plan"),
        "act": create_mock_response("act"),
        "synthesize": create_mock_response("synthesize"),
        "check": create_mock_response("check"),
    }


@pytest.fixture
def mock_review_context() -> ReviewContext:
    """Standard ReviewContext fixture for testing.

    Provides a realistic ReviewContext with:
    - Single changed file
    - Sample diff
    - PR metadata (title, description, refs)

    Returns:
        ReviewContext with test data
    """
    return ReviewContext(
        changed_files=["src/test.py"],
        diff="--- a/src/test.py\n+++ b/src/test.py\n@@ -1,1 +1,1 @@-old+new",
        repo_root="/test/repo",
        base_ref="main",
        head_ref="HEAD",
        pr_title="Test PR",
        pr_description="Test PR description",
    )


@pytest.fixture
def mock_simple_runner():
    """Fixture factory for mocking SimpleReviewAgentRunner.

    Returns a factory function that creates a mocked runner with
    configurable response.

    Usage:
        def test_example(mock_simple_runner):
            runner = mock_simple_runner('{"result": "ok"}')
            # use runner...

    Returns:
        Factory function that creates AsyncMock runner
    """

    def _create_runner(response: str = '{"result": "ok"}') -> AsyncMock:
        """Create a mocked SimpleReviewAgentRunner.

        Args:
            response: JSON string response for run_with_retry

        Returns:
            AsyncMock configured as SimpleReviewAgentRunner
        """
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = response
        return mock_runner

    return _create_runner


def assert_valid_review_output(output: ReviewOutput) -> None:
    """Validate ReviewOutput structure.

    Asserts that the output has all required fields with valid values:
    - agent: non-empty string
    - summary: non-empty string
    - severity: one of "merge", "warning", "critical", "blocking"
    - scope: Scope object with relevant_files
    - merge_gate: MergeGate object with valid decision

    Args:
        output: ReviewOutput to validate

    Raises:
        AssertionError: If any validation fails
    """
    # Check type
    assert isinstance(output, ReviewOutput), f"Expected ReviewOutput, got {type(output)}"

    # Check agent field
    assert isinstance(output.agent, str), "agent must be a string"
    assert len(output.agent) > 0, "agent must not be empty"

    # Check summary field
    assert isinstance(output.summary, str), "summary must be a string"
    assert len(output.summary) > 0, "summary must not be empty"

    # Check severity field
    valid_severities = {"merge", "warning", "critical", "blocking"}
    assert output.severity in valid_severities, (
        f"severity must be one of {valid_severities}, got {output.severity}"
    )

    # Check scope field
    assert isinstance(output.scope, Scope), f"scope must be Scope, got {type(output.scope)}"
    assert isinstance(output.scope.relevant_files, list), "scope.relevant_files must be a list"

    # Check checks field
    assert isinstance(output.checks, list), "checks must be a list"
    for check in output.checks:
        assert isinstance(check, Check), f"each check must be Check, got {type(check)}"

    # Check skips field
    assert isinstance(output.skips, list), "skips must be a list"
    for skip in output.skips:
        assert isinstance(skip, Skip), f"each skip must be Skip, got {type(skip)}"

    # Check findings field
    assert isinstance(output.findings, list), "findings must be a list"
    for finding in output.findings:
        assert isinstance(finding, Finding), f"each finding must be Finding, got {type(finding)}"

    # Check merge_gate field
    assert isinstance(output.merge_gate, MergeGate), (
        f"merge_gate must be MergeGate, got {type(output.merge_gate)}"
    )
    valid_decisions = {"approve", "needs_changes", "block", "approve_with_warnings"}
    assert output.merge_gate.decision in valid_decisions, (
        f"merge_gate.decision must be one of {valid_decisions}, got {output.merge_gate.decision}"
    )

    # Check thinking_log field (optional)
    if output.thinking_log is not None:
        assert isinstance(output.thinking_log, RunLog), (
            f"thinking_log must be RunLog, got {type(output.thinking_log)}"
        )
