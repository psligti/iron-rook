"""Dynamic security subagent that executes individual security tasks.

This module provides SecuritySubagent, a lightweight FSM-based agent that:
- Receives a specific security task from the parent SecurityReviewer
- Runs a 5-phase ReAct-style FSM: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
- Uses tools directly (grep, ast-grep, bandit, semgrep, etc.)
- Returns findings without delegating to other agents

Key features:
- Actual tool execution in ACT phase
- SYNTHESIZE phase checks against original INTAKE intent
- Loop back to PLAN if intent not satisfied
- Built-in stop conditions (max iterations, stagnation, goal met)

This is used by SecurityReviewer's DELEGATE phase to execute individual
security TODOs that require deep analysis.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging
import json
import subprocess
import os

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    Finding,
    Scope,
    MergeGate,
    ThinkingFrame,
    ThinkingStep,
    RunLog,
)
from iron_rook.review.security_phase_logger import SecurityPhaseLogger
from dawn_kestrel.core.harness import SimpleReviewAgentRunner

logger = logging.getLogger(__name__)


REACT_FSM_TRANSITIONS: Dict[str, List[str]] = {
    "intake": ["plan"],
    "plan": ["act"],
    "act": ["synthesize"],
    "synthesize": ["plan", "done"],
    "done": [],
}

MAX_ITERATIONS = 10
STAGNATION_THRESHOLD = 2


class SecuritySubagent(BaseReviewerAgent):
    """ReAct-style security subagent that executes a single security task.

    Runs a 5-phase FSM with looping:
    - INTAKE: Capture intent, acceptance criteria, evidence requirements
    - PLAN: Select tools based on SYNTHESIZE output (or INTAKE first iteration)
    - ACT: Execute tools (grep, semgrep, bandit, read) and collect evidence
    - SYNTHESIZE: Analyze results, check against original intent, decide next step
    - DONE: Return findings with evidence

    The FSM loops: PLAN → ACT → SYNTHESIZE → (PLAN or DONE)

    Stop conditions:
    - Max iterations reached (MAX_ITERATIONS = 10)
    - Goal met (SYNTHESIZE confirms intent satisfied)
    - Stagnation (no new findings for STAGNATION_THRESHOLD iterations)

    Task definition format:
    {
        "todo_id": "SEC-001",
        "title": "Check for SQL injection vulnerabilities",
        "scope": {...},
        "risk_category": "injection",
        "acceptance_criteria": [...],
        "evidence_required": [...]
    }
    """

    def __init__(
        self,
        task: Dict[str, Any],
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
    ):
        self._task = task
        self._current_phase = "intake"
        self._phase_outputs: Dict[str, Any] = {}
        self._phase_logger = SecurityPhaseLogger()
        self._thinking_log = RunLog()

        self._iteration_count = 0
        self._accumulated_evidence: List[Dict[str, Any]] = []
        self._accumulated_findings: List[Dict[str, Any]] = []
        self._findings_per_iteration: List[int] = []
        self._original_intent: Dict[str, Any] = {}
        self._context_data: Dict[str, Any] = {}

    def get_agent_name(self) -> str:
        return f"security_subagent_{self._task.get('todo_id', 'unknown')}"

    def get_allowed_tools(self) -> List[str]:
        return [
            "git",
            "grep",
            "rg",
            "ast-grep",
            "python",
            "bandit",
            "semgrep",
            "pip-audit",
            "read",
            "file",
        ]

    def get_relevant_file_patterns(self) -> List[str]:
        scope = self._task.get("scope") or {}
        paths = scope.get("paths", []) if isinstance(scope, dict) else scope
        return paths if isinstance(paths, list) else [paths] if paths else ["**/*.py"]

    def get_system_prompt(self) -> str:
        return f"""You are a Security Subagent.

You execute a single security task assigned by the parent SecurityReviewer.

You run a 5-phase ReAct-style FSM: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE).

Key differences from main SecurityReviewer:
- You do NOT delegate to other agents
- You do your own work using available tools
- Your scope is limited to the assigned task
- You must use tools (grep, ast-grep, bandit, semgrep) to collect evidence

