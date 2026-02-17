# Domain Subagent Template

This document provides the pattern for creating new domain-specific subagents that inherit from `BaseDynamicSubagent`.

## Overview

Domain subagents are specialized agents that execute a 5-phase ReAct-style FSM loop:

```
INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
```

Key characteristics:
- **Tool execution**: Subagents use tools directly (grep, ast-grep, linters, etc.)
- **Evidence-based**: Findings must be backed by concrete tool outputs
- **Bounded loops**: Stop conditions prevent infinite iteration
- **Self-contained**: No delegation to other agents

## FSM Loop Structure

| Phase | Purpose | Transition |
|-------|---------|------------|
| `intake` | Capture intent, acceptance criteria, evidence requirements | → `plan` |
| `plan` | Select tools and define search patterns | → `act` |
| `act` | Execute tools, collect evidence, generate findings | → `synthesize` |
| `synthesize` | Analyze results, check against intent, decide next step | → `plan` or `done` |
| `done` | Return `ReviewOutput` with findings | Terminal |

## Stop Conditions

The FSM stops when ANY of these conditions are met:
1. **Max iterations**: `MAX_ITERATIONS = 10` reached
2. **Goal met**: SYNTHESIZE confirms intent satisfied (`goal_achieved: true`)
3. **Stagnation**: No new findings for `STAGNATION_THRESHOLD = 2` consecutive iterations
4. **Diminishing returns**: 3+ iterations with findings (force done)

---

## Required Method Signatures

All domain subagents MUST implement these methods:

### 1. Constructor: `__init__()`

```python
def __init__(
    self,
    task: Dict[str, Any],
    verifier=None,
    max_retries: int = 3,
    agent_runtime=None,
    repo_root: str = "",
) -> None:
    """Initialize the {DOMAIN} subagent.
    
    Args:
        task: Task definition dict with keys:
            - todo_id: Unique task identifier
            - title: Task title/description
            - scope: Scope dict with paths, file patterns
            - acceptance_criteria: List of criteria for task completion
            - evidence_required: List of evidence types needed
        verifier: FindingsVerifier strategy instance
        max_retries: Maximum retry attempts for failed operations
        agent_runtime: Optional AgentRuntime for tool execution
        repo_root: Repository root path
    """
    # Initialize task and state
    self._task = task
    self._current_phase = "intake"
    self._phase_outputs: Dict[str, Any] = {}
    self._thinking_log = RunLog()
    
    # Iteration tracking
    self._iteration_count = 0
    
    # Accumulated results
    self._accumulated_evidence: List[Dict[str, Any]] = []
    self._accumulated_findings: List[Dict[str, Any]] = []
    self._findings_per_iteration: List[int] = []
    
    # Context
    self._original_intent: Dict[str, Any] = {}
    self._context_data: Dict[str, Any] = {}
    self._repo_root = repo_root
```

### 2. `get_domain_tools() -> List[str]`

```python
@abstractmethod
def get_domain_tools(self) -> List[str]:
    """Get list of domain-specific tools this subagent can use.
    
    Returns:
        List of tool names (e.g., ["grep", "bandit", "read"])
    
    Example:
        >>> class {DOMAIN}Subagent(BaseDynamicSubagent):
        ...     def get_domain_tools(self) -> List[str]:
        ...         return ["grep", "rg", "read", "file"]
    """
    pass
```

### 3. `get_domain_prompt() -> str`

```python
@abstractmethod
def get_domain_prompt(self) -> str:
    """Get domain-specific prompt instructions.
    
    Returns:
        Domain-specific prompt section to include in system prompt
    
    Example:
        >>> class {DOMAIN}Subagent(BaseDynamicSubagent):
        ...     def get_domain_prompt(self) -> str:
        ...         return "Focus on finding evidence-based {DOMAIN_LOWER} findings..."
    """
    pass
```

### 4. `get_system_prompt() -> str`

```python
def get_system_prompt(self) -> str:
    """Return full system prompt with domain-specific context.
    
    Should include:
    - Role definition
    - Available tools
    - Task definition
    - Domain-specific guidance
    """
    return f"""You are a {DOMAIN} Subagent.

You execute a single {DOMAIN_LOWER} task assigned by the parent reviewer.

You run a 5-phase ReAct-style FSM: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE).

Available tools:
{self._format_tools()}

Your assigned task:
{json.dumps(self._task, indent=2)}

{self.get_domain_prompt()}
"""
```

