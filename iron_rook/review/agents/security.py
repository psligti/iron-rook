"""Security Reviewer agent for checking security vulnerabilities with 6-phase FSM."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
import logging
import asyncio

from iron_rook.fsm.loop_state import LoopState
from iron_rook.fsm.loop_fsm import LoopFSM
from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.security_phase_logger import SecurityPhaseLogger
from iron_rook.review.contracts import (
    ReviewOutput,
    Scope,
    MergeGate,
    Finding,
    RunLog,
    ThinkingFrame,
    ThinkingStep,
    get_review_output_schema,
    get_phase_output_schema,
)
from dawn_kestrel.core.harness import SimpleReviewAgentRunner

logger = logging.getLogger(__name__)


# Custom transitions for security FSM phases
SECURITY_FSM_TRANSITIONS: Dict[str, List[str]] = {
    "intake": ["plan_todos"],
    "plan_todos": ["delegate"],
    "delegate": ["collect", "consolidate", "evaluate", "done"],
    "collect": ["consolidate"],
    "consolidate": ["evaluate"],
    "evaluate": ["done"],
}


class SecurityReviewer(BaseReviewerAgent):
    """Reviewer agent specialized in security vulnerability analysis with 6-phase FSM.

    Implements INTAKE → PLAN_TODOS → DELEGATE → COLLECT → CONSOLIDATE → EVALUATE → DONE
    using LoopFSM pattern.

    Checks for:
    - Secrets handling (API keys, passwords, tokens)
    - Authentication/authorization issues
    - Injection risks (SQL, XSS, command)
    - CI/CD exposures
    - Unsafe code execution patterns
    """

    # Override to use custom transitions
    def __init__(
        self,
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
    ):
        """Initialize security reviewer with FSM infrastructure."""
        # Initialize base without calling super().__init__ to avoid duplicate LoopFSM
        from iron_rook.review.verifier import FindingsVerifier, GrepFindingsVerifier
        from iron_rook.fsm.state import AgentState

        self._verifier = verifier or GrepFindingsVerifier()
        # Use LoopFSM directly without mapping to AgentState
        self._fsm = LoopFSM(max_retries=max_retries, agent_runtime=agent_runtime)
        # Map security phase strings to LoopState for transitions
        self._phase_to_loop_state: Dict[str, LoopState] = {
            "intake": LoopState.INTAKE,
            "plan_todos": LoopState.PLAN,
            "delegate": LoopState.ACT,
            "collect": LoopState.SYNTHESIZE,
            "consolidate": LoopState.PLAN,
            "evaluate": LoopState.ACT,
            "done": LoopState.DONE,
        }
        self._phase_logger = SecurityPhaseLogger()
        self._phase_outputs: Dict[str, Any] = {}
        self._current_security_phase: str = "intake"
        self._thinking_log = RunLog()

    @property
    def state(self):
        """Get current security phase as string."""
        # Return security phase name for compatibility
        return self._current_security_phase

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "security_fsm"

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform security review using 6-phase FSM.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with findings, severity, and merge gate decision

        Raises:
            ValueError: If API key is missing or invalid
            TimeoutError: If LLM request times out
            Exception: For other API-related errors
        """
        # Reset FSM for new review
        self._fsm.reset()
        self._phase_outputs = {}
        self._current_security_phase = "intake"

        # Execute 6-phase FSM
        while self._current_security_phase != "done":
            try:
                if self._current_security_phase == "intake":
                    output = await self._run_intake(context)
                    self._phase_outputs["intake"] = output
                    next_phase = output.get("next_phase_request", "plan_todos")
                    self._transition_to_phase(next_phase)

                elif self._current_security_phase == "plan_todos":
                    output = await self._run_plan_todos(context)
                    self._phase_outputs["plan_todos"] = output
                    next_phase = output.get("next_phase_request", "delegate")
                    self._transition_to_phase(next_phase)

                elif self._current_security_phase == "delegate":
                    output = await self._run_delegate(context)
                    self._phase_outputs["delegate"] = output
                    next_phase = output.get("next_phase_request", "collect")
                    self._transition_to_phase(next_phase)

                elif self._current_security_phase == "collect":
                    output = await self._run_collect(context)
                    self._phase_outputs["collect"] = output
                    next_phase = output.get("next_phase_request", "consolidate")
                    self._transition_to_phase(next_phase)

                elif self._current_security_phase == "consolidate":
                    output = await self._run_consolidate(context)
                    self._phase_outputs["consolidate"] = output
                    next_phase = output.get("next_phase_request", "evaluate")
                    self._transition_to_phase(next_phase)

                elif self._current_security_phase == "evaluate":
                    output = await self._run_evaluate(context)
                    self._phase_outputs["evaluate"] = output
                    next_phase = output.get("next_phase_request", "done")
                    self._transition_to_phase(next_phase)

                else:
                    raise ValueError(f"Unknown phase: {self._current_security_phase}")

            except Exception as e:
                logger.error(
                    f"[{self.__class__.__name__}] Phase {self._current_security_phase} failed: {e}"
                )
                # Build partial report with error
                return self._build_error_review_output(context, str(e))

        # Build final ReviewOutput from evaluate phase output
        evaluate_output = self._phase_outputs.get("evaluate", {})
        return self._build_review_output_from_evaluate(evaluate_output, context)

    def _transition_to_phase(self, next_phase: str) -> None:
        """Transition to next security phase with logging.

        Args:
            next_phase: Target phase name (e.g., "plan_todos", "delegate")

        Raises:
            ValueError: If transition is invalid
        """
        # Validate transition against custom FSM_TRANSITIONS
        valid_transitions = SECURITY_FSM_TRANSITIONS.get(self._current_security_phase, [])
        if next_phase not in valid_transitions:
            raise ValueError(
                f"Invalid transition: {self._current_security_phase} -> {next_phase}. "
                f"Valid transitions: {valid_transitions}"
            )

        # Log the transition
        self._phase_logger.log_transition(self._current_security_phase, next_phase)

        # Update current phase
        self._current_security_phase = next_phase

    async def _run_intake(self, context: ReviewContext) -> Dict[str, Any]:
        """Run INTAKE phase: analyze PR changes and identify security surfaces.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "INTAKE", "Analyzing PR changes for security-sensitive surfaces"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("intake")

        # Build user message with context
        user_message = self._build_intake_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("INTAKE", thinking)

        # Log thinking output
        self._phase_logger.log_thinking(
            "INTAKE", f"INTAKE analysis complete, preparing to plan todos"
        )

        # Parse JSON response
        output = self._parse_phase_response(response_text, "intake")

        data = output.get("data", {})
        goals = data.get("goals", [])
        checks = data.get("checks", [])
        risks = data.get("risks", [])

        steps: List[ThinkingStep] = []
        if thinking:
            steps.append(
                ThinkingStep(
                    kind="transition",
                    why=thinking,
                    evidence=[],
                    next="plan_todos",
                    confidence="medium",
                )
            )

        frame = ThinkingFrame(
            state="intake",
            goals=goals if goals else ["Analyze PR changes for security surfaces"],
            checks=checks if checks else ["Identify security-sensitive code areas"],
            risks=risks if risks else data.get("risk_hypotheses", []),
            steps=steps,
            decision=output.get("next_phase_request", "plan_todos"),
        )

        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        return output

    async def _run_plan_todos(self, context: ReviewContext) -> Dict[str, Any]:
        """Run PLAN_TODOS phase: create structured security TODOs.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "PLAN_TODOS", "Creating structured security TODOs with priorities"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("plan_todos")

        # Build user message with context
        user_message = self._build_plan_todos_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("PLAN_TODOS", thinking)

        # Parse JSON response
        output = self._parse_phase_response(response_text, "plan_todos")

        # Create ThinkingFrame with extracted data
        goals = [
            "Create structured security TODOs with priorities",
            "Map TODOs to appropriate subagents or self",
            "Specify tool choices for each TODO",
        ]
        checks = [
            "Verify TODOs cover all risk hypotheses from INTAKE",
            "Ensure each TODO has clear acceptance criteria",
            "Check subagent assignments are appropriate",
        ]
        risks = [
            "Incomplete coverage of security risks",
            "Inappropriate subagent delegation",
            "Missing evidence requirements",
        ]

        # Create ThinkingStep from extracted thinking
        steps = []
        if thinking:
            steps.append(
                ThinkingStep(
                    kind="transition",
                    why=thinking,
                    evidence=["LLM response analysis"],
                    next="delegate",
                    confidence="medium",
                )
            )

        # Get decision from output
        decision = output.get("next_phase_request", "delegate")

        # Create ThinkingFrame
        frame = ThinkingFrame(
            state="plan_todos",
            goals=goals,
            checks=checks,
            risks=risks,
            steps=steps,
            decision=decision,
        )

        # Log ThinkingFrame using phase logger
        self._phase_logger.log_thinking_frame(frame)

        # Add ThinkingFrame to thinking log accumulator
        self._thinking_log.add(frame)

        # Log thinking output
        self._phase_logger.log_thinking(
            "PLAN_TODOS",
            f"PLAN_TODOS complete, {len(self._phase_outputs.get('intake', {}).get('data', {}).get('risk_hypotheses', []))} TODOs planned",
        )

        return output

    async def _run_delegate(self, context: ReviewContext) -> Dict[str, Any]:
        """Run DELEGATE phase: generate subagent requests for delegated TODOs.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "DELEGATE", "Generating subagent requests for delegated TODOs"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("delegate")

        # Build user message with context
        user_message = self._build_delegate_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("DELEGATE", thinking)

        # Parse JSON response
        output = self._parse_phase_response(response_text, "delegate")

        goals = [
            "Generate subagent requests for delegated TODOs",
            "Create local analysis plans for self-assigned TODOs",
            "Validate delegation strategy aligns with TODO priorities",
        ]
        checks = [
            "Verify all delegated TODOs have appropriate subagent requests",
            "Ensure self-assigned TODOs have clear analysis plans",
            "Validate subagent types match TODO risk categories",
        ]
        risks = [
            "Incomplete delegation leading to missing security checks",
            "Inappropriate subagent assignments",
            "Self-analysis may miss complex security patterns",
        ]

        steps = []
        if thinking:
            steps.append(
                ThinkingStep(
                    kind="delegate",
                    why=thinking,
                    evidence=["LLM response analysis"],
                    next=output.get("next_phase_request", "collect"),
                    confidence="medium",
                )
            )

        decision = output.get("next_phase_request", "collect")

        frame = ThinkingFrame(
            state="delegate",
            goals=goals,
            checks=checks,
            risks=risks,
            steps=steps,
            decision=decision,
        )

        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        # Log thinking output
        self._phase_logger.log_thinking("DELEGATE", "DELEGATE complete, subagents dispatched")

        return output

    async def _run_collect(self, context: ReviewContext) -> Dict[str, Any]:
        """Run COLLECT phase: validate and aggregate subagent results.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking("COLLECT", "Validating and aggregating subagent results")

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("collect")

        # Build user message with context
        user_message = self._build_collect_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("COLLECT", thinking)

        # Log thinking output
        self._phase_logger.log_thinking("COLLECT", "COLLECT complete, all TODO statuses marked")

        # Parse JSON response
        output = self._parse_phase_response(response_text, "collect")
        return output

    async def _run_consolidate(self, context: ReviewContext) -> Dict[str, Any]:
        """Run CONSOLIDATE phase: merge and deduplicate findings.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "CONSOLIDATE", "Merging and de-duplicating security findings"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("consolidate")

        # Build user message with context
        user_message = self._build_consolidate_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("CONSOLIDATE", thinking)

        # Log thinking output
        self._phase_logger.log_thinking(
            "CONSOLIDATE", "CONSOLIDATE complete, findings merged and de-duplicated"
        )

        # Parse JSON response
        output = self._parse_phase_response(response_text, "consolidate")
        return output

    async def _run_evaluate(self, context: ReviewContext) -> Dict[str, Any]:
        """Run EVALUATE phase: assess severity and generate final report.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "EVALUATE", "Assessing findings severity and generating final security report"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("evaluate")

        # Build user message with context
        user_message = self._build_evaluate_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("EVALUATE", thinking)

        # Log thinking output
        self._phase_logger.log_thinking("EVALUATE", "EVALUATE complete, final report generated")

        # Parse JSON response
        output = self._parse_phase_response(response_text, "evaluate")
        return output

    def _get_phase_prompt(self, phase: str) -> str:
        """Get phase-specific system prompt.

        Args:
            phase: Phase name (e.g., "INTAKE", "PLAN_TODOS")

        Returns:
            System prompt string for the phase
        """
        # Read phase-specific prompts from security_review_agent.md
        # For now, return a basic prompt structure
        base_prompt = f"""You are the Security Review Agent.

You are in the {phase} phase of the 6-phase security review FSM.

{get_phase_output_schema(phase)}

Your agent name is "security_fsm".

{self._get_phase_specific_instructions(phase)}
"""
        return base_prompt

    def _get_phase_specific_instructions(self, phase: str) -> str:
        """Get phase-specific instructions from security_review_agent.md.

        Args:
            phase: Phase name (e.g., "INTAKE", "PLAN_TODOS")

        Returns:
            Phase-specific instructions string
        """
        instructions = {
            "INTAKE": """INTAKE Phase:
Task:
1. Summarize what changed (by path + change type).
2. Identify likely security surfaces touched.
3. Generate initial risk hypotheses.

Output JSON format:
{
  "phase": "intake",
  "data": {
    "summary": "...",
    "risk_hypotheses": ["..."],
    "questions": ["..."]
  },
  "next_phase_request": "plan_todos"
}
""",
            "PLAN_TODOS": """PLAN_TODOS Phase:
Task:
1. Create structured security TODOs (3-12) with:
   - Priority (high/medium/low)
   - Scope (paths, symbols, related_paths)
   - Risk category (authn_authz, injection, crypto, data_exposure, etc.)
   - Acceptance criteria
   - Evidence requirements
2. Map each TODO to an appropriate subagent_type or "self" if trivial.
3. Specify tool choices considered and chosen.

Output JSON format:
{
  "phase": "plan_todos",
  "data": {
    "todos": [...],
    "delegation_plan": {...},
    "tools_considered": [...],
    "tools_chosen": [...],
    "why": "..."
  },
  "next_phase_request": "delegate"
}
""",
            "DELEGATE": """DELEGATE Phase:
Task:
1. For each TODO requiring delegation, produce a subagent request object.
2. For TODOs marked "self", produce a brief local analysis plan.
3. Do not fabricate tool outputs.

Output JSON format:
{
  "phase": "delegate",
  "data": {
    "subagent_requests": [...],
    "self_analysis_plan": [...]
  },
  "next_phase_request": "collect"
}
""",
            "COLLECT": """COLLECT Phase:
Task:
1. Validate each result references a todo_id and contains evidence.
2. Mark TODO status as done/blocked and explain.
3. Identify any issues with results.

CRITICAL: After validation, you MUST proceed to the CONSOLIDATE phase. Do NOT transition to any other phase.

Output JSON format:
{
  "phase": "collect",
  "data": {
    "todo_status": [...],
    "issues_with_results": []
  },
  "next_phase_request": "consolidate"
}

REMEMBER: The next phase MUST be "consolidate" - this is the only valid transition from COLLECT.
""",
            "CONSOLIDATE": """CONSOLIDATE Phase:
Task:
1. Merge all subagent findings into structured evidence list.
2. De-duplicate findings by severity and finding_id.
3. Synthesize summary of issues found.

Output JSON format:
{
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
}
""",
            "EVALUATE": """EVALUATE Phase:
Task:
1. Assess findings for severity distribution and blockers.
2. Generate final risk assessment (critical/high/medium/low).
3. Generate final security review report.

Output JSON format:
{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [],
      "high": [...],
      "medium": [],
      "low": []
    },
    "risk_assessment": {
      "overall": "high",
      "rationale": "...",
      "areas_touched": [...]
    },
    "evidence_index": [...],
    "actions": {
      "required": [...],
      "suggested": []
    },
    "confidence": 0.9,
    "missing_information": []
  },
  "next_phase_request": "done"
}
""",
        }
        return instructions.get(phase, "")

    def _build_intake_message(self, context: ReviewContext) -> str:
        """Build user message for INTAKE phase.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Formatted user message string
        """
        parts = [
            "## Review Context",
            "",
            f"**Repository Root**: {context.repo_root}",
            "",
            "### Changed Files",
        ]
        for file_path in context.changed_files:
            parts.append(f"- {file_path}")
        parts.append("")
        parts.append("### Diff Content")
        parts.append("```diff")
        parts.append(context.diff)
        parts.append("```")
        return "\n".join(parts)

    def _build_plan_todos_message(self, context: ReviewContext) -> str:
        """Build user message for PLAN_TODOS phase."""
        intake_output = self._phase_outputs.get("intake", {}).get("data", {})
        parts = [
            "## INTAKE Output",
            "",
            json.dumps(intake_output, indent=2),
            "",
            "## Current Phase Context",
            "",
            f"Changed Files: {len(context.changed_files)}",
            f"Diff Size: {len(context.diff)} chars",
        ]
        return "\n".join(parts)

    def _build_delegate_message(self, context: ReviewContext) -> str:
        """Build user message for DELEGATE phase."""
        plan_todos_output = self._phase_outputs.get("plan_todos", {}).get("data", {})
        parts = [
            "## PLAN_TODOS Output",
            "",
            json.dumps(plan_todos_output, indent=2),
            "",
            "## Current Phase Context",
            "",
            f"Changed Files: {len(context.changed_files)}",
        ]
        return "\n".join(parts)

    def _build_collect_message(self, context: ReviewContext) -> str:
        """Build user message for COLLECT phase."""
        delegate_output = self._phase_outputs.get("delegate", {}).get("data", {})
        plan_todos_output = self._phase_outputs.get("plan_todos", {}).get("data", {})
        parts = [
            "## DELEGATE Output",
            "",
            json.dumps(delegate_output, indent=2),
            "",
            "## TODOs from PLAN_TODOS",
            "",
            json.dumps(plan_todos_output.get("todos", []), indent=2),
        ]
        return "\n".join(parts)

    def _build_consolidate_message(self, context: ReviewContext) -> str:
        """Build user message for CONSOLIDATE phase."""
        collect_output = self._phase_outputs.get("collect", {}).get("data", {})
        parts = [
            "## COLLECT Output",
            "",
            json.dumps(collect_output, indent=2),
        ]
        return "\n".join(parts)

    def _build_evaluate_message(self, context: ReviewContext) -> str:
        """Build user message for EVALUATE phase."""
        consolidate_output = self._phase_outputs.get("consolidate", {}).get("data", {})
        parts = [
            "## CONSOLIDATE Output",
            "",
            json.dumps(consolidate_output, indent=2),
        ]
        return "\n".join(parts)

    async def _execute_llm(self, system_prompt: str, user_message: str) -> str:
        """Execute LLM call using SimpleReviewAgentRunner.

        Args:
            system_prompt: System prompt for the LLM
            user_message: User message with context

        Returns:
            LLM response text

        Raises:
            ValueError: If API key is missing or invalid
            TimeoutError: If LLM request times out
            Exception: For other API-related errors
        """
        from dawn_kestrel.core.harness import SimpleReviewAgentRunner

        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        response_text = await runner.run_with_retry(system_prompt, user_message)
        logger.info(f"[{self.__class__.__name__}] Got LLM response: {len(response_text)} chars")
        return response_text

    def _extract_thinking_from_response(self, response_text: str) -> str:
        """Extract thinking/reasoning from LLM response text.

        Attempts to extract thinking in multiple formats:
        1. JSON "thinking" field at top level
        2. JSON "thinking" field inside "data" object
        3. <thinking>...</thinking> tags
        4. Returns empty string if no thinking found

        Args:
            response_text: Raw LLM response text

        Returns:
            Extracted thinking string, or empty string if not found
        """
        # Try to parse as JSON first
        try:
            # Strip markdown code blocks if present
            json_text = response_text
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()

            response_json = json.loads(json_text)

            # Check for "thinking" field at top level
            if "thinking" in response_json:
                thinking = response_json["thinking"]
                return str(thinking) if thinking else ""

            # Check for "thinking" field inside "data" object
            if "data" in response_json and isinstance(response_json["data"], dict):
                if "thinking" in response_json["data"]:
                    thinking = response_json["data"]["thinking"]
                    return str(thinking) if thinking else ""

        except (json.JSONDecodeError, KeyError, ValueError):
            # Not valid JSON or missing fields, try tag format
            pass

        # Try <thinking>...</thinking> tags
        if "<thinking>" in response_text and "</thinking>" in response_text:
            start = response_text.find("<thinking>") + len("<thinking>")
            end = response_text.find("</thinking>")
            thinking = response_text[start:end].strip()
            return thinking

        return ""

    def _parse_phase_response(self, response_text: str, expected_phase: str) -> Dict[str, Any]:
        """Parse phase JSON response with error handling.

        Args:
            response_text: Raw LLM response text
            expected_phase: Expected phase name (for validation)

        Returns:
            Parsed phase output dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        try:
            # Strip markdown code blocks if present
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            output = json.loads(response_text)

            # Validate phase name
            actual_phase = output.get("phase")
            if actual_phase != expected_phase:
                logger.warning(
                    f"[{self.__class__.__name__}] Expected phase '{expected_phase}', got '{actual_phase}'"
                )

            return output
        except json.JSONDecodeError as e:
            logger.error(f"[{self.__class__.__name__}] Failed to parse JSON: {e}")
            logger.error(
                f"[{self.__class__.__name__}] Response (first 500 chars): {response_text[:500]}..."
            )
            raise ValueError(f"Failed to parse phase response: {e}") from e

    def _build_review_output_from_evaluate(
        self, evaluate_output: Dict[str, Any], context: ReviewContext
    ) -> ReviewOutput:
        """Build ReviewOutput from EVALUATE phase output.

        Args:
            evaluate_output: EVALUATE phase output dictionary
            context: ReviewContext containing changed files

        Returns:
            ReviewOutput with findings, severity, and merge gate decision
        """
        data = evaluate_output.get("data", {})
        findings_dict = data.get("findings", {})
        risk_assessment = data.get("risk_assessment", {})
        actions = data.get("actions", {})
        confidence = data.get("confidence", 0.5)

        # Flatten findings from severity buckets
        all_findings: List[Finding] = []
        for severity, findings in findings_dict.items():
            # Map security severity (high, medium, low) to Finding severity (critical, warning, blocking)
            finding_severity = (
                "critical"
                if severity == "high"
                else "warning"
                if severity == "medium"
                else "blocking"
            )
            # Map to Finding confidence (high, medium, low)
            finding_confidence = (
                "high" if severity == "high" else "medium" if severity == "medium" else "low"
            )

            for finding_dict in findings:
                finding = Finding(
                    id="finding-" + str(len(all_findings)),
                    title=finding_dict.get("title", "Security issue"),
                    severity=finding_severity,
                    confidence=finding_confidence,
                    owner="security",
                    estimate="M",
                    evidence=json.dumps(finding_dict.get("evidence", [])),
                    risk=finding_dict.get("description", ""),
                    recommendation=finding_dict.get("recommendations", [""])[0]
                    if finding_dict.get("recommendations")
                    else "",
                    suggested_patch=None,
                )
                all_findings.append(finding)

        # Determine merge gate decision
        overall_risk = risk_assessment.get("overall", "low")

        # Map security risk assessment to ReviewOutput.severity
        # ReviewOutput.severity accepts: "merge", "warning", "critical", "blocking"
        # Security risk uses: "critical", "high", "medium", "low"
        if overall_risk == "critical":
            review_severity = "critical"
        elif overall_risk == "high":
            review_severity = "critical"
        elif overall_risk == "medium":
            review_severity = "warning"
        else:  # low or no issues
            review_severity = "merge"

        if overall_risk in ("critical", "high"):
            decision = "needs_changes"
            must_fix = [f.title for f in all_findings if f.severity in ("critical", "high")]
            should_fix = [f.title for f in all_findings if f.severity == "medium"]
        else:
            decision = "approve"
            must_fix = []
            should_fix = [f.title for f in all_findings if f.severity == "low"]

        relevant_files = [
            file_path
            for file_path in context.changed_files
            if self.is_relevant_to_changes([file_path])
        ]

        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Security review complete. Overall risk: {overall_risk.upper()}. "
            f"Found {len(all_findings)} issues with {confidence:.0%} confidence.",
            severity=review_severity,
            scope=Scope(
                relevant_files=relevant_files,
                ignored_files=[],
                reasoning="Security review completed with 6-phase FSM analysis.",
            ),
            findings=all_findings,
            merge_gate=MergeGate(
                decision=decision,
                must_fix=must_fix,
                should_fix=should_fix,
                notes_for_coding_agent=[
                    f"Overall risk assessment: {overall_risk.upper()} - {risk_assessment.get('rationale', '')}",
                ],
            ),
        )

    def _build_error_review_output(self, context: ReviewContext, error_msg: str) -> ReviewOutput:
        """Build error ReviewOutput when FSM fails.

        Args:
            context: ReviewContext containing changed files
            error_msg: Error message string

        Returns:
            ReviewOutput with error information
        """
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Security review failed in {self._current_security_phase} phase: {error_msg}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                ignored_files=[],
                reasoning=f"FSM error in {self._current_security_phase} phase.",
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=[
                    f"Security review encountered an error: {error_msg}",
                    f"Phase: {self._current_security_phase}",
                    "Please retry the review.",
                ],
            ),
        )

    def get_system_prompt(self) -> str:
        """Return the system prompt for this reviewer agent."""
        # System prompt is phase-specific, returned by _get_phase_prompt()
        # Return intake phase prompt for initial context building
        return self._get_phase_prompt("intake")

    def get_relevant_file_patterns(self) -> List[str]:
        """Return file patterns this reviewer is relevant to."""
        return [
            "**/*.py",
            "**/*.js",
            "**/*.ts",
            "**/*.tsx",
            "**/*.go",
            "**/*.java",
            "**/*.rb",
            "**/*.php",
            "**/*.cs",
            "**/*.cpp",
            "**/*.c",
            "**/*.h",
            "**/*.sh",
            "**/*.yaml",
            "**/*.yml",
            "**/*.json",
            "**/*.toml",
            "**/*.ini",
            "**/*.env*",
            "**/Dockerfile*",
            "**/*.tf",
            "**/.github/workflows/**",
            "**/.gitlab-ci.yml",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for security review checks."""
        return [
            "git",
            "grep",
            "rg",
            "ast-grep",
            "python",
            "bandit",
            "semgrep",
            "pip-audit",
            "uv",
            "poetry",
            "read",
            "file",
        ]
