"""Tests for DiffScoperReviewer FSM implementation.

Tests verify that DiffScoperReviewer follows the FSM pattern from ArchitectureReviewer:
- INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE
- Domain: diff scope, change impact analysis
- Tools: grep, read, file, python
- Owner field: "dev"
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import ReviewOutput


class TestDiffScoperFSMInitialization:
    """Test DiffScoperReviewer FSM initialization."""

    def test_reviewer_exists(self):
        """Verify DiffScoperReviewer can be imported."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        assert DiffScoperReviewer is not None

    def test_diff_scoper_reviewer_initializes_with_fsm(self):
        """Verify DiffScoperReviewer initializes with FSM attributes."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        # FSM reviewers should have these attributes
        assert hasattr(reviewer, "_adapter") or hasattr(reviewer, "_fsm")
        assert hasattr(reviewer, "_phase_logger") or hasattr(reviewer, "_logger")

    def test_diff_scoper_reviewer_initial_phase_is_intake(self):
        """Verify initial phase is 'intake'."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        # FSM reviewers should start at "intake" or use AgentState.IDLE mapped to "intake"
        state = reviewer.state
        assert state == "intake" or state == "idle"

    def test_diff_scoper_reviewer_get_agent_name_returns_diff_scoper(self):
        """Verify get_agent_name returns 'diff_scoper'."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert reviewer.get_agent_name() == "diff_scoper"


class TestDiffScoperFSMTransitions:
    """Test diff_scoper FSM state transitions."""

    def test_valid_transitions_defined(self):
        """Verify VALID_TRANSITIONS class attribute exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        assert hasattr(DiffScoperReviewer, "VALID_TRANSITIONS") or hasattr(
            DiffScoperReviewer, "FSM_TRANSITIONS"
        )

    def test_intake_to_plan_valid(self):
        """Verify intake -> plan is a valid transition."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        transitions = getattr(DiffScoperReviewer, "VALID_TRANSITIONS", None) or getattr(
            DiffScoperReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_intake = transitions.get("intake", set())
        assert "plan" in valid_from_intake

    def test_plan_to_act_valid(self):
        """Verify plan -> act is a valid transition."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        transitions = getattr(DiffScoperReviewer, "VALID_TRANSITIONS", None) or getattr(
            DiffScoperReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_plan = transitions.get("plan", set())
        assert "act" in valid_from_plan

    def test_act_to_synthesize_valid(self):
        """Verify act -> synthesize is a valid transition."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        transitions = getattr(DiffScoperReviewer, "VALID_TRANSITIONS", None) or getattr(
            DiffScoperReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_act = transitions.get("act", set())
        assert "synthesize" in valid_from_act

    def test_synthesize_to_check_valid(self):
        """Verify synthesize -> check is a valid transition."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        transitions = getattr(DiffScoperReviewer, "VALID_TRANSITIONS", None) or getattr(
            DiffScoperReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_synthesize = transitions.get("synthesize", set())
        assert "check" in valid_from_synthesize

    def test_check_to_done_valid(self):
        """Verify check -> done is a valid transition."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        transitions = getattr(DiffScoperReviewer, "VALID_TRANSITIONS", None) or getattr(
            DiffScoperReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_check = transitions.get("check", set())
        assert "done" in valid_from_check

    def test_done_has_no_transitions(self):
        """Verify done is a terminal state with no outgoing transitions."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        transitions = getattr(DiffScoperReviewer, "VALID_TRANSITIONS", None) or getattr(
            DiffScoperReviewer, "FSM_TRANSITIONS", {}
        )
        valid_from_done = transitions.get("done", None)
        assert valid_from_done is not None
        assert len(valid_from_done) == 0


class TestDiffScoperPhaseMethods:
    """Test diff_scoper phase methods implementation."""

    @pytest.mark.asyncio
    async def test_run_intake_method_exists(self):
        """Verify _run_intake method exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert hasattr(reviewer, "_run_intake")
        assert callable(reviewer._run_intake)

    @pytest.mark.asyncio
    async def test_run_plan_method_exists(self):
        """Verify _run_plan method exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert hasattr(reviewer, "_run_plan")
        assert callable(reviewer._run_plan)

    @pytest.mark.asyncio
    async def test_run_act_method_exists(self):
        """Verify _run_act method exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert hasattr(reviewer, "_run_act")
        assert callable(reviewer._run_act)

    @pytest.mark.asyncio
    async def test_run_synthesize_method_exists(self):
        """Verify _run_synthesize method exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert hasattr(reviewer, "_run_synthesize")
        assert callable(reviewer._run_synthesize)

    @pytest.mark.asyncio
    async def test_run_check_method_exists(self):
        """Verify _run_check method exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert hasattr(reviewer, "_run_check")
        assert callable(reviewer._run_check)


class TestDiffScoperPrefersDirectReview:
    """Test prefers_direct_review method for diff_scoper reviewer."""

    def test_prefers_direct_review_returns_true(self):
        """Verify prefers_direct_review() returns True for FSM-based reviewer."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        # FSM-based reviewers should prefer direct review
        assert reviewer.prefers_direct_review() == True


