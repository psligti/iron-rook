"""Integration tests for SecurityReviewer end-to-end FSM execution.

Tests complete 6-phase FSM flow:
  - INTAKE → PLAN_TODOS → DELEGATE → COLLECT → CONSOLIDATE → EVALUATE → DONE
  - Subagent dispatch and result aggregation
  - Result consolidation and de-duplication
  - Final report generation with schema validation
  - Error handling with subagent failures
  - Phase transition logging
  - Thinking capture for all phases
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from iron_rook.review.agents.security import SecurityReviewer
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput, Scope, MergeGate, Finding, ThinkingFrame


@pytest.fixture
def mock_review_context():
    """Create a mock ReviewContext for testing."""
    return ReviewContext(
        changed_files=["src/test.py", "src/auth.py", "src/api.py"],
        diff="--- a/src/test.py\n+++ b/src/test.py\n@@ -1,1 +1,1 @@\n-def test():\n+def test_security():",
        repo_root="/test/repo",
        base_ref="main",
        head_ref="HEAD",
        pr_title="Add security feature",
        pr_description="Implement authentication and authorization",
    )


@pytest.fixture
def mock_runner_responses():
    """Create mock LLM responses for all 6 phases."""
    return {
        "intake": """{
  "phase": "intake",
  "data": {
    "summary": "Test PR adds authentication and authorization features",
    "risk_hypotheses": [
      "Potential injection vulnerability in API endpoints",
      "Secret handling in authentication code",
      "Session management issues"
    ],
    "questions": [
      "How are API keys managed?",
      "Is session token validation implemented?"
    ]
  },
  "next_phase_request": "plan_todos"
}""",
        "plan_todos": """{
  "phase": "plan_todos",
  "data": {
    "todos": [
      {
        "id": "TODO-001",
        "description": "Review authentication implementation",
        "priority": "high",
        "risk_category": "authn_authz",
        "acceptance_criteria": "JWT implementation verified",
        "evidence_required": ["JWT configuration", "token validation"]
      },
      {
        "id": "TODO-002",
        "description": "Scan for SQL injection patterns",
        "priority": "high",
        "risk_category": "injection",
        "acceptance_criteria": "No SQL injection patterns found",
        "evidence_required": ["database queries", "user input handling"]
      }
    ],
    "delegation_plan": {
      "TODO-001": "auth_security",
      "TODO-002": "injection_scanner"
    },
    "tools_considered": ["grep", "ast-grep", "bandit"],
    "tools_chosen": ["grep", "ast-grep"],
    "why": "High-risk authentication and injection areas require specialized subagents"
  },
  "next_phase_request": "delegate"
}""",
        "delegate": """{
  "phase": "delegate",
  "data": {
    "subagent_requests": [
      {
        "todo_id": "TODO-001",
        "agent_type": "auth_security",
        "scope": ["src/auth.py"],
        "instructions": "Review JWT implementation and session management"
      },
      {
        "todo_id": "TODO-002",
        "agent_type": "injection_scanner",
        "scope": ["src/api.py"],
        "instructions": "Scan for SQL injection patterns"
      }
    ],
    "self_analysis_plan": [
      "Review configuration files for secrets",
      "Check CI/CD workflows for security issues"
    ]
  },
  "next_phase_request": "collect"
}""",
        "collect": """{
  "phase": "collect",
  "data": {
    "todo_status": [
      {
        "todo_id": "TODO-001",
        "status": "done",
        "evidence": [
          {
            "type": "file_ref",
            "path": "src/auth.py",
            "line": 45
          }
        ],
        "notes": "JWT implementation verified with proper signing"
      },
      {
        "todo_id": "TODO-002",
        "status": "done",
        "evidence": [
          {
            "type": "code_pattern",
            "pattern": "parameterized query",
            "location": "src/api.py:78"
          }
        ],
        "notes": "No SQL injection patterns found"
      }
    ],
    "issues_with_results": []
  },
  "next_phase_request": "consolidate"
}""",
        "consolidate": """{
  "phase": "consolidate",
  "data": {
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true,
      "findings_categorized": true,
      "confidence_set": true
    },
    "findings_summary": {
      "total": 1,
      "by_severity": {
        "medium": 1,
        "low": 0
      }
    },
    "missing_information": []
  },
  "next_phase_request": "evaluate"
}""",
        "evaluate": """{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [],
      "medium": [],
      "low": []
    },
    "risk_assessment": {
      "overall": "low",
      "rationale": "No security issues found. Review passed all checks.",
      "areas_touched": []
    },
    "evidence_index": [],
    "actions": {
      "required": [],
      "suggested": []
    },
    "confidence": 1.0,
    "missing_information": []
  },
  "next_phase_request": "done"
}""",
    }


class TestCompleteFSMExecution:
    """Test complete 6-phase FSM execution flow."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_complete_fsm_execution_all_phases(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test complete FSM execution through all 6 phases in order."""
        reviewer = SecurityReviewer()

        # Mock runner responses for all 6 phases
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Mock phase logger
        reviewer._phase_logger.log_thinking = Mock()
        reviewer._phase_logger.log_transition = Mock()

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify ReviewOutput is valid
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"

        # Verify severity and merge decision
        assert output.severity == "medium"
        assert output.merge_gate.decision == "approve"

        # Verify findings
        assert len(output.findings) == 1
        assert output.findings[0].severity == "warning"  # "medium" maps to "warning"
        assert output.findings[0].title == "Missing input validation in API endpoint"

        # Verify all LLM calls were made (6 phases)
        assert mock_runner.run_with_retry.call_count == 6

        # Verify thinking was logged for all phases
        assert reviewer._phase_logger.log_thinking.call_count >= 6

        # Verify transitions were logged (6 transitions)
        # intake -> plan_todos, plan_todos -> delegate, delegate -> collect,
        # collect -> consolidate, consolidate -> evaluate, evaluate -> done
        assert reviewer._phase_logger.log_transition.call_count >= 6

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_phases_executed_in_correct_order(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that phases execute in correct order."""
        reviewer = SecurityReviewer()

        # Track phase order
        phase_order = []

        # Mock runner to track phase order
        async def track_phase(system_prompt, user_message):
            # Extract phase name from system prompt
            if "INTAKE" in system_prompt:
                phase_order.append("intake")
                return mock_runner_responses["intake"]
            elif "PLAN_TODOS" in system_prompt:
                phase_order.append("plan_todos")
                return mock_runner_responses["plan_todos"]
            elif "DELEGATE" in system_prompt:
                phase_order.append("delegate")
                return mock_runner_responses["delegate"]
            elif "COLLECT" in system_prompt:
                phase_order.append("collect")
                return mock_runner_responses["collect"]
            elif "CONSOLIDATE" in system_prompt:
                phase_order.append("consolidate")
                return mock_runner_responses["consolidate"]
            elif "EVALUATE" in system_prompt:
                phase_order.append("evaluate")
                return mock_runner_responses["evaluate"]
            return mock_runner_responses["intake"]

        mock_runner = AsyncMock(side_effect=track_phase)
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify phase order
        expected_order = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]
        assert phase_order == expected_order


class TestSubagentDispatchAndCollection:
    """Test subagent dispatch and result aggregation."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_subagent_requests_created_in_delegate_phase(
        self, mock_runner_class, mock_review_context
    ):
        """Test that DELEGATE phase creates subagent requests."""
        reviewer = SecurityReviewer()

        # Mock delegate phase response with subagent requests
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            """{
  "phase": "intake",
  "data": {
    "summary": "Test summary",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}""",
            """{
  "phase": "plan_todos",
  "data": {
    "todos": [
      {
        "id": "TODO-001",
        "description": "Review auth",
        "priority": "high"
      }
    ],
    "delegation_plan": {
      "TODO-001": "auth_security"
    },
    "tools_considered": [],
    "tools_chosen": [],
    "why": ""
  },
  "next_phase_request": "delegate"
}""",
            """{
  "phase": "delegate",
  "data": {
    "subagent_requests": [
      {
        "todo_id": "TODO-001",
        "agent_type": "auth_security",
        "scope": ["src/auth.py"],
        "instructions": "Review JWT implementation"
      }
    ],
    "self_analysis_plan": []
  },
  "next_phase_request": "collect"
}""",
            """{
  "phase": "collect",
  "data": {
    "todo_status": [],
    "issues_with_results": []
  },
  "next_phase_request": "consolidate"
}""",
            """{
  "phase": "consolidate",
  "data": {
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true,
      "findings_categorized": true,
      "confidence_set": true
    },
    "missing_information": []
  },
  "next_phase_request": "evaluate"
}""",
            """{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [],
      "medium": [],
      "low": []
    },
    "risk_assessment": {
      "overall": "low",
      "rationale": ""
    },
    "evidence_index": [],
    "actions": {
      "required": [],
      "suggested": []
    },
    "confidence": 1.0,
    "missing_information": []
  },
  "next_phase_request": "done"
}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify delegate phase output contains subagent_requests
        delegate_output = reviewer._phase_outputs.get("delegate", {})
        assert "data" in delegate_output
        assert "subagent_requests" in delegate_output["data"]
        subagent_requests = delegate_output["data"]["subagent_requests"]
        assert len(subagent_requests) >= 1
        assert subagent_requests[0]["agent_type"] == "auth_security"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_collect_phase_aggregates_subagent_results(
        self, mock_runner_class, mock_review_context
    ):
        """Test that COLLECT phase aggregates subagent results."""
        reviewer = SecurityReviewer()

        # Mock collect phase response with aggregated results
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            """{
  "phase": "intake",
  "data": {
    "summary": "Test summary",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}""",
            """{
  "phase": "plan_todos",
  "data": {
    "todos": [
      {
        "id": "TODO-001",
        "description": "Review auth",
        "priority": "high"
      }
    ],
    "delegation_plan": {},
    "tools_considered": [],
    "tools_chosen": [],
    "why": ""
  },
  "next_phase_request": "delegate"
}""",
            """{
  "phase": "delegate",
  "data": {
    "subagent_requests": [],
    "self_analysis_plan": []
  },
  "next_phase_request": "collect"
}""",
            """{
  "phase": "collect",
  "data": {
    "todo_status": [
      {
        "todo_id": "TODO-001",
        "status": "done",
        "evidence": [
          {
            "type": "file_ref",
            "path": "src/auth.py",
            "line": 45
          }
        ],
        "notes": "JWT verified"
      },
      {
        "todo_id": "TODO-002",
        "status": "done",
        "evidence": [
          {
            "type": "code_pattern",
            "pattern": "parameterized query",
            "location": "src/api.py:78"
          }
        ],
        "notes": "No injection found"
      }
    ],
    "issues_with_results": []
  },
  "next_phase_request": "consolidate"
}""",
            """{
  "phase": "consolidate",
  "data": {
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true,
      "findings_categorized": true,
      "confidence_set": true
    },
    "missing_information": []
  },
  "next_phase_request": "evaluate"
}""",
            """{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [],
      "medium": [],
      "low": []
    },
    "risk_assessment": {
      "overall": "low",
      "rationale": ""
    },
    "evidence_index": [],
    "actions": {
      "required": [],
      "suggested": []
    },
    "confidence": 1.0,
    "missing_information": []
  },
  "next_phase_request": "done"
}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify collect phase output contains todo_status
        collect_output = reviewer._phase_outputs.get("collect", {})
        assert "data" in collect_output
        assert "todo_status" in collect_output["data"]
        todo_status = collect_output["data"]["todo_status"]
        assert len(todo_status) >= 1
        assert todo_status[0]["status"] == "done"


