"""Telemetry Reviewer agent with FSM pattern.

Reviews code changes for telemetry and observability issues including:
- Logging quality (structured logs, proper levels, correlation IDs)
- Metrics coverage (counters, gauges, histograms, cardinality)
- Tracing spans and propagation
- Error reporting (meaningful errors, no sensitive data)
- Observability coverage of workflows and failure modes

Implements FSM phases: INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, cast

from dawn_kestrel.core.harness import SimpleReviewAgentRunner

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    AgentState,
    Check,
    Finding,
    MergeGate,
    ReviewOutput,
    RunLog,
    Scope,
    Skip,
    get_review_output_schema,
)
from iron_rook.review.security_phase_logger import SecurityPhaseLogger

logger = logging.getLogger(__name__)


class TelemetryMetricsReviewer(BaseReviewerAgent):
    """Telemetry reviewer agent with FSM-based review process.

    This agent implements a 5-phase FSM for telemetry review:
    - INTAKE: Analyze PR changes for telemetry surfaces
    - PLAN: Create TODOs for telemetry analysis
    - ACT: Use TelemetryDelegationSkill to dispatch subagents
    - SYNTHESIZE: Aggregate subagent results
    - CHECK: Final validation and risk assessment

    The agent specializes in detecting:
    - Logging quality issues (proper log levels, structured logging)
    - Error reporting issues (exceptions raised with context)
    - Observability coverage issues (metrics, traces)
    - Silent failures (swallowed exceptions)
    """

    # Valid phase transitions for the telemetry review FSM
    VALID_TRANSITIONS: Dict[str, set[str]] = {
        "intake": {"plan"},
        "plan": {"act"},
        "act": {"synthesize", "done"},
        "synthesize": {"check"},
        "check": {"done"},
        "done": set(),
    }

    # Legacy FSM_TRANSITIONS for backward compatibility
    FSM_TRANSITIONS: dict[AgentState, set[AgentState]] = {
        AgentState.IDLE: {AgentState.INITIALIZING},
        AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
        AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
        AgentState.RUNNING: {AgentState.COMPLETED, AgentState.FAILED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: set(),
    }

    def __init__(
        self,
        max_retries: int = 3,
        agent_runtime=None,
        phase_timeout_seconds: int | None = None,
    ) -> None:
        """Initialize telemetry reviewer.

        Args:
            max_retries: Maximum retry attempts for failed operations.
            agent_runtime: Optional agent runtime for subagent execution.
            phase_timeout_seconds: Timeout in seconds per phase (default: None = no timeout).
        """
        self._max_retries = max_retries
        self._agent_runtime = agent_runtime
        self._phase_timeout_seconds = phase_timeout_seconds
        self._phase_logger = SecurityPhaseLogger()
        self._phase_outputs: Dict[str, Any] = {}
        self._current_phase: str = "intake"
        self._thinking_log = RunLog()
        self._fsm: object | None = {"current_phase": "intake", "phase_outputs": {}}

    def get_agent_name(self) -> str:
        """Return the agent identifier."""
        return "telemetry"

    def prefers_direct_review(self) -> bool:
        """Telemetry agent has its own FSM requiring multiple LLM calls."""
        return True

    @property
    def state(self) -> str:
        """Get current FSM phase as string."""
        return self._current_phase

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform telemetry review using FSM pattern.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with telemetry findings, severity, and merge gate decision
        """
        return await self._run_review_fsm(context)

    async def _run_review_fsm(self, context: ReviewContext) -> ReviewOutput:
        """Run the telemetry review phases in sequence."""
        self._phase_outputs = {}
        self._current_phase = "intake"

        phase_handlers = {
            "intake": self._run_intake,
            "plan": self._run_plan,
            "act": self._run_act,
            "synthesize": self._run_synthesize,
            "check": self._run_check,
        }

        while self._current_phase != "done":
            handler = phase_handlers.get(self._current_phase)
            if handler is None:
                logger.error(f"No handler for phase: {self._current_phase}")
                return self._build_error_review_output(
                    context, f"No handler for phase: {self._current_phase}"
                )

            try:
                output = await handler(context)
            except Exception as e:
                logger.exception(f"Phase '{self._current_phase}' failed: {e}")
                return self._build_error_review_output(context, str(e))

            if output is None:
                output = {}

            self._phase_outputs[self._current_phase] = output
            next_phase = output.get("next_phase_request")

            if next_phase is None:
                valid = self.VALID_TRANSITIONS.get(self._current_phase, set())
                next_phase = next(iter(valid)) if valid else "done"

            valid_transitions = self.VALID_TRANSITIONS.get(self._current_phase, set())
            if next_phase not in valid_transitions and next_phase != "done":
                logger.error(
                    f"Invalid transition: {self._current_phase} -> {next_phase}. "
                    f"Valid: {valid_transitions}"
                )
                return self._build_error_review_output(
                    context, f"Invalid transition: {self._current_phase} -> {next_phase}"
                )

            self._phase_logger.log_transition(self._current_phase, next_phase)
            self._current_phase = next_phase

        check_output = self._phase_outputs.get("check", {})
        return self._build_review_output_from_check(check_output, context)

    def _transition_to_phase(self, next_phase: str) -> None:
        """Transition to next phase with validation.

        Args:
            next_phase: Target phase name

        Raises:
            ValueError: If transition is invalid
        """
        valid_transitions = self.VALID_TRANSITIONS.get(self._current_phase, set())
        if next_phase not in valid_transitions:
            raise ValueError(
                f"Invalid transition: {self._current_phase} -> {next_phase}. "
                f"Valid transitions: {valid_transitions}"
            )

        self._phase_logger.log_transition(self._current_phase, next_phase)
        self._current_phase = next_phase

    async def _run_intake(self, context: ReviewContext) -> Dict[str, Any]:
        """Run INTAKE phase: analyze PR changes for telemetry surfaces."""
        self._phase_logger.log_thinking("INTAKE", "Analyzing PR changes for telemetry surfaces")
        system_prompt = self._get_phase_prompt("intake")
        user_message = self._build_intake_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "intake")
        self._phase_logger.log_thinking("INTAKE", "INTAKE analysis complete, preparing to plan todos")
        return output

    async def _run_plan(self, context: ReviewContext) -> Dict[str, Any]:
        """Run PLAN phase: create structured telemetry TODOs."""
        self._phase_logger.log_thinking("PLAN", "Creating structured telemetry TODOs with priorities")
        system_prompt = self._get_phase_prompt("plan")
        user_message = self._build_plan_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "plan")
        self._phase_logger.log_thinking("PLAN", "PLAN complete, preparing for ACT phase")
        return output

    async def _run_act(self, context: ReviewContext) -> Dict[str, Any]:
        """Run ACT phase: delegate todos to subagents using TelemetryDelegationSkill."""
        self._phase_logger.log_thinking("ACT", "Delegating telemetry todos to subagents")

        from iron_rook.review.skills.telemetry_delegation import TelemetryDelegationSkill

        skill = TelemetryDelegationSkill(
            max_retries=self._max_retries,
            agent_runtime=self._agent_runtime,
            phase_outputs=self._phase_outputs,
        )

        review_output = await skill.review(context)

        subagent_results = []
        findings = review_output.findings or []

        for finding in findings:
            subagent_results.append(
                {
                    "title": finding.title,
                    "severity": finding.severity,
                    "risk": finding.risk,
                    "evidence": finding.evidence,
                    "recommendation": finding.recommendation,
                }
            )

        output = {
            "phase": "act",
            "data": {
                "subagent_results": subagent_results,
                "findings": [f.model_dump() for f in findings],
            },
            "next_phase_request": "synthesize",
        }

        self._phase_logger.log_thinking("ACT", f"ACT complete, {len(findings)} findings generated")
        return output

    async def _run_synthesize(self, context: ReviewContext) -> Dict[str, Any]:
        """Run SYNTHESIZE phase: aggregate and validate subagent results."""
        self._phase_logger.log_thinking("SYNTHESIZE", "Aggregating and validating telemetry findings from ACT")

        act_output = self._phase_outputs.get("act", {})
        is_early_exit = act_output.get("next_phase_request") == "done"

        if is_early_exit:
            self._phase_logger.log_thinking("SYNTHESIZE", "Early-exit detected (act returned done), running minimal synthesis")

        system_prompt = self._get_phase_prompt("synthesize")
        user_message = self._build_synthesize_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "synthesize")
        self._phase_logger.log_thinking("SYNTHESIZE", "SYNTHESIZE complete, preparing for CHECK phase")
        return output

    async def _run_check(self, context: ReviewContext) -> Dict[str, Any]:
        """Run CHECK phase: assess severity and generate final report."""
        self._phase_logger.log_thinking("CHECK", "Assessing findings severity and generating final telemetry report")
        system_prompt = self._get_phase_prompt("check")
        user_message = self._build_check_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "check")
        self._phase_logger.log_thinking("CHECK", "CHECK complete, final report generated")
        return output

    def _get_phase_prompt(self, phase: str) -> str:
        """Get system prompt for a specific FSM phase."""
        return f"""You are the Telemetry Review Agent.

You are in the {phase} phase of the 5-phase telemetry review FSM.

{get_review_output_schema()}

Your agent name is "telemetry".

{self._get_phase_specific_instructions(phase)}"""

    def _get_phase_specific_instructions(self, phase: str) -> str:
        """Get phase-specific instructions."""
        instructions_upper_key = phase.upper()
        instructions = {
            "INTAKE": """INTAKE Phase:
Task:
1. Summarize what changed (by path + change type).
2. Identify likely telemetry surfaces touched.
3. Generate initial telemetry risk hypotheses.

Telemetry Detection Patterns:
- Changes to logging statements or logger configurations
- New workflows, background jobs, pipelines, orchestration
- Network calls, IO boundaries, retry logic, timeouts
- Error handling changes, exception mapping
- New metrics, counters, gauges, histograms
- Tracing span additions or modifications

Output JSON format:
{
  "phase": "intake",
  "data": {
    "summary": "...",
    "files_requiring_analysis": ["..."],
    "questions": ["..."]
  },
  "next_phase_request": "plan"
}
""",
            "PLAN": """PLAN Phase:
Task:
1. Create structured telemetry TODOs with:
   - Priority (high/medium/low)
   - Scope (paths, symbols)
   - Category (logging, metrics, tracing, observability, alerts)
   - Acceptance criteria
2. Specify which telemetry areas to check.

Output JSON format:
{
  "phase": "plan",
  "data": {
    "todos": [...],
    "tools_considered": [...],
    "why": "..."
  },
  "next_phase_request": "act"
}
""",
            "ACT": """ACT Phase:
Task:
1. Delegate todos to telemetry subagents.
2. Each subagent will use tools (grep, read) to collect evidence.
3. Collect and aggregate subagent results.

Output JSON format:
{
  "phase": "act",
  "data": {
    "findings": [...],
    "gaps": [...]
  },
  "next_phase_request": "synthesize"
}
""",
            "SYNTHESIZE": """SYNTHESIZE Phase:
Task:
1. Validate subagent results and findings.
2. Merge all findings into structured evidence list.
3. De-duplicate findings by severity.
4. Synthesize summary of telemetry issues found.

Output JSON format:
{
  "phase": "synthesize",
  "data": {
    "findings": {
      "critical": [],
      "high": [...],
      "medium": [],
      "low": []
    },
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true
    },
    "summary": "Brief summary of consolidated findings"
  },
  "next_phase_request": "check"
}
""",
            "CHECK": """CHECK Phase:
Task:
1. Assess findings for severity distribution.
2. Generate final risk assessment.
3. Generate final telemetry review report.

Severity Classification Guidelines:
- CRITICAL: Secrets/PII logged, critical path with no logging/metrics
- HIGH: Retry loops without visibility, high-cardinality metric labels
- MEDIUM: Missing structured logging, correlation IDs missing
- LOW: Minor logging style issues, naming inconsistencies

Output JSON format:
{
  "phase": "check",
  "data": {
    "findings": {
      "critical": [],
      "high": [...],
      "medium": [],
      "low": []
    },
    "risk_assessment": {
      "overall": "high|medium|low",
      "rationale": "..."
    },
    "actions": {
      "required": [...],
      "suggested": []
    },
    "confidence": 0.9
  },
  "next_phase_request": "done"
}
""",
        }
        return instructions.get(instructions_upper_key, "")

    def _build_intake_message(self, context: ReviewContext) -> str:
        """Build user message for INTAKE phase."""
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

    def _build_plan_message(self, context: ReviewContext) -> str:
        """Build user message for PLAN phase."""
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

    def _build_synthesize_message(self, context: ReviewContext) -> str:
        """Build user message for SYNTHESIZE phase."""
        act_output = self._phase_outputs.get("act", {})
        act_data = act_output.get("data", {})
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})

        is_early_exit = act_output.get("next_phase_request") == "done"

        parts = [
            "## ACT Output",
            "",
            json.dumps(act_data, indent=2) if act_data else "{}",
            "",
            "## TODOs from PLAN",
            "",
            json.dumps(plan_output.get("todos", []), indent=2),
        ]

        if is_early_exit:
            parts.extend(
                [
                    "",
                    "## Early-Exit Note",
                    "",
                    "The ACT phase returned next_phase_request='done', indicating no significant telemetry issues.",
                    "Run minimal synthesis: validate outputs and proceed to CHECK with empty findings.",
                ]
            )

        return "\n".join(parts)

    def _build_check_message(self, context: ReviewContext) -> str:
        """Build user message for CHECK phase."""
        synthesize_output = self._phase_outputs.get("synthesize", {}).get("data", {})
        parts = [
            "## SYNTHESIZE Output",
            "",
            json.dumps(synthesize_output, indent=2),
        ]
        return "\n".join(parts)

    async def _execute_llm(self, system_prompt: str, user_message: str) -> str:
        """Execute LLM call using SimpleReviewAgentRunner."""
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        response_text = await runner.run_with_retry(system_prompt, user_message)
        logger.info(f"[{self.__class__.__name__}] Got LLM response: {len(response_text)} chars")
        return response_text

    def _parse_phase_response(self, response_text: str, expected_phase: str) -> Dict[str, Any]:
        """Parse phase JSON response with error handling."""
        try:
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            output = json.loads(response_text)

            actual_phase = output.get("phase")
            if actual_phase != expected_phase:
                logger.warning(
                    f"[{self.__class__.__name__}] Expected phase '{expected_phase}', got '{actual_phase}'"
                )

            return output
        except json.JSONDecodeError as e:
            logger.error(f"[{self.__class__.__name__}] Failed to parse JSON: {e}")
            raise ValueError(f"Failed to parse JSON response: {e}") from e

    def _build_review_output_from_check(
        self, check_output: Dict[str, Any], context: ReviewContext
    ) -> ReviewOutput:
        """Build ReviewOutput from CHECK phase output."""
        data = check_output.get("data", {})
        findings_by_severity = data.get("findings", {})
        risk_assessment = data.get("risk_assessment", {})
        actions = data.get("actions", {})

        findings: List[Finding] = []
        severity_mapping: Dict[str, str] = {
            "critical": "critical",
            "high": "blocking",
            "medium": "warning",
            "low": "warning",
        }
        for fsm_severity in ("critical", "high", "medium", "low"):
            mapped = severity_mapping.get(fsm_severity, "warning")
            finding_severity = cast(
                Literal["warning", "critical", "blocking"],
                "critical"
                if mapped == "critical"
                else ("blocking" if mapped == "blocking" else "warning"),
            )
            for finding_dict in findings_by_severity.get(fsm_severity, []):
                findings.append(
                    Finding(
                        id=f"tel-{len(findings)}-{finding_dict.get('title', 'unknown')[:20]}",
                        title=finding_dict.get("title", "Untitled finding"),
                        severity=finding_severity,
                        confidence="medium",
                        owner="dev",
                        estimate="S",
                        evidence=str(finding_dict.get("evidence", "")),
                        risk=finding_dict.get("description", finding_dict.get("risk", "")),
                        recommendation=finding_dict.get("recommendation", ""),
                    )
                )

        critical_high = findings_by_severity.get("critical", []) + findings_by_severity.get("high", [])
        medium_low = findings_by_severity.get("medium", []) + findings_by_severity.get("low", [])

        if critical_high:
            decision = "block"
        elif medium_low:
            decision = "needs_changes"
        else:
            decision = "approve"

        overall_risk = risk_assessment.get("overall", "low")
        severity_mapping_output: Dict[str, str] = {
            "critical": "critical",
            "high": "critical",
            "medium": "warning",
            "low": "warning",
            "merge": "merge",
        }
        output_severity = severity_mapping_output.get(overall_risk, "warning")

        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Telemetry review complete. {len(findings)} findings. Risk: {overall_risk}",
            severity=output_severity,
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Analyzed telemetry patterns for changed files",
            ),
            checks=[
                Check(
                    name="telemetry_analysis",
                    required=True,
                    commands=[],
                    why="Verify telemetry and observability patterns",
                )
            ],
            findings=findings,
            merge_gate=MergeGate(
                decision=decision,
                must_fix=actions.get("required", []),
                should_fix=actions.get("suggested", []),
                notes_for_coding_agent=[f"Review {len(findings)} telemetry findings"],
            ),
        )

    def _build_error_review_output(
        self, context: ReviewContext, error_message: str
    ) -> ReviewOutput:
        """Build error ReviewOutput when FSM fails."""
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Telemetry review failed: {error_message}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Error during telemetry review FSM",
            ),
            checks=[],
            skips=[
                Skip(
                    name="telemetry_review",
                    why_safe=f"Telemetry review error: {error_message}",
                    when_to_run="After fixing telemetry review error",
                )
            ],
            findings=[],
            merge_gate=MergeGate(
                decision="block",
                must_fix=["Fix telemetry review error"],
                should_fix=[],
                notes_for_coding_agent=[f"Telemetry review failed: {error_message}"],
            ),
        )

    def get_system_prompt(self) -> str:
        """Get the system prompt for the telemetry reviewer."""
        return f"""You are the Telemetry Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to observability.
- Propose minimal targeted checks; escalate when failure modes are introduced.
- If changed_files or diff are missing, request them.
- Discover repo conventions (logging frameworks, metrics libs, tracing setup).

You specialize in:
- logging quality (structured logs, levels, correlation IDs)
- tracing spans / propagation (if applicable)
- metrics: counters/gauges/histograms, cardinality control
- error reporting: meaningful errors, no sensitive data
- observability coverage of new workflows and failure modes
- performance signals: timing, retries, rate limits, backoff

Relevant changes:
- new workflows, background jobs, pipelines, orchestration
- network calls, IO boundaries, retry logic, timeouts
- error handling changes, exception mapping

Checks you may request:
- log format checks (if repo has them)
- smoke run command to ensure logs/metrics emitted (if available)
- grep for logger usage & secrets leakage

Blocking:
- secrets/PII likely logged
- critical path introduced with no error logging/metrics
- retry loops without visibility or limits (runaway risk)
- high-cardinality metric labels introduced

{get_review_output_schema()}

Your agent name is "telemetry"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns relevant to telemetry review."""
        return [
            "**/*.py",
            "**/logging/**",
            "**/observability/**",
            "**/metrics/**",
            "**/tracing/**",
            "**/monitoring/**",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for telemetry review checks."""
        return ["git", "grep", "read", "file"]
