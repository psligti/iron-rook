"""Dynamic architecture subagent that executes individual architecture tasks."""

from __future__ import annotations

from typing import Dict, Any, List, Union
import logging
import json
import subprocess
import os
import ast

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
from iron_rook.review.subagents.base_subagent import (
    BaseDynamicSubagent,
    MAX_ITERATIONS,
)
from iron_rook.review.security_phase_logger import SecurityPhaseLogger
from iron_rook.review.runner import SimpleReviewAgentRunner

logger = logging.getLogger(__name__)


class ArchitectureSubagent(BaseDynamicSubagent):
    """ReAct-style architecture subagent that executes a single architecture task."""

    def __init__(
        self,
        task: Dict[str, Any],
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        repo_root: str = "",
    ) -> None:
        super().__init__(
            task=task,
            verifier=verifier,
            max_retries=max_retries,
            agent_runtime=agent_runtime,
            repo_root=repo_root,
        )
        self._phase_logger = SecurityPhaseLogger()
        self._runlog = RunLog()

    def get_agent_name(self) -> str:
        return f"architecture_subagent_{self._task.get('todo_id', 'unknown')}"

    def get_domain_tools(self) -> List[str]:
        return ["grep", "read", "file", "python"]

    def get_allowed_tools(self) -> List[str]:
        return self.get_domain_tools()

    def get_domain_prompt(self) -> str:
        return """Focus on finding evidence-based architecture findings.

Key areas to check:
1. SOLID principles compliance (Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion)
2. Design patterns usage and correctness (Factory, Singleton, Strategy, Observer, etc.)
3. Code structure and organization (modules, packages, layers)
4. Coupling and cohesion analysis
5. Dependency injection and inversion patterns
6. Interface design and abstraction levels

Use tools to verify your analysis. Every finding must include:
1. Specific file:line: references
2. Actual code snippets showing architecture issues
3. Clear recommendation with design pattern examples
"""

    def get_system_prompt(self) -> str:
        task_json = json.dumps(self._task, indent=2)
        return f"""You are an Architecture Subagent.

You execute a single architecture task assigned by the parent ArchitectureReviewer.

You run a 5-phase ReAct-style FSM: INTAKE -> PLAN -> ACT -> SYNTHESIZE -> (PLAN or DONE).

Available tools:
- grep: search for patterns in files
- read: read file contents
- file: analyze file type/properties
- python: run Python commands (including AST analysis for class/function structure)

Your assigned task:
{task_json}

{self.get_domain_prompt()}"""

    def get_relevant_file_patterns(self) -> List[str]:
        scope = self._task.get("scope") or {}
        paths = scope.get("paths", []) if isinstance(scope, dict) else scope
        if paths:
            return paths if isinstance(paths, list) else [paths]
        return ["**/*.py", "src/**", "lib/**", "app/**", "core/**"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        from iron_rook.review.llm_audit_logger import SpanContext

        self._repo_root = context.repo_root
        with SpanContext(span_name=self._task.get("title", "unknown")):
            return await self._run_subagent_fsm(context)

    async def _run_intake_phase(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("INTAKE", "Capturing architecture intent")
        system_prompt = self._get_phase_prompt("intake", context)
        user_message = self._build_intake_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        thinking = self._extract_thinking_from_response(response_text)

        frame = ThinkingFrame(
            state="intake",
            goals=["Understand architecture task", "Capture acceptance criteria"],
            checks=["Task definition is clear", "Acceptance criteria are specific"],
            risks=["Ambiguous criteria", "Missing context"],
            steps=[
                ThinkingStep(
                    kind="transition",
                    why=thinking or "Intent captured",
                    evidence=[f"Task: {self._task.get('title', 'unknown')}"],
                    next="plan",
                    confidence="medium",
                )
            ],
            decision="plan",
        )
        self._phase_logger.log_thinking_frame(frame)
        self._runlog.add(frame)
        return self._parse_response(response_text, "intake")

    async def _run_plan_phase(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("PLAN", "Selecting architecture tools")
        system_prompt = self._get_phase_prompt("plan", context)
        user_message = self._build_plan_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        thinking = self._extract_thinking_from_response(response_text)
        output = self._parse_response(response_text, "plan")
        plan_data = output.get("data", {})
        self._context_data["current_plan"] = plan_data

        frame = ThinkingFrame(
            state="plan",
            goals=["Select tools", "Define search patterns"],
            checks=["Tools match task", "Patterns are specific"],
            risks=["Wrong tool selection", "Patterns too broad"],
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
        self._runlog.add(frame)
        return output

    async def _run_act_phase(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("ACT", "Executing architecture tools")
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})
        tool_results = await self._execute_tools(plan_output, context)
        system_prompt = self._get_phase_prompt("act", context)
        user_message = self._build_act_message(context, tool_results)
        response_text = await self._execute_llm(system_prompt, user_message)
        thinking = self._extract_thinking_from_response(response_text)
        output = self._parse_response(response_text, "act")
        act_data = output.get("data", {})
        act_data["tool_results"] = tool_results
        findings_count = len(act_data.get("findings", []))

        frame = ThinkingFrame(
            state="act",
            goals=["Execute tools", "Collect evidence", "Generate findings"],
            checks=["Tools executed", "Evidence collected"],
            risks=["Tool failures", "Missing patterns"],
            steps=[
                ThinkingStep(
                    kind="gate",
                    why=thinking or f"Tools executed, {findings_count} findings",
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
        self._runlog.add(frame)
        output["data"] = act_data
        return output

    async def _run_synthesize_phase(self, context: ReviewContext) -> Dict[str, Any]:
        self._phase_logger.log_thinking("SYNTHESIZE", "Analyzing architecture results")
        system_prompt = self._get_phase_prompt("synthesize", context)
        user_message = self._build_synthesize_message(context)
        response_text = await self._execute_llm(system_prompt, user_message)
        thinking = self._extract_thinking_from_response(response_text)
        output = self._parse_response(response_text, "synthesize")
        synthesize_data = output.get("data", {})
        goal_achieved = synthesize_data.get("goal_achieved", False)
        next_phase = "done" if goal_achieved else "plan"

        frame = ThinkingFrame(
            state="synthesize",
            goals=["Analyze results", "Check against criteria"],
            checks=["All criteria evaluated", "Evidence supports conclusions"],
            risks=["Premature termination", "Endless looping"],
            steps=[
                ThinkingStep(
                    kind="gate" if goal_achieved else "transition",
                    why=thinking or ("Goal achieved" if goal_achieved else "More analysis needed"),
                    evidence=[
                        f"Total findings: {len(self._accumulated_findings)}",
                        f"Iteration: {self._iteration_count}/{MAX_ITERATIONS}",
                    ],
                    next=next_phase,
                    confidence="high" if goal_achieved else "medium",
                )
            ],
            decision=next_phase,
        )
        self._phase_logger.log_thinking_frame(frame)
        self._runlog.add(frame)
        return output

    async def _execute_tools(
        self, plan_output: Dict[str, Any], context: ReviewContext
    ) -> Dict[str, Any]:
        tools_to_use = plan_output.get("tools_to_use", [])
        search_patterns = plan_output.get("search_patterns", [])
        results: Dict[str, Any] = {}
        repo_root = self._context_data.get("repo_root", context.repo_root)

        for tool in tools_to_use:
            try:
                if tool == "grep":
                    results[tool] = await self._execute_grep(search_patterns, repo_root)
                elif tool == "read":
                    results["read"] = await self._execute_read(context)
                elif tool == "file":
                    results["file"] = await self._execute_file(context)
                elif tool == "python":
                    results["python"] = await self._execute_python_ast_analysis(context, repo_root)
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
        results: Dict[str, Any] = {}
        patterns_to_search = patterns if patterns else self._get_default_patterns()
        for pattern in patterns_to_search[:5]:
            try:
                cmd = ["rg", "-n", "--max-count=50", "-g", "*.py", pattern, repo_root]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0 and proc.stdout:
                    results[pattern] = proc.stdout[:2000]
                else:
                    results[pattern] = "(no matches)"
            except subprocess.TimeoutExpired:
                results[pattern] = "(timeout)"
            except FileNotFoundError:
                try:
                    cmd = ["grep", "-rn", "--max-count=50", pattern, repo_root]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    results[pattern] = (
                        proc.stdout[:2000] if proc.returncode == 0 else "(no matches)"
                    )
                except Exception as e:
                    results[pattern] = f"(error: {e})"
            except Exception as e:
                results[pattern] = f"(error: {e})"
        return {"tool": "grep", "results": results}

    async def _execute_read(self, context: ReviewContext) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        repo_root = self._context_data.get("repo_root", context.repo_root)
        for file_path in context.changed_files[:5]:
            try:
                full_path = os.path.join(repo_root, file_path)
                if os.path.exists(full_path):
                    with open(full_path, "r") as f:
                        results[file_path] = f.read()
                else:
                    results[file_path] = "(file not found)"
            except Exception as e:
                results[file_path] = f"(error: {e})"
        return {"tool": "read", "results": results}

    async def _execute_file(self, context: ReviewContext) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        repo_root = self._context_data.get("repo_root", context.repo_root)
        for file_path in context.changed_files[:5]:
            try:
                full_path = os.path.join(repo_root, file_path)
                if os.path.exists(full_path):
                    cmd = ["file", full_path]
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    results[file_path] = (
                        proc.stdout.strip() if proc.returncode == 0 else "(file check failed)"
                    )
                else:
                    results[file_path] = "(file not found)"
            except Exception as e:
                results[file_path] = f"(error: {e})"
        return {"tool": "file", "results": results}

    async def _execute_python_ast_analysis(
        self, context: ReviewContext, repo_root: str
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        py_files = [f for f in context.changed_files if f.endswith(".py")][:5]
        for file_path in py_files:
            try:
                full_path = os.path.join(repo_root, file_path)
                if os.path.exists(full_path):
                    with open(full_path, "r") as f:
                        content = f.read()
                    try:
                        tree = ast.parse(content)
                        ast_info = self._extract_ast_info(tree, file_path)
                        results[file_path] = ast_info
                    except SyntaxError as e:
                        results[file_path] = f"(syntax error: {e})"
                else:
                    results[file_path] = "(file not found)"
            except Exception as e:
                results[file_path] = f"(error: {e})"
        return {"tool": "python", "results": results}

    def _extract_ast_info(self, tree: ast.Module, file_path: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "file": file_path,
            "classes": [],
            "functions": [],
            "imports": [],
            "module_docstring": ast.get_docstring(tree) is not None,
        }
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                is_public = not node.name.startswith("_")
                args_count = len(node.args.args)
                has_return_annotation = node.returns is not None
                info["functions"].append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "is_public": is_public,
                        "args_count": args_count,
                        "has_return_annotation": has_return_annotation,
                    }
                )
            elif isinstance(node, ast.ClassDef):
                is_public = not node.name.startswith("_")
                bases = [self._get_name_from_node(b) for b in node.bases]
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(
                            {
                                "name": item.name,
                                "is_public": not item.name.startswith("_"),
                                "args_count": len(item.args.args),
                            }
                        )
                info["classes"].append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "is_public": is_public,
                        "bases": bases,
                        "methods": methods,
                        "method_count": len(methods),
                        "public_method_count": len([m for m in methods if m["is_public"]]),
                    }
                )
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        info["imports"].append(alias.name)
                else:
                    module = node.module or ""
                    for alias in node.names:
                        info["imports"].append(f"{module}.{alias.name}" if module else alias.name)
        return info

    def _get_name_from_node(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name_from_node(node.value)}.{node.attr}"
        return ""

    def _get_default_patterns(self) -> List[str]:
        arch_type = self._task.get("architecture_type", "general")
        patterns = {
            "solid": ["class ", "def ", "import ", "self.", "dependency"],
            "patterns": ["class ", "def ", "factory", "singleton", "strategy", "observer"],
            "coupling": ["import ", "from ", "dependency", "inject"],
            "layers": ["import ", "from ", "controller", "service", "repository", "model"],
            "modularity": ["class ", "def ", "interface", "abstract"],
        }
        return patterns.get(arch_type, ["class ", "def ", "import ", "self."])

    def _get_phase_prompt(self, phase: str, context: ReviewContext) -> str:
        task_title = self._task.get("title", "Unknown task")
        task_json = json.dumps(self._task, indent=2)

        if phase == "intake":
            return self._build_intake_prompt(task_title, task_json)
        elif phase == "plan":
            return self._build_plan_prompt(task_title, task_json)
        elif phase == "act":
            return self._build_act_prompt(task_title, task_json)
        elif phase == "synthesize":
            return self._build_synthesize_prompt(task_title, task_json)
        return ""

    def _build_intake_prompt(self, task_title: str, task_json: str) -> str:
        return f"""You are an Architecture Subagent executing task: {task_title}

INTAKE Phase: Capture intent, acceptance criteria, and evidence requirements.

ACCEPTANCE CRITERIA REQUIREMENTS:
1. Each criterion MUST be specific and verifiable
2. Each criterion MUST define SUCCESS condition
3. Each criterion MUST define verification method
4. Minimum 3 criteria, maximum 5 criteria

GOOD CRITERION EXAMPLES:
- "Single responsibility principle followed" - Met: Each class has <= 3 public methods
- "Dependency injection used" - Met: No direct instantiation of dependencies in constructors

Output JSON format:
{{"phase": "intake", "data": {{"task_understanding": "...", "acceptance_criteria": [{{"criterion": "...", "success_condition": "...", "verification_method": "..."}}], "evidence_required": [...], "scope_files": [...], "key_questions": [...]}}, "next_phase_request": "plan"}}

Your task:
{task_json}
"""

    def _build_plan_prompt(self, task_title: str, task_json: str) -> str:
        plan_context = self._get_plan_context()
        return f"""You are an Architecture Subagent executing task: {task_title}

PLAN Phase (Iteration {self._iteration_count}): Select tools and define search patterns.

Available tools: grep, read, file, python (AST for class/function/dependency analysis)

PLAN REQUIREMENTS:
1. "tools_to_use": List 2-4 specific tools
2. "search_patterns": 3-5 concrete patterns
3. "analysis_plan": Specific steps
4. "expected_evidence": What evidence you expect
5. "rationale": Why these tools/patterns

Output JSON format:
{{"phase": "plan", "data": {{"analysis_plan": "...", "tools_to_use": [...], "search_patterns": [...], "expected_evidence": "...", "rationale": "..."}}, "next_phase_request": "act"}}

{plan_context}
"""

    def _build_act_prompt(self, task_title: str, task_json: str) -> str:
        acceptance_criteria = json.dumps(
            self._original_intent.get("acceptance_criteria", []), indent=2
        )
        return f"""You are an Architecture Subagent executing task: {task_title}

ACT Phase (Iteration {self._iteration_count}): Analyze tool results and generate findings.

IMPORTANT: Tool results have been EXECUTED. Use ACTUAL outputs as evidence.

EVIDENCE REQUIREMENTS:
1. "evidence" field MUST contain concrete evidence with file:line: numbers
2. Each evidence item MUST include: file path, line number(s), and actual content

FINDING REQUIREMENTS:
1. "description": Explain the architecture issue with specific locations
2. "recommendations": Provide SPECIFIC fixes with design pattern examples
3. "severity": "warning" for minor issues, "critical" for severe violations

Output JSON format:
{{"phase": "act", "data": {{"findings": [{{"severity": "warning|critical", "title": "...", "description": "...", "evidence": [...], "recommendations": [...]}}], "evidence_collected": [...], "summary": "...", "gaps_remaining": [...]}}, "next_phase_request": "synthesize"}}

Original acceptance criteria:
{acceptance_criteria}
"""

    def _build_synthesize_prompt(self, task_title: str, task_json: str) -> str:
        original_intent = json.dumps(self._original_intent, indent=2)
        return f"""You are an Architecture Subagent executing task: {task_title}

SYNTHESIZE Phase (Iteration {self._iteration_count}): Evaluate if intent has been satisfied.

CRITICAL CONVERGENCE RULES:
1. BIAS TOWARD DONE: After iteration 1 with ANY findings, prefer "done"
2. DIMINISHING RETURNS: More iterations rarely help for architecture tasks
3. MAX 2 ITERATIONS: For most tasks, 1-2 iterations is sufficient.

When to set goal_achieved: true:
- You have ANY findings related to the task
- Iteration >= 2 AND you have findings

Output JSON format:
{{"phase": "synthesize", "data": {{"criteria_status": [{{"criterion": "...", "status": "met|partially_met|not_met", "evidence": "..."}}], "goal_achieved": true|false, "summary": "...", "remaining_gaps": [...], "recommendation": "done|continue"}}, "next_phase_request": "done|plan"}}

ORIGINAL INTAKE INTENT:
{original_intent}

ACCUMULATED FINDINGS: {len(self._accumulated_findings)}
ITERATION: {self._iteration_count}/{MAX_ITERATIONS}
"""

    def _get_plan_context(self) -> str:
        if self._iteration_count == 1:
            intake = self._phase_outputs.get("intake", {}).get("data", {})
            return f"INTAKE Output:\n{json.dumps(intake, indent=2)}\n\nThis is your first iteration. Plan your initial approach."
        else:
            synthesize = self._phase_outputs.get("synthesize", {}).get("data", {})
            return f"Previous SYNTHESIZE Output:\n{json.dumps(synthesize, indent=2)}\n\nAdjust your approach based on gaps identified."

    def _build_intake_message(self, context: ReviewContext) -> str:
        changed_files = chr(10).join(f"- {f}" for f in context.changed_files[:15])
        task_json = json.dumps(self._task, indent=2)
        return f"## Task Definition\n{task_json}\n\n## Review Context\nRepository: {context.repo_root}\nChanged files: {len(context.changed_files)}\nChanged file paths:\n{changed_files}\n\n## Task\nDefine acceptance criteria and evidence requirements."

    def _build_plan_message(self, context: ReviewContext) -> str:
        changed_files = chr(10).join(f"- {f}" for f in context.changed_files[:20])
        task_json = json.dumps(self._task, indent=2)
        return f"## Task\n{task_json}\n\n## Context\nIteration: {self._iteration_count}/{MAX_ITERATIONS}\n{self._get_plan_context()}\n\n## Changed Files\n{changed_files}\n\n## Plan\nCreate a specific, actionable analysis plan."

    def _build_act_message(self, context: ReviewContext, tool_results: Dict[str, Any]) -> str:
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})
        return f"## Plan\n{json.dumps(plan_output, indent=2)}\n\n## Task\n{json.dumps(self._task, indent=2)}\n\n## ACTUAL TOOL RESULTS\n{json.dumps(tool_results, indent=2)}\n\n## Instructions\nAnalyze the results and generate findings."

    def _build_synthesize_message(self, context: ReviewContext) -> str:
        act_output = self._phase_outputs.get("act", {}).get("data", {})
        findings = act_output.get("findings", [])
        return f"## Original INTAKE Intent\n{json.dumps(self._original_intent, indent=2)}\n\n## Current ACT Phase Findings\n{json.dumps(findings, indent=2)}\n\n## Accumulated Evidence\nTotal findings: {len(self._accumulated_findings)}\nTotal evidence: {len(self._accumulated_evidence)}\n\n## Iteration Status\nCurrent: {self._iteration_count}/{MAX_ITERATIONS}\n\n## Synthesis Task\nCheck criteria and determine if goal achieved."

    async def _execute_llm(self, system_prompt: str, user_message: str) -> str:
        import time
        from iron_rook.review.llm_audit_logger import LLMAuditLogger

        llm_logger = LLMAuditLogger.get()
        phase = self._current_phase or "unknown"
        llm_logger.log_request(
            agent_name=self.get_agent_name(),
            phase=phase,
            system_prompt=system_prompt,
            user_message=user_message,
        )

        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(), allowed_tools=self.get_domain_tools()
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
            logger.info(f"[{self.get_agent_name()}] LLM response: {len(response_text)} chars")
            return response_text
        except Exception as e:
            llm_logger.log_error(agent_name=self.get_agent_name(), phase=phase, error=e)
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
                for key in ["reasoning", "analysis", "rationale"]:
                    if key in response_json["data"]:
                        return str(response_json["data"][key])
            for key in ["reasoning", "analysis", "rationale"]:
                if key in response_json:
                    return str(response_json[key])
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        if "<thinking>" in response_text and "</thinking>" in response_text:
            start = response_text.find("<thinking>") + len("<thinking>")
            end = response_text.find("</thinking>")
            return response_text[start:end].strip()
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
        except json.JSONDecodeError:
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

            json_text = clean_json_string(response_text[start_idx:end_idx])
            try:
                output = json.loads(json_text)
                actual_phase = output.get("phase")
                if actual_phase != expected_phase:
                    logger.warning(
                        f"[{self.get_agent_name()}] Expected phase '{expected_phase}', got '{actual_phase}'"
                    )
                return output
            except json.JSONDecodeError as e2:
                logger.error(f"[{self.get_agent_name()}] Failed to parse JSON: {e2}")
                raise ValueError(f"Failed to parse phase response: {e2}") from e2

    def _build_review_output(self, context: ReviewContext) -> ReviewOutput:
        findings: List[Finding] = []
        seen_titles = set()

        for idx, finding_dict in enumerate(self._accumulated_findings):
            title = finding_dict.get("title", f"Architecture issue {idx}")
            if title in seen_titles:
                continue
            seen_titles.add(title)

            description = finding_dict.get("description", "")
            raw_severity = finding_dict.get("severity", "warning")

            if raw_severity == "critical":
                finding_severity = "critical"
                finding_confidence = "high"
            elif raw_severity == "warning":
                finding_severity = "warning"
                finding_confidence = "medium"
            else:
                finding_severity = "blocking"
                finding_confidence = "low"

            finding = Finding(
                id=f"arch-{self._task.get('todo_id')}-{idx}",
                title=title,
                severity=finding_severity,
                confidence=finding_confidence,
                owner="dev",
                estimate="S",
                evidence=json.dumps(finding_dict.get("evidence", [])),
                risk=description,
                recommendation=finding_dict.get("recommendations", [""])[0]
                if finding_dict.get("recommendations")
                else "",
                suggested_patch=None,
            )
            findings.append(finding)

        todo_id = self._task.get("todo_id", "unknown")
        synthesize_output = self._phase_outputs.get("synthesize", {}).get("data", {})
        summary = synthesize_output.get(
            "summary", f"Architecture task completed in {self._iteration_count} iterations"
        )

        critical_findings = [f for f in findings if f.severity == "critical"]
        warning_findings = [f for f in findings if f.severity == "warning"]

        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Task {todo_id} complete. {self._iteration_count} iterations, {len(findings)} findings. {summary}",
            severity="critical"
            if critical_findings
            else "warning"
            if warning_findings
            else "merge",
            scope=Scope(
                relevant_files=self.get_relevant_file_patterns(),
                ignored_files=[],
                reasoning=f"Architecture subagent for task {todo_id} ({self._iteration_count} iterations)",
            ),
            findings=findings,
            merge_gate=MergeGate(
                decision="needs_changes" if (critical_findings or warning_findings) else "approve",
                must_fix=[f.title for f in critical_findings],
                should_fix=[f.title for f in warning_findings],
                notes_for_coding_agent=[
                    f"Task {todo_id} completed in {self._iteration_count} iterations",
                    f"Total evidence: {len(self._accumulated_evidence)} items",
                    f"Goal achieved: {synthesize_output.get('goal_achieved', False)}",
                ],
            ),
            thinking_log=self._runlog,
        )

    def _build_error_output(self, context: ReviewContext, error_message: str) -> ReviewOutput:
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Architecture task failed at iteration {self._iteration_count}: {error_message}",
            severity="critical",
            scope=Scope(
                relevant_files=[], ignored_files=[], reasoning="Error during architecture analysis"
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[f"Architecture subagent error: {error_message}"],
                should_fix=[],
                notes_for_coding_agent=[f"Failed at iteration {self._iteration_count}"],
            ),
            thinking_log=self._runlog,
        )