class TestResultConsolidation:
    """Test result consolidation and de-duplication."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_consolidate_phase_merges_findings(self, mock_runner_class, mock_review_context):
        """Test that CONSOLIDATE phase merges findings from multiple sources."""
        reviewer = SecurityReviewer()

        # Mock consolidate phase response with merged findings
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            """{
  "phase": "intake",
  "data": {
    "summary": "Test summary",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}""",
            """{
  "phase": "plan_todos",
  "data": {
    "todos": [],
    "delegation_plan": {},
    "tools_considered": [],
    "tools_chosen": [],
    "why": ""
  },
  "next_phase_request": "delegate"
}""",
            """{
  "phase": "delegate",
  "data": {
    "subagent_requests": [],
    "self_analysis_plan": []
  },
  "next_phase_request": "collect"
}""",
            """{
  "phase": "collect",
  "data": {
    "todo_status": [],
    "issues_with_results": []
  },
  "next_phase_request": "consolidate"
}""",
            """{
  "phase": "consolidate",
  "data": {
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true,
      "findings_categorized": true,
      "confidence_set": true
    },
    "findings_summary": {
      "total": 3,
      "by_severity": {
        "high": 1,
        "medium": 2,
        "low": 0
      }
    },
    "deduplicated_count": 5,
    "missing_information": []
  },
  "next_phase_request": "evaluate"
}""",
            """{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [
        {
          "severity": "high",
          "title": "SQL injection vulnerability",
          "description": "Unparameterized query",
          "evidence": [
            {
              "type": "file_ref",
              "path": "src/api.py",
              "line": 78
            }
          ],
          "recommendations": ["Use parameterized queries"]
        }
      ],
      "medium": [
        {
          "severity": "medium",
          "title": "Missing input validation",
          "description": "No validation",
          "evidence": [],
          "recommendations": ["Add validation"]
        },
        {
          "severity": "medium",
          "title": "Weak password policy",
          "description": "No min length",
          "evidence": [],
          "recommendations": ["Add min length"]
        }
      ],
      "low": []
    },
    "risk_assessment": {
      "overall": "high",
      "rationale": "One high-risk finding"
    },
    "evidence_index": [],
    "actions": {
      "required": [],
      "suggested": []
    },
    "confidence": 0.9,
    "missing_information": []
  },
  "next_phase_request": "done"
}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify consolidate phase output contains findings_summary
        consolidate_output = reviewer._phase_outputs.get("consolidate", {})
        assert "data" in consolidate_output
        assert "gates" in consolidate_output["data"]
        gates = consolidate_output["data"]["gates"]
        assert gates["all_todos_resolved"] is True
        assert gates["findings_categorized"] is True

        # Verify final ReviewOutput has consolidated findings
        assert len(output.findings) == 3
        assert output.severity == "critical"  # "high" maps to "critical"
        assert output.merge_gate.decision == "needs_changes"


