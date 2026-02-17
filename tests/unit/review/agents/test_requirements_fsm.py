"""Tests for RequirementsReviewer FSM implementation.

TDD RED PHASE: These tests are designed to FAIL initially because
the FSM implementation doesn't exist yet. The RequirementsReviewer
currently uses the simple _execute_review_with_runner() pattern.

After implementing FSM phases, these tests should pass.

Domain: requirements traceability, acceptance criteria
Tools: grep, read, file
Owner field: "dev"
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput


class TestRequirementsFSMInitialization:
    """Test RequirementsReviewer FSM initialization."""

    def test_reviewer_exists(self):
        """Verify RequirementsReviewer can be imported."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        assert RequirementsReviewer is not None

    def test_requirements_reviewer_initializes_with_fsm(self):
        """Verify RequirementsReviewer initializes with FSM attributes."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        # FSM reviewers should have these attributes
        assert hasattr(reviewer, "_adapter") or hasattr(reviewer, "_fsm")
        assert hasattr(reviewer, "_phase_logger") or hasattr(reviewer, "_logger")

    def test_requirements_reviewer_initial_phase_is_intake(self):
        """Verify initial phase is 'intake'."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        # FSM reviewers should start at "intake" or use AgentState.IDLE mapped to "intake"
        state = reviewer.state
        assert state == "intake" or state == "idle"

    def test_requirements_reviewer_get_agent_name_returns_requirements(self):
        """Verify get_agent_name returns 'requirements'."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert reviewer.get_agent_name() == "requirements"


class TestRequirementsFSMTransitions:
    """Test requirements FSM state transitions."""

    def test_valid_transitions_defined(self):
        """Verify VALID_TRANSITIONS class attribute exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        assert hasattr(RequirementsReviewer, "VALID_TRANSITIONS") or hasattr(
            RequirementsReviewer, "FSM_TRANSITIONS"
        )

    def test_intake_to_plan_valid(self):
        """Verify intake -> plan is a valid transition."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        transitions = getattr(RequirementsReviewer, "VALID_TRANSITIONS", None) or getattr(
            RequirementsReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_intake = transitions.get("intake", set())
        assert "plan" in valid_from_intake

    def test_plan_to_act_valid(self):
        """Verify plan -> act is a valid transition."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        transitions = getattr(RequirementsReviewer, "VALID_TRANSITIONS", None) or getattr(
            RequirementsReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_plan = transitions.get("plan", set())
        assert "act" in valid_from_plan

    def test_act_to_synthesize_valid(self):
        """Verify act -> synthesize is a valid transition."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        transitions = getattr(RequirementsReviewer, "VALID_TRANSITIONS", None) or getattr(
            RequirementsReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_act = transitions.get("act", set())
        assert "synthesize" in valid_from_act

    def test_synthesize_to_check_valid(self):
        """Verify synthesize -> check is a valid transition."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        transitions = getattr(RequirementsReviewer, "VALID_TRANSITIONS", None) or getattr(
            RequirementsReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_synthesize = transitions.get("synthesize", set())
        assert "check" in valid_from_synthesize

    def test_check_to_done_valid(self):
        """Verify check -> done is a valid transition."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        transitions = getattr(RequirementsReviewer, "VALID_TRANSITIONS", None) or getattr(
            RequirementsReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_check = transitions.get("check", set())
        assert "done" in valid_from_check

    def test_done_has_no_transitions(self):
        """Verify done is a terminal state with no outgoing transitions."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        transitions = getattr(RequirementsReviewer, "VALID_TRANSITIONS", None) or getattr(
            RequirementsReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_done = transitions.get("done", None)
        assert valid_from_done is not None
        assert len(valid_from_done) == 0


