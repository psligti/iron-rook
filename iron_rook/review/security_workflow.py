"""Security Workflow FSM - Subclass of dawn-kestrel's WorkflowFSM.

This module provides a security-focused workflow FSM that:
- Reuses dawn-kestrel's workflow machinery (FSM, budget, stop conditions)
- Adds security-specific prompts and context
- Uses risk-based todo prioritization
- Loads security context from SECURITY_CONTEXT.md

The unique value here is the SECURITY PROMPTS, not the FSM machinery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from dawn_kestrel.agents.workflow_fsm import (
    WorkflowFSM,
    WorkflowConfig,
    WorkflowBudget,
    WorkflowState,
)
from dawn_kestrel.agents.runtime import AgentRuntime
from dawn_kestrel.agents.workflow import (
    IntakeOutput,
    PlanOutput,
    ActOutput,
    SynthesizeOutput,
    CheckOutput,
    get_intake_output_schema,
    get_plan_output_schema,
    get_act_output_schema,
    get_synthesize_output_schema,
    get_check_output_schema,
)
from dawn_kestrel.core.result import Result, Err
from dawn_kestrel.core.agent_task import TaskStatus
from dawn_kestrel.core.mediator import EventMediator

if TYPE_CHECKING:
    from dawn_kestrel.core.agent_types import SessionManagerLike
    from dawn_kestrel.tools.framework import ToolRegistry

from iron_rook.review.security_context import load_security_context

logger = logging.getLogger(__name__)


# Risk-based priority ordering (higher risk = higher priority)
RISK_PRIORITY = {
    "authn_authz": 0,
    "injection": 1,
    "crypto": 2,
    "data_exposure": 3,
    "secrets": 4,
    "dos": 5,
    "config": 6,
    "general": 7,
}


@dataclass
class SecurityWorkflowConfig:
    """Configuration for security workflow FSM."""

    agent_name: str = "security_fsm"
    session_id: str = ""
    tool_ids: List[str] = field(default_factory=list)
    skill_names: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    session_manager: "Optional[SessionManagerLike]" = None
    tools: "Optional[ToolRegistry]" = None
    budget: WorkflowBudget = field(default_factory=WorkflowBudget)

    # Security-specific fields
    changed_files: List[str] = field(default_factory=list)
    diff_content: str = ""
    repo_root: str = ""

    stagnation_threshold: int = 3
    confidence_threshold: float = 0.8
    max_risk_level: str = "high"


class SecurityWorkflowFSM(WorkflowFSM):
    """Security-focused workflow FSM."""

    def __init__(
        self,
        runtime: AgentRuntime,
        config: SecurityWorkflowConfig,
        fsm_id: Optional[str] = None,
        mediator: Optional[EventMediator] = None,
    ):
        workflow_config = WorkflowConfig(
            agent_name=config.agent_name,
            session_id=config.session_id,
            tool_ids=config.tool_ids,
            skill_names=config.skill_names,
            options=config.options,
            session_manager=config.session_manager,
            tools=config.tools,
            budget=config.budget,
            stagnation_threshold=config.stagnation_threshold,
            confidence_threshold=config.confidence_threshold,
            max_risk_level=config.max_risk_level,
        )
        super().__init__(runtime, workflow_config, fsm_id, mediator)

        self._security_config = config
        self._security_context = ""
        if config.repo_root:
            self._security_context = load_security_context(config.repo_root)

    def _require_session_manager(self):
        """Assert that session_manager is configured. Raises RuntimeError if not."""
        if self.config.session_manager is None:
            raise RuntimeError("session_manager is required but was not configured")
        return self.config.session_manager

    def _build_context_summary(self) -> str:
        base_summary = super()._build_context_summary()
        if self._security_context:
            return f"{base_summary}\n\n## SECURITY CONTEXT\n\n{self._security_context}"
        return base_summary

    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response with repair for common issues.

        Handles:
        - Markdown code blocks (```json...```)
        - Unescaped newlines in string values
        - Trailing commas
        - Plain text responses (returns empty dict with warning)

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed JSON dict, or empty dict if no valid JSON found.

        Raises:
            Never raises - returns empty dict on failure for resilience.
        """
        import json
        import re

        if not response or not response.strip():
            logger.warning("Empty response from LLM")
            return {}

        # First, extract JSON from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()

        # Find JSON object boundaries
        start_idx = response.find("{")
        end_idx = response.rfind("}")

        # Check if we actually have JSON-like content
        if start_idx < 0 or end_idx < 0 or end_idx <= start_idx:
            logger.warning(f"No JSON object found in response: {response[:200]}...")
            return {}

        response = response[start_idx : end_idx + 1]

        # Try parsing as-is first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Repair attempt 1: Fix unescaped newlines in string values
        # This regex finds string values and escapes newlines within them
        def repair_json_strings(json_str: str) -> str:
            """Escape unescaped newlines and other control chars in JSON strings."""
            result = []
            i = 0
            in_string = False
            escape_next = False

            while i < len(json_str):
                char = json_str[i]

                if escape_next:
                    result.append(char)
                    escape_next = False
                    i += 1
                    continue

                if char == "\\" and in_string:
                    result.append(char)
                    escape_next = True
                    i += 1
                    continue

                if char == '"':
                    in_string = not in_string
                    result.append(char)
                    i += 1
                    continue

                if in_string:
                    # Handle unescaped control characters inside strings
                    if char == "\n":
                        result.append("\\n")
                    elif char == "\r":
                        result.append("\\r")
                    elif char == "\t":
                        result.append("\\t")
                    else:
                        result.append(char)
                else:
                    result.append(char)

                i += 1

            return "".join(result)

        repaired = repair_json_strings(response)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

        # Repair attempt 2: Remove trailing commas before } or ]
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON after repair attempts: {e}")
            logger.debug(f"Repaired JSON preview: {repaired[:500]}...")
            return {}

    async def _retry_json_parse(
        self,
        phase: str,
        original_response: str,
        schema: str,
        max_retries: int = 1,
    ) -> Dict[str, Any]:
        """Retry LLM call with stronger JSON enforcement when parsing fails.

        Args:
            phase: Name of the phase (for logging)
            original_response: The invalid response that failed to parse
            schema: The JSON schema the response should match
            max_retries: Maximum number of retry attempts

        Returns:
            Parsed JSON dict on success, empty dict on failure.
        """
        for attempt in range(max_retries):
            retry_prompt = f"""CRITICAL ERROR: Your previous response was NOT valid JSON.

You returned:
---
{original_response[:1000]}
---

This is UNACCEPTABLE. You MUST respond with ONLY valid JSON.

REQUIRED OUTPUT FORMAT:
{schema}

ABSOLUTE REQUIREMENTS:
1. Output MUST start with {{ and end with }}
2. NO explanatory text before or after the JSON
3. NO markdown code blocks
4. NO prose - ONLY the JSON object

Now provide your response as valid JSON only:"""

            result = await self.runtime.execute_agent(
                agent_name=self.config.agent_name,
                session_id=self.config.session_id,
                user_message=retry_prompt,
                session_manager=self._require_session_manager(),
                tools=self.config.tools,
                skills=self.config.skill_names,
                options=self.config.options,
            )

            if result.error:
                logger.warning(
                    f"[{phase}] Retry attempt {attempt + 1} failed with error: {result.error}"
                )
                continue

            output_json = self._extract_json_from_response(result.response)
            if output_json:
                logger.info(f"[{phase}] Retry attempt {attempt + 1} succeeded")
                return output_json

            logger.warning(f"[{phase}] Retry attempt {attempt + 1} still returned invalid JSON")

        return {}

    async def _execute_intake_phase(self) -> Result[None]:
        logger.info("Executing security INTAKE phase")

        prompt = f"""You are a security reviewer analyzing PR changes.

Your task:
1. Identify security-sensitive surfaces in the changes
2. List constraints (what you can/cannot check)
3. Capture initial evidence from the diff

## Changed Files
{chr(10).join(f"- {f}" for f in self._security_config.changed_files)}

## Diff Content
```
{self._security_config.diff_content[:10000]}
```

{self._security_context}

{get_intake_output_schema()}

Respond with ONLY valid JSON matching the schema above.
"""

        result = await self.runtime.execute_agent(
            agent_name=self.config.agent_name,
            session_id=self.config.session_id,
            user_message=prompt,
            session_manager=self._require_session_manager(),
            tools=self.config.tools,
            skills=self.config.skill_names,
            options=self.config.options,
        )

        if result.error:
            return Err(f"Intake phase execution failed: {result.error}")

        logger.info(f"[INTAKE] Raw response length: {len(result.response)} chars")
        logger.debug(f"[INTAKE] Raw response: {result.response[:500]}...")

        if not result.response or len(result.response.strip()) == 0:
            logger.warning("[INTAKE] Empty response from LLM, using defaults")
            self.context.intent = "Security review of code changes"
            self.context.constraints = []
            self.context.initial_evidence = []
            return await self.transition_to(WorkflowState.PLAN)

        try:
            output_json = self._extract_json_from_response(result.response)
            logger.info(f"[INTAKE] Parsed JSON keys: {list(output_json.keys())}")

            # Handle empty JSON response - LLM returned plain text instead of JSON
            if not output_json:
                logger.warning("[INTAKE] No valid JSON found in response, using defaults")
                self.context.intent = "Security review of code changes"
                self.context.constraints = []
                self.context.initial_evidence = []
                return await self.transition_to(WorkflowState.PLAN)

            try:
                intake_output = IntakeOutput(**output_json)
            except Exception as validation_error:
                logger.warning(
                    f"[INTAKE] IntakeOutput validation failed: {validation_error}, using defaults"
                )
                self.context.intent = output_json.get("intent", "Security review of code changes")
                self.context.constraints = output_json.get("constraints", [])
                self.context.initial_evidence = output_json.get("initial_evidence", [])
                return await self.transition_to(WorkflowState.PLAN)

            logger.info(f"[INTAKE] IntakeOutput parsed successfully")

            self.context.intent = intake_output.intent
            self.context.constraints = intake_output.constraints
            self.context.initial_evidence = intake_output.initial_evidence
            self.context.last_intake_output = intake_output

            logger.info(f"Intake complete: intent={intake_output.intent[:100]}")
            return await self.transition_to(WorkflowState.PLAN)

        except Exception as e:
            logger.error(f"Failed to parse intake output: {e}")
            # Don't crash the workflow - continue with defaults
            logger.warning("[INTAKE] Continuing to PLAN with defaults due to parse error")
            self.context.intent = "Security review of code changes"
            self.context.constraints = []
            self.context.initial_evidence = []
            return await self.transition_to(WorkflowState.PLAN)

    async def _execute_plan_phase(self) -> Result[None]:
        logger.info("Executing security PLAN phase")

        context_summary = self._build_context_summary()

        prompt = f"""You are in the PLAN phase of a security review.

Your task:
1. Create security TODOs based on the intake analysis
2. Each TODO should include in the 'notes' field: risk_category and what to search for
3. Prioritize by risk (high for auth/injection/crypto, medium for data_exposure/secrets)
4. The system will work on ONE todo at a time

IMPORTANT: The 'notes' field is a simple string. Include all context there (risk_category, search patterns, etc).

Current workflow context:
{context_summary}

{get_plan_output_schema()}

Respond with ONLY valid JSON matching the schema above.
"""

        result = await self.runtime.execute_agent(
            agent_name=self.config.agent_name,
            session_id=self.config.session_id,
            user_message=prompt,
            session_manager=self._require_session_manager(),
            tools=self.config.tools,
            skills=self.config.skill_names,
            options=self.config.options,
        )

        if result.error:
            return Err(f"Plan phase execution failed: {result.error}")

        logger.info(f"[PLAN] Raw response length: {len(result.response)} chars")
        logger.debug(f"[PLAN] Raw response: {result.response[:500]}...")

        if not result.response or len(result.response.strip()) == 0:
            logger.warning("[PLAN] Empty response from LLM, transitioning to DONE")
            return await self.transition_to(WorkflowState.DONE)

        from dawn_kestrel.core.agent_task import create_agent_task

        output_json = self._extract_json_from_response(result.response)
        logger.info(f"[PLAN] Parsed JSON keys: {list(output_json.keys())}")

        if not output_json:
            output_json = await self._retry_json_parse(
                phase="PLAN",
                original_response=result.response,
                schema=get_plan_output_schema(),
            )
            if output_json:
                logger.info(f"[PLAN] Retry succeeded, parsed JSON keys: {list(output_json.keys())}")

        if not output_json:
            logger.warning("[PLAN] No valid JSON found after retry, transitioning to DONE")
            return await self.transition_to(WorkflowState.DONE)

        try:
            plan_output = PlanOutput(**output_json)
        except Exception as validation_error:
            logger.warning(f"[PLAN] PlanOutput validation failed: {validation_error}")
            return await self.transition_to(WorkflowState.DONE)

        for todo_item in plan_output.todos:
            if todo_item.id not in self.context.todos:
                notes_str = todo_item.notes if isinstance(todo_item.notes, str) else ""
                risk_category = "general"
                if "risk_category:" in notes_str.lower():
                    import re

                    match = re.search(r"risk_category:\s*(\w+)", notes_str, re.IGNORECASE)
                    if match:
                        risk_category = match.group(1).lower()

                agent_task = create_agent_task(
                    agent_name=self.config.agent_name,
                    description=todo_item.description,
                    tool_ids=self.config.tool_ids,
                    skill_names=self.config.skill_names,
                    options=self.config.options,
                    metadata={
                        "priority": todo_item.priority,
                        "operation": todo_item.operation,
                        "notes": notes_str,
                        "dependencies": todo_item.dependencies,
                        "risk_category": risk_category,
                    },
                )
                self.context.todos[todo_item.id] = agent_task
            else:
                existing_task = self.context.todos[todo_item.id]
                existing_task.description = todo_item.description
                existing_task.metadata["priority"] = todo_item.priority
                existing_task.metadata["operation"] = todo_item.operation

        self.context.last_plan_output = plan_output

        selected_todo_id = self._select_next_todo()
        if selected_todo_id:
            self.context.current_todo_id = selected_todo_id
            self.context.todos[selected_todo_id].status = TaskStatus.RUNNING
            logger.info(f"Plan complete: selected todo {selected_todo_id}")
        else:
            logger.info("Plan complete: no pending todos")

        return await self.transition_to(WorkflowState.ACT)

    def _select_next_todo(self) -> Optional[str]:
        # Resume in-progress todos first
        for tid, task in self.context.todos.items():
            if task.status == TaskStatus.RUNNING:
                return tid

        # Pick by risk category, then by priority
        pending = [
            (tid, task)
            for tid, task in self.context.todos.items()
            if task.status == TaskStatus.PENDING
        ]

        if not pending:
            return None

        def sort_key(item):
            tid, task = item
            risk_category = task.metadata.get("risk_category", "general")
            risk_priority = RISK_PRIORITY.get(risk_category, 99)
            priority_order = {"high": 0, "medium": 1, "low": 2}
            task_priority = priority_order.get(task.metadata.get("priority", "medium"), 3)
            return (risk_priority, task_priority)

        pending.sort(key=sort_key)
        return pending[0][0]

    async def _execute_act_phase(self) -> Result[None]:
        logger.info("Executing security ACT phase")

        if (
            not self.context.current_todo_id
            or self.context.current_todo_id not in self.context.todos
        ):
            logger.info("No current todo selected, skipping act phase")
            self.context.last_act_output = ActOutput()
            return await self.transition_to(WorkflowState.SYNTHESIZE)

        current_task = self.context.todos[self.context.current_todo_id]
        risk_category = current_task.metadata.get("risk_category", "general")
        notes = current_task.metadata.get("notes", "")

        prompt = f"""You are in the ACT phase of a security review.

SINGLE ACTION CONSTRAINT: Perform exactly ONE tool call this iteration.

Current todo:
- ID: {self.context.current_todo_id}
- Description: {current_task.description}
- Risk Category: {risk_category}
- Priority: {current_task.metadata.get("priority", "medium")}
- Notes: {notes if notes else "Search for relevant security patterns"}

VERIFICATION INSTRUCTIONS:
1. Use grep/read to find evidence BEFORE reporting a finding
2. If you find a potential issue, verify it with actual code
3. Do NOT report issues without evidence
4. If no evidence found, report that the check passed

{get_act_output_schema()}

Respond with ONLY valid JSON matching the schema above.
"""

        result = await self.runtime.execute_agent(
            agent_name=self.config.agent_name,
            session_id=self.config.session_id,
            user_message=prompt,
            session_manager=self._require_session_manager(),
            tools=self.config.tools,
            skills=self.config.skill_names,
            options=self.config.options,
        )

        if result.error:
            return Err(f"Act phase execution failed: {result.error}")

        # Log raw response for debugging
        logger.info(f"[ACT] Raw response length: {len(result.response)} chars")
        logger.debug(f"[ACT] Raw response: {result.response[:500]}...")

        if not result.response or len(result.response.strip()) == 0:
            logger.warning("[ACT] Empty response from LLM, skipping to SYNTHESIZE")
            self.context.last_act_output = ActOutput()
            return await self.transition_to(WorkflowState.SYNTHESIZE)

        try:
            output_json = self._extract_json_from_response(result.response)
            logger.info(f"[ACT] Parsed JSON keys: {list(output_json.keys())}")

            # Handle empty JSON response - LLM returned plain text instead of JSON
            if not output_json:
                logger.warning("[ACT] No valid JSON found in response, using default ActOutput")
                self.context.last_act_output = ActOutput()
                return await self.transition_to(WorkflowState.SYNTHESIZE)

            # Fix action object if missing required fields or has invalid values
            if "action" in output_json and output_json["action"] is not None:
                action = output_json["action"]
                if isinstance(action, dict):
                    # Ensure required fields have defaults
                    action.setdefault("status", "success")
                    action.setdefault("tool_name", "unknown")
                    action.setdefault("result_summary", "")
                    action.setdefault("arguments", {})
                    action.setdefault("duration_seconds", 0.0)
                    action.setdefault("artifacts", [])

                    # Normalize status to valid values (success, failure, timeout)
                    valid_statuses = {"success", "failure", "timeout"}
                    if action.get("status") not in valid_statuses:
                        logger.warning(
                            f"[ACT] Invalid status '{action.get('status')}', defaulting to 'success'"
                        )
                        action["status"] = "success"

            try:
                act_output = ActOutput(**output_json)
            except Exception as validation_error:
                logger.warning(
                    f"[ACT] ActOutput validation failed: {validation_error}, using defaults"
                )
                # Try to create with minimal required fields
                act_output = ActOutput(
                    action=None,
                    acted_todo_id=output_json.get("acted_todo_id", self.context.current_todo_id),
                    tool_result_summary=output_json.get("tool_result_summary", ""),
                    artifacts=output_json.get("artifacts", []),
                    failure=output_json.get("failure", ""),
                )

            logger.info(f"[ACT] ActOutput parsed successfully")

            if act_output.action:
                self.context.budget_consumed.tool_calls += 1

            if act_output.artifacts:
                self.context.artifacts.extend(act_output.artifacts)

            if act_output.action and act_output.action.status == "success":
                new_evidence = [
                    f"{act_output.action.tool_name}: {act_output.action.result_summary}"
                ]
                self.context.update_evidence(new_evidence)

            self.context.last_act_output = act_output
            return await self.transition_to(WorkflowState.SYNTHESIZE)

        except Exception as e:
            logger.error(f"Failed to parse act output: {e}")
            # Don't crash the entire workflow - continue with default output
            logger.warning(
                "[ACT] Continuing to SYNTHESIZE with default ActOutput due to parse error"
            )
            self.context.last_act_output = ActOutput()
            return await self.transition_to(WorkflowState.SYNTHESIZE)

    async def _execute_synthesize_phase(self) -> Result[None]:
        logger.info("Executing security SYNTHESIZE phase")

        context_summary = self._build_context_summary()

        prompt = f"""You are in the SYNTHESIZE phase of a security review.

Your task:
1. Analyze the tool results from the ACT phase
2. Extract any security findings with evidence
3. Do NOT fabricate findings - only report what the evidence shows

Current workflow context:
{context_summary}

Last ACT output:
{self.context.last_act_output.model_dump() if self.context.last_act_output else "None"}

{get_synthesize_output_schema()}

Respond with ONLY valid JSON matching the schema above.
"""

        result = await self.runtime.execute_agent(
            agent_name=self.config.agent_name,
            session_id=self.config.session_id,
            user_message=prompt,
            session_manager=self._require_session_manager(),
            tools=self.config.tools,
            skills=self.config.skill_names,
            options=self.config.options,
        )

        if result.error:
            return Err(f"Synthesize phase execution failed: {result.error}")

        # Log raw response for debugging
        logger.info(f"[SYNTHESIZE] Raw response length: {len(result.response)} chars")
        logger.debug(f"[SYNTHESIZE] Raw response: {result.response[:500]}...")

        if not result.response or len(result.response.strip()) == 0:
            logger.warning("[SYNTHESIZE] Empty response from LLM, skipping to CHECK")
            self.context.last_synthesize_output = SynthesizeOutput()
            return await self.transition_to(WorkflowState.CHECK)

        try:
            output_json = self._extract_json_from_response(result.response)
            logger.info(f"[SYNTHESIZE] Parsed JSON keys: {list(output_json.keys())}")

            # Handle empty JSON response - LLM returned plain text instead of JSON
            if not output_json:
                logger.warning("[SYNTHESIZE] No valid JSON found in response, using defaults")
                self.context.last_synthesize_output = SynthesizeOutput()
                return await self.transition_to(WorkflowState.CHECK)

            try:
                synthesize_output = SynthesizeOutput(**output_json)
            except Exception as validation_error:
                logger.warning(
                    f"[SYNTHESIZE] SynthesizeOutput validation failed: {validation_error}, using defaults"
                )
                self.context.last_synthesize_output = SynthesizeOutput()
                return await self.transition_to(WorkflowState.CHECK)

            logger.info(f"[SYNTHESIZE] SynthesizeOutput parsed successfully")

            for finding in synthesize_output.findings:
                self.context.findings.append(finding.model_dump())

            self.context.last_synthesize_output = synthesize_output
            return await self.transition_to(WorkflowState.CHECK)

        except Exception as e:
            logger.error(f"Failed to parse synthesize output: {e}")
            # Don't crash the workflow - continue with default output
            logger.warning("[SYNTHESIZE] Continuing to CHECK with defaults due to parse error")
            self.context.last_synthesize_output = SynthesizeOutput()
            return await self.transition_to(WorkflowState.CHECK)

    async def _execute_check_phase(self) -> Result[None]:
        logger.info("Executing security CHECK phase")

        context_summary = self._build_context_summary()

        prompt = f"""You are in the CHECK phase of a security review.

Your task:
1. Determine if the current todo is complete (evidence gathered, finding documented)
2. If complete, set todo_complete = true
3. Route to:
   - "act" if todo not complete (need more tool calls)
   - "plan" if todo complete but more todos remain
   - "done" if all todos complete

Current workflow context:
{context_summary}

Current todo ID: {self.context.current_todo_id}

{get_check_output_schema()}

Respond with ONLY valid JSON matching the schema above.
"""

        result = await self.runtime.execute_agent(
            agent_name=self.config.agent_name,
            session_id=self.config.session_id,
            user_message=prompt,
            session_manager=self._require_session_manager(),
            tools=self.config.tools,
            skills=self.config.skill_names,
            options=self.config.options,
        )

        if result.error:
            return Err(f"Check phase execution failed: {result.error}")

        logger.info(f"[CHECK] Raw response length: {len(result.response)} chars")
        logger.debug(f"[CHECK] Raw response: {result.response[:500]}...")

        if not result.response or len(result.response.strip()) == 0:
            logger.warning("[CHECK] Empty response from LLM, defaulting to DONE")
            self.context.iteration_count += 1
            return await self.transition_to(WorkflowState.DONE)

        try:
            output_json = self._extract_json_from_response(result.response)
            logger.info(f"[CHECK] Parsed JSON keys: {list(output_json.keys())}")

            # Handle empty JSON response - LLM returned plain text instead of JSON
            if not output_json:
                logger.warning("[CHECK] No valid JSON found in response, defaulting to DONE")
                self.context.iteration_count += 1
                return await self.transition_to(WorkflowState.DONE)

            try:
                check_output = CheckOutput(**output_json)
            except Exception as validation_error:
                logger.warning(
                    f"[CHECK] CheckOutput validation failed: {validation_error}, defaulting to DONE"
                )
                self.context.iteration_count += 1
                return await self.transition_to(WorkflowState.DONE)

            logger.info(f"[CHECK] CheckOutput parsed successfully")

            if check_output.todo_complete and self.context.current_todo_id:
                self.context.todos[self.context.current_todo_id].status = TaskStatus.COMPLETED
                logger.info(f"Todo {self.context.current_todo_id} marked complete")

            self.context.last_check_output = check_output
            self.context.iteration_count += 1

            next_phase = check_output.next_phase
            if next_phase == "act":
                return await self.transition_to(WorkflowState.ACT)
            elif next_phase == "plan":
                return await self.transition_to(WorkflowState.PLAN)
            else:
                return await self.transition_to(WorkflowState.DONE)

        except Exception as e:
            logger.error(f"Failed to parse check output: {e}")
            # Don't crash the workflow - transition to DONE
            logger.warning("[CHECK] Transitioning to DONE due to parse error")
            self.context.iteration_count += 1
            return await self.transition_to(WorkflowState.DONE)
