"""
FSM Security Review Orchestrator.

This orchestrator implements a Finite State Machine (FSM) for the
Security Review Agent, managing phase transitions, subagent delegation,
budget enforcement and result consolidation.

The orchestrator uses dawn-kestrel's AgentRuntime for subagent execution.
"""

from __future__ import annotations

import pydantic as pd

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


class PhaseContext:
    """Typed context for phase handoffs - validates required fields before phase transitions."""

    def __init__(
        self,
        pr: Optional[PullRequestChangeList] = None,
        pr_dict: Optional[Dict[str, Any]] = None,
        changes_list: Optional[List[Dict[str, Any]]] = None,
        intake_output: Optional[Dict[str, Any]] = None,
        plan_todos_output: Optional[Dict[str, Any]] = None,
        delegate_output: Optional[Dict[str, Any]] = None,
        collect_output: Optional[Dict[str, Any]] = None,
        consolidate_output: Optional[Dict[str, Any]] = None,
        todos: Optional[List[Any]] = None,
    ) -> None:
        """Initialize phase context with typed fields."""
        self.pr = pr
        self.pr_dict = pr_dict
        self.changes_list = changes_list
        self.intake_output = intake_output
        self.plan_todos_output = plan_todos_output
        self.delegate_output = delegate_output
        self.collect_output = collect_output
        self.consolidate_output = consolidate_output
        self.todos = todos or []

    def validate_for_phase(self, phase: str) -> None:
        """Validate that required fields exist for the specified phase.

        Args:
            phase: FSM phase name

        Raises:
            MissingPhaseContextError: If required fields are missing
        """
        required_fields: Dict[str, List[str]] = {
            "intake": ["pr_dict", "changes_list"],
            "plan_todos": ["pr_dict", "changes_list", "intake_output"],
            "delegate": ["pr_dict", "todos"],
            "collect": ["pr_dict", "delegate_output", "todos"],
            "consolidate": ["pr_dict", "collect_output", "todos"],
            "evaluate": ["pr_dict", "consolidate_output", "todos"],
        }

        if phase not in required_fields:
            raise ValueError(f"Unknown phase: {phase}")

        missing_fields = []
        for field in required_fields[phase]:
            if not hasattr(self, field) or getattr(self, field) is None:
                missing_fields.append(field)

        if missing_fields:
            raise MissingPhaseContextError(
                f"Missing required fields for phase '{phase}': {', '.join(missing_fields)}. "
                f"Required fields: {', '.join(required_fields[phase])}"
            )


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


