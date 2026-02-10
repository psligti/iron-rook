"""Tests for phase prompt loading and JSON envelope compliance."""

from pathlib import Path

import pytest
import pydantic as pd
from unittest.mock import MagicMock
from iron_rook.review.fsm_security_orchestrator import (
    SecurityReviewOrchestrator,
    MissingPhasePromptError,
)


class MockAgentRuntime:
    def __init__(self) -> None:
        self.sessions: dict[str, object] = {}
        self.execute_calls: list[dict[str, object]] = []

    async def get_session(self, session_id: str) -> object:
        if session_id not in self.sessions:
            self.sessions[session_id] = MagicMock()
        return self.sessions[session_id]

    async def release_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id] = None

    async def execute_agent(
        self, agent_name: str, session_id: str, user_message: str, **kwargs: object
    ) -> object:
        self.execute_calls.append(
            {
                "agent_name": agent_name,
                "session_id": session_id,
                "user_message": user_message,
            }
        )

        return MagicMock(
            content='{"phase": "test_phase", "data": {}, "next_phase_request": "test_next"}'
        )


class TestPhasePromptLoading:
    @pytest.fixture
    def mock_session_manager(self) -> object:
        manager = MagicMock(
            **{
                "get_session": MagicMock(
                    side_effect=lambda session_id: MagicMock(
                        id=session_id,
                        list_messages=MagicMock(return_value=[]),
                        add_message=MagicMock(),
                        add_part=MagicMock(),
                        release_session=MagicMock(),
                    )
                ),
            }
        )
        return manager

    @pytest.fixture
    def minimal_prompt_file(self, tmp_path: Path) -> str:
        prompt_file = tmp_path / "minimal_prompt.md"
        content = """# Test Prompt

### INTAKE

This is intake phase content.

---

### PLAN_TODOS

This is plan_todos phase content.

---

"""
        prompt_file.write_text(content)
        return str(prompt_file)

    @pytest.fixture
    def missing_phase_prompt_file(self, tmp_path: Path) -> str:
        prompt_file = tmp_path / "missing_phase_prompt.md"
        content = """# Test Prompt

### INTAKE

This is intake phase content.

---

### DELEGATE

This is delegate phase content.

---

"""
        prompt_file.write_text(content)
        return str(prompt_file)

    def test_load_phase_prompt_all_phases_from_security_review_agent(
        self,
        mock_session_manager: object,
    ) -> None:
        orchestrator = SecurityReviewOrchestrator(
            agent_runtime=MockAgentRuntime(),
            session_manager=mock_session_manager,
            prompt_path=None,
        )

        phases = ["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"]

        for phase in phases:
            prompt = orchestrator._load_phase_prompt(phase)
            assert prompt, f"Phase {phase} should return non-empty prompt"
            assert f"### {phase.upper()}" in prompt, f"Phase {phase} should contain header"


class TestJSONEnvelopeCompliance:
    def test_phase_output_extra_fields_forbidden(self) -> None:
        from iron_rook.review.contracts import PhaseOutput
        import json

        # Extra field at top level should fail with extra="forbid"
        invalid_dict = {
            "phase": "intake",
            "data": {},
            "next_phase_request": "plan_todos",
            "extra_field": "not_allowed",
        }
        with pytest.raises(pd.ValidationError) as exc_info:
            PhaseOutput(**invalid_dict)
        assert "extra" in str(exc_info.value).lower()

    def test_phase_output_valid_intake_output(self) -> None:
        from iron_rook.review.contracts import PhaseOutput

        valid_output = PhaseOutput(
            phase="intake",
            data={
                "summary": "Summary of changes",
                "risk_hypotheses": ["hypothesis 1", "hypothesis 2"],
                "questions": ["question 1"],
            },
            next_phase_request="plan_todos",
        )

        assert valid_output.phase == "intake"
        assert valid_output.next_phase_request == "plan_todos"
        assert valid_output.data["summary"] == "Summary of changes"

    def test_phase_output_valid_evaluate_output(self) -> None:
        from iron_rook.review.contracts import PhaseOutput

        valid_output = PhaseOutput(
            phase="evaluate",
            data={
                "findings": {
                    "critical": [],
                    "high": [],
                    "medium": [],
                    "low": [],
                },
                "risk_assessment": {
                    "overall": "low",
                    "rationale": "No issues found",
                    "areas_touched": [],
                },
                "confidence": 0.9,
            },
            next_phase_request="done",
        )

        assert valid_output.phase == "evaluate"
        assert valid_output.next_phase_request == "done"
        assert valid_output.data["confidence"] == 0.9