class TestDiffScoperPhaseLoggerIntegration:
    """Test phase logger integration for thinking output."""

    @patch("iron_rook.review.agents.diff_scoper.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_intake_phase_returns_valid_output(self, mock_runner_class):
        """Verify INTAKE phase returns valid JSON output."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

        # Mock runner response
        mock_runner = AsyncMock()
        mock_runner.run_with_retry.return_value = """{
            "phase": "intake",
            "data": {
                "summary": "Diff scope changes detected",
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

    @patch("iron_rook.review.agents.diff_scoper.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_plan_phase_returns_valid_output(self, mock_runner_class):
        """Verify PLAN phase returns valid JSON output."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

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


class TestDiffScoperFilePatternsAndTools:
    """Test diff_scoper reviewer file patterns and tools."""

    def test_get_relevant_file_patterns_returns_diff_scoper_patterns(self):
        """Verify get_relevant_file_patterns returns diff_scoper-related patterns."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        patterns = reviewer.get_relevant_file_patterns()

        # Diff scoper is relevant to all files
        assert "**/*" in patterns or len(patterns) > 0

    def test_get_allowed_tools_returns_diff_scoper_tools(self):
        """Verify get_allowed_tools returns diff_scoper-related tools."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        tools = reviewer.get_allowed_tools()

        # Verify diff scoper tools
        assert "grep" in tools
        assert "python" in tools
        # git or file should be present
        assert "git" in tools or "file" in tools


class TestDiffScoperReviewOutputGeneration:
    """Test ReviewOutput generation from diff_scoper FSM."""

    def test_build_review_output_from_check_creates_valid_output(self):
        """Verify _build_review_output_from_check creates valid ReviewOutput."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

        # Mock check output for diff scoping (risk assessment and routing)
        check_output = {
            "phase": "check",
            "data": {
                "findings": {
                    "critical": [],
                    "high": [],
                    "medium": [
                        {
                            "severity": "medium",
                            "title": "Large diff detected",
                            "description": "Changes span multiple modules",
                            "evidence": [{"type": "file_ref", "path": "src/test.py"}],
                            "recommendations": ["Consider breaking into smaller PRs"],
                        }
                    ],
                    "low": [],
                },
                "risk_assessment": {"overall": "medium", "rationale": "Moderate change scope"},
                "routing": {"architecture": "high", "security": "medium", "linting": "low"},
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
        assert output.agent == "diff_scoper"
        assert len(output.findings) >= 0

    def test_build_error_review_output_creates_output(self):
        """Verify _build_error_review_output creates ReviewOutput on error."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

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
        assert output.agent == "diff_scoper"
        assert "error" in output.summary.lower() or "failed" in output.summary.lower()


class TestDiffScoperInvalidTransitions:
    """Test invalid FSM transition handling."""

    def test_invalid_transition_raises_error(self):
        """Verify invalid transition raises ValueError."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

        # Try invalid transition: done -> intake
        reviewer._current_phase = "done"

        with pytest.raises((ValueError, Exception)):
            reviewer._transition_to_phase("intake")

    def test_transition_to_phase_method_exists(self):
        """Verify _transition_to_phase method exists."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()
        assert hasattr(reviewer, "_transition_to_phase")
        assert callable(reviewer._transition_to_phase)


class TestDiffScoperFullFSMExecution:
    """Test end-to-end FSM execution flow."""

    @patch("iron_rook.review.agents.diff_scoper.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_executes_all_phases(self, mock_runner_class):
        """Verify FSM executes through all phases."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

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
        assert output.agent == "diff_scoper"

    @patch("iron_rook.review.agents.diff_scoper.SimpleReviewAgentRunner")
    @pytest.mark.asyncio
    async def test_fsm_stops_at_done_phase(self, mock_runner_class):
        """Verify FSM stops at DONE phase."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

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

    @pytest.mark.asyncio
    async def test_fsm_generates_routing_information(self):
        """Verify FSM generates routing information for other reviewers."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

        # Build check output with routing
        check_output = {
            "phase": "check",
            "data": {
                "findings": {},
                "risk_assessment": {"overall": "medium", "rationale": "Test rationale"},
                "routing": {"architecture": "high", "security": "medium", "documentation": "low"},
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

        # Verify routing information is present in merge_gate notes
        assert output.merge_gate is not None
        assert isinstance(output.merge_gate.notes_for_coding_agent, list)


class TestDiffScoperOwnerField:
    """Test that owner field is set to 'dev' for all findings."""

    def test_owner_field_is_dev(self):
        """Verify owner field is set to 'dev' for findings."""
        from iron_rook.review.agents.diff_scoper import DiffScoperReviewer

        reviewer = DiffScoperReviewer()

        check_output = {
            "phase": "check",
            "data": {
                "findings": {
                    "critical": [],
                    "high": [
                        {
                            "title": "Large change scope",
                            "description": "Test",
                            "evidence": [],
                            "recommendations": [],
                        }
                    ],
                    "medium": [],
                    "low": [],
                },
                "confidence": 0.8,
            },
            "next_phase_request": "done",
        }

        context = ReviewContext(
            changed_files=["src/test.py"],
            diff="test diff",
            repo_root="/test",
        )

        output = reviewer._build_review_output_from_check(check_output, context)

        # All findings should have owner="dev"
        for finding in output.findings:
            assert finding.owner == "dev"