### 5. `_run_intake_phase() -> Dict[str, Any]`

```python
async def _run_intake_phase(self, context: ReviewContext) -> Dict[str, Any]:
    """Run INTAKE phase - capture intent and acceptance criteria.
    
    Args:
        context: ReviewContext with repository info
    
    Returns:
        Dict with:
        - phase: "intake"
        - data: {"task_understanding", "acceptance_criteria", "evidence_required", ...}
        - next_phase_request: "plan"
    """
    system_prompt = self._get_phase_prompt("intake", context)
    user_message = self._build_intake_message(context)
    
    response_text = await self._execute_llm(system_prompt, user_message)
    output = self._parse_response(response_text, "intake")
    
    # Store original intent for SYNTHESIZE phase
    self._original_intent = output.get("data", {})
    
    return output
```

### 6. `_run_plan_phase() -> Dict[str, Any]`

```python
async def _run_plan_phase(self, context: ReviewContext) -> Dict[str, Any]:
    """Run PLAN phase - select tools and analysis approach.
    
    Args:
        context: ReviewContext with repository info
    
    Returns:
        Dict with:
        - phase: "plan"
        - data: {"tools_to_use", "search_patterns", "analysis_plan", ...}
        - next_phase_request: "act"
    """
    system_prompt = self._get_phase_prompt("plan", context)
    user_message = self._build_plan_message(context)
    
    response_text = await self._execute_llm(system_prompt, user_message)
    output = self._parse_response(response_text, "plan")
    
    # Store plan for ACT phase
    self._context_data["current_plan"] = output.get("data", {})
    
    return output
```

### 7. `_run_act_phase() -> Dict[str, Any]`

```python
async def _run_act_phase(self, context: ReviewContext) -> Dict[str, Any]:
    """Run ACT phase - execute tools and collect evidence.
    
    Args:
        context: ReviewContext with repository info
    
    Returns:
        Dict with:
        - phase: "act"
        - data: {"findings", "evidence_collected", "tool_results", ...}
        - next_phase_request: "synthesize"
    """
    plan_output = self._phase_outputs.get("plan", {}).get("data", {})
    
    # Execute tools based on plan
    tool_results = await self._execute_tools(plan_output, context)
    
    system_prompt = self._get_phase_prompt("act", context)
    user_message = self._build_act_message(context, tool_results)
    
    response_text = await self._execute_llm(system_prompt, user_message)
    output = self._parse_response(response_text, "act")
    
    # Add tool results to output
    act_data = output.get("data", {})
    act_data["tool_results"] = tool_results
    
    return output
```

### 8. `_run_synthesize_phase() -> Dict[str, Any]`

```python
async def _run_synthesize_phase(self, context: ReviewContext) -> Dict[str, Any]:
    """Run SYNTHESIZE phase - analyze results and decide next step.
    
    Args:
        context: ReviewContext with repository info
    
    Returns:
        Dict with:
        - phase: "synthesize"
        - data: {"criteria_status", "goal_achieved", "summary", ...}
        - next_phase_request: "plan" or "done"
    """
    system_prompt = self._get_phase_prompt("synthesize", context)
    user_message = self._build_synthesize_message(context)
    
    response_text = await self._execute_llm(system_prompt, user_message)
    output = self._parse_response(response_text, "synthesize")
    
    return output
```

### 9. `_build_review_output() -> ReviewOutput`

