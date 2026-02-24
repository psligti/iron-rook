"""Dependency & License Reviewer agent with FSM pattern.

Reviews code changes for dependency and license issues including:
- License compatibility (MIT, Apache, GPL, etc.)
- Security advisories and known vulnerabilities
- Version pinning and reproducibility
- Supply chain risks (typosquatting, untrusted packages)

Implements FSM phases: INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, cast

from iron_rook.review.runner import SimpleReviewAgentRunner

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
    get_phase_output_schema,
)
from iron_rook.review.security_phase_logger import SecurityPhaseLogger

logger = logging.getLogger(__name__)


class DependencyLicenseReviewer(BaseReviewerAgent):
    """Dependency and license reviewer agent with FSM-based review process.

    This agent implements a 5-phase FSM for dependency review:
    - INTAKE: Analyze PR changes for dependency surfaces
    - PLAN: Create TODOs for dependency analysis
    - ACT: Use DependenciesDelegationSkill to dispatch subagents
    - SYNTHESIZE: Aggregate subagent results
    - CHECK: Final validation and risk assessment

    The agent specializes in detecting:
    - License compatibility issues
    - Security advisories and vulnerabilities
    - Version pinning problems
    - Supply chain risks
    """

    VALID_TRANSITIONS: Dict[str, set[str]] = {
        "intake": {"plan"},
        "plan": {"act"},
        "act": {"synthesize", "done"},
        "synthesize": {"check"},
        "check": {"done"},
        "done": set(),
    }

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
        self._max_retries = max_retries
        self._agent_runtime = agent_runtime
        self._phase_timeout_seconds = phase_timeout_seconds
        self._phase_logger = SecurityPhaseLogger()
        self._phase_outputs: Dict[str, Any] = {}
        self._current_phase: str = "intake"
        self._thinking_log = RunLog()
        self._fsm: object | None = {"current_phase": "intake", "phase_outputs": {}}  # type: ignore[assignment]

    def get_agent_name(self) -> str:
        return "dependencies"

    def prefers_direct_review(self) -> bool:
        return True

    @property
    def state(self) -> str:  # type: ignore[override]
        return self._current_phase

    async def review(self, context: ReviewContext) -> ReviewOutput:
        return await self._run_review_fsm(context)

    async def _run_review_fsm(self, context: ReviewContext) -> ReviewOutput:
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
        valid_transitions = self.VALID_TRANSITIONS.get(self._current_phase, set())
        if next_phase not in valid_transitions:
            raise ValueError(
                f"Invalid transition: {self._current_phase} -> {next_phase}. "
                f"Valid transitions: {valid_transitions}"
            )

        self._phase_logger.log_transition(self._current_phase, next_phase)
        self._current_phase = next_phase

    async def _run_intake(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("INTAKE", "Analyzing PR changes for dependency surfaces")

        system_prompt = self._get_phase_prompt("intake")
        user_message = self._build_intake_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "intake")

        self._phase_logger.log_thinking(
            "INTAKE", "INTAKE analysis complete, preparing to plan todos"
        )

        return output

    async def _run_plan(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking(
            "PLAN", "Creating structured dependency TODOs with priorities"
        )

        system_prompt = self._get_phase_prompt("plan")
        user_message = self._build_plan_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "plan")

        self._phase_logger.log_thinking("PLAN", "PLAN complete, preparing for ACT phase")

        return output

    async def _run_act(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("ACT", "Delegating dependency todos to subagents")

        from iron_rook.review.skills.dependencies_delegation import DependenciesDelegationSkill

        skill = DependenciesDelegationSkill(
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
        self._phase_logger.log_thinking(
            "SYNTHESIZE", "Aggregating and validating dependency findings from ACT"
        )

        act_output = self._phase_outputs.get("act", {})
        is_early_exit = act_output.get("next_phase_request") == "done"

        if is_early_exit:
            self._phase_logger.log_thinking(
                "SYNTHESIZE", "Early-exit detected (act returned done), running minimal synthesis"
            )

        system_prompt = self._get_phase_prompt("synthesize")
        user_message = self._build_synthesize_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "synthesize")

        self._phase_logger.log_thinking(
            "SYNTHESIZE", "SYNTHESIZE complete, preparing for CHECK phase"
        )

        return output

    async def _run_check(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking(
            "CHECK", "Assessing findings severity and generating final dependency report"
        )

        system_prompt = self._get_phase_prompt("check")
        user_message = self._build_check_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        output = self._parse_phase_response(response_text, "check")

        self._phase_logger.log_thinking("CHECK", "CHECK complete, final report generated")

        return output

    def _get_phase_prompt(self, phase: str) -> str:
        return f"""You are the Dependencies Review Agent.

You are in the {phase} phase of the 5-phase dependency review FSM.

{get_phase_output_schema(phase)}

Your agent name is "dependencies".

{self._get_phase_specific_instructions(phase)}"""

    def _get_phase_specific_instructions(self, phase: str) -> str:
        instructions_upper_key = phase.upper()
        instructions = {
            "INTAKE": """INTAKE Phase:
