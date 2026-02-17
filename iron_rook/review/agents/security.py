"""Security Reviewer agent for checking security vulnerabilities."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import json
import logging
import asyncio
import subprocess
import os

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.security_phase_logger import SecurityPhaseLogger
from iron_rook.review.security_context import load_security_context
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
from iron_rook.review.skills.delegate_todo import DelegateTodoSkill
from dawn_kestrel.core.harness import SimpleReviewAgentRunner

logger = logging.getLogger(__name__)


class SecurityReviewer(BaseReviewerAgent):
    """Reviewer agent specialized in security vulnerability analysis.

    Implements INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE

    Checks for:
    - Secrets handling (API keys, passwords, tokens)
    - Authentication/authorization issues
    - Injection risks (SQL, XSS, command)
    - CI/CD exposures
    - Unsafe code execution patterns
    """

    # Valid phase transitions for the security review FSM
    VALID_TRANSITIONS: Dict[str, set[str]] = {
        "intake": {"plan"},
        "plan": {"act"},
        "act": {"synthesize", "done"},
        "synthesize": {"check"},
        "check": {"done"},
    }

    def __init__(
        self,
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        phase_timeout_seconds: int | None = None,
        delegate_timeout_seconds: int = 600,
    ):
        """Initialize security reviewer.

        Args:
            verifier: Optional findings verifier instance.
            max_retries: Maximum retry attempts for failed operations.
            agent_runtime: Optional agent runtime for subagent execution.
            phase_timeout_seconds: Timeout in seconds per phase (default: None = no timeout).
            delegate_timeout_seconds: Timeout for ACT phase which runs subagents (default: 600s).
        """
        from iron_rook.review.verifier import GrepFindingsVerifier

        self._verifier = verifier or GrepFindingsVerifier()
        self._max_retries = max_retries
        self._agent_runtime = agent_runtime
        self._phase_timeout_seconds = phase_timeout_seconds
        self._delegate_timeout_seconds = delegate_timeout_seconds
        self._phase_logger = SecurityPhaseLogger()
        self._phase_outputs: Dict[str, Any] = {}
        self._current_phase: str = "intake"
        self._thinking_log = RunLog()
        self._security_context: str = ""

    def get_agent_name(self) -> str:
        """Get agent identifier."""
        return "security_fsm"

    def prefers_direct_review(self) -> bool:
        """Security agent has its own FSM requiring multiple LLM calls."""
        return True

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform security review."""
        from iron_rook.review.llm_audit_logger import TraceContext

        self._security_context = load_security_context(context.repo_root)

        with TraceContext():
            return await self._run_review_fsm(context)

    async def _run_review_fsm(self, context: ReviewContext) -> ReviewOutput:
        """Run the security review phases in sequence."""
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
                if self._phase_timeout_seconds:
                    output = await asyncio.wait_for(
                        handler(context), timeout=self._phase_timeout_seconds
                    )
                else:
                    output = await handler(context)
            except asyncio.TimeoutError:
                logger.error(f"Phase '{self._current_phase}' timed out")
                return self._build_error_review_output(
                    context, f"Phase '{self._current_phase}' timed out"
                )
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

    @property
    def _current_security_phase(self) -> str:
        return self._current_phase

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
            logger.info(f"[{self.__class__.__name__}] thinking: {thinking}")
        else:
            logger.info(
                f"[{self.__class__.__name__}] LLM response (no thinking): {response_text[:500]}..."
            )

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
                    next="plan",
                    confidence="medium",
                )
            )

        frame = ThinkingFrame(
            state="intake",
            goals=goals if goals else ["Analyze PR changes for security surfaces"],
            checks=checks if checks else ["Identify security-sensitive code areas"],
            risks=risks if risks else data.get("risk_hypotheses", []),
            steps=steps,
            decision=output.get("next_phase_request", "plan"),
        )

        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        return output

    async def _run_plan(self, context: ReviewContext) -> Dict[str, Any]:
        """Run PLAN phase: create structured security TODOs.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request
        """
        self._phase_logger.log_thinking(
            "PLAN", "Creating structured security TODOs with priorities"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("plan")

        # Build user message with context
        user_message = self._build_plan_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("PLAN", thinking)
            logger.info(f"[{self.__class__.__name__}] thinking: {thinking}")
        else:
            logger.info(
                f"[{self.__class__.__name__}] LLM response (no thinking): {response_text[:500]}..."
            )

        # Parse JSON response
        output = self._parse_phase_response(response_text, "plan")

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
                    next="act",
                    confidence="medium",
                )
            )

        # Get decision from output
        decision = output.get("next_phase_request", "act")

        # Create ThinkingFrame
        frame = ThinkingFrame(
            state="plan",
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
            "PLAN",
            f"PLAN complete, {len(self._phase_outputs.get('intake', {}).get('data', {}).get('risk_hypotheses', []))} TODOs planned",
        )

        return output

    _run_plan = _run_plan

    async def _run_act(self, context: ReviewContext) -> Dict[str, Any]:
        """Run ACT phase: delegate todos to subagents using DelegateTodoSkill.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            Phase output with next_phase_request and subagent_results
        """
        self._phase_logger.log_thinking("ACT", "Delegating todos to subagents")

        skill = DelegateTodoSkill(
            verifier=self._verifier,
            max_retries=self._max_retries,
            agent_runtime=None,
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

        frame = ThinkingFrame(
            state="act",
            goals=["Delegated todos to subagents", "Collected security findings"],
            checks=["All delegated subagents completed"],
            risks=["Incomplete security analysis", "Subagent execution failures"],
            steps=[
                ThinkingStep(
                    kind="delegate",
                    why="Using DelegateTodoSkill for delegation",
                    evidence=[f"Findings collected: {len(findings)}"],
                    next="synthesize",
                    confidence="medium",
                )
            ],
            decision="synthesize",
        )

        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        self._phase_logger.log_thinking("ACT", f"ACT complete, {len(findings)} findings generated")

        return output

    async def _execute_tools(
        self, tools_to_use: List[str], search_patterns: List[str], context: ReviewContext
    ) -> Dict[str, Any]:
        """Execute security analysis tools.

        Args:
            tools_to_use: List of tool names to execute
            search_patterns: List of search patterns for grep/rg
            context: ReviewContext containing repo information

        Returns:
            Dictionary mapping tool names to their results
        """
        results = {}
        repo_root = context.repo_root

        for tool in tools_to_use:
            try:
                if tool in ("grep", "rg"):
                    results[tool] = await self._execute_grep(search_patterns, repo_root)
                elif tool == "read":
                    results["read"] = await self._execute_read(context)
                elif tool == "bandit":
                    results["bandit"] = await self._execute_bandit(repo_root)
                elif tool == "semgrep":
                    results["semgrep"] = await self._execute_semgrep(repo_root)
                else:
                    results[tool] = {
                        "status": "skipped",
                        "reason": f"Tool '{tool}' not implemented",
                    }
            except Exception as e:
                results[tool] = {"status": "error", "error": str(e)}
                logger.warning(f"[{self.get_agent_name()}] Tool {tool} failed: {e}")

        return results

    async def _execute_grep(self, patterns: List[str], repo_root: str) -> Dict[str, Any]:
        """Execute ripgrep for security pattern search.

        Args:
            patterns: List of regex patterns to search
            repo_root: Repository root path

        Returns:
            Dictionary with tool results
        """
        results = {}

        patterns_to_search = patterns if patterns else self._get_default_patterns()

        for pattern in patterns_to_search[:5]:
            try:
                cmd = [
                    "rg",
                    "-n",
                    "--max-count=50",
                    "-g",
                    "*.py",
                    "-g",
                    "*.js",
                    "-g",
                    "*.ts",
                    pattern,
                    repo_root,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0 and proc.stdout:
                    results[pattern] = proc.stdout[:2000]
                else:
                    results[pattern] = "(no matches)"
            except subprocess.TimeoutExpired:
                results[pattern] = "(timeout)"
            except FileNotFoundError:
                results[pattern] = "(rg not available)"
            except Exception as e:
                results[pattern] = f"(error: {e})"

        return {"tool": "rg", "results": results}

    async def _execute_read(self, context: ReviewContext) -> Dict[str, Any]:
        """Read changed files for detailed analysis.

        Args:
            context: ReviewContext containing changed files

        Returns:
            Dictionary with file contents
        """
        results = {}
        repo_root = context.repo_root

        for file_path in context.changed_files[:5]:
            try:
                full_path = os.path.join(repo_root, file_path)
                if os.path.exists(full_path):
                    with open(full_path, "r") as f:
                        content = f.read()
                        results[file_path] = content[:3000]
                else:
                    results[file_path] = "(file not found)"
            except Exception as e:
                results[file_path] = f"(error: {e})"

        return {"tool": "read", "results": results}

    async def _execute_bandit(self, repo_root: str) -> Dict[str, Any]:
        """Execute bandit Python security linter.

        Args:
            repo_root: Repository root path

        Returns:
            Dictionary with bandit results
        """
        try:
            cmd = ["bandit", "-r", "-f", "json", "-q", repo_root]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.stdout:
                return {"tool": "bandit", "results": proc.stdout[:3000]}
            return {"tool": "bandit", "results": "(no issues found)"}
        except subprocess.TimeoutExpired:
            return {"tool": "bandit", "results": "(timeout)"}
        except FileNotFoundError:
            return {"tool": "bandit", "results": "(bandit not available)"}
        except Exception as e:
            return {"tool": "bandit", "results": f"(error: {e})"}

    async def _execute_semgrep(self, repo_root: str) -> Dict[str, Any]:
        """Execute semgrep semantic code analysis.

        Args:
            repo_root: Repository root path

        Returns:
            Dictionary with semgrep results
        """
        try:
            cmd = ["semgrep", "--config", "auto", "--json", "--quiet", repo_root]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.stdout:
                return {"tool": "semgrep", "results": proc.stdout[:3000]}
            return {"tool": "semgrep", "results": "(no issues found)"}
        except subprocess.TimeoutExpired:
            return {"tool": "semgrep", "results": "(timeout)"}
        except FileNotFoundError:
            return {"tool": "semgrep", "results": "(semgrep not available)"}
        except Exception as e:
            return {"tool": "semgrep", "results": f"(error: {e})"}

    def _get_default_patterns(self) -> List[str]:
        """Get default security search patterns.

        Returns:
            List of default regex patterns for security analysis
        """
        return [
            "password",
            "secret",
            "api_key",
            "token",
            "auth",
            "execute",
            "eval",
            "subprocess",
            "os.system",
        ]

    def _get_default_patterns_for_risk(self, risk_category: str) -> List[str]:
        """Get default patterns based on risk category.

        Args:
            risk_category: Risk category string

        Returns:
            List of patterns relevant to the risk category
        """
        patterns = {
            "prompt_injection": [
                "sanitize",
                "bleach",
                "BeautifulSoup",
                "soup.decompose",
                "html.escape",
                "DOMPurify",
                "clean_html",
            ],
            "injection": [
                "execute",
                "exec",
                "eval",
                "subprocess",
                "os.system",
                "sql",
                "cursor",
                "query",
            ],
            "authn_authz": [
                "authenticate",
                "login",
                "password",
                "token",
                "jwt",
                "session",
                "permission",
                "role",
            ],
            "crypto": [
                "encrypt",
                "decrypt",
                "hash",
                "md5",
                "sha1",
                "aes",
                "rsa",
                "crypto",
            ],
            "data_exposure": [
                "password",
                "secret",
                "api_key",
                "token",
                "credentials",
                ".env",
                "config",
            ],
            "general": [
                "password",
                "secret",
                "api_key",
                "token",
                "auth",
                "execute",
                "eval",
                "subprocess",
                "os.system",
            ],
        }

        return patterns.get(risk_category, patterns["general"])

    def _build_act_message(
        self,
        context: ReviewContext,
        tool_results: Dict[str, Any],
        plan_output: Dict[str, Any],
        delegate_output: Dict[str, Any],
    ) -> str:
        """Build user message for ACT phase.

        Args:
            context: ReviewContext containing changed files
            tool_results: Results from tool execution
            plan_output: Output from plan phase
            delegate_output: Output from delegate phase

        Returns:
            Formatted user message string
        """
        parts = [
            "## PLAN Output",
            "",
            json.dumps(plan_output, indent=2),
            "",
            "## DELEGATE Output",
            "",
            json.dumps(delegate_output, indent=2),
            "",
            "## ACTUAL TOOL EXECUTION RESULTS",
            "",
            json.dumps(tool_results, indent=2),
            "",
            "## Analysis Instructions",
            "",
            "The tools have been EXECUTED. Analyze the ACTUAL results above and generate findings.",
            "",
            "1. Review each tool's output",
            "2. Identify security issues with evidence",
            "3. Note any gaps that need more investigation",
            "",
            "Return your findings in the ACT phase JSON format.",
            "Use actual evidence from the tool outputs - do not speculate.",
        ]
        return "\n".join(parts)

    async def _run_synthesize(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking(
            "SYNTHESIZE", "Validating, merging and de-duplicating security findings from ACT"
        )

        act_output = self._phase_outputs.get("act", {})
        is_early_exit = act_output.get("next_phase_request") == "done"

        if is_early_exit:
            self._phase_logger.log_thinking(
                "SYNTHESIZE", "Early-exit detected (act returned done), running minimal synthesis"
            )

        system_prompt = self._get_phase_prompt("synthesize")

        # Build user message with context
        user_message = self._build_synthesize_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("SYNTHESIZE", thinking)
            logger.info(f"[{self.__class__.__name__}] thinking: {thinking}")
        else:
            logger.info(
                f"[{self.__class__.__name__}] LLM response (no thinking): {response_text[:500]}..."
            )

        output = self._parse_phase_response(response_text, "synthesize")

        goals = [
            "Validate subagent results and findings (ensure each references todo_id with evidence)",
            "Mark TODO statuses as done/blocked and explain issues",
            "Merge all findings into structured evidence list",
            "De-duplicate findings by severity and finding_id",
            "Synthesize summary of issues found",
        ]
        checks = [
            "Verify all subagent responses are received and valid",
            "Validate findings structure and required fields",
            "Ensure TODO status updates are consistent",
            "Ensure de-duplication correctly identifies duplicate findings",
            "Validate summary accurately reflects findings",
        ]
        risks = [
            "Malformed subagent responses",
            "Incomplete or inconsistent findings",
            "Missing status updates for TODOs",
            "Inaccurate merging of conflicting findings",
            "Missing findings due to aggressive de-duplication",
            "Incomplete summary of security issues",
        ]

        steps = []
        if thinking:
            steps.append(
                ThinkingStep(
                    kind="gate",
                    why=thinking,
                    evidence=["LLM response analysis"],
                    next=output.get("next_phase_request", "check"),
                    confidence="medium",
                )
            )

        decision = output.get("next_phase_request", "check")

        frame = ThinkingFrame(
            state="synthesize",
            goals=goals,
            checks=checks,
            risks=risks,
            steps=steps,
            decision=decision,
        )

        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        # Log thinking output
        if is_early_exit:
            self._phase_logger.log_thinking(
                "SYNTHESIZE",
                "SYNTHESIZE complete (minimal), no significant findings to consolidate",
            )
        else:
            self._phase_logger.log_thinking(
                "SYNTHESIZE", "SYNTHESIZE complete, findings validated, merged and de-duplicated"
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
            "CHECK", "Assessing findings severity and generating final security report"
        )

        # Build phase-specific prompt
        system_prompt = self._get_phase_prompt("check")

        # Build user message with context
        user_message = self._build_check_message(context)

        # Execute LLM call
        response_text = await self._execute_llm(system_prompt, user_message)

        # Extract and log LLM thinking from response
        thinking = self._extract_thinking_from_response(response_text)
        if thinking:
            self._phase_logger.log_thinking("CHECK", thinking)
            logger.info(f"[{self.__class__.__name__}] thinking: {thinking}")
        else:
            logger.info(
                f"[{self.__class__.__name__}] LLM response (no thinking): {response_text[:500]}..."
            )

        # Log thinking output
        self._phase_logger.log_thinking("CHECK", "CHECK complete, final report generated")

        # Parse JSON response
        output = self._parse_phase_response(response_text, "check")

        # Create ThinkingFrame with extracted data
        goals = [
            "Assess findings severity (critical/high/medium/low)",
            "Generate comprehensive risk assessment",
            "Provide clear recommendations for each finding",
            "Determine overall risk level (critical/high/medium/low)",
            "Specify required and suggested actions",
        ]
        checks = [
            "Verify findings are properly categorized by severity",
            "Ensure evidence is provided for each finding",
            "Check recommendations are actionable and specific",
            "Validate risk assessment is consistent with findings",
        ]
        risks = [
            "Underestimating critical vulnerabilities",
            "Missing high-impact security issues",
            "Providing ambiguous or impractical recommendations",
            "Inconsistent severity classification",
        ]

        # Create ThinkingStep from extracted thinking
        steps = []
        if thinking:
            steps.append(
                ThinkingStep(
                    kind="transition",
                    why=thinking,
                    evidence=["LLM response analysis"],
                    next="done",
                    confidence="medium",
                )
            )

        # Get decision from output (CHECK is final phase)
        decision = output.get("next_phase_request", "done")

        # Create ThinkingFrame
        frame = ThinkingFrame(
            state="check",
            goals=goals,
            checks=checks,
            risks=risks,
            steps=steps,
            decision=decision,
        )

        # Log ThinkingFrame using phase logger
        self._phase_logger.log_thinking_frame(frame)

        # Add ThinkingFrame to thinking log
        self._thinking_log.add(frame)

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
            logger.info(f"[{self.__class__.__name__}] thinking: {thinking}")
        else:
            logger.info(
                f"[{self.__class__.__name__}] LLM response (no thinking): {response_text[:500]}..."
            )

        # Log thinking output
        self._phase_logger.log_thinking("EVALUATE", "EVALUATE complete, final report generated")

        # Parse JSON response
        output = self._parse_phase_response(response_text, "evaluate")

        # Create ThinkingFrame with extracted data
        goals = [
            "Assess findings severity (critical/high/medium/low)",
            "Generate comprehensive risk assessment",
            "Provide clear recommendations for each finding",
            "Determine overall risk level (critical/high/medium/low)",
            "Specify required and suggested actions",
        ]
        checks = [
            "Verify findings are properly categorized by severity",
            "Ensure evidence is provided for each finding",
            "Check recommendations are actionable and specific",
            "Validate risk assessment is consistent with findings",
        ]
        risks = [
            "Underestimating critical vulnerabilities",
            "Missing high-impact security issues",
            "Providing ambiguous or impractical recommendations",
            "Inconsistent severity classification",
        ]

        # Create ThinkingStep from extracted thinking
        steps = []
        if thinking:
            steps.append(
                ThinkingStep(
                    kind="transition",
                    why=thinking,
                    evidence=["LLM response analysis"],
                    next="done",
                    confidence="medium",
                )
            )

        # Get decision from output (EVALUATE is final phase)
        decision = output.get("next_phase_request", "done")

        # Create ThinkingFrame
        frame = ThinkingFrame(
            state="evaluate",
            goals=goals,
            checks=checks,
            risks=risks,
            steps=steps,
            decision=decision,
        )

        # Log ThinkingFrame using phase logger
        self._phase_logger.log_thinking_frame(frame)

        # Add ThinkingFrame to thinking log
        self._thinking_log.add(frame)

        return output

    def _get_phase_prompt(self, phase: str) -> str:
        context_section = (
            f"""

{self._security_context}
"""
            if self._security_context
            else ""
        )

        return f"""You are the Security Review Agent.

You are in the {phase} phase of the 5-phase security review FSM.

{get_phase_output_schema(phase)}

Your agent name is "security_fsm".

{self._get_phase_specific_instructions(phase)}
{context_section}"""

    def _get_phase_specific_instructions(self, phase: str) -> str:
        """Get phase-specific instructions from security_review_agent.md.

        Args:
            phase: Phase name (e.g., "INTAKE", "PLAN")

        Returns:
            Phase-specific instructions string
        """
        instructions_upper_key = phase.upper()
        instructions = {
            "INTAKE": """INTAKE Phase:
Task:
1. Summarize what changed (by path + change type).
2. Identify likely security surfaces touched.
3. Generate initial risk hypotheses.

Security Detection Patterns Reference:
- HTML Sanitization: Search for BeautifulSoup (soup.decompose, soup.extract, soup.find_all, soup.get_text), bleach, DOMPurify, html5lib, sanitize_html, clean_html, strip_tags, lxml.html.clean
- Input Validation: Check for Pydantic validators, marshmallow schemas, type checking, regex patterns, size limits
- Rate Limiting: Look for Flask-Limiter, @limiter decorators, rate_limit config, throttle middleware
- Size Limits: MAX_CONTENT_LENGTH, content_length checks, size validation, payload limits

Output JSON format:
{
  "phase": "intake",
  "data": {
    "summary": "...",
    "risk_hypotheses": ["..."],
    "questions": ["..."]
  },
  "next_phase_request": "plan"
}
""",
            "PLAN": """PLAN Phase:
Task:
1. Create structured security TODOs (3-12) with:
   - Priority (high/medium/low)
   - Scope (paths, symbols, related_paths)
   - Risk category (authn_authz, injection, crypto, data_exposure, etc.)
   - Acceptance criteria
   - Evidence requirements
2. Specify tool choices to be used in ACT phase (grep, read, bandit, semgrep).

Output JSON format:
{
  "phase": "plan",
  "data": {
    "todos": [...],
    "tools_considered": [...],
    "tools_chosen": [...],
    "why": "..."
  },
  "next_phase_request": "act"
}
""",
            "ACT": """ACT Phase:
Task:
1. Delegate todos to subagents using DelegateTodoSkill.
2. Each subagent will use tools (grep, read, ast-grep, bandit, semgrep) to collect evidence.
3. Collect and aggregate subagent results.
4. Generate security findings grounded in the subagent results.

Subagent Execution:
- Subagents use tools (grep, read, bandit, semgrep) to analyze security
- Each TODO results in a subagent finding or blocked status
- Results are collected and returned as findings list

Output JSON format:
{
  "phase": "act",
  "data": {
    "findings": [
      {
        "id": "finding-1",
        "title": "Potential SQL injection",
        "severity": "high",
        "evidence": "Subagent output showing raw SQL query with user input",
        "recommendation": "Use parameterized queries"
      }
    ],
    "gaps": [
      "Need to review authentication flow",
      "Missing configuration file analysis"
    ]
  },
  "next_phase_request": "synthesize"
}
""",
            "SYNTHESIZE": """SYNTHESIZE Phase:
Task:
1. Validate each subagent result references a todo_id and contains evidence.
2. Mark TODO status as done/blocked and explain any issues.
3. Merge all subagent findings from ACT output into a structured findings list.
4. De-duplicate findings by severity and finding_id/title.
5. Synthesize summary of issues found.

CRITICAL: Your output MUST include the "findings" field with the merged findings from subagents.
Do NOT skip this - the findings are essential for the CHECK phase.

Early-Exit Handling:
If the ACT phase returned next_phase_request="done" (no significant security issues),
you can run minimal synthesis with empty findings and proceed to CHECK.

Output JSON format:
{
  "phase": "synthesize",
  "data": {
    "todo_status": [
      {"todo_id": "...", "status": "done|blocked", "notes": "..."}
    ],
    "findings": {
      "critical": [],
      "high": [...list of high severity findings...],
      "medium": [...list of medium severity findings...],
      "low": []
    },
    "gates": {
      "all_todos_resolved": true,
      "evidence_present": true,
      "findings_categorized": true,
      "confidence_set": true
    },
    "summary": "Brief summary of consolidated findings",
    "issues_with_results": [],
    "missing_information": []
  },
  "next_phase_request": "check"
}

Each finding in the findings object should have:
{
  "id": "finding-N",
  "title": "Finding title",
  "severity": "high|medium|low|critical",
  "description": "Description of the issue",
  "evidence": "Evidence from code/tool output",
  "recommendation": "How to fix this"
}
""",
            "CHECK": """CHECK Phase:
Task:
1. Assess findings for severity distribution and blockers.
2. Generate final risk assessment (critical/high/medium/low).
3. Generate final security review report.

Severity Classification Guidelines:
- CRITICAL: Active vulnerability in changed code that can be exploited NOW (e.g., SQL injection, auth bypass, exposed secrets)
- HIGH: Significant security weakness in changed code requiring immediate attention (e.g., missing auth check, insecure crypto)
- MEDIUM: Security hardening opportunity or missing best practice (e.g., no rate limiting, missing input size limits)
- LOW: Minor security improvement or defensive measure (e.g., missing logging, generic error messages)

IMPORTANT: Do NOT classify missing hardening measures (rate limiting, size validation) as CRITICAL unless they directly enable exploitation.

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
            "EVALUATE": """EVALUATE Phase:
Task:
1. CRITICAL: Use the findings from the SYNTHESIZE Output in your input - DO NOT ignore them.
2. Assess findings for severity distribution and blockers.
3. Generate final risk assessment (critical/high/medium/low).
4. Generate final security review report.

CRITICAL: Your input contains "## SYNTHESIZE Output" which has a "findings" object with
consolidated findings by severity (critical, high, medium, low). You MUST use these findings
in your final report. Do NOT say "No security findings" if the SYNTHESIZE Output has findings.

Severity Classification Guidelines:
- CRITICAL: Active vulnerability in changed code that can be exploited NOW (e.g., SQL injection, auth bypass, exposed secrets)
- HIGH: Significant security weakness in changed code requiring immediate attention (e.g., missing auth check, insecure crypto)
- MEDIUM: Security hardening opportunity or missing best practice (e.g., no rate limiting, missing input size limits)
- LOW: Minor security improvement or defensive measure (e.g., missing logging, generic error messages)

IMPORTANT: Do NOT classify missing hardening measures (rate limiting, size validation) as CRITICAL unless they directly enable exploitation.

Output JSON format:
{
  "phase": "evaluate",
  "data": {
    "findings": {
      "critical": [...copy from SYNTHESIZE or empty array...],
      "high": [...copy findings from SYNTHESIZE here...],
      "medium": [...copy findings from SYNTHESIZE here...],
      "low": [...copy findings from SYNTHESIZE here...]
    },
    "risk_assessment": {
      "overall": "high|medium|low",
      "rationale": "Based on the N findings from SYNTHESIZE...",
      "areas_touched": [...]
    },
    "evidence_index": [...],
    "actions": {
      "required": [...list critical/high findings to fix...],
      "suggested": [...list medium/low findings to consider...]
    },
    "confidence": 0.9,
    "missing_information": []
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

    def _build_delegate_message(self, context: ReviewContext) -> str:
        """Build user message for DELEGATE phase."""
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})
        parts = [
            "## PLAN Output",
            "",
            json.dumps(plan_output, indent=2),
            "",
            "## Current Phase Context",
            "",
            f"Changed Files: {len(context.changed_files)}",
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
                    "The ACT phase returned next_phase_request='done', indicating no significant security issues.",
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

    def _build_evaluate_message(self, context: ReviewContext) -> str:
        synthesize_output = self._phase_outputs.get("synthesize", {}).get("data", {})
        act_output = self._phase_outputs.get("act", {}).get("data", {})
        parts = [
            "## SYNTHESIZE Output",
            "",
            json.dumps(synthesize_output, indent=2),
            "",
            "## ACT Output (Findings to Evaluate)",
            "",
            json.dumps(act_output, indent=2),
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
        import time
        from dawn_kestrel.core.harness import SimpleReviewAgentRunner
        from iron_rook.review.llm_audit_logger import LLMAuditLogger

        llm_logger = LLMAuditLogger.get()
        phase = self._current_security_phase or "unknown"

        llm_logger.log_request(
            agent_name=self.get_agent_name(),
            phase=phase,
            system_prompt=system_prompt,
            user_message=user_message,
        )

        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        start_time = time.time()
        try:
            response_text = await runner.run_with_retry(system_prompt, user_message)
            duration_ms = int((time.time() - start_time) * 1000)

            llm_logger.log_response(
                agent_name=self.get_agent_name(),
                phase=phase,
                response=response_text,
                duration_ms=duration_ms,
            )

            logger.info(f"[{self.__class__.__name__}] Got LLM response: {len(response_text)} chars")
            return response_text
        except Exception as e:
            llm_logger.log_error(
                agent_name=self.get_agent_name(),
                phase=phase,
                error=e,
            )
            raise

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

    def _build_review_output_from_check(
        self, check_output: Dict[str, Any], context: ReviewContext
    ) -> ReviewOutput:
        data = check_output.get("data", {})
        risk_assessment = data.get("risk_assessment", {})
        confidence = data.get("confidence", 0.5)

        all_findings: List[Finding] = []

        act_output = self._phase_outputs.get("act", {})
        subagent_results = act_output.get("data", {}).get("subagent_results", [])

        for subagent_result in subagent_results:
            if subagent_result.get("status") != "done":
                continue
            result_data = subagent_result.get("result", {})
            if not result_data:
                continue
            subagent_findings = result_data.get("findings", [])
            for finding_dict in subagent_findings:
                severity_str = finding_dict.get("severity", "medium")
                if severity_str == "critical":
                    finding_severity = "critical"
                    finding_confidence = "high"
                elif severity_str == "warning":
                    finding_severity = "warning"
                    finding_confidence = "medium"
                elif severity_str == "high":
                    finding_severity = "critical"
                    finding_confidence = "high"
                else:
                    finding_severity = "blocking"
                    finding_confidence = "low"

                finding = Finding(
                    id=finding_dict.get("id", f"finding-{len(all_findings)}"),
                    title=finding_dict.get("title", "Security issue"),
                    severity=finding_severity,
                    confidence=finding_confidence,
                    owner="security",
                    estimate="M",
                    evidence=finding_dict.get("evidence", ""),
                    risk=finding_dict.get("risk", finding_dict.get("description", "")),
                    recommendation=finding_dict.get("recommendation", ""),
                    suggested_patch=finding_dict.get("suggested_patch"),
                )
                all_findings.append(finding)

        findings_dict = data.get("findings", {})
        for severity, findings in findings_dict.items():
            if not isinstance(findings, list):
                continue
            finding_severity = (
                "critical"
                if severity == "high"
                else "warning"
                if severity == "medium"
                else "blocking"
            )
            finding_confidence = (
                "high" if severity == "high" else "medium" if severity == "medium" else "low"
            )

            for finding_dict in findings:
                if not isinstance(finding_dict, dict):
                    continue
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

        seen_keys = set()
        unique_findings = []
        for f in all_findings:
            key = (f.title, f.severity)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_findings.append(f)
        all_findings = unique_findings

        overall_risk = risk_assessment.get("overall", "low")

        if overall_risk == "critical":
            review_severity = "critical"
        elif overall_risk == "high":
            review_severity = "critical"
        elif overall_risk == "medium":
            review_severity = "warning"
        else:
            review_severity = "merge"

        if overall_risk in ("critical", "high") or any(
            f.severity == "critical" for f in all_findings
        ):
            decision = "needs_changes"
            must_fix = [f.title for f in all_findings if f.severity in ("critical", "warning")]
            should_fix = [f.title for f in all_findings if f.severity == "blocking"]
        else:
            decision = "approve"
            must_fix = []
            should_fix = []

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
                reasoning="Security review completed.",
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
