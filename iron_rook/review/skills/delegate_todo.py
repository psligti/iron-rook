"""Delegate Todo skill for LLM-based subagent delegation.

This skill encapsulates the delegation logic that analyzes todos from plan_todos
phase and generates subagent requests for delegated items.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    Check,
    Finding,
    MergeGate,
    ReviewOutput,
    Scope,
    Skip,
)

logger = logging.getLogger(__name__)


def get_phase_output_schema(phase: str) -> str:
    """Get JSON schema for expected phase output.

    Args:
        phase: Phase name (e.g., "delegate")

    Returns:
        JSON schema string
    """
    schemas = {
        "delegate": """Output JSON format:
{
  "phase": "delegate",
  "data": {
    "subagent_requests": [
      {
        "todo_id": "1",
        "title": "Check SQL injection risks",
        "scope": {"paths": ["src/api/handlers.py"]},
        "risk_category": "injection",
        "tools_to_use": ["grep", "read", "ast-grep"],
        "acceptance_criteria": ["Identify all SQL queries", "Check parameter binding"]
      }
    ],
    "thinking": "Reasoning about delegation decisions"
  },
  "next_phase_request": "collect"
}""",
    }
    return schemas.get(phase, "Output JSON with 'phase', 'data', 'next_phase_request'")


class DelegateTodoSkill(BaseReviewerAgent):
    """Skill for LLM-based delegation of todos to subagents.

    This skill analyzes todos from the plan_todos phase and uses an LLM to
    generate subagent requests. It then executes each subagent and collects results.

    The skill:
    1. Extracts todos from plan_todos phase output
    2. Builds delegation prompt for LLM
    3. Executes LLM to generate subagent_requests
    4. Dispatches subagents to execute tasks
    5. Collects and returns subagent_results
    """

    def __init__(
        self,
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        phase_outputs: Dict[str, Any] | None = None,
    ):
        """Initialize DelegateTodoSkill.

        Args:
            verifier: Optional findings verifier
            max_retries: Maximum retry attempts
            agent_runtime: Optional agent runtime for execution
            phase_outputs: Dictionary of outputs from previous phases
        """
        super().__init__(verifier=verifier, max_retries=max_retries, agent_runtime=agent_runtime)
        self._phase_outputs = phase_outputs or {}
        self._max_retries: int = max_retries

    def get_agent_name(self) -> str:
        """Return agent name."""
        return "delegate_todo"

    def get_allowed_tools(self) -> List[str]:
        """Return list of tools this agent can use.

        Returns delegation-related tools for planning and dispatching.
        """
        return ["read", "grep", "file"]

    def prefers_direct_review(self) -> bool:
        """Check if agent prefers to use its own review method.

        DelegateTodoSkill has its own internal LLM orchestration that
        outputs DELEGATE phase format, not ReviewOutput format. It must
        run directly to avoid SDK parsing failures.

        Returns:
            True - always use direct review to avoid SDK path
        """
        return True

    def get_system_prompt(self) -> str:
        """Get system prompt for this skill.

        Returns system prompt instructing LLM on delegation responsibilities.
        """
        return f"""You are Delegate Todo Skill.

You are in DELEGATE phase of security review FSM.

{get_phase_output_schema("delegate")}

Your agent name is "delegate_todo".

DELEGATE Phase:
Task:
1. For EVERY TODO, produce a subagent request object.
2. Each subagent will use tools (grep, read, ast-grep, bandit, semgrep) to collect evidence.
3. You MUST populate "subagent_requests" array with one entry per TODO.
4. ALL analysis must be delegated to subagents - populate subagent_requests for every TODO.