```python
def _build_review_output(self, context: ReviewContext) -> ReviewOutput:
    """Build final ReviewOutput from accumulated results.
    
    Args:
        context: ReviewContext with repository info
    
    Returns:
        ReviewOutput with findings, severity, and merge decision
    """
    findings: List[Finding] = []
    
    # Deduplicate and convert accumulated findings
    seen_titles = set()
    for idx, finding_dict in enumerate(self._accumulated_findings):
        title = finding_dict.get("title", f"Issue {idx}")
        if title in seen_titles:
            continue
        seen_titles.add(title)
        
        finding = Finding(
            id=f"{DOMAIN_LOWER}-{self._task.get('todo_id')}-{idx}",
            title=title,
            severity=self._classify_severity(finding_dict),
            confidence="medium",
            owner="{DOMAIN_LOWER}",
            estimate="M",
            evidence=json.dumps(finding_dict.get("evidence", [])),
            risk=finding_dict.get("description", ""),
            recommendation=finding_dict.get("recommendations", [""])[0]
                if finding_dict.get("recommendations") else "",
        )
        findings.append(finding)
    
    # Build merge gate
    critical_findings = [f for f in findings if f.severity == "critical"]
    
    return ReviewOutput(
        agent=self.get_agent_name(),
        summary=f"Task completed in {self._iteration_count} iterations, {len(findings)} findings",
        severity="critical" if critical_findings else "merge",
        scope=Scope(
            relevant_files=self.get_relevant_file_patterns(),
            ignored_files=[],
            reasoning=f"{DOMAIN} subagent analysis",
        ),
        findings=findings,
        merge_gate=MergeGate(
            decision="needs_changes" if critical_findings else "approve",
            must_fix=[f.title for f in critical_findings],
            should_fix=[],
            notes_for_coding_agent=[
                f"Completed in {self._iteration_count} iterations",
                f"Total evidence: {len(self._accumulated_evidence)} items",
            ],
        ),
    )
```

### 10. `_build_error_output() -> ReviewOutput`

```python
def _build_error_output(self, context: ReviewContext, error_message: str) -> ReviewOutput:
    """Build ReviewOutput for error case.
    
    Args:
        context: ReviewContext with repository info
        error_message: Error description
    
    Returns:
        ReviewOutput with error information
    """
    return ReviewOutput(
        agent=self.get_agent_name(),
        summary=f"Task failed at iteration {self._iteration_count}: {error_message}",
        severity="critical",
        scope=Scope(
            relevant_files=[],
            ignored_files=[],
            reasoning=f"Error during {DOMAIN} analysis",
        ),
        findings=[],
        merge_gate=MergeGate(
            decision="needs_changes",
            must_fix=[f"Subagent error: {error_message}"],
            should_fix=[],
            notes_for_coding_agent=[f"Failed at iteration {self._iteration_count}"],
        ),
    )
```

---

## Code Template

Copy and customize this template for new domain subagents:

