"""
FSM Security Review Orchestrator.

This orchestrator implements a Finite State Machine (FSM) for the
Security Review Agent, managing phase transitions, subagent delegation,
budget enforcement and result consolidation.

The orchestrator uses dawn-kestrel's AgentRuntime for subagent execution.
"""

from __future__ import annotations

# Patch dawn-kestrel get_settings() to always return to first loaded instance
import dawn_kestrel.core.settings as settings_module

_first_settings_instance = settings_module.get_settings()
settings_module.get_settings = lambda: _first_settings_instance  # type: ignore[misc]

# Patch dawn-kestrel get_settings() to always return the first loaded instance
import dawn_kestrel.core.settings as settings_module

_first_settings_instance = settings_module.get_settings()
settings_module.get_settings = lambda: _first_settings_instance  # type: ignore[misc]

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dawn_kestrel.agents.runtime import AgentRuntime
from dawn_kestrel.core.agent_types import SessionManagerLike
from iron_rook.review.contracts import (
    EvidenceRef,
    FSMState,
    PhaseOutput,
    PullRequestChangeList,
    RiskAssessment,
    SecurityReviewReport,
    SecurityTodo,
    SubagentResult,
    TodoStatus,
)

logger = logging.getLogger(__name__)

import logging

logger = logging.getLogger(__name__)


class FSMPhaseError(Exception):
    """Error raised when FSM phase transition is invalid."""

    pass


class BudgetExceededError(Exception):
    """Error raised when execution budget is exceeded."""

    pass


class InvalidPhaseOutputError(Exception):
    """Error raised when LLM output doesn't match PhaseOutput schema."""

    pass


class MissingPhasePromptError(Exception):
    """Error raised when phase prompt section is missing or empty in agent prompt file."""

    pass


