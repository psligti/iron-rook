"""Tests for FSM Security Agent contracts and schemas."""

import pytest
import pydantic as pd

from iron_rook.review.contracts import (
    PullRequestChangeList,
    SecurityTodo,
    SubagentRequest,
    SubagentResult,
    SecurityReviewReport,
    EvidenceRef,
)


class TestPullRequestChangeList:
    """Test PullRequestChangeList validation."""

    def test_valid_minimal_pr(self) -> None:
        """Test minimal valid PR input."""
        pr_data = {
            "pr": {
                "id": "1234",
                "title": "Test PR",
                "base_branch": "main",
                "head_branch": "feature/test",
                "author": "alice",
            },
            "changes": [
                {
                    "path": "test.py",
                    "change_type": "added",
                    "diff_summary": "Added test file",
                    "risk_hints": [],
                }
            ],
            "metadata": {
                "repo": "testrepo",
                "commit_range": "abc..def",
                "created_at": "2026-02-09T18:00:00Z",
            },
            "constraints": {},
        }

        pr = PullRequestChangeList.model_validate(pr_data)
        assert pr.pr.id == "1234"
        assert pr.pr.title == "Test PR"
        assert len(pr.changes) == 1

    def test_full_pr_with_constraints(self) -> None:
        """Test PR with full constraints."""
        pr_data = {
            "pr": {
                "id": "1234",
                "title": "Test PR with constraints",
                "base_branch": "main",
                "head_branch": "feature/auth",
                "author": "alice",
            },
            "changes": [
                {
                    "path": "src/auth/jwt.py",
                    "change_type": "modified",
                    "diff_summary": "JWT verification updates",
                    "risk_hints": ["auth", "crypto"],
                }
            ],
            "metadata": {
                "repo": "myrepo",
                "commit_range": "abc567..def890",
                "created_at": "2026-02-09T18:00:00Z",
            },
            "constraints": {
                "tool_budget": 25,
                "max_subagents": 5,
                "max_iterations": 4,
            },
        }

        pr = PullRequestChangeList.model_validate(pr_data)
        assert pr.constraints.tool_budget == 25
        assert pr.constraints.max_subagents == 5
        assert pr.constraints.max_iterations == 4

    def test_invalid_pr_missing_required(self) -> None:
        """Test validation fails for missing required fields."""
        pr_data = {
            "pr": {
                "id": "1234",
                "title": "Test PR",
            },
            "changes": [],
            "metadata": {
                "repo": "testrepo",
                "commit_range": "abc..def",
                "created_at": "2026-02-09T18:00:00Z",
            },
            "constraints": {},
        }

        with pytest.raises(pd.ValidationError) as exc_info:
            PullRequestChangeList.model_validate(pr_data)
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)


class TestSecurityTodo:
    """Test SecurityTodo validation."""

    def test_valid_todo_with_delegation(self) -> None:
        """Test valid TODO with delegation."""
        todo_data = {
            "todo_id": "SEC-001",
            "title": "Validate JWT verification",
            "scope": {
                "paths": ["src/auth/jwt.py", "src/auth/middleware.py"],
                "symbols": ["verify_jwt", "refresh_token"],
                "related_paths": ["src/config/security.yml"],
            },
            "priority": "high",
            "risk_category": "authn_authz",
            "acceptance_criteria": [
                "Signature verification uses correct algorithm",
                "Token expiry handled safely",
            ],
            "evidence_required": ["file_refs", "config_refs"],
            "delegation": {
                "subagent_type": "auth_security",
                "goal": "Assess JWT verification logic",
                "expected_artifacts": ["findings", "evidence"],
            },
        }

        todo = SecurityTodo.model_validate(todo_data)
        assert todo.todo_id == "SEC-001"
        assert todo.priority == "high"
        assert len(todo.scope.paths) == 2
        assert todo.delegation is not None
        assert todo.delegation.subagent_type == "auth_security"

    def test_valid_todo_without_delegation(self) -> None:
        """Test valid TODO without delegation."""
        todo_data = {
            "todo_id": "SEC-002",
            "title": "Check for SQL injection",
            "scope": {
                "paths": ["src/api/user.py"],
                "symbols": ["execute_query"],
            },
            "priority": "medium",
            "risk_category": "injection",
            "acceptance_criteria": [
                "No user input concatenation",
                "Parameterized queries used",
            ],
            "evidence_required": ["file_refs"],
            "delegation": None,
        }

        todo = SecurityTodo.model_validate(todo_data)
        assert todo.delegation is None

    def test_invalid_todo_missing_required(self) -> None:
        """Test validation fails for missing required fields."""
        todo_data = {
            "todo_id": "SEC-003",
            "title": "Test TODO",
        }

        with pytest.raises(pd.ValidationError) as exc_info:
            SecurityTodo.model_validate(todo_data)
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)