```python
"""Dynamic {DOMAIN} subagent that executes individual {DOMAIN_LOWER} tasks.

This module provides {DOMAIN_CLASS}Subagent, a lightweight FSM-based agent that:
- Receives a specific {DOMAIN_LOWER} task from the parent reviewer
- Runs a 5-phase ReAct-style FSM: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
- Uses tools directly (grep, linters, analyzers, etc.)
- Returns findings without delegating to other agents
"""

from __future__ import annotations

from typing import Dict, Any, List
import logging
import json
import subprocess
import os

from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    Finding,
    Scope,
    MergeGate,
    RunLog,
)
from iron_rook.review.subagents.base_subagent import BaseDynamicSubagent
from dawn_kestrel.core.harness import SimpleReviewAgentRunner

logger = logging.getLogger(__name__)


class {DOMAIN_CLASS}Subagent(BaseDynamicSubagent):
    """ReAct-style {DOMAIN_LOWER} subagent that executes a single task.
    
    Runs a 5-phase FSM with looping:
    - INTAKE: Capture intent, acceptance criteria, evidence requirements
    - PLAN: Select tools based on SYNTHESIZE output (or INTAKE first iteration)
    - ACT: Execute tools and collect evidence
    - SYNTHESIZE: Analyze results, check against original intent, decide next step
    - DONE: Return findings with evidence
    
    Task definition format:
    {{
        "todo_id": "{DOMAIN_UPPER}-001",
        "title": "Check for {DOMAIN_LOWER} issues",
        "scope": {{...}},
        "acceptance_criteria": [...],
        "evidence_required": [...]
    }}
    """
    
    def __init__(
        self,
        task: Dict[str, Any],
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        repo_root: str = "",
    ):
        """Initialize the {DOMAIN} subagent."""
        super().__init__(
            task=task,
            verifier=verifier,
            max_retries=max_retries,
            agent_runtime=agent_runtime,
            repo_root=repo_root,
        )
        # Add domain-specific state here
        # self._{DOMAIN_LOWER}_context = ""
    
    def get_agent_name(self) -> str:
        """Get agent identifier based on task ID."""
        return f"{DOMAIN_LOWER}_subagent_{{self._task.get('todo_id', 'unknown')}}"
    
    def get_domain_tools(self) -> List[str]:
        """Get list of tools this subagent can use."""
        return [
            # Add domain-specific tools here
            "grep",
            "rg",
            "read",
            # "ast-grep",
            # "custom-linter",
        ]
    
    def get_domain_prompt(self) -> str:
        """Get domain-specific prompt instructions."""
        return """Focus on finding evidence-based {DOMAIN_LOWER} findings.

{DOMAIN_SPECIFIC_GUIDANCE}

Use tools to verify your analysis. Every finding must include:
1. Specific file:line: references
2. Actual code snippets from tool outputs
3. Clear recommendation with code examples
"""
    
    def get_system_prompt(self) -> str:
        """Return full system prompt."""
        return f"""You are a {DOMAIN} Subagent.

You execute a single {DOMAIN_LOWER} task assigned by the parent reviewer.

You run a 5-phase ReAct-style FSM: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE).

Available tools:
{self._format_tools_list()}

Your assigned task:
{{json.dumps(self._task, indent=2)}}

{{self.get_domain_prompt()}}
"""
    
    def _format_tools_list(self) -> str:
        """Format available tools for system prompt."""
        tools = self.get_domain_tools()
        return "\n".join(f"- {{t}}" for t in tools)
    
    # ========================================================================
    # Phase Implementation
    # ========================================================================
    
    async def _run_intake_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run INTAKE phase."""
        # TODO: Implement domain-specific intake logic
        raise NotImplementedError("Subclasses must implement _run_intake_phase")
    
    async def _run_plan_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run PLAN phase."""
        # TODO: Implement domain-specific plan logic
        raise NotImplementedError("Subclasses must implement _run_plan_phase")
    
    async def _run_act_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run ACT phase."""
        # TODO: Implement domain-specific act logic
        raise NotImplementedError("Subclasses must implement _run_act_phase")
    
    async def _run_synthesize_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run SYNTHESIZE phase."""
        # TODO: Implement domain-specific synthesize logic
        raise NotImplementedError("Subclasses must implement _run_synthesize_phase")
    
    # ========================================================================
    # Tool Execution
    # ========================================================================
    
    async def _execute_tools(
        self, plan_output: Dict[str, Any], context: ReviewContext
    ) -> Dict[str, Any]:
        """Execute tools based on plan output."""
        tools_to_use = plan_output.get("tools_to_use", [])
        search_patterns = plan_output.get("search_patterns", [])
        results = {{}}
        repo_root = self._context_data.get("repo_root", context.repo_root)
        
        for tool in tools_to_use:
            try:
                if tool in ("grep", "rg"):
                    results[tool] = await self._execute_grep(search_patterns, repo_root)
                elif tool == "read":
                    results["read"] = await self._execute_read(context)
                # Add domain-specific tool execution here
                else:
                    results[tool] = {{
                        "status": "skipped",
                        "reason": f"Tool 'tool' not implemented",
                    }}
            except Exception as e:
                results[tool] = {{"status": "error", "error": str(e)}}
                logger.warning(f"[{{self.get_agent_name()}}] Tool {{tool}} failed: {{e}}")
        
        return results
    
    async def _execute_grep(self, patterns: List[str], repo_root: str) -> Dict[str, Any]:
        """Execute grep/rg search."""
        results = {{}}
        
        for pattern in patterns[:5]:  # Limit to 5 patterns
            try:
                cmd = ["rg", "-n", "--max-count=50", pattern, repo_root]
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
                results[pattern] = f"(error: {{e}})"
        
        return {{"tool": "rg", "results": results}}
    
    async def _execute_read(self, context: ReviewContext) -> Dict[str, Any]:
        """Read file contents."""
        results = {{}}
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
                results[file_path] = f"(error: {{e}})"
        
        return {{"tool": "read", "results": results}}
    
    # ========================================================================
    # Output Building
    # ========================================================================
    
    def _build_review_output(self, context: ReviewContext) -> ReviewOutput:
        """Build final ReviewOutput."""
        # TODO: Implement domain-specific output building
        raise NotImplementedError("Subclasses must implement _build_review_output")
    
    def _build_error_output(self, context: ReviewContext, error_message: str) -> ReviewOutput:
        """Build error ReviewOutput."""
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Task failed at iteration {{self._iteration_count}}: {{error_message}}",
            severity="critical",
            scope=Scope(
                relevant_files=[],
                ignored_files=[],
                reasoning=f"Error during {DOMAIN_LOWER} analysis",
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[f"Subagent error: {{error_message}}"],
                should_fix=[],
                notes_for_coding_agent=[f"Failed at iteration {{self._iteration_count}}"],
            ),
        )
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    async def _execute_llm(self, system_prompt: str, user_message: str) -> str:
        """Execute LLM call with logging."""
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_domain_tools(),
        )
        
        response_text = await runner.run_with_retry(system_prompt, user_message)
        logger.info(f"[{{self.get_agent_name()}}] LLM response: {{len(response_text)}} chars")
        return response_text
    
    def _parse_response(self, response_text: str, expected_phase: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        # Handle markdown code blocks
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
                f"[{{self.get_agent_name()}}] Expected phase 'expected_phase', got 'actual_phase'"
            )
        
        return output
```