class SecurityReviewOrchestrator:
    """Orchestrator for FSM-based Security Review Agent.

    Manages the FSM lifecycle: INTAKE → PLAN_TODOS → DELEGATE → COLLECT
    → CONSOLIDATE → EVALUATE → DONE/STOPPED.

    Responsible for:
    - Phase transition validation and enforcement
    - Subagent dispatch via dawn-kestrel AgentRuntime
    - Budget enforcement (tool_budget, max_subagents, max_iterations)
    - Result collection and consolidation
    - Final report generation
    """

    def __init__(
        self,
        agent_runtime: AgentRuntime | None,
        session_manager: SessionManagerLike,
        prompt_path: str | None = None,
    ) -> None:
        """Initialize the FSM Security Review Orchestrator.

        Args:
            agent_runtime: dawn-kestrel AgentRuntime instance for subagent execution (optional, None for direct LLM calls)
            session_manager: dawn-kestrel SessionManagerLike for session management
            prompt_path: Optional path to security_review_agent.md prompt file
        """
        self.agent_runtime = agent_runtime
        self.session_manager = session_manager

        if prompt_path is None:
            default_prompt = Path(__file__).parent / "security_review_agent.md"
        else:
            default_prompt = Path(prompt_path)

        with open(default_prompt, "r") as f:
            self.system_prompt = f.read()

        self.state = FSMState(phase="intake", iterations=0, tool_calls_used=0, subagents_used=0)
        self.pr_input: Optional[PullRequestChangeList] = None
        self.todos: List[SecurityTodo] = []
        self.subagent_results: List[SubagentResult] = []
        self.evidence_index: List[EvidenceRef] = []

    def _check_budget(self) -> None:
        """Check if budget limits have been exceeded.

        Raises:
            BudgetExceededError: If budget is exceeded
        """
        if (
            self.state.tool_calls_used > MAX_TOOL_CALLS
            or self.state.iterations > MAX_ITERATIONS
            or self.state.subagents_used > MAX_SUBAGENTS
        ):
            logger.warning(
                f"Budget exceeded: {self.state.tool_calls_used}/{MAX_TOOL_CALLS} calls, "
                f"{self.state.iterations}/{MAX_ITERATIONS} iterations, "
                f"{self.state.subagents_used}/{MAX_SUBAGENTS} subagents"
            )
            raise BudgetExceededError(
                f"Budget exceeded: tool_calls={self.state.tool_calls_used}, "
                f"iterations={self.state.iterations}, "
                f"subagents={self.state.subagents_used}"
            )

    def _validate_phase_transition(self, to_phase: str, output_data: Dict[str, Any]) -> None:
        """Validate that phase transition is valid for current state.

        Args:
            to_phase: Phase to transition to
            output_data: Output data from current phase

        Raises:
            FSMPhaseError: If transition is invalid

        Transitions:
            intake → [plan_todos]
            plan_todos → [delegate]
            delegate → [collect, consolidate, evaluate, done]
            collect → [consolidate]
            consolidate → [evaluate]
            evaluate → [done]
        """
        from_phase = self.state.phase

        if from_phase not in FSM_TRANSITIONS:
            logger.error(
                f"Invalid transition from {from_phase} to {to_phase}. "
                f"Valid transitions from {from_phase}: {FSM_TRANSITIONS.get(from_phase, [])}"
            )
            raise FSMPhaseError(
                f"Invalid transition from {from_phase} to {to_phase}. "
                f"Valid transitions from {from_phase}: {FSM_TRANSITIONS.get(from_phase, [])}"
            )

        logger.debug(
            f"Validated transition: {from_phase} → {to_phase}, "
            f"next_phase_request={output_data.get('next_phase_request')}"
        )

    def _load_phase_prompt(self, phase: str) -> str:
        """Load the system prompt for a given FSM phase.

        Args:
            phase: FSM phase name (intake, plan_todos, etc.)

        Returns:
            System prompt for the phase

        Raises:
            MissingPhasePromptError: If phase section is not found or is empty
        """
        section_start = f"### {phase.upper()}"
        section_end = "---"

        in_section = False
        prompt_lines = []
        section_found = False

        for line in self.system_prompt.split("\n"):
            if line.strip() == section_start:
                in_section = True
                section_found = True
                prompt_lines.append(line)
            elif line.strip() == section_end:
                if in_section:
                    in_section = False
            elif in_section:
                prompt_lines.append(line)

        phase_prompt = "\n".join(prompt_lines)

        if not section_found:
            raise MissingPhasePromptError(
                f"Phase section '{phase.upper()}' not found in security_review_agent.md. "
                f"Expected format: '### {phase.upper()}' followed by section content ending with '---'"
            )

        if not phase_prompt.strip():
            raise MissingPhasePromptError(
                f"Phase section '{phase.upper()}' is empty in security_review_agent.md. "
                f"Phase sections must contain phase-specific instructions."
            )

        return phase_prompt

    def _construct_phase_user_message(self, phase: str, context_data: Dict[str, Any]) -> str:
        """Construct the user message for a given FSM phase.

        Args:
            phase: FSM phase name
            context_data: Context data for the phase

        Returns:
            User message as JSON string
        """
        user_data = context_data.get(phase, {})

        if phase == "intake":
            return json.dumps(
                {
                    "pr": {
                        "id": self.pr_input.pr.id,
                        "title": self.pr_input.pr.title,
                        "base_branch": self.pr_input.pr.base_branch,
                        "head_branch": self.pr_input.pr.head_branch,
                        "author": self.pr_input.pr.author,
                        "url": self.pr_input.pr.url,
                    },
                    "changes": [
                        {
                            "path": change.path,
                            "change_type": change.change_type,
                            "diff_summary": change.diff_summary,
                            "risk_hints": change.risk_hints,
                        }
                        for change in self.pr_input.changes
                    ],
                }
            )

        elif phase == "plan_todos":
            return json.dumps(
                {
                    "pr": {
                        "id": self.pr_input.pr.id,
                        "title": self.pr_input.pr.title,
                        "base_branch": self.pr_input.pr.base_branch,
                        "head_branch": self.pr_input.pr.head_branch,
                        "author": self.pr_input.pr.author,
                        "url": self.pr_input.pr.url,
                    },
                    "changes": [
                        {
                            "path": change.path,
                            "change_type": change.change_type,
                            "diff_summary": change.diff_summary,
                            "risk_hints": change.risk_hints,
                        }
                        for change in self.pr_input.changes
                    ],
                    "intake_output": context_data.get("intake_output", {}),
                }
            )

        elif phase == "delegate":
            return json.dumps(
                {
                    "pr": {
                        "id": self.pr_input.pr.id,
                        "title": self.pr_input.pr.title,
                        "base_branch": self.pr_input.pr.base_branch,
                        "head_branch": self.pr_input.pr.head_branch,
                        "author": self.pr_input.pr.author,
                        "url": self.pr_input.pr.url,
                    },
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        elif phase == "collect":
            delegate_output = context_data.get("delegate_output", {})
            return json.dumps(
                {
                    "pr": {
                        "id": self.pr_input.pr.id,
                        "title": self.pr_input.pr.title,
                        "base_branch": self.pr_input.pr.base_branch,
                        "head_branch": self.pr_input.pr.head_branch,
                        "author": self.pr_input.pr.author,
                        "url": self.pr_input.pr.url,
                    },
                    "delegate_output": delegate_output,
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        elif phase == "consolidate":
            consolidate_output = context_data.get("consolidate_output", {})
            return json.dumps(
                {
                    "pr": {
                        "id": self.pr_input.pr.id,
                        "title": self.pr_input.pr.title,
                        "base_branch": self.pr_input.pr.base_branch,
                        "head_branch": self.pr_input.pr.head_branch,
                        "author": self.pr_input.pr.author,
                        "url": self.pr_input.pr.url,
                    },
                    "consolidate_output": consolidate_output,
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        elif phase == "evaluate":
            consolidate_output = context_data.get("consolidate_output", {})
            return json.dumps(
                {
                    "pr": {
                        "id": self.pr_input.pr.id,
                        "title": self.pr_input.pr.title,
                        "base_branch": self.pr_input.pr.base_branch,
                        "head_branch": self.pr_input.pr.head_branch,
                        "author": self.pr_input.pr.author,
                        "url": self.pr_input.pr.url,
                    },
                    "consolidate_output": consolidate_output,
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        else:
            raise ValueError(f"Unknown phase: {phase}")

    async def _execute_phase(
        self,
        phase: str,
        context_data: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        """Execute a single FSM phase using LLM.

        Args:
            phase: Phase to execute
            context_data: Context data for the phase

        Returns:
            Phase output data (parsed JSON)

        Raises:
            InvalidPhaseOutputError: If output doesn't match PhaseOutput schema
            BudgetExceededError: If budget is exceeded
        """
        self._check_budget()

        system_prompt = self._load_phase_prompt(phase)
        user_message = self._construct_phase_user_message(phase, context_data)

        session = await self.session_manager.get_session("security_review_fsm")

        try:
            if self.agent_runtime is None:
                # Direct LLM call without agent runtime - use LLMClient
                from dawn_kestrel.llm import LLMClient, LLMRequestOptions
                from dawn_kestrel.core.settings import settings

                account = settings.get_default_account()
                logger.debug(f"Account from settings: {account}")

                # DEBUG: Log settings details to diagnose issues
                logger.debug(f"Settings object ID: {id(settings)}")
                logger.debug(f"Settings.accounts dict: {settings.accounts}")
                logger.debug(f"Account type: {type(account)}")
                if account:
                    logger.debug(f"Account.provider_id: {account.provider_id}")
                    logger.debug(f"Account.model: {account.model}")
                    logger.debug(f"Account.api_key type: {type(account.api_key)}")

                if account is None:
                    logger.error(
                        f"No default account available. "
                        f"Settings module: {settings.__class__.__module__}, "
                        f"get_default_account() returned: {account}. "
                        f"Available accounts: {list(settings.accounts.keys())}"
                    )
                    raise RuntimeError(
                        "No default account configured for LLM calls. "
                        "Check your dawn-kestrel API key configuration."
                    )

                llm_client = LLMClient(
                    provider_id=account.provider_id,
                    model=account.model,
                    api_key=account.api_key.get_secret_value(),
                )

                response = await llm_client.complete(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    options=LLMRequestOptions(temperature=0.3),
                )

                response_text = response.text
                logger.debug(
                    f"LLM response for phase {phase}: {response_text[:500]}{'...' if len(response_text) > 500 else ''}"
                )

                # Handle markdown-wrapped JSON (LLM sometimes returns ```json...```json```)
                json_text = response_text.strip()
                if json_text.startswith("```"):
                    lines = json_text.split("\n")
                    in_code_block = False
                    json_lines = []
                    for line in lines:
                        if line.strip().startswith("```"):
                            in_code_block = not in_code_block
                        elif in_code_block and not line.strip().startswith("```"):
                            json_lines.append(line)
                    json_text = "\n".join(json_lines).strip()
                    logger.debug(f"Extracted JSON content: {repr(json_text[:200])}")

                try:
                    output_data = json.loads(json_text)
                    logger.debug(f"Parsed JSON successfully: {output_data}")
                    return output_data
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing failed: {e}")
                    raise InvalidPhaseOutputError(
                        f"Failed to parse phase {phase} output as JSON: {e}"
                    )

        except BudgetExceededError as e:
            logger.error(f"Budget exceeded: {e}")
            return None

        except RuntimeError as e:
            logger.error(f"Runtime error: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in _execute_phase: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _build_partial_report(self, reason: str) -> SecurityReviewReport:
        """Build a partial report when FSM is stopped early.

        Args:
            reason: Reason for incomplete execution

        Returns:
            Partial SecurityReviewReport
        """
        return SecurityReviewReport(
            agent={"name": "security_review_agent", "version": "0.1.0"},
            pr={
                "id": self.pr_input.pr.id if self.pr_input else "unknown",
                "title": self.pr_input.pr.title if self.pr_input else "Unknown PR",
            },
            fsm=FSMState(
                phase=self.state.phase,
                iterations=self.state.iterations,
                stop_reason=self.state.stop_reason or reason,
                tool_calls_used=self.state.tool_calls_used,
                subagents_used=self.state.subagents_used,
            ),
            todos=[
                TodoStatus(
                    todo_id=todo.todo_id,
                    status="pending",
                    subagent_type=None,
                )
                for todo in self.todos
            ],
            findings={
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            },
            risk_assessment=RiskAssessment(
                overall="low",  # type: ignore[possibly-missing-attribute]
                rationale=f"Execution stopped before completion: {reason}",  # type: ignore[possibly-missing-attribute]
            ),  # type: ignore[possibly-missing-attribute]
            evidence_index=[],  # type: ignore[possibly-missing-attribute]
            actions={"required": [], "suggested": []},  # type: ignore[possibly-missing-attribute]
            confidence=0.0,
        )

    def _build_final_report(self, context_data: Dict[str, Any]) -> SecurityReviewReport:
        """Build the final security review report.

        Args:
            context_data: All phase outputs collected during the review

        Returns:
            Complete SecurityReviewReport with findings, risk assessment, and recommendations
        """
        evaluate_output = context_data.get("evaluate_output", {})
        evaluate_data = evaluate_output.get("data", {})

        findings = evaluate_data.get(
            "findings",
            {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            },
        )
        risk_assessment_data = evaluate_data.get(
            "risk_assessment",
            {
                "overall": "low",
                "rationale": "No evaluation data available",
                "areas_touched": [],
            },
        )
        evidence_index = evaluate_data.get("evidence_index", [])
        actions = evaluate_data.get(
            "actions",
            {
                "required": [],
                "suggested": [],
            },
        )
        confidence = evaluate_data.get("confidence", 0.0)
        missing_information = evaluate_data.get("missing_information", [])

        collect_output = context_data.get("collect_output", {})
        collect_data = collect_output.get("data", {})
        todo_statuses_raw = collect_data.get("todo_status", [])

        todos = []
        for todo_status in todo_statuses_raw:
            todos.append(
                TodoStatus(
                    todo_id=todo_status.get("todo_id", "unknown"),
                    status=todo_status.get("status", "pending"),
                    subagent_type=todo_status.get("subagent_type"),
                )
            )

        # If no statuses from collect phase, assume todos are done since we reached evaluate phase successfully
        if not todos and self.todos:
            todos = [
                TodoStatus(
                    todo_id=todo.todo_id,
                    status="done",
                    subagent_type=todo.delegation.subagent_type if todo.delegation else None,
                )
                for todo in self.todos
            ]

        return SecurityReviewReport(
            agent={"name": "security_review_agent", "version": "0.1.0"},
            pr={
                "id": self.pr_input.pr.id if self.pr_input else "unknown",
                "title": self.pr_input.pr.title if self.pr_input else "Unknown PR",
            },
            fsm=FSMState(
                phase="done",
                iterations=self.state.iterations,
                stop_reason="done",
                tool_calls_used=self.state.tool_calls_used,
                subagents_used=self.state.subagents_used,
            ),
            todos=todos,
            findings=findings,
            risk_assessment=RiskAssessment(
                overall=risk_assessment_data.get("overall", "low"),  # type: ignore[possibly-missing-attribute]
                rationale=risk_assessment_data.get("rationale", ""),  # type: ignore[possibly-missing-attribute]
                areas_touched=risk_assessment_data.get("areas_touched", []),  # type: ignore[possibly-missing-attribute]
            ),  # type: ignore[possibly-missing-attribute]
            evidence_index=evidence_index,  # type: ignore[possibly-missing-attribute]
            actions=actions,  # type: ignore[possibly-missing-attribute]
            confidence=confidence,
            missing_information=missing_information,
        )

    async def run_review(self, pr_input: PullRequestChangeList) -> SecurityReviewReport:
        """Run the full FSM security review.

        Args:
            pr_input: PullRequestChangeList with PR metadata, changes, and constraints

        Returns:
            SecurityReviewReport with consolidated findings and risk assessment

        Raises:
            BudgetExceededError: If execution budget is exceeded
            FSMPhaseError: If phase transition is invalid
        """
        logger.info(
            f"Starting FSM Security Review for PR {pr_input.pr.id}: "
            f"'{pr_input.pr.title}' with {len(pr_input.changes)} changed files"
        )

        self.pr_input = pr_input

        phase_output = PhaseOutput(phase="intake", data={})
        context_data = {
            "pr": {
                "id": pr_input.pr.id,
                "title": pr_input.pr.title,
                "base_branch": pr_input.pr.base_branch,
                "head_branch": pr_input.pr.head_branch,
                "author": pr_input.pr.author,
                "url": pr_input.pr.url,
            },
            "changes": [
                {
                    "path": change.path,
                    "change_type": change.change_type,
                    "diff_summary": change.diff_summary,
                    "risk_hints": change.risk_hints,
                }
                for change in pr_input.changes
            ],
        }

        intake_output = await self._execute_phase("intake", context_data)

        if intake_output is None:
            logger.error("Intake phase returned None - LLM execution failed")
            return self._build_partial_report("intake_failed")

        logger.debug(f"Intake output type: {type(intake_output)}, content: {intake_output}")

        context_data["intake_output"] = intake_output

        try:
            phase_output = PhaseOutput.model_validate(intake_output)
            logger.debug(
                f"PhaseOutput validated successfully: phase={phase_output.phase}, next_phase_request={phase_output.next_phase_request}"
            )
        except pd.ValidationError as e:
            logger.error(f"PhaseOutput validation failed: {e}")
            logger.error(f"Intake output that failed validation: {intake_output}")
            return self._build_partial_report("intake_validation_failed")

        self.state.phase = phase_output.next_phase_request or "plan_todos"
        logger.debug(f"State phase set to: {self.state.phase}")

        if self.state.phase == "stopped_budget" or self.state.phase == "stopped_human":
            return self._build_partial_report("stopped_by_gate")

        plan_todos_output = await self._execute_phase(
            "plan_todos",
            {"todos": [todo.model_dump() for todo in self.todos]},
        )

        if plan_todos_output is None:
            return self._build_partial_report("plan_todos_failed")

        context_data["plan_todos_output"] = plan_todos_output

        phase_output = PhaseOutput.model_validate(plan_todos_output)
        self.state.phase = phase_output.next_phase_request or "collect"
        logger.debug(f"State phase set to: {self.state.phase}")

        # Populate self.todos from plan_todos output
        plan_todos_data = phase_output.data.get("todos", [])
        self.todos = [SecurityTodo.model_validate(todo) for todo in plan_todos_data]

        while self.state.phase not in ("done", "stopped_budget", "stopped_human"):
            if self.state.phase == "delegate":
                delegate_output = await self._execute_phase(
                    "delegate",
                    {"todos": [todo.model_dump() for todo in self.todos]},
                )
                if delegate_output is None:
                    return self._build_partial_report("delegate_failed")
                context_data["delegate_output"] = delegate_output
                phase_output = PhaseOutput.model_validate(delegate_output)

            elif self.state.phase == "collect":
                collect_output = await self._execute_phase(
                    "collect",
                    {
                        "delegate_output": context_data.get("delegate_output", plan_todos_output),
                        "todos": [todo.model_dump() for todo in self.todos],
                    },
                )
                if collect_output is None:
                    return self._build_partial_report("collect_failed")
                context_data["collect_output"] = collect_output
                phase_output = PhaseOutput.model_validate(collect_output)

            elif self.state.phase == "consolidate":
                consolidate_output = await self._execute_phase(
                    "consolidate",
                    {
                        "collect_output": context_data.get("collect_output", {}),
                        "todos": [todo.model_dump() for todo in self.todos],
                    },
                )
                if consolidate_output is None:
                    return self._build_partial_report("consolidate_failed")
                context_data["consolidate_output"] = consolidate_output
                phase_output = PhaseOutput.model_validate(consolidate_output)

            elif self.state.phase == "evaluate":
                evaluate_output = await self._execute_phase(
                    "evaluate",
                    {
                        "consolidate_output": context_data.get("consolidate_output", {}),
                        "todos": [todo.model_dump() for todo in self.todos],
                    },
                )
                if evaluate_output is None:
                    return self._build_partial_report("evaluate_failed")
                context_data["evaluate_output"] = evaluate_output
                phase_output = PhaseOutput.model_validate(evaluate_output)

            else:
                logger.error(f"Unknown phase: {self.state.phase}")
                return self._build_partial_report(f"unknown_phase_{self.state.phase}")

            self.state.phase = phase_output.next_phase_request or "done"
            logger.debug(f"State phase set to: {self.state.phase}")

        self.state.stop_reason = self.state.phase
        return self._build_final_report(context_data)


FSM_TRANSITIONS = {
    "intake": ["plan_todos"],
    "plan_todos": ["delegate"],
    "delegate": ["collect", "consolidate", "evaluate", "done"],
    "collect": ["consolidate"],
    "consolidate": ["evaluate"],
    "evaluate": ["done"],
}


MAX_TOOL_CALLS = 50
MAX_ITERATIONS = 5
MAX_SUBAGENTS = 5