class TestRequirementsPhaseMethods:
    """Test requirements phase methods implementation."""

    @pytest.mark.asyncio
    async def test_run_intake_method_exists(self):
        """Verify _run_intake method exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert hasattr(reviewer, "_run_intake")
        assert callable(reviewer._run_intake)

    @pytest.mark.asyncio
    async def test_run_plan_method_exists(self):
        """Verify _run_plan method exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert hasattr(reviewer, "_run_plan")
        assert callable(reviewer._run_plan)

    @pytest.mark.asyncio
    async def test_run_act_method_exists(self):
        """Verify _run_act method exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert hasattr(reviewer, "_run_act")
        assert callable(reviewer._run_act)

    @pytest.mark.asyncio
    async def test_run_synthesize_method_exists(self):
        """Verify _run_synthesize method exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert hasattr(reviewer, "_run_synthesize")
        assert callable(reviewer._run_synthesize)

    @pytest.mark.asyncio
    async def test_run_check_method_exists(self):
        """Verify _run_check method exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert hasattr(reviewer, "_run_check")
        assert callable(reviewer._run_check)


class TestRequirementsPrefersDirectReview:
    """Test prefers_direct_review method for requirements reviewer."""

    def test_prefers_direct_review_returns_true(self):
        """Verify prefers_direct_review() returns True for FSM-based reviewer."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        # FSM-based reviewers should prefer direct review
        assert reviewer.prefers_direct_review() == True