Output JSON format:
{get_phase_output_schema("delegate")}"""

    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns this skill is relevant to.

        Returns empty list as this skill orchestrates rather than reviews files.
        """
        return []

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform delegation review on given context.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with subagent_results
        """
        from dawn_kestrel.core.harness import SimpleReviewAgentRunner
        from iron_rook.review.subagents.security_subagent_dynamic import (
            SecuritySubagent,
        )

        logger.info(
            f"[{self.__class__.__name__}] Starting DELEGATE phase with {len(context.changed_files)} changed files"
        )

        # Extract plan output (SecurityReviewer stores PLAN phase under key "plan")
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})
        todos = plan_output.get("todos", [])

        logger.info(f"[{self.__class__.__name__}] Found {len(todos)} todos from plan phase")

        # Build system and user prompts
        system_prompt = self.get_system_prompt()
        user_message = self._build_delegate_message(context)

        # Execute LLM call
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        try:
            response_text = await runner.run_with_retry(system_prompt, user_message)
            logger.info(f"[{self.__class__.__name__}] Got LLM response: {len(response_text)} chars")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] LLM call failed: {e}", exc_info=True)
            return self._build_error_review_output(context, str(e))

        # Parse JSON response
        try:
            output = self._parse_response(response_text)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Failed to parse response: {e}")
            return self._build_error_review_output(context, f"Failed to parse response: {e}")

        # Extract subagent_requests
        subagent_requests = output.get("data", {}).get("subagent_requests", [])

        logger.info(
            f"[{self.__class__.__name__}] Generated {len(subagent_requests)} subagent requests"
        )

        # Execute subagents
        subagent_results = []
        if subagent_requests:
            logger.info(
                f"[{self.__class__.__name__}] Executing {len(subagent_requests)} subagent tasks concurrently"
            )

            # Create subagent tasks for concurrent execution
            async def execute_subagent(request: Dict[str, Any]) -> Dict[str, Any]:
                try:
                    subagent = SecuritySubagent(
                        task=request,
                        max_retries=self._max_retries,
                    )
                    result = await subagent.review(context)
                    logger.info(
                        f"[{self.__class__.__name__}] Subagent task {request.get('todo_id')} completed: "
                        f"{len(result.findings) if result else 0} findings"
                    )
                    return {
                        "todo_id": request.get("todo_id"),
                        "title": request.get("title"),
                        "subagent_type": "security_subagent",
                        "status": "done" if result else "blocked",
                        "result": result.model_dump() if result else None,
                    }
                except Exception as e:
                    logger.error(
                        f"[{self.__class__.__name__}] Subagent task {request.get('todo_id')} failed: {e}",
                        exc_info=True,
                    )
                    return {
                        "todo_id": request.get("todo_id"),
                        "title": request.get("title"),
                        "subagent_type": "security_subagent",
                        "status": "blocked",
                        "error": str(e),
                    }

            # Execute all subagents concurrently
            subagent_tasks = [execute_subagent(request) for request in subagent_requests]
            gather_results = await asyncio.gather(*subagent_tasks, return_exceptions=True)

            # Convert exceptions to error results and filter to Dict only
            subagent_results = []
            for i, result in enumerate(gather_results):
                if isinstance(result, Exception):
                    request = subagent_requests[i]
                    logger.error(
                        f"[{self.__class__.__name__}] Subagent task {request.get('todo_id')} raised exception: {result}",
                        exc_info=True,
                    )
                    subagent_results.append(
                        {
                            "todo_id": request.get("todo_id"),
                            "title": request.get("title"),
                            "subagent_type": "security_subagent",
                            "status": "blocked",
                            "error": str(result),
                        }
                    )
                else:
                    subagent_results.append(result)

        # Build and return ReviewOutput
        return self._build_review_output(context, subagent_results)

    def _build_delegate_message(self, context: ReviewContext) -> str:
        """Build user message for DELEGATE phase.

        Args:
            context: ReviewContext containing changed files and metadata

        Returns:
            User message string with context information
        """
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})
        parts = [
            "## PLAN Output",
            "",
            json.dumps(plan_output, indent=2),
            "",
            "## Current Phase Context",
            "",
            f"Changed Files: {len(context.changed_files)}",
            f"Files: {', '.join(context.changed_files[:5])}" if context.changed_files else "None",
        ]
        return "\n".join(parts)

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM JSON response.

        Args:
            response_text: Raw LLM response text

        Returns:
            Parsed response dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        # Strip markdown code blocks if present
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        output = json.loads(response_text)

        # Validate phase name
        actual_phase = output.get("phase")
        if actual_phase != "delegate":
            logger.warning(
                f"[{self.__class__.__name__}] Expected phase 'delegate', got '{actual_phase}'"
            )

        return output

    def _build_review_output(
        self, context: ReviewContext, subagent_results: List[Dict[str, Any]]
    ) -> ReviewOutput:
        """Build ReviewOutput from subagent results.

        Args:
            context: ReviewContext containing review information
            subagent_results: List of subagent execution results

        Returns:
            ReviewOutput with findings and merge gate
        """
        findings: List[Finding] = []

        for result in subagent_results:
            if result.get("status") != "done":
                continue

            result_data = result.get("result", {})
            if not result_data:
                continue

            subagent_findings = result_data.get("findings", [])
            for finding_dict in subagent_findings:
                severity_str = finding_dict.get("severity", "medium")
                if severity_str == "critical":
                    finding_severity = "critical"
                elif severity_str == "high":
                    finding_severity = "critical"
                elif severity_str == "low":
                    finding_severity = "warning"
                else:
                    finding_severity = severity_str

                findings.append(
                    Finding(
                        id=f"delegate-{len(findings)}-{finding_dict.get('title', 'unknown')[:20]}",
                        title=finding_dict.get("title", "Untitled finding"),
                        severity=finding_severity,
                        confidence="medium",
                        owner="security",
                        estimate="M",
                        evidence=str(finding_dict.get("evidence", "")),
                        risk=finding_dict.get(
                            "description", finding_dict.get("risk", "Security issue identified")
                        ),
                        recommendation=finding_dict.get(
                            "recommendation", "Review and address this finding"
                        ),
                    )
                )

        # Determine merge decision
        if any(f.severity == "critical" for f in findings):
            decision = "block"
        elif any(f.severity == "warning" for f in findings):
            decision = "needs_changes"
        else:
            decision = "approve"

        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Delegated {len(subagent_results)} subagent tasks, found {len(findings)} findings",
            severity="critical"
            if any(f.severity == "critical" for f in findings)
            else "warning"
            if findings
            else "merge",
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Delegated todos to subagents for detailed security analysis",
            ),
            checks=[
                Check(
                    name="subagent_execution",
                    required=True,
                    commands=[],
                    why="Verify all delegated subagents completed successfully",
                )
            ],
            findings=findings,
            merge_gate=MergeGate(
                decision=decision,
                must_fix=[f.title for f in findings if f.severity in ("critical", "blocking")],
                should_fix=[f.title for f in findings if f.severity == "warning"],
                notes_for_coding_agent=[
                    f"Review {len(findings)} security findings from {len(subagent_results)} subagents"
                ],
            ),
        )

    def _build_error_review_output(
        self, context: ReviewContext, error_message: str
    ) -> ReviewOutput:
        """Build error ReviewOutput when delegation fails.

        Args:
            context: ReviewContext containing review information
            error_message: Error message to include

        Returns:
            ReviewOutput with error information
        """
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Delegation failed: {error_message}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Error during delegation phase",
            ),
            checks=[],
            skips=[
                Skip(
                    name="delegation",
                    why_safe=f"Delegation error: {error_message}",
                    when_to_run="After fixing delegation error",
                )
            ],
            findings=[],
            merge_gate=MergeGate(
                decision="block",
                must_fix=["Fix delegation error"],
                should_fix=[],
                notes_for_coding_agent=[f"Delegation failed with error: {error_message}"],
            ),
        )