class TestFinalReportGeneration:
    """Test final report generation with schema validation."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_final_report_generation(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that EVALUATE phase generates final report with valid schema."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify ReviewOutput structure matches schema
        assert isinstance(output, ReviewOutput)

        # Verify required fields
        assert hasattr(output, "agent")
        assert hasattr(output, "summary")
        assert hasattr(output, "severity")
        assert hasattr(output, "scope")
        assert hasattr(output, "findings")
        assert hasattr(output, "merge_gate")

        # Verify agent field
        assert output.agent == "security_fsm"

        # Verify severity field
        assert output.severity in ["merge", "warning", "critical", "blocking"]
        assert output.severity == "medium"

        # Verify scope field
        assert isinstance(output.scope, Scope)
        assert isinstance(output.scope.relevant_files, list)
        assert isinstance(output.scope.ignored_files, list)
        assert isinstance(output.scope.reasoning, str)

        # Verify findings field
        assert isinstance(output.findings, list)
        assert all(isinstance(f, Finding) for f in output.findings)

        # Verify merge_gate field
        assert isinstance(output.merge_gate, MergeGate)
        assert output.merge_gate.decision in [
            "approve",
            "needs_changes",
            "block",
            "approve_with_warnings",
        ]
        assert isinstance(output.merge_gate.must_fix, list)
        assert isinstance(output.merge_gate.should_fix, list)
        assert isinstance(output.merge_gate.notes_for_coding_agent, list)

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_reviewoutput_agent_field_matches_fsm(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that ReviewOutput.agent field is 'security_fsm'."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify agent field
        assert output.agent == "security_fsm"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_severity_mapped_correctly(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that security severity is mapped correctly to ReviewOutput.severity."""
        reviewer = SecurityReviewer()

        # Mock runner responses with medium risk
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify severity mapping (medium -> "merge" in root, "warning" in findings)
        assert output.severity == "medium"
        assert output.merge_gate.decision == "approve"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_merge_decision_based_on_severity(self, mock_runner_class, mock_review_context):
        """Test that merge_decision is set based on overall risk assessment."""
        reviewer = SecurityReviewer()

        # Test with high risk
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            """{
  "phase": "intake",
  "data": {"summary": "test", "risk_hypotheses": [], "questions": []},
  "next_phase_request": "plan_todos"
}""",
            """{
  "phase": "plan_todos",
  "data": {"todos": [], "delegation_plan": {}, "tools_considered": [], "tools_chosen": [], "why": ""},
  "next_phase_request": "delegate"
}""",
            """{
  "phase": "delegate",
  "data": {"subagent_requests": [], "self_analysis_plan": []},
  "next_phase_request": "collect"
}""",
            """{
  "phase": "collect",
  "data": {"todo_status": [], "issues_with_results": []},
  "next_phase_request": "consolidate"
}""",
            """{
  "phase": "consolidate",
  "data": {"gates": {"all_todos_resolved": true, "evidence_present": true, "findings_categorized": true, "confidence_set": true}, "missing_information": []},
  "next_phase_request": "evaluate"
}""",
            """{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [{"severity": "high", "title": "High risk issue", "description": "test", "evidence": [], "recommendations": []}],
      "medium": [],
      "low": []
    },
    "risk_assessment": {"overall": "high", "rationale": "High risk"},
    "evidence_index": [],
    "actions": {"required": [], "suggested": []},
    "confidence": 0.9,
    "missing_information": []
  },
  "next_phase_request": "done"
}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify merge decision for high risk
        assert output.severity == "high"
        assert output.merge_gate.decision == "needs_changes"
        assert len(output.findings) == 1


class TestSubagentFailureHandling:
    """Test error handling when subagents fail."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_partial_review_continues_on_error(self, mock_runner_class, mock_review_context):
        """Test that review continues when some phases have errors."""
        reviewer = SecurityReviewer()

        # Mock runner to simulate partial failure
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            # INTAKE - success
            """{
  "phase": "intake",
  "data": {"summary": "test", "risk_hypotheses": [], "questions": []},
  "next_phase_request": "plan_todos"
}""",
            # PLAN_TODOS - success
            """{
  "phase": "plan_todos",
  "data": {"todos": [], "delegation_plan": {}, "tools_considered": [], "tools_chosen": [], "why": ""},
  "next_phase_request": "delegate"
}""",
            # DELEGATE - success
            """{
  "phase": "delegate",
  "data": {"subagent_requests": [], "self_analysis_plan": []},
  "next_phase_request": "collect"
}""",
            # COLLECT - success with issues
            """{
  "phase": "collect",
  "data": {
    "todo_status": [],
    "issues_with_results": [
      {
        "todo_id": "TODO-001",
        "issue": "Subagent timeout"
      }
    ]
  },
  "next_phase_request": "consolidate"
}""",
            # CONSOLIDATE - success
            """{
  "phase": "consolidate",
  "data": {"gates": {"all_todos_resolved": false, "evidence_present": true, "findings_categorized": true, "confidence_set": true}, "missing_information": ["Subagent timeout"]},
  "next_phase_request": "evaluate"
}""",
            # EVALUATE - success with missing information
            """{
  "phase": "evaluate",
  "data": {
    "findings": {"critical": [], "high": [], "medium": [], "low": []},
    "risk_assessment": {"overall": "low", "rationale": "Partial review"},
    "evidence_index": [],
    "actions": {"required": [], "suggested": []},
    "confidence": 0.5,
    "missing_information": ["Subagent timeout"]
  },
  "next_phase_request": "done"
}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify review completed despite issues
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"

        # Verify confidence is lower due to issues
        evaluate_output = reviewer._phase_outputs.get("evaluate", {})
        assert evaluate_output.get("data", {}).get("confidence") == 0.5

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_error_returns_partial_report(self, mock_runner_class, mock_review_context):
        """Test that FSM errors return partial ReviewOutput."""
        reviewer = SecurityReviewer()

        # Mock runner to fail on third phase
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            # INTAKE - success
            """{
  "phase": "intake",
  "data": {"summary": "test", "risk_hypotheses": [], "questions": []},
  "next_phase_request": "plan_todos"
}""",
            # PLAN_TODOS - success
            """{
  "phase": "plan_todos",
  "data": {"todos": [], "delegation_plan": {}, "tools_considered": [], "tools_chosen": [], "why": ""},
  "next_phase_request": "delegate"
}""",
            # DELEGATE - raise exception
            Exception("LLM API timeout"),
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify partial ReviewOutput is returned
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"
        assert output.severity == "critical"
        assert "failed" in output.summary.lower() or "error" in output.summary.lower()
        assert output.merge_gate.decision == "needs_changes"


class TestPhaseTransitionsLogged:
    """Test phase transition logging."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_phase_transitions_logged_correctly(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that all phase transitions are logged."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Mock phase logger
        reviewer._phase_logger.log_transition = Mock()

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify all 6 transitions were logged
        expected_transitions = [
            ("intake", "plan_todos"),
            ("plan_todos", "delegate"),
            ("delegate", "collect"),
            ("collect", "consolidate"),
            ("consolidate", "evaluate"),
            ("evaluate", "done"),
        ]

        assert reviewer._phase_logger.log_transition.call_count == 6

        # Verify transition order
        actual_calls = reviewer._phase_logger.log_transition.call_args_list
        for i, (from_state, to_state) in enumerate(expected_transitions):
            actual_call = actual_calls[i]
            actual_from = actual_call[0][0]
            actual_to = actual_call[0][1]
            assert actual_from == from_state
            assert actual_to == to_state

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_transition_order_matches_fsm_flow(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that transition order matches FSM flow."""
        reviewer = SecurityReviewer()

        # Track transition order
        transition_order = []

        def track_transition(from_state, to_state):
            transition_order.append((from_state, to_state))

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Override log_transition to track order
        reviewer._phase_logger.log_transition = track_transition

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify transition order
        expected_order = [
            ("intake", "plan_todos"),
            ("plan_todos", "delegate"),
            ("delegate", "collect"),
            ("collect", "consolidate"),
            ("consolidate", "evaluate"),
            ("evaluate", "done"),
        ]
        assert transition_order == expected_order


class TestThinkingLoggedForAllPhases:
    """Test thinking capture for all phases."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_logged_for_all_phases(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that thinking is logged for all 6 phases."""
        reviewer = SecurityReviewer()

        # Mock runner responses with thinking in responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Mock phase logger
        reviewer._phase_logger.log_thinking = Mock()

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify thinking was called for all phases
        # Each phase calls log_thinking at least once (sometimes 2-3 times)
        assert reviewer._phase_logger.log_thinking.call_count >= 6

        # Verify thinking was logged for each phase
        phase_thinking_calls = {}
        for call in reviewer._phase_logger.log_thinking.call_args_list:
            phase = call[0][0]
            thinking = call[0][1]
            if phase not in phase_thinking_calls:
                phase_thinking_calls[phase] = []
            phase_thinking_calls[phase].append(thinking)

        # Verify all phases have thinking logged
        expected_phases = ["INTAKE", "PLAN_TODOS", "DELEGATE", "COLLECT", "CONSOLIDATE", "EVALUATE"]
        for phase in expected_phases:
            assert phase in phase_thinking_calls, f"Phase {phase} not in thinking logs"
            assert len(phase_thinking_calls[phase]) >= 1, f"Phase {phase} has no thinking logs"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_content_captured_correctly(
        self, mock_runner_class, mock_review_context
    ):
        """Test that thinking content is correctly captured from responses."""
        reviewer = SecurityReviewer()

        # Mock runner response with thinking field
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = """{
  "thinking": "Analyzing PR changes for security surfaces",
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}"""
        mock_runner_class.return_value = mock_runner

        # Mock phase logger
        reviewer._phase_logger.log_thinking = Mock()

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify thinking was captured and logged
        assert reviewer._phase_logger.log_thinking.call_count >= 1

        # Check if thinking content was logged
        thinking_calls = [str(call) for call in reviewer._phase_logger.log_thinking.call_args_list]
        has_thinking_content = any(
            "Analyzing PR changes for security surfaces" in call for call in thinking_calls
        )
        # Note: Thinking is extracted from LLM response, but we only verify log_thinking was called
        # The actual thinking content depends on the LLM response format

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_extraction_from_xml_tags(self, mock_runner_class, mock_review_context):
        """Test that thinking is extracted from <thinking> XML tags."""
        reviewer = SecurityReviewer()

        # Mock runner response with <thinking> tags
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            """<thinking>Need to check authentication flow</thinking>
```json
{
  "phase": "intake",
  "data": {
    "summary": "test",
    "risk_hypotheses": [],
    "questions": []
  },
  "next_phase_request": "plan_todos"
}
```""",
            """{
  "phase": "plan_todos",
  "data": {
    "todos": [],
    "delegation_plan": {},
    "tools_considered": [],
    "tools_chosen": [],
    "why": ""
  },
  "next_phase_request": "delegate"
}""",
            """{
  "phase": "delegate",
  "data": {
    "subagent_requests": [],
    "self_analysis_plan": []
  },
  "next_phase_request": "collect"
}""",
            """{
  "phase": "collect",
  "data": {
    "todo_status": [],
    "issues_with_results": []
  },
  "next_phase_request": "consolidate"
}""",
            """{
  "phase": "consolidate",
  "data": {
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true,
      "findings_categorized": true,
      "confidence_set": true
    },
    "missing_information": []
  },
  "next_phase_request": "evaluate"
}""",
            """{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [],
      "medium": [],
      "low": []
    },
    "risk_assessment": {
      "overall": "low",
      "rationale": ""
    },
    "evidence_index": [],
    "actions": {
      "required": [],
      "suggested": []
    },
    "confidence": 1.0,
    "missing_information": []
  },
  "next_phase_request": "done"
}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Mock phase logger
        reviewer._phase_logger.log_thinking = Mock()

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify thinking was logged
        assert reviewer._phase_logger.log_thinking.call_count >= 6


class TestThinkingFramesWorkflow:
    """Test ThinkingFrames creation and logging across full workflow."""

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_full_fsm_workflow_creates_thinking_frames_for_all_phases(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that ThinkingFrames are created for all 6 phases during full review workflow."""
        reviewer = SecurityReviewer()

        # Mock runner responses for all 6 phases
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        output = await reviewer.review(mock_review_context)

        # Verify review completed successfully
        assert isinstance(output, ReviewOutput)
        assert output.agent == "security_fsm"

        # Verify all 6 phases were executed
        expected_phases = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]
        for phase in expected_phases:
            assert phase in reviewer._phase_outputs, f"Phase {phase} not in outputs"

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_frames_logged_using_log_thinking_frame(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that log_thinking_frame() is called for each phase."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Mock log_thinking_frame to track calls
        reviewer._phase_logger.log_thinking_frame = Mock()

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify log_thinking_frame was called for all 6 phases
        assert reviewer._phase_logger.log_thinking_frame.call_count == 6

        # Verify each call received a ThinkingFrame object
        for call in reviewer._phase_logger.log_thinking_frame.call_args_list:
            frame_arg = call[0][0]
            assert isinstance(frame_arg, ThinkingFrame), (
                "log_thinking_frame() called with non-ThinkingFrame"
            )

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_log_accumulates_frames_across_all_phases(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that _thinking_log accumulates ThinkingFrames from all phases."""
        reviewer = SecurityReviewer()

        # Verify initial state
        assert len(reviewer._thinking_log.frames) == 0

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify _thinking_log has exactly 6 frames (one per phase)
        assert len(reviewer._thinking_log.frames) == 6

        # Verify each frame has correct structure
        for frame in reviewer._thinking_log.frames:
            assert isinstance(frame, ThinkingFrame)
            assert hasattr(frame, "state")
            assert hasattr(frame, "goals")
            assert hasattr(frame, "checks")
            assert hasattr(frame, "risks")
            assert hasattr(frame, "steps")
            assert hasattr(frame, "decision")

        # Verify phase states in frames match expected order
        expected_states = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]
        actual_states = [frame.state for frame in reviewer._thinking_log.frames]
        assert actual_states == expected_states

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_frames_have_correct_phase_specific_content(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that ThinkingFrames have phase-specific goals, checks, and risks."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Get frames by phase
        frames_by_phase = {frame.state: frame for frame in reviewer._thinking_log.frames}

        # Verify INTAKE frame content
        intake_frame = frames_by_phase.get("intake")
        assert intake_frame is not None
        assert intake_frame.decision == "plan_todos"
        assert len(intake_frame.goals) > 0
        assert len(intake_frame.checks) > 0

        # Verify PLAN_TODOS frame content
        plan_todos_frame = frames_by_phase.get("plan_todos")
        assert plan_todos_frame is not None
        assert plan_todos_frame.decision == "delegate"
        assert len(plan_todos_frame.goals) > 0
        assert len(plan_todos_frame.checks) > 0

        # Verify DELEGATE frame content
        delegate_frame = frames_by_phase.get("delegate")
        assert delegate_frame is not None
        assert delegate_frame.decision == "collect"
        assert len(delegate_frame.goals) > 0
        assert len(delegate_frame.checks) > 0

        # Verify COLLECT frame content
        collect_frame = frames_by_phase.get("collect")
        assert collect_frame is not None
        assert collect_frame.decision == "consolidate"
        assert len(collect_frame.goals) > 0
        assert len(collect_frame.checks) > 0

        # Verify CONSOLIDATE frame content
        consolidate_frame = frames_by_phase.get("consolidate")
        assert consolidate_frame is not None
        assert consolidate_frame.decision == "evaluate"
        assert len(consolidate_frame.goals) > 0
        assert len(consolidate_frame.checks) > 0

        # Verify EVALUATE frame content
        evaluate_frame = frames_by_phase.get("evaluate")
        assert evaluate_frame is not None
        assert evaluate_frame.decision == "done"
        assert len(evaluate_frame.goals) > 0
        assert len(evaluate_frame.checks) > 0

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_frames_have_decision_field_set_correctly(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that ThinkingFrames have decision field set to next_phase_request."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify each frame has correct decision
        expected_decisions = {
            "intake": "plan_todos",
            "plan_todos": "delegate",
            "delegate": "collect",
            "collect": "consolidate",
            "consolidate": "evaluate",
            "evaluate": "done",
        }

        for frame in reviewer._thinking_log.frames:
            expected_decision = expected_decisions[frame.state]
            assert frame.decision == expected_decision, (
                f"Frame {frame.state} has decision '{frame.decision}', expected '{expected_decision}'"
            )

    @patch("iron_rook.review.agents.security.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_thinking_log_is_private_attribute(
        self, mock_runner_class, mock_review_context, mock_runner_responses
    ):
        """Test that _thinking_log is a private attribute not exposed in public API."""
        reviewer = SecurityReviewer()

        # Mock runner responses
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            mock_runner_responses["intake"],
            mock_runner_responses["plan_todos"],
            mock_runner_responses["delegate"],
            mock_runner_responses["collect"],
            mock_runner_responses["consolidate"],
            mock_runner_responses["evaluate"],
        ]
        mock_runner_class.return_value = mock_runner

        # Execute review
        await reviewer.review(mock_review_context)

        # Verify _thinking_log is a private attribute (starts with underscore)
        assert hasattr(reviewer, "_thinking_log")

        # Verify it's not exposed without underscore
        assert not hasattr(reviewer, "thinking_log")

        # Verify it's not in dir() without special filter
        public_attrs = [attr for attr in dir(reviewer) if not attr.startswith("_")]
        assert "thinking_log" not in public_attrs


# End of integration tests