class TestSubagentRequest:
    """Test SubagentRequest validation."""

    def test_valid_subagent_request(self) -> None:
        """Test valid subagent request."""
        request_data = {
            "todo_id": "SEC-001",
            "subagent_type": "auth_security",
            "goal": "Assess JWT verification logic",
            "scope": {
                "paths": ["src/auth/jwt.py"],
                "symbols": ["verify_jwt"],
                "related_paths": [],
            },
            "evidence_required": ["file_refs", "config_refs"],
            "limits": {
                "tool_budget": 5,
                "max_iterations": 3,
            },
        }

        request = SubagentRequest.model_validate(request_data)
        assert request.todo_id == "SEC-001"
        assert request.subagent_type == "auth_security"

    def test_invalid_subagent_request(self) -> None:
        """Test validation fails for invalid subagent request."""
        request_data = {
            "todo_id": "SEC-001",
            "goal": "Invalid goal",
        }

        with pytest.raises(pd.ValidationError) as exc_info:
            SubagentRequest.model_validate(request_data)
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)


class TestSubagentResult:
    """Test SubagentResult validation."""

    def test_valid_subagent_result(self) -> None:
        """Test valid subagent result."""
        result_data = {
            "todo_id": "SEC-001",
            "subagent_type": "auth_security",
            "fsm": {
                "phase": "done",
                "iterations": 2,
                "stop_reason": "done",
            },
            "summary": "JWT verification completed",
            "findings": [
                {
                    "severity": "medium",
                    "title": "JWKS cache TTL issue",
                    "description": "Cache TTL is 24h",
                    "evidence": [
                        {
                            "type": "file_ref",
                            "path": "src/auth/jwt.py",
                            "lines": "88-121",
                        }
                    ],
                    "recommendations": [
                        "Reduce TTL to 1h",
                    ],
                }
            ],
            "evidence": [
                {
                    "type": "file_ref",
                    "path": "src/auth/jwt.py",
                    "lines": "88-121",
                }
            ],
            "recommendations": [
                "Reduce TTL to 1h",
            ],
            "confidence": 0.85,
            "needs_more": [],
        }

        result = SubagentResult.model_validate(result_data)
        assert result.fsm.phase == "done"
        assert result.confidence == 0.85
        assert len(result.findings) == 1

    def test_blocked_subagent_result(self) -> None:
        """Test blocked subagent result."""
        result_data = {
            "todo_id": "SEC-002",
            "subagent_type": "injection_security",
            "fsm": {
                "phase": "blocked",
                "iterations": 1,
                "stop_reason": "insufficient_evidence",
            },
            "summary": "Cannot analyze without access to code",
            "findings": [],
            "evidence": [],
            "recommendations": [],
            "confidence": 0.0,
            "needs_more": [
                "Need access to src/api/user.py",
            ],
        }

        result = SubagentResult.model_validate(result_data)
        assert result.fsm.phase == "blocked"
        assert result.fsm.stop_reason == "insufficient_evidence"