Available tools:
- git: git operations (diff, log, blame)
- grep/rg: search for patterns in files
- ast-grep: AST-aware code pattern matching
- python: run Python commands
- bandit: Python security linter
- semgrep: semantic code analysis
- pip-audit: dependency vulnerability check
- read: read file contents
- file: analyze file type/properties

Your assigned task:
{json.dumps(self._task, indent=2)}

Focus on finding evidence-based security findings. Use tools to verify your analysis.
"""

    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Execute security task using 5-phase ReAct-style FSM."""
        self._phase_outputs = {}
        self._current_phase = "intake"
        self._iteration_count = 0
        self._accumulated_evidence = []
        self._accumulated_findings = []
        self._findings_per_iteration = []
        self._original_intent = {}
        self._context_data = {"repo_root": context.repo_root}

        task_title = self._task.get("title", "unknown")
        logger.info(f"[{self.get_agent_name()}] Starting task: {task_title}")

        try:
            while self._current_phase != "done":
                if self._current_phase == "intake":
                    logger.info(f"[{self.get_agent_name()}] === Starting INTAKE phase ===")
                    output = await self._run_intake(context)
                    self._phase_outputs["intake"] = output
                    self._original_intent = output.get("data", {})
                    next_phase = output.get("next_phase_request", "plan")
                    logger.info(
                        f"[{self.get_agent_name()}] INTAKE phase completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                elif self._current_phase == "plan":
                    self._iteration_count += 1
                    logger.info(
                        f"[{self.get_agent_name()}] === Starting PLAN phase (iteration {self._iteration_count}/{MAX_ITERATIONS}) ==="
                    )

                    if self._iteration_count > MAX_ITERATIONS:
                        logger.warning(
                            f"[{self.get_agent_name()}] Max iterations ({MAX_ITERATIONS}) reached, forcing done"
                        )
                        self._current_phase = "done"
                        break

                    output = await self._run_plan(context)
                    self._phase_outputs["plan"] = output
                    next_phase = output.get("next_phase_request", "act")
                    logger.info(
                        f"[{self.get_agent_name()}] PLAN phase completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                elif self._current_phase == "act":
                    logger.info(
                        f"[{self.get_agent_name()}] === Starting ACT phase (iteration {self._iteration_count}) ==="
                    )
                    output = await self._run_act(context)
                    self._phase_outputs["act"] = output

                    new_evidence = output.get("data", {}).get("evidence_collected", [])
                    new_findings = output.get("data", {}).get("findings", [])

                    self._accumulated_evidence.extend(new_evidence)
                    self._accumulated_findings.extend(new_findings)
                    self._findings_per_iteration.append(len(new_findings))

                    self._context_data["tool_results"] = output.get("data", {}).get(
                        "tool_results", {}
                    )

                    next_phase = output.get("next_phase_request", "synthesize")
                    logger.info(
                        f"[{self.get_agent_name()}] ACT phase completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                elif self._current_phase == "synthesize":
                    logger.info(
                        f"[{self.get_agent_name()}] === Starting SYNTHESIZE phase (iteration {self._iteration_count}) ==="
                    )
                    output = await self._run_synthesize(context)
                    self._phase_outputs["synthesize"] = output
                    next_phase = output.get("next_phase_request", "done")

                    if self._should_stop():
                        next_phase = "done"

                    logger.info(
                        f"[{self.get_agent_name()}] SYNTHESIZE phase completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                else:
                    raise ValueError(f"Unknown phase: {self._current_phase}")

            logger.info(
                f"[{self.get_agent_name()}] === Task completed in {self._iteration_count} iterations ==="
            )
            return self._build_review_output(context)

        except Exception as e:
            logger.error(
                f"[{self.get_agent_name()}] === Task FAILED after {self._iteration_count} iterations ==="
            )
            logger.error(
                f"[{self.get_agent_name()}] Error: {type(e).__name__}: {str(e)}", exc_info=True
            )
            return self._build_error_output(context, str(e))

    def _should_stop(self) -> bool:
        if self._iteration_count >= MAX_ITERATIONS:
            logger.info(f"[{self.get_agent_name()}] Stop: max iterations reached")
            return True

        if self._check_stagnation():
            logger.info(f"[{self.get_agent_name()}] Stop: stagnation detected")
            return True

        return False

    def _check_stagnation(self) -> bool:
        if len(self._findings_per_iteration) < STAGNATION_THRESHOLD:
            return False

        recent = self._findings_per_iteration[-STAGNATION_THRESHOLD:]
        all_zero = all(count == 0 for count in recent)
        has_findings = sum(recent) > 0
        enough_iterations = len(self._findings_per_iteration) >= 3

        if all_zero:
            logger.info(
                f"[{self.get_agent_name()}] Stagnation: zero findings for {STAGNATION_THRESHOLD} iterations"
            )
            return True

        if enough_iterations and has_findings:
            logger.info(
                f"[{self.get_agent_name()}] Stagnation: 3+ iterations with findings, forcing done"
            )
            return True

        return False

        recent = self._findings_per_iteration[-STAGNATION_THRESHOLD:]

        # Stagnation type 1: Zero findings for multiple iterations
        if all(count == 0 for count in recent):
            logger.info(
                f"[{self.get_agent_name()}] Stagnation: zero findings for {STAGNATION_THRESHOLD} iterations"
            )
            return True

        # Stagnation type 2: After 3+ iterations with findings, force done
        # (diminishing returns - more iterations won't help)
        if len(self._findings_per_iteration) >= 3 and sum(recent) > 0:
            logger.info(
                f"[{self.get_agent_name()}] Stagnation: 3+ iterations with findings, forcing done"
            )
            return True

        return False

    def _transition_to_phase(self, next_phase: str) -> None:
        valid_transitions = REACT_FSM_TRANSITIONS.get(self._current_phase, [])
        if next_phase not in valid_transitions:
            raise ValueError(
                f"Invalid transition: {self._current_phase} -> {next_phase}. "
                f"Valid: {valid_transitions}"
            )
        self._phase_logger.log_transition(self._current_phase, next_phase)
        logger.info(f"[{self.get_agent_name()}] Transition: {self._current_phase} -> {next_phase}")
        self._current_phase = next_phase

    async def _run_intake(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("INTAKE", "Capturing intent and acceptance criteria")

        system_prompt = self._get_phase_prompt("intake", context)
        user_message = self._build_intake_message(context)

        response_text = await self._execute_llm(system_prompt, user_message)

        thinking = self._extract_thinking_from_response(response_text)

        frame = ThinkingFrame(
            state="intake",
            goals=[
                "Understand assigned security task",
                "Capture acceptance criteria for later verification",
                "Identify evidence needed",
            ],
            checks=[
                "Task definition is clear",
                "Acceptance criteria are specific",
                "Scope files are accessible",
            ],
            risks=[
                "Ambiguous acceptance criteria",
                "Missing context for analysis",
            ],
            steps=[
                ThinkingStep(
                    kind="transition",
                    why=thinking or "Intent captured, ready to plan",
                    evidence=[f"Task: {self._task.get('title', 'unknown')}"],
                    next="plan",
                    confidence="medium",
                )
            ],
            decision="plan",
        )
        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        output = self._parse_response(response_text, "intake")
        return output

    async def _run_plan(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("PLAN", "Selecting tools and analysis approach")

        system_prompt = self._get_phase_prompt("plan", context)
        user_message = self._build_plan_message(context)

        response_text = await self._execute_llm(system_prompt, user_message)

        thinking = self._extract_thinking_from_response(response_text)

        plan_data = {}
        try:
            parsed = json.loads(
                response_text.split("```json")[1].split("```")[0]
                if "```json" in response_text
                else response_text
            )
            plan_data = parsed.get("data", {})
        except (json.JSONDecodeError, IndexError):
            pass

        self._context_data["current_plan"] = plan_data

        frame = ThinkingFrame(
            state="plan",
            goals=[
                "Select appropriate security tools",
                "Define specific search patterns",
                "Plan evidence collection strategy",
            ],
            checks=[
                "Tools match task requirements",
                "Patterns are specific enough",
            ],
            risks=[
                "Wrong tool selection",
                "Patterns too broad or too narrow",
            ],
            steps=[
                ThinkingStep(
                    kind="tool",
                    why=thinking or "Tool selection complete",
                    evidence=plan_data.get("tools_to_use", []),
                    next="act",
                    confidence="medium",
                )
            ],
            decision="act",
        )
        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        output = self._parse_response(response_text, "plan")
        return output

    async def _run_act(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("ACT", "Executing tools and collecting evidence")

        plan_output = self._phase_outputs.get("plan", {}).get("data", {})

        tool_results = await self._execute_tools(plan_output, context)

        system_prompt = self._get_phase_prompt("act", context)
        user_message = self._build_act_message(context, tool_results)

        response_text = await self._execute_llm(system_prompt, user_message)

        thinking = self._extract_thinking_from_response(response_text)

        act_data = {}
        try:
            parsed = json.loads(
                response_text.split("```json")[1].split("```")[0]
                if "```json" in response_text
                else response_text
            )
            act_data = parsed.get("data", {})
        except (json.JSONDecodeError, IndexError):
            pass

        act_data["tool_results"] = tool_results
        findings_count = len(act_data.get("findings", []))

        frame = ThinkingFrame(
            state="act",
            goals=[
                "Execute planned tools",
                "Collect evidence from tool outputs",
                "Generate initial findings",
            ],
            checks=[
                "Tools executed successfully",
                "Evidence collected from actual outputs",
            ],
            risks=[
                "Tool execution failures",
                "False positives from tool output",
            ],
            steps=[
                ThinkingStep(
                    kind="gate",
                    why=thinking or f"Tools executed, {findings_count} findings generated",
                    evidence=[
                        f"Tools run: {list(tool_results.keys())}",
                        f"Findings: {findings_count}",
                    ],
                    next="synthesize",
                    confidence="high" if findings_count > 0 else "medium",
                )
            ],
            decision="synthesize",
        )
        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        output = self._parse_response(response_text, "act")
        output["data"] = act_data
        return output

    async def _execute_tools(
        self, plan_output: Dict[str, Any], context: ReviewContext
    ) -> Dict[str, Any]:
        tools_to_use = plan_output.get("tools_to_use", [])
        search_patterns = plan_output.get("search_patterns", [])
        results = {}
        repo_root = self._context_data.get("repo_root", context.repo_root)

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
        results = {}
        repo_root = self._context_data.get("repo_root", context.repo_root)

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
        risk_category = self._task.get("risk_category", "general")

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
                "query",
                "cursor.execute",
            ],
            "authn_authz": [
                "authenticate",
                "authorize",
                "token",
                "session",
                "password",
                "secret",
                "api_key",
            ],
            "secrets": [
                "password",
                "secret",
                "api_key",
                "token",
                "credential",
                "private_key",
                "aws_access_key",
            ],
            "data_exposure": [
                "log",
                "print",
                "response",
                "jsonify",
                "serialize",
                "to_dict",
                "model_dump",
            ],
        }

        return patterns.get(risk_category, ["security", "vuln", "exploit"])

    async def _run_synthesize(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("SYNTHESIZE", "Analyzing results and checking intent")

        system_prompt = self._get_phase_prompt("synthesize", context)
        user_message = self._build_synthesize_message(context)

        response_text = await self._execute_llm(system_prompt, user_message)

        thinking = self._extract_thinking_from_response(response_text)

        synthesize_data = {}
        try:
            parsed = json.loads(
                response_text.split("```json")[1].split("```")[0]
                if "```json" in response_text
                else response_text
            )
            synthesize_data = parsed.get("data", {})
        except (json.JSONDecodeError, IndexError):
            pass

        goal_achieved = synthesize_data.get("goal_achieved", False)
        next_phase = "done" if goal_achieved else "plan"

        frame = ThinkingFrame(
            state="synthesize",
            goals=[
                "Analyze tool execution results",
                "Check findings against acceptance criteria",
                "Decide: goal achieved or more analysis needed",
            ],
            checks=[
                "All acceptance criteria evaluated",
                "Evidence supports conclusions",
            ],
            risks=[
                "Premature termination",
                "Endless looping",
            ],
            steps=[
                ThinkingStep(
                    kind="gate" if goal_achieved else "transition",
                    why=thinking
                    or (
                        "Goal achieved, proceeding to done"
                        if goal_achieved
                        else "More analysis needed"
                    ),
                    evidence=[
                        f"Total findings: {len(self._accumulated_findings)}",
                        f"Iteration: {self._iteration_count}/{MAX_ITERATIONS}",
                        f"Goal achieved: {goal_achieved}",
                    ],
                    next=next_phase,
                    confidence="high" if goal_achieved else "medium",
                )
            ],
            decision=next_phase,
        )
        self._phase_logger.log_thinking_frame(frame)
        self._thinking_log.add(frame)

        output = self._parse_response(response_text, "synthesize")
        return output

    def _get_phase_prompt(self, phase: str, context: ReviewContext) -> str:
        task_title = self._task.get("title", "Unknown task")

        prompts = {
            "intake": f"""You are a Security Subagent executing task: {task_title}

INTAKE Phase:
Task: Capture the intent, acceptance criteria, and evidence requirements for this security task.

You are in the INTAKE phase of a 5-phase ReAct-style FSM.
This phase runs ONCE at the beginning. Your output will be used to verify goal completion later.

Output JSON format:
{{
  "phase": "intake",
  "data": {{
    "task_understanding": "Clear description of what you need to analyze",
    "acceptance_criteria": [
      "Criterion 1: e.g., 'Identify all HTML sanitization code'",
      "Criterion 2: e.g., 'Verify sanitization removes dangerous tags'",
      "Criterion 3: e.g., 'Check for bypass vectors'"
    ],
    "evidence_required": [
      "grep results for sanitization patterns",
      "code snippets showing sanitization logic"
    ],
    "scope_files": ["list of files to analyze"],
    "key_questions": ["What specific patterns indicate secure vs insecure?"]
  }},
  "next_phase_request": "plan"
}}

Your task:
{json.dumps(self._task, indent=2)}

Define clear, verifiable acceptance criteria that can be checked in the SYNTHESIZE phase.
""",
            "plan": f"""You are a Security Subagent executing task: {task_title}

PLAN Phase (Iteration {self._iteration_count}):
Task: Select tools and define specific search patterns.

Available tools:
- grep/rg: Search for patterns in files (fast, text-based)
- ast-grep: AST-aware code pattern matching (structural)
- bandit: Python security linter (automated checks)
- semgrep: Semantic code analysis (pattern-based)
- read: Read file contents (detailed analysis)

Output JSON format:
{{
  "phase": "plan",
  "data": {{
    "analysis_plan": "What you will do in this iteration",
    "tools_to_use": ["grep", "read"],
    "search_patterns": ["sanitize", "BeautifulSoup", "bleach"],
    "expected_evidence": "What you expect to find",
    "rationale": "Why these tools and patterns"
  }},
  "next_phase_request": "act"
}}

{self._get_plan_context()}

Select specific, actionable tools and patterns. Be concrete about what you'll search for.
""",
            "act": f"""You are a Security Subagent executing task: {task_title}

ACT Phase (Iteration {self._iteration_count}):
Task: Analyze the tool execution results and generate findings.

IMPORTANT: Tool results have been EXECUTED and are provided below.
Use the ACTUAL tool outputs as evidence - do not speculate.

Output JSON format:
{{
  "phase": "act",
  "data": {{
    "findings": [
      {{
        "severity": "critical|high|medium|low",
        "title": "Clear finding title",
        "description": "What was found and why it's a security issue",
        "evidence": ["Specific evidence from tool outputs"],
        "recommendations": ["How to fix this issue"]
      }}
    ],
    "evidence_collected": ["Summary of evidence gathered"],
    "summary": "Brief summary of this iteration's analysis",
    "gaps_remaining": ["What still needs to be checked"]
  }},
  "next_phase_request": "synthesize"
}}

Original acceptance criteria:
{json.dumps(self._original_intent.get("acceptance_criteria", []), indent=2)}

Generate findings based on ACTUAL tool outputs provided below.
""",
            "synthesize": f"""You are a Security Subagent executing task: {task_title}

SYNTHESIZE Phase (Iteration {self._iteration_count}):
Task: Evaluate if the original intent has been satisfied and decide next steps.

CRITICAL CONVERGENCE RULES:
1. BIAS TOWARD DONE: After iteration 1 with ANY findings, you should strongly prefer "done"
2. DIMINISHING RETURNS: More iterations rarely produce better results for search/verification tasks
3. GOOD ENOUGH: If you have evidence addressing the core question, mark goal_achieved: true
4. MAX 2 ITERATIONS: For most tasks, 1-2 iterations is sufficient. Looping more wastes time.

When to set goal_achieved: true:
- You have ANY findings related to the task (even partial evidence counts)
- You ran the requested tools and have results to report
- You can answer the original question with current evidence
- Iteration >= 2 AND you have findings (stop, don't loop forever)

When to loop back to PLAN (goal_achieved: false):
- Tool execution failed completely (not partial results)
- Zero findings after iteration 1 for a search task
- Critical file was not readable and you need it

Output JSON format:
{{
  "phase": "synthesize",
  "data": {{
    "criteria_status": [
      {{"criterion": "...", "status": "met|partially_met|not_met", "evidence": "..."}}
    ],
    "goal_achieved": true|false,
    "summary": "Overall assessment of the analysis",
    "remaining_gaps": ["What still needs investigation if goal not achieved"],
    "recommendation": "done|continue"
  }},
  "next_phase_request": "done|plan"
}}

ORIGINAL INTAKE INTENT (from first phase):
{json.dumps(self._original_intent, indent=2)}

ACCUMULATED FINDINGS SO FAR: {len(self._accumulated_findings)}
ITERATION: {self._iteration_count}/{MAX_ITERATIONS}

STOP CONDITION CHECK:
- Findings count: {len(self._accumulated_findings)} (if > 0, prefer done)
- Iteration: {self._iteration_count}/{MAX_ITERATIONS} (if >= 2, strongly prefer done)

Set "goal_achieved": true if you have any relevant findings. Report what you found.
""",
        }
        return prompts.get(phase, "")

    def _get_plan_context(self) -> str:
        if self._iteration_count == 1:
            intake = self._phase_outputs.get("intake", {}).get("data", {})
            return f"""INTAKE Output (first iteration):
{json.dumps(intake, indent=2)}

This is your first iteration. Plan your initial analysis approach."""
        else:
            synthesize = self._phase_outputs.get("synthesize", {}).get("data", {})
            return f"""Previous SYNTHESIZE Output (iteration {self._iteration_count - 1}):
{json.dumps(synthesize, indent=2)}

Previous plan did not fully satisfy acceptance criteria. Adjust your approach based on gaps identified."""

    def _build_intake_message(self, context: ReviewContext) -> str:
        return f"""## Task Definition
{json.dumps(self._task, indent=2)}

## Review Context
Repository: {context.repo_root}
Changed files: {len(context.changed_files)}
Changed file paths:
{chr(10).join(f"- {f}" for f in context.changed_files[:15])}

## Task
Define clear acceptance criteria and evidence requirements for this security task.
What specific evidence will prove the security issue is present or absent?

Return your analysis in the INTAKE phase JSON format.
"""

    def _build_plan_message(self, context: ReviewContext) -> str:
        return f"""## Task
{json.dumps(self._task, indent=2)}

## Context
Iteration: {self._iteration_count}/{MAX_ITERATIONS}
{self._get_plan_context()}

## Changed Files (in scope)
{chr(10).join(f"- {f}" for f in context.changed_files[:20])}

## Plan
Create a specific, actionable analysis plan:
1. Which tools will you use? (grep, rg, bandit, semgrep, read)
2. What EXACT patterns will you search for?
3. What evidence do you expect?

Return your plan in the PLAN phase JSON format.
"""

    def _build_act_message(self, context: ReviewContext, tool_results: Dict[str, Any]) -> str:
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})

        return f"""## Plan from PLAN Phase
{json.dumps(plan_output, indent=2)}

## Task
{json.dumps(self._task, indent=2)}

## ACTUAL TOOL EXECUTION RESULTS
{json.dumps(tool_results, indent=2)}

## Analysis Instructions
The tools have been EXECUTED. Analyze the ACTUAL results above and generate findings.

1. Review each tool's output
2. Identify security issues with evidence
3. Note any gaps that need more investigation

Return your findings in the ACT phase JSON format.
Use actual evidence from the tool outputs - do not speculate.
"""

    def _build_synthesize_message(self, context: ReviewContext) -> str:
        act_output = self._phase_outputs.get("act", {}).get("data", {})

        return f"""## Original INTAKE Intent
{json.dumps(self._original_intent, indent=2)}

## Current ACT Phase Findings
{json.dumps(act_output.get("findings", []), indent=2)}

## Accumulated Evidence (all iterations)
Total findings collected: {len(self._accumulated_findings)}
Total evidence items: {len(self._accumulated_evidence)}

## Iteration Status
Current iteration: {self._iteration_count}/{MAX_ITERATIONS}

## Synthesis Task
1. Check each acceptance criterion against the evidence collected
2. Determine if the goal has been FULLY achieved
3. If not achieved, specify what additional analysis is needed

Return your synthesis in the SYNTHESIZE phase JSON format.
Be honest - set goal_achieved=true ONLY if all criteria are satisfied.
"""

    async def _execute_llm(self, system_prompt: str, user_message: str) -> str:
        logger.info(
            f"[{self.get_agent_name()}] Calling LLM (system_prompt: {len(system_prompt)} chars, user_message: {len(user_message)} chars)"
        )
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        try:
            response_text = await runner.run_with_retry(system_prompt, user_message)
            logger.info(f"[{self.get_agent_name()}] LLM response: {len(response_text)} chars")
            return response_text
        except Exception as e:
            logger.error(f"[{self.get_agent_name()}] LLM call failed: {type(e).__name__}: {str(e)}")
            raise

    def _extract_thinking_from_response(self, response_text: str) -> str:
        try:
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

            if "thinking" in response_json:
                return str(response_json["thinking"])

            if "data" in response_json and isinstance(response_json["data"], dict):
                if "thinking" in response_json["data"]:
                    return str(response_json["data"]["thinking"])

                for key in ["reasoning", "analysis", "rationale", "thoughts"]:
                    if key in response_json["data"]:
                        return str(response_json["data"][key])

            for key in ["reasoning", "analysis", "rationale", "thoughts"]:
                if key in response_json:
                    return str(response_json[key])

        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        if "<thinking>" in response_text and "</thinking>" in response_text:
            start = response_text.find("<thinking>") + len("<thinking>")
            end = response_text.find("</thinking>")
            thinking = response_text[start:end].strip()
            return thinking

        return ""

    def _parse_response(self, response_text: str, expected_phase: str) -> Dict[str, Any]:
        try:
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            output = json.loads(response_text)

            actual_phase = output.get("phase")
            if actual_phase != expected_phase:
                logger.warning(
                    f"[{self.get_agent_name()}] Expected phase '{expected_phase}', got '{actual_phase}'"
                )

            return output

        except json.JSONDecodeError as e:
            try:
                start_idx = response_text.find("{")
                if start_idx == -1:
                    raise ValueError("No JSON object found in response")

                brace_count = 0
                end_idx = start_idx
                in_string = False
                escape_next = False

                for i, char in enumerate(response_text[start_idx:], start_idx):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == "\\":
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break

                json_text = response_text[start_idx:end_idx]

                def clean_json_string(s: str) -> str:
                    result = []
                    in_str = False
                    escape = False
                    for c in s:
                        if escape:
                            result.append(c)
                            escape = False
                        elif c == "\\":
                            result.append(c)
                            escape = True
                        elif c == '"':
                            result.append(c)
                            in_str = not in_str
                        elif in_str and ord(c) < 32:
                            if c == "\n":
                                result.append("\\n")
                            elif c == "\r":
                                result.append("\\r")
                            elif c == "\t":
                                result.append("\\t")
                            else:
                                result.append(f"\\u{ord(c):04x}")
                        else:
                            result.append(c)
                    return "".join(result)

                json_text = clean_json_string(json_text)
                output = json.loads(json_text)

                actual_phase = output.get("phase")
                if actual_phase != expected_phase:
                    logger.warning(
                        f"[{self.get_agent_name()}] Expected phase '{expected_phase}', got '{actual_phase}'"
                    )
                return output

            except (json.JSONDecodeError, ValueError) as e2:
                logger.error(
                    f"[{self.get_agent_name()}] Failed to parse JSON after extraction: {e2}"
                )
                logger.error(
                    f"[{self.get_agent_name()}] Response (first 500 chars): {response_text[:500]}..."
                )
                raise ValueError(f"Failed to parse phase response: {e2}") from e2

    def _build_review_output(self, context: ReviewContext) -> ReviewOutput:
        findings: List[Finding] = []

        seen_titles = set()
        for idx, finding_dict in enumerate(self._accumulated_findings):
            title = finding_dict.get("title", f"Security issue {idx}")
            if title in seen_titles:
                continue
            seen_titles.add(title)

            severity = finding_dict.get("severity", "medium")
            if severity == "high" or severity == "critical":
                finding_severity = "critical"
                finding_confidence = "high"
            elif severity == "medium":
                finding_severity = "warning"
                finding_confidence = "medium"
            else:
                finding_severity = "blocking"
                finding_confidence = "low"

            finding = Finding(
                id=f"subagent-{self._task.get('todo_id')}-{idx}",
                title=title,
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
            findings.append(finding)

        todo_id = self._task.get("todo_id", "unknown")

        synthesize_output = self._phase_outputs.get("synthesize", {}).get("data", {})
        summary = synthesize_output.get(
            "summary", f"Task completed in {self._iteration_count} iterations"
        )

        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Task {todo_id} complete. {self._iteration_count} iterations, {len(findings)} unique findings. {summary}",
            severity="critical"
            if any(f.severity == "critical" for f in findings)
            else "warning"
            if findings
            else "merge",
            scope=Scope(
                relevant_files=self.get_relevant_file_patterns(),
                ignored_files=[],
                reasoning=f"Security subagent for task {todo_id} ({self._iteration_count} iterations)",
            ),
            findings=findings,
            merge_gate=MergeGate(
                decision="needs_changes" if findings else "approve",
                must_fix=[f.title for f in findings if f.severity in ("critical", "warning")],
                should_fix=[f.title for f in findings if f.severity == "blocking"],
                notes_for_coding_agent=[
                    f"Task {todo_id} completed in {self._iteration_count} iterations",
                    f"Total evidence collected: {len(self._accumulated_evidence)} items",
                    f"Goal achieved: {synthesize_output.get('goal_achieved', False)}",
                ],
            ),
            thinking_log=self._thinking_log,
        )

    def _build_error_output(self, context: ReviewContext, error_msg: str) -> ReviewOutput:
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Task failed at iteration {self._iteration_count}: {error_msg}",
            severity="critical",
            scope=Scope(
                relevant_files=[],
                ignored_files=[],
                reasoning="Security subagent encountered error",
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=[
                    f"Task {self._task.get('todo_id')} failed: {error_msg}",
                    f"Completed {self._iteration_count} iterations before failure",
                    "Please retry or investigate error",
                ],
            ),
            thinking_log=self._thinking_log,
        )