Task:
1. Summarize what changed (by path + change type).
2. Identify likely dependency surfaces touched.
3. Generate initial dependency risk hypotheses.

Dependency Detection Patterns:
- Changes to pyproject.toml, requirements*.txt, poetry.lock, uv.lock
- Changes to CI/CD dependency steps
- New dependencies added or version bumps
- Loosened version pins
- Changes to dependency resolution settings

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
1. Create structured dependency TODOs with:
   - Priority (high/medium/low)
   - Scope (paths, packages)
   - Category (license, security, versions, supply_chain, audit)
   - Acceptance criteria
2. Specify which dependency areas to check.

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
1. Delegate todos to dependency subagents.
2. Each subagent will use tools (grep, read, file) to collect evidence.
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
4. Synthesize summary of dependency issues found.

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
3. Generate final dependency review report.

Severity Classification Guidelines:
- CRITICAL: Known vulnerabilities introduced, GPL license in MIT project
- HIGH: Unpinned dependencies, missing license info
- MEDIUM: Minor version bumps without notes, lockfile inconsistencies
- LOW: Formatting issues, non-blocking recommendations

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
                    "The ACT phase returned next_phase_request='done', indicating no significant dependency issues.",
                    "Run minimal synthesis: validate outputs and proceed to CHECK with empty findings.",
                ]
            )

        return "\n".join(parts)

    def _build_check_message(self, context: ReviewContext) -> str:
        synthesize_output = self._phase_outputs.get("synthesize", {}).get("data", {})
        parts = [
            "## SYNTHESIZE Output",
            "",
            json.dumps(synthesize_output, indent=2),
        ]
        return "\n".join(parts)

    async def _execute_llm(self, system_prompt: str, user_message: str) -> str:
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        response_text = await runner.run_with_retry(system_prompt, user_message)
        logger.info(f"[{self.__class__.__name__}] Got LLM response: {len(response_text)} chars")
        return response_text

    def _parse_phase_response(self, response_text: str, expected_phase: str) -> Dict[str, Any]:
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
                        id=f"dep-{len(findings)}-{finding_dict.get('title', 'unknown')[:20]}",
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

        critical_high = findings_by_severity.get("critical", []) + findings_by_severity.get(
            "high", []
        )
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
            summary=f"Dependency review complete. {len(findings)} findings. Risk: {overall_risk}",
            severity=output_severity,  # type: ignore[arg-type]
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Analyzed dependency patterns for changed files",
            ),
            checks=[
                Check(
                    name="dependency_analysis",
                    required=True,
                    commands=[],
                    why="Verify dependency security and license compliance",
                )
            ],
            findings=findings,
            merge_gate=MergeGate(
                decision=decision,
                must_fix=actions.get("required", []),
                should_fix=actions.get("suggested", []),
                notes_for_coding_agent=[f"Review {len(findings)} dependency findings"],
            ),
            thinking_log=self._thinking_log,
        )

    def _build_error_review_output(
        self, context: ReviewContext, error_message: str
    ) -> ReviewOutput:
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Dependency review failed: {error_message}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Error during dependency review FSM",
            ),
            checks=[],
            skips=[
                Skip(
                    name="dependency_review",
                    why_safe=f"Dependency review error: {error_message}",
                    when_to_run="After fixing dependency review error",
                )
            ],
            findings=[],
            merge_gate=MergeGate(
                decision="block",
                must_fix=["Fix dependency review error"],
                should_fix=[],
                notes_for_coding_agent=[f"Dependency review failed: {error_message}"],
            ),
            thinking_log=self._thinking_log,
        )

    def get_system_prompt(self) -> str:
        return f"""You are the Dependency & License Review Subagent.

Use this shared behavior:
- If dependency changes are present but file contents are missing, request dependency files and lockfiles.
- Evaluate reproducibility and audit readiness.

Focus:
- new deps added, version bumps, loosened pins
- supply chain risk signals (typosquatting, untrusted packages)
- license compatibility (if enforced)
- build reproducibility (lockfile consistency)

Relevant files:
- pyproject.toml, requirements*.txt, poetry.lock, uv.lock
- CI dependency steps

Checks you may request:
- pip-audit / poetry audit / uv audit
- license checker if repo uses it
- lockfile diff sanity checks

Severity:
- critical/blocking for risky dependency introduced without justification
- critical if pins loosened causing non-repro builds
- warning for safe bumps but missing notes

{get_review_output_schema()}

Your agent name is "dependencies"."""

    def get_relevant_file_patterns(self) -> List[str]:
        return [
            "pyproject.toml",
            "requirements*.txt",
            "requirements.txt",
            "setup.py",
            "Pipfile",
            "poetry.lock",
            "uv.lock",
            "setup.cfg",
            "tox.ini",
        ]

    def get_allowed_tools(self) -> List[str]:
        return ["git", "grep", "read", "file"]