class MissingPhaseContextError(Exception):
    """Error raised when required fields are missing from phase context data."""

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

    def _validate_phase_context(self, phase: str, context_data: Dict[str, Any]) -> None:
        """Validate that required fields exist for the specified phase.

        Args:
            phase: FSM phase name
            context_data: Context data dictionary to validate

        Raises:
            MissingPhaseContextError: If required fields are missing
        """
        phase_context = PhaseContext(
            pr=self.pr_input,
            pr_dict=context_data.get("pr"),
            changes_list=context_data.get("changes"),
            intake_output=context_data.get("intake_output"),
            plan_todos_output=context_data.get("plan_todos_output"),
            delegate_output=context_data.get("delegate_output"),
            collect_output=context_data.get("collect_output"),
            consolidate_output=context_data.get("consolidate_output"),
            todos=self.todos,
        )
        phase_context.validate_for_phase(phase)

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

    def _transition_to_phase(self, next_phase_request: Optional[str]) -> None:
        """Transition to next phase with validation and state updates.

        This method ensures:
        - next_phase_request is validated against FSM_TRANSITIONS
        - self.state.phase is updated atomically
        - self.state.iterations is incremented appropriately
        - self.state.stop_reason is set for stop gates
        - Unexpected/invalid requests raise FSMPhaseError

        Args:
            next_phase_request: Next phase requested by LLM output

        Raises:
            FSMPhaseError: If transition is invalid or request is unexpected
        """
        from_phase = self.state.phase

        # Handle None requests - invalid
        if next_phase_request is None:
            error_msg = (
                f"Phase {from_phase} returned None for next_phase_request. "
                f"Expected one of: plan_todos, delegate, collect, consolidate, evaluate, done, stopped_budget, stopped_human"
            )
            logger.error(error_msg)
            raise FSMPhaseError(error_msg)

        # Validate next_phase_request type - must be string
        if not isinstance(next_phase_request, str):
            error_msg = (
                f"Phase {from_phase} returned invalid type for next_phase_request: {type(next_phase_request)}. "
                f"Expected string. Value: {next_phase_request!r}"
            )
            logger.error(error_msg)
            raise FSMPhaseError(error_msg)

        # Validate next_phase_request is a valid phase value
        valid_phases = {
            "intake",
            "plan_todos",
            "delegate",
            "collect",
            "consolidate",
            "evaluate",
            "done",
            "stopped_budget",
            "stopped_human",
        }
        if next_phase_request not in valid_phases:
            error_msg = (
                f"Phase {from_phase} returned unexpected next_phase_request: {next_phase_request!r}. "
                f"Valid values: {sorted(valid_phases)}"
            )
            logger.error(error_msg)
            raise FSMPhaseError(error_msg)

        # Handle stop states - these are terminal but not part of FSM_TRANSITIONS
        if next_phase_request in ("stopped_budget", "stopped_human"):
            self.state.phase = next_phase_request
            self.state.stop_reason = next_phase_request
            logger.info(f"FSM transitioned to stop state: {next_phase_request}")
            return

        # Handle done - terminal state, validate against FSM_TRANSITIONS
        if next_phase_request == "done":
            # Check if current phase allows transition to done
            allowed_from = FSM_TRANSITIONS.get(from_phase, [])
            if "done" not in allowed_from and from_phase != "done":
                error_msg = (
                    f"Invalid transition from {from_phase} to done. "
                    f"Valid transitions from {from_phase}: {allowed_from}"
                )
                logger.error(error_msg)
                raise FSMPhaseError(error_msg)
            self.state.phase = "done"
            self.state.stop_reason = "done"
            logger.info(f"FSM completed successfully: {from_phase} → done")
            return

        # Validate regular phase transition against FSM_TRANSITIONS
        allowed_from = FSM_TRANSITIONS.get(from_phase, [])
        if next_phase_request not in allowed_from:
            error_msg = (
                f"Invalid transition from {from_phase} to {next_phase_request}. "
                f"Valid transitions from {from_phase}: {allowed_from}"
            )
            logger.error(error_msg)
            raise FSMPhaseError(error_msg)

        # Transition is valid - update state
        self.state.phase = next_phase_request

        # Increment iterations counter on transitions (not on initialization)
        if from_phase != "intake":
            self.state.iterations += 1

        logger.info(
            f"FSM transition: {from_phase} → {next_phase_request}, iterations={self.state.iterations}"
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
        """Construct user message for a given FSM phase.

        Args:
            phase: FSM phase name
            context_data: Context data for phase

        Returns:
            User message as JSON string
        """
        pr_dict = context_data.get("pr")
        changes_list = context_data.get("changes")

        if phase == "intake":
            return json.dumps(
                {
                    "pr": pr_dict,
                    "changes": changes_list,
                }
            )

        elif phase == "plan_todos":
            return json.dumps(
                {
                    "pr": pr_dict,
                    "changes": changes_list,
                    "intake_output": context_data.get("intake_output", {}),
                }
            )

        elif phase == "delegate":
            return json.dumps(
                {
                    "pr": pr_dict,
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        elif phase == "collect":
            delegate_output = context_data.get("delegate_output", {})
            return json.dumps(
                {
                    "pr": pr_dict,
                    "delegate_output": delegate_output,
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        elif phase == "consolidate":
            consolidate_output = context_data.get("consolidate_output", {})
            return json.dumps(
                {
                    "pr": pr_dict,
                    "consolidate_output": consolidate_output,
                    "todos": [todo.model_dump() for todo in self.todos],
                }
            )

        elif phase == "evaluate":
            consolidate_output = context_data.get("consolidate_output", {})
            return json.dumps(
                {
                    "pr": pr_dict,
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

        self._validate_phase_context("intake", context_data)
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

        self._transition_to_phase(phase_output.next_phase_request)

        if self.state.phase in ("stopped_budget", "stopped_human"):
            return self._build_partial_report("stopped_by_gate")

        self._validate_phase_context("plan_todos", context_data)
        plan_todos_output = await self._execute_phase("plan_todos", context_data)

        if plan_todos_output is None:
            return self._build_partial_report("plan_todos_failed")

        context_data["plan_todos_output"] = plan_todos_output

        phase_output = PhaseOutput.model_validate(plan_todos_output)
        self._transition_to_phase(phase_output.next_phase_request)

        # Populate self.todos from plan_todos output
        plan_todos_data = phase_output.data.get("todos", [])
        self.todos = [SecurityTodo.model_validate(todo) for todo in plan_todos_data]

        while self.state.phase not in ("done", "stopped_budget", "stopped_human"):
            if self.state.phase == "delegate":
                self._validate_phase_context("delegate", context_data)
                delegate_output = await self._execute_phase(
                    "delegate",
                    context_data,
                )
                if delegate_output is None:
                    return self._build_partial_report("delegate_failed")
                context_data["delegate_output"] = delegate_output
                phase_output = PhaseOutput.model_validate(delegate_output)

            elif self.state.phase == "collect":
                self._validate_phase_context("collect", context_data)
                collect_output = await self._execute_phase(
                    "collect",
                    context_data,
                )
                if collect_output is None:
                    return self._build_partial_report("collect_failed")
                context_data["collect_output"] = collect_output
                phase_output = PhaseOutput.model_validate(collect_output)

            elif self.state.phase == "consolidate":
                self._validate_phase_context("consolidate", context_data)
                consolidate_output = await self._execute_phase(
                    "consolidate",
                    context_data,
                )
                if consolidate_output is None:
                    return self._build_partial_report("consolidate_failed")
                context_data["consolidate_output"] = consolidate_output
                phase_output = PhaseOutput.model_validate(consolidate_output)

            elif self.state.phase == "evaluate":
                self._validate_phase_context("evaluate", context_data)
                evaluate_output = await self._execute_phase(
                    "evaluate",
                    context_data,
                )
                if evaluate_output is None:
                    return self._build_partial_report("evaluate_failed")
                context_data["evaluate_output"] = evaluate_output
                phase_output = PhaseOutput.model_validate(evaluate_output)

            else:
                logger.error(f"Unknown phase: {self.state.phase}")
                return self._build_partial_report(f"unknown_phase_{self.state.phase}")

            self._transition_to_phase(phase_output.next_phase_request)

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
