"""Documentation Review Subagent with FSM pattern.

Reviews code changes for documentation coverage including:
- Docstrings for public functions/classes
- README updates for new features
- Configuration documentation
- Usage examples

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


class DocumentationReviewer(BaseReviewerAgent):
    """Documentation reviewer agent with FSM-based review process.

    This agent implements a 5-phase FSM for documentation review:
    - INTAKE: Analyze PR changes for documentation surfaces
    - PLAN: Create TODOs for documentation analysis
    - ACT: Use DocumentationDelegationSkill to dispatch subagents
    - SYNTHESIZE: Aggregate subagent results
    - CHECK: Final validation and risk assessment

    The agent specializes in detecting:
    - Missing docstrings for public functions/classes
    - Outdated or missing README documentation
    - Missing configuration documentation
    - Missing usage examples
    """

    # Valid phase transitions for the documentation review FSM
    VALID_TRANSITIONS: Dict[str, set[str]] = {
        "intake": {"plan"},
        "plan": {"act"},
        "act": {"synthesize", "done"},
        "synthesize": {"check"},
        "check": {"done"},
        "done": set(),
    }

    def __init__(
        self,
        max_retries: int = 3,
        agent_runtime=None,
        phase_timeout_seconds: int | None = None,
    ) -> None:
        """Initialize documentation reviewer.

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
        self._fsm: object | None = {"current_phase": "intake", "phase_outputs": {}}  # type: ignore[assignment]

    def get_agent_name(self) -> str:
        """Return the agent identifier."""
        return "documentation"

    def prefers_direct_review(self) -> bool:
        """Documentation agent has its own FSM requiring multiple LLM calls."""
        return True

    @property
    def state(self) -> str:  # type: ignore[override]
        """Get current FSM phase as string."""
        return self._current_phase

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform documentation review using FSM pattern.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with documentation findings, severity, and merge gate decision
        """
        return await self._run_review_fsm(context)

    async def _run_review_fsm(self, context: ReviewContext) -> ReviewOutput:
        """Run the documentation review phases in sequence."""
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
        """Run INTAKE phase: analyze PR changes for documentation surfaces.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking("INTAKE", "Analyzing PR changes for documentation surfaces")

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("intake")

        # Build user message with context
        user_message = self._build_intake_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Parse JSON response
        output = self._parse_phase_response(response_text, "intake")

        self._phase_logger.log_thinking(
            "INTAKE", "INTAKE analysis complete, preparing to plan todos"
        )

        return output

    async def _run_plan(self, context: ReviewContext) -> Dict[str, Any]:
        """Run PLAN phase: create structured documentation TODOs.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "PLAN", "Creating structured documentation TODOs with priorities"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("plan")

        # Build user message with context
        user_message = self._build_plan_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Parse JSON response
        output = self._parse_phase_response(response_text, "plan")

        self._phase_logger.log_thinking("PLAN", "PLAN complete, preparing for ACT phase")

        return output

    async def _run_act(self, context: ReviewContext) -> Dict[str, Any]:
        """Run ACT phase: delegate todos to subagents using DocumentationDelegationSkill.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request and subagent_results
        """
        self._phase_logger.log_thinking("ACT", "Delegating documentation todos to subagents")

        from iron_rook.review.skills.documentation_delegation import DocumentationDelegationSkill

        skill = DocumentationDelegationSkill(
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
        """Run SYNTHESIZE phase: aggregate and validate subagent results.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "SYNTHESIZE", "Aggregating and validating documentation findings from ACT"
        )

        act_output = self._phase_outputs.get("act", {})
        is_early_exit = act_output.get("next_phase_request") == "done"

        if is_early_exit:
            self._phase_logger.log_thinking(
                "SYNTHESIZE", "Early-exit detected (act returned done), running minimal synthesis"
            )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("synthesize")

        # Build user message with context
        user_message = self._build_synthesize_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Parse JSON response
        output = self._parse_phase_response(response_text, "synthesize")

        self._phase_logger.log_thinking(
            "SYNTHESIZE", "SYNTHESIZE complete, preparing for CHECK phase"
        )

        return output

    async def _run_check(self, context: ReviewContext) -> Dict[str, Any]:
        """Run CHECK phase: assess severity and generate final report.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "CHECK", "Assessing findings severity and generating final documentation report"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("check")

        # Build user message with context
        user_message = self._build_check_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Parse JSON response
        output = self._parse_phase_response(response_text, "check")

        self._phase_logger.log_thinking("CHECK", "CHECK complete, final report generated")

        return output

    def _get_phase_prompt(self, phase: str) -> str:
        """Get system prompt for a specific FSM phase.

        Args:
            phase: Phase name (intake, plan, act, synthesize, check)

        Returns:
            System prompt string for the phase
        """
        return f"""You are the Documentation Review Agent.

You are in the {phase} phase of the 5-phase documentation review FSM.

{get_review_output_schema()}

Your agent name is "documentation".

{self._get_phase_specific_instructions(phase)}"""

    def _get_phase_specific_instructions(self, phase: str) -> str:
        """Get phase-specific instructions.

        Args:
            phase: Phase name (intake, plan, act, synthesize, check)

        Returns:
            Phase-specific instructions string
        """
        instructions_upper_key = phase.upper()
        instructions = {
            "INTAKE": """INTAKE Phase:
Task:
1. Summarize what changed (by path + change type).
2. Identify likely documentation surfaces touched.
3. Generate initial documentation risk hypotheses.

Documentation Detection Patterns:
- New public APIs, functions, classes
- Changes to function signatures, parameters, return types
- New CLI commands or options
- Changes to configuration/environment variables
- New modules or packages