---

## Example Configuration: Performance Subagent

Here's an example configuration for a hypothetical Performance subagent:

```python
# performance_subagent.py

class PerformanceSubagent(BaseDynamicSubagent):
    """Performance analysis subagent."""
    
    def get_domain_tools(self) -> List[str]:
        return [
            "grep",      # Search for patterns
            "rg",        # Fast grep
            "read",      # Read files
            "python",    # Run Python profiling
            # Domain-specific tools
            "py-spy",    # Python profiler
            "memory_profiler",  # Memory analysis
        ]
    
    def get_domain_prompt(self) -> str:
        return """Focus on finding evidence-based performance findings.

Key areas to check:
1. N+1 query patterns (ORM usage in loops)
2. Memory leaks (caches without bounds)
3. Inefficient algorithms (O(n²) in hot paths)
4. Blocking I/O in async code
5. Unnecessary object allocations

Use tools to verify your analysis. Every finding must include:
1. Specific file:line: references
2. Actual code snippets showing the issue
3. Performance impact estimate (time/space complexity)
4. Clear recommendation with code examples
"""

    def _get_default_patterns(self) -> List[str]:
        """Default search patterns for performance issues."""
        return [
            # ORM in loops
            "for.*in.*query",
            "for.*in.*objects.all",
            "for.*in.*filter",
            # Blocking calls
            "time.sleep",
            "requests.get",
            "requests.post",
            # Unbounded caches
            "cache = {}",
            "_cache = {}",
            "lru_cache",
        ]
```

---

## Phase Prompt Guidelines

Each phase needs a specific prompt that tells the LLM:
1. What to do in this phase
2. What JSON format to return
3. What evidence is required

### INTAKE Prompt Key Points
- Define clear, verifiable acceptance criteria
- Specify 3-5 specific evidence types needed
- Avoid vague criteria like "check for issues"

### PLAN Prompt Key Points
- Select 2-4 specific tools
- Define 3-5 concrete search patterns
- Be specific about expected evidence

### ACT Prompt Key Points
- Emphasize using ACTUAL tool outputs
- Require file:line: references in evidence
- Require code snippets, not paraphrased descriptions

### SYNTHESIZE Prompt Key Points
- BIAS TOWARD DONE (prevent infinite loops)
- Check each acceptance criterion against evidence
- Set `goal_achieved: true` if ANY findings exist after iteration 1

---

## Testing Checklist

When creating a new domain subagent, verify:

- [ ] Inherits from `BaseDynamicSubagent`
- [ ] Implements all required methods
- [ ] `get_domain_tools()` returns valid tool names
- [ ] `get_domain_prompt()` provides domain-specific guidance
- [ ] Phase methods return correct JSON format with `next_phase_request`
- [ ] `_build_review_output()` creates valid `ReviewOutput`
- [ ] `_build_error_output()` handles failure cases
- [ ] Stagnation detection works (no infinite loops)
- [ ] Evidence includes file:line: references
- [ ] Findings are deduplicated by title

---

## Common Pitfalls

1. **Vague acceptance criteria**: "Check for issues" → Use specific, verifiable criteria
2. **Missing evidence**: "Code may have issues" → Require file:line: code snippets
3. **Infinite loops**: No convergence rules → Add BIAS TOWARD DONE
4. **Tool speculation**: "I would use grep" → Actually execute tools and use real output
5. **Missing phase output**: Forgetting `next_phase_request` → Always include in response