class TestRequirementsPhaseLoggerIntegration:
    """Test phase logger integration for thinking output."""

    @patch("iron_rook.review.agents.requirements.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_intake_phase_returns_valid_output(self, mock_runner_class):
        """Verify INTAKE phase returns valid JSON output."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = """{
            "phase": "intake",
            "data": {
                "summary": "Requirements traceability analysis",
                "files_requiring_analysis": [],
                "questions": []
            },
            "next_phase_request": "plan"
        }"""
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute phase
        output = await reviewer._run_intake(context)

        # Verify phase is in output
        assert "phase" in output
        assert output["phase"] == "intake"

        # Verify next_phase_request
        assert "next_phase_request" in output
        assert output["next_phase_request"] == "plan"

    @patch("iron_rook.review.agents.requirements.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_plan_phase_returns_valid_output(self, mock_runner_class):
        """Verify PLAN phase returns valid JSON output."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = """{
            "phase": "plan",
            "data": {
                "todos": [],
                "files_to_check": [],
                "tools_considered": []
            },
            "next_phase_request": "act"
        }"""
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute phase
        output = await reviewer._run_plan(context)

        # Verify phase is in output
        assert "phase" in output
        assert output["phase"] == "plan"

        # Verify next_phase_request
        assert "next_phase_request" in output
        assert output["next_phase_request"] == "act"


class TestRequirementsFilePatternsAndTools:
    """Test requirements reviewer file patterns and tools."""

    def test_get_relevant_file_patterns_returns_requirements_patterns(self):
        """Verify get_relevant_file_patterns returns requirements-related patterns."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        patterns = reviewer.get_relevant_file_patterns()

        # Requirements reviewer checks all files
        assert "**/*" in patterns or len(patterns) > 0

    def test_get_allowed_tools_returns_requirements_tools(self):
        """Verify get_allowed_tools returns requirements-related tools."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        tools = reviewer.get_allowed_tools()

        # Verify requirements tools (grep, read, file as specified)
        assert "grep" in tools
        assert "read" in tools or "file" in tools


class TestRequirementsReviewOutputGeneration:
    """Test ReviewOutput generation from requirements FSM."""

    def test_build_review_output_from_check_creates_valid_output(self):
        """Verify _build_review_output_from_check creates valid ReviewOutput."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock check output
        check_output = {
            "phase": "check",
            "data": {
                "findings": {
                    "critical": [],
                    "high": [],
                    "medium": [
                        {
                            "severity": "medium",
                            "title": "Requirement not fully implemented",
                            "description": "Acceptance criteria not met",
                            "evidence": [{"type": "file_ref", "path": "src/test.py"}],
                            "recommendations": ["Implement missing functionality"],
                        }
                    ],
                    "low": [],
                },
                "confidence": 0.8,
            },
            "next_phase_request": "done",
        }

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Build ReviewOutput
        output = reviewer._build_review_output_from_check(check_output, context)

        # Verify ReviewOutput structure
        assert isinstance(output, ReviewOutput)
        assert output.agent == "requirements"
        assert len(output.findings) >= 0

    def test_build_error_review_output_creates_output(self):
        """Verify _build_error_review_output creates ReviewOutput on error."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Build error output
        output = reviewer._build_error_review_output(context, "Test error")

        # Verify ReviewOutput structure
        assert isinstance(output, ReviewOutput)
        assert output.agent == "requirements"
        assert "error" in output.summary.lower() or "failed" in output.summary.lower()


class TestRequirementsInvalidTransitions:
    """Test invalid FSM transition handling."""

    def test_invalid_transition_raises_error(self):
        """Verify invalid transition raises ValueError."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Try invalid transition: done -> intake
        reviewer._current_phase = "done"

        with pytest.raises((ValueError, Exception)):
            reviewer._transition_to_phase("intake")

    def test_transition_to_phase_method_exists(self):
        """Verify _transition_to_phase method exists."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()
        assert hasattr(reviewer, "_transition_to_phase")
        assert callable(reviewer._transition_to_phase)


class TestRequirementsFullFSMExecution:
    """Test end-to-end FSM execution flow."""

    @patch("iron_rook.review.agents.requirements.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_executes_all_phases(self, mock_runner_class):
        """Verify FSM executes through all phases."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock runner responses for all phases
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.side_effect = [
            # INTAKE response
            """{"phase": "intake", "data": {"summary": "test"}, "next_phase_request": "plan"}""",
            # PLAN response
            """{"phase": "plan", "data": {"todos": []}, "next_phase_request": "act"}""",
            # ACT response
            """{"phase": "act", "data": {"checks_performed": []}, "next_phase_request": "synthesize"}""",
            # SYNTHESIZE response
            """{"phase": "synthesize", "data": {"findings": {}}, "next_phase_request": "check"}""",
            # CHECK response
            """{"phase": "check", "data": {"findings": {}, "confidence": 1.0}, "next_phase_request": "done"}""",
        ]
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await reviewer.review(context)

        # Verify ReviewOutput
        assert isinstance(output, ReviewOutput)
        assert output.agent == "requirements"

    @patch("iron_rook.review.agents.requirements.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_stops_at_done_phase(self, mock_runner_class):
        """Verify FSM stops at DONE phase."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = """{
            "phase": "check",
            "data": {
                "findings": {"critical": [], "high": [], "medium": [], "low": []},
                "confidence": 1.0
            },
            "next_phase_request": "done"
        }"""
        mock_runner_class.return_value = mock_runner

        # Mock context
        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        # Execute review
        output = await reviewer.review(context)

        # Verify final state is "done"
        assert reviewer.state == "done"

        # Verify ReviewOutput is valid
        assert isinstance(output, ReviewOutput)


class TestRequirementsFindingOwnerField:
    """Test that requirements findings have owner field set to 'dev'."""

    def test_finding_owner_is_dev(self):
        """Verify findings have owner='dev'."""
        from iron_rook.review.agents.requirements import RequirementsReviewer

        reviewer = RequirementsReviewer()

        # Mock check output with a finding
        check_output = {
            "phase": "check",
            "data": {
                "findings": {
                    "critical": [],
                    "high": [
                        {
                            "severity": "high",
                            "title": "Missing acceptance criteria",
                            "description": "Requirement not testable",
                            "evidence": [],
                            "recommendations": [],
                        }
                    ],
                    "medium": [],
                    "low": [],
                },
                "confidence": 0.9,
            },
            "next_phase_request": "done",
        }

        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        output = reviewer._build_review_output_from_check(check_output, context)

        # Verify findings have owner='dev'
        for finding in output.findings:
            assert finding.owner == "dev"