class TestSecurityReviewReport:
    """Test SecurityReviewReport validation."""

    def test_valid_final_report(self) -> None:
        """Test valid final security review report."""
        report_data = {
            "agent": {
                "name": "security_review_agent",
                "version": "0.1.0",
            },
            "pr": {
                "id": "1234",
                "title": "Add auth middleware",
            },
            "fsm": {
                "iterations": 2,
                "stop_reason": "done",
                "tool_calls_used": 14,
                "subagents_used": 3,
            },
            "todos": [
                {
                    "todo_id": "SEC-001",
                    "status": "done",
                    "subagent_type": "auth_security",
                },
                {
                    "todo_id": "SEC-002",
                    "status": "done",
                    "subagent_type": None,
                },
            ],
            "findings": {
                "critical": [],
                "high": [],
                "medium": [
                    {
                        "id": "FND-001",
                        "todo_id": "SEC-001",
                        "severity": "medium",
                        "title": "JWKS cache TTL issue",
                        "description": "Cache TTL is 24h",
                        "evidence": [
                            {
                                "type": "file_ref",
                                "path": "src/auth/jwt.py",
                                "lines": "88-121",
                            }
                        ],
                        "recommendations": [
                            "Reduce TTL",
                        ],
                    }
                ],
                "low": [],
                "info": [],
            },
            "risk_assessment": {
                "overall": "medium",
                "rationale": "Authentication changes with caching concern",
                "areas_touched": ["auth", "config"],
            },
            "evidence_index": [
                {
                    "type": "file_ref",
                    "path": "src/auth/jwt.py",
                    "lines": "88-121",
                }
            ],
            "actions": {
                "required": [
                    {
                        "type": "code_change",
                        "description": "Reduce JWKS cache TTL",
                    }
                ],
                "suggested": [],
            },
            "confidence": 0.82,
            "missing_information": [],
        }

        report = SecurityReviewReport.model_validate(report_data)
        assert report.agent["version"] == "0.1.0"
        assert report.fsm.iterations == 2
        assert len(report.findings["medium"]) == 1

    def test_invalid_report_missing_required(self) -> None:
        """Test validation fails for missing required fields."""
        report_data = {
            "agent": {
                "name": "security_review_agent",
            },
        }

        with pytest.raises(pd.ValidationError) as exc_info:
            SecurityReviewReport.model_validate(report_data)
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)


class TestEvidenceRef:
    """Test EvidenceRef validation."""

    def test_valid_file_ref(self) -> None:
        """Test valid file reference."""
        ref_data = {
            "type": "file_ref",
            "path": "src/auth/jwt.py",
            "lines": "88-121",
        }

        ref = EvidenceRef.model_validate(ref_data)
        assert ref.type == "file_ref"
        assert ref.path == "src/auth/jwt.py"

    def test_valid_diff_ref(self) -> None:
        """Test valid diff reference."""
        ref_data = {
            "type": "diff_ref",
            "path": "src/auth/middleware.py",
            "lines": "12-79",
            "excerpt": "Added JWT verification",
        }

        ref = EvidenceRef.model_validate(ref_data)
        assert ref.type == "diff_ref"
        assert ref.path == "src/auth/middleware.py"

    def test_invalid_evidence_ref_missing_type(self) -> None:
        """Test validation fails for missing type."""
        ref_data = {
            "path": "src/auth/jwt.py",
        }

        with pytest.raises(pd.ValidationError) as exc_info:
            EvidenceRef.model_validate(ref_data)
        has_missing_loc = False
        for error in exc_info.value.errors():
            if error["loc"] and len(error["loc"]) > 0 and error["loc"][0] == "missing":
                has_missing_loc = True
                break
        assert has_missing_loc


def test_all_schemas_import() -> None:
    """Test that all new schemas can be imported."""
    from iron_rook.review.contracts import (
        PullRequestChangeList,
        SecurityTodo,
        SubagentResult,
        SecurityReviewReport,
    )

    assert PullRequestChangeList is not None
    assert SecurityTodo is not None
    assert SubagentResult is not None
    assert SecurityReviewReport is not None


if __name__ == "__main__":
    pytest.main([__file__])