Output JSON format:
{
  "phase": "intake",
  "data": {
    "summary": "...",
    "files_requiring_docs": ["..."],
    "questions": ["..."]
  },
  "next_phase_request": "plan"
}
""",
            "PLAN": """PLAN Phase:
Task:
1. Create structured documentation TODOs with:
   - Priority (high/medium/low)
   - Scope (paths, symbols)
   - Category (docstrings, readme, config_docs, examples, api_docs)
   - Acceptance criteria
2. Specify which documentation areas to check.

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
1. Delegate todos to documentation subagents.
2. Each subagent will use tools (grep, read, ast-grep) to collect evidence.
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
4. Synthesize summary of documentation issues found.

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
3. Generate final documentation review report.

Severity Classification Guidelines:
- CRITICAL: Public interface changed with no documentation and high risk of misuse
- HIGH: Behavior changed but docs claim old behavior
- MEDIUM: Missing docstring or minor README mismatch
- LOW: Minor documentation improvement

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
                    "The ACT phase returned next_phase_request='done', indicating no significant documentation issues.",
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
        """Execute LLM call using SimpleReviewAgentRunner.

        Args:
            system_prompt: System prompt for the LLM
            user_message: User message with context

        Returns:
            LLM response text
        """
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        response_text = await runner.run_with_retry(system_prompt, user_message)
        logger.info(f"[{self.__class__.__name__}] Got LLM response: {len(response_text)} chars")
        return response_text

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
            raise ValueError(f"Failed to parse JSON response: {e}") from e

    def _build_review_output_from_check(
        self, check_output: Dict[str, Any], context: ReviewContext
    ) -> ReviewOutput:
        """Build ReviewOutput from CHECK phase output.

        Args:
            check_output: Output from CHECK phase
            context: ReviewContext with changed files and metadata

        Returns:
            ReviewOutput with findings and merge gate decision
        """
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
                        id=f"docs-{len(findings)}-{finding_dict.get('title', 'unknown')[:20]}",
                        title=finding_dict.get("title", "Untitled finding"),
                        severity=finding_severity,
                        confidence="medium",
                        owner="docs",
                        estimate="S",
                        evidence=str(finding_dict.get("evidence", "")),
                        risk=finding_dict.get("description", finding_dict.get("risk", "")),
                        recommendation=finding_dict.get("recommendation", ""),
                    )
                )

        # Determine merge decision
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
            summary=f"Documentation review complete. {len(findings)} findings. Risk: {overall_risk}",
            severity=output_severity,  # type: ignore[arg-type]
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Analyzed documentation coverage for changed files",
            ),
            checks=[
                Check(
                    name="documentation_coverage",
                    required=True,
                    commands=[],
                    why="Verify documentation coverage for public APIs",
                )
            ],
            findings=findings,
            merge_gate=MergeGate(
                decision=decision,
                must_fix=actions.get("required", []),
                should_fix=actions.get("suggested", []),
                notes_for_coding_agent=[f"Review {len(findings)} documentation findings"],
            ),
        )

    def _build_error_review_output(
        self, context: ReviewContext, error_message: str
    ) -> ReviewOutput:
        """Build error ReviewOutput when FSM fails.

        Args:
            context: ReviewContext with changed files and metadata
            error_message: Error message describing the failure

        Returns:
            ReviewOutput with error information
        """
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Documentation review failed: {error_message}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Error during documentation review FSM",
            ),
            checks=[],
            skips=[
                Skip(
                    name="documentation_review",
                    why_safe=f"Documentation review error: {error_message}",
                    when_to_run="After fixing documentation review error",
                )
            ],
            findings=[],
            merge_gate=MergeGate(
                decision="block",
                must_fix=["Fix documentation review error"],
                should_fix=[],
                notes_for_coding_agent=[f"Documentation review failed: {error_message}"],
            ),
        )

    def get_system_prompt(self) -> str:
        """Get the system prompt for the documentation reviewer.

        This method is kept for compatibility but the FSM uses phase-specific prompts.
        """
        return f"""You are the Documentation Review Subagent.

Use this shared behavior:
- Identify which changed files/diffs are relevant to documentation.
- Propose minimal checks; request doc build checks only if relevant.
- If changed_files or diff are missing, request them.
- Discover repo conventions (README, docs toolchain) to propose correct commands.

You specialize in:
- docstrings for public functions/classes
- module-level docs explaining purpose and contracts
- README / usage updates when behavior changes
- configuration documentation (env vars, settings, CLI flags)
- examples and edge case documentation

Relevant changes:
- new public APIs, new commands/tools/skills/agents
- changes to behavior, defaults, outputs, error handling
- renamed modules, moved files, breaking interface changes

Checks you may request:
- docs build/check (mkdocs/sphinx) if repo has it
- docstring linting if configured
- ensure examples match CLI/help output if changed

Documentation review must answer:
1) Would a new engineer understand how to use the changed parts?
2) Are contracts described (inputs/outputs/errors)?
3) Are sharp edges warned?
4) Is terminology consistent?

Severity guidance:
- warning: missing docstring or minor README mismatch
- critical: behavior changed but docs claim old behavior; config/env changes undocumented
- blocking: public interface changed with no documentation and high risk of misuse

{get_review_output_schema()}

Your agent name is "documentation"."""

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns relevant to documentation review."""
        return [
            "**/*.py",
            "README*",
            "docs/**",
            "*.md",
            "pyproject.toml",
            "setup.cfg",
            ".env.example",
        ]

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools for documentation review checks."""
        return ["git", "grep", "python", "markdownlint", "mkdocs"]
