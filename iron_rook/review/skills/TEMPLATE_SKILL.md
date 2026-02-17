# Delegation Skill Template

This document provides a template and guide for creating new delegation skills that dispatch work to subagents.

## Overview

Delegation skills inherit from `BaseDelegationSkill` and orchestrate parallel execution of specialized subagents. They are used by parent reviewers during the ACT phase to delegate specific analysis tasks.

## Quick Start

```python
# iron_rook/review/skills/{DOMAIN_LOWER}_delegation.py

from typing import Any, Dict, List, Type
from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import ReviewOutput
from iron_rook.review.skills.base_delegation import BaseDelegationSkill
from iron_rook.review.subagents.{DOMAIN_LOWER}_subagent import {DOMAIN}Subagent


class {DOMAIN}DelegationSkill(BaseDelegationSkill):
    """Skill for delegating {DOMAIN_LOWER} analysis to specialized subagents."""
    
    def __init__(
        self,
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        phase_outputs: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            verifier=verifier,
            max_retries=max_retries,
            agent_runtime=agent_runtime,
        )
        self._phase_outputs = phase_outputs or {}
    
    # ... implement required methods
```

## Required Methods

### 1. `__init__()`

Initialize the skill with references to phase outputs from the parent reviewer.

```python
def __init__(
    self,
    verifier=None,
    max_retries: int = 3,
    agent_runtime=None,
    phase_outputs: Dict[str, Any] | None = None,
) -> None:
    """Initialize {DOMAIN}DelegationSkill.
    
    Args:
        verifier: Optional findings verifier
        max_retries: Maximum retry attempts for subagent execution
        agent_runtime: Optional agent runtime for execution
        phase_outputs: Dictionary of outputs from previous phases
    """
    super().__init__(
        verifier=verifier,
        max_retries=max_retries,
        agent_runtime=agent_runtime,
    )
    self._phase_outputs = phase_outputs or {}
```

### 2. `get_subagent_class()`

Return the subagent class that will be instantiated for each delegated task.

```python
@abstractmethod
def get_subagent_class(self) -> Type[BaseReviewerAgent]:
    """Return the subagent class to instantiate for each request.
    
    Returns:
        The subagent class (must inherit from BaseReviewerAgent)
    
    Example:
        def get_subagent_class(self) -> Type[BaseReviewerAgent]:
            return {DOMAIN}Subagent
    """
    return {DOMAIN}Subagent
```

### 3. `build_subagent_request()`

Build a request dictionary for each subagent based on the todo item.

```python
@abstractmethod
def build_subagent_request(
    self, todo: Dict[str, Any], context: ReviewContext
) -> Dict[str, Any]:
    """Build a request dict for a subagent.
    
    Args:
        todo: Todo item to delegate (contains id, title, scope, etc.)
        context: ReviewContext with changed files and metadata
    
    Returns:
        Request dict that will be passed to subagent constructor
    
    Example:
        def build_subagent_request(self, todo, context) -> dict:
            return {
                "todo_id": todo["id"],
                "title": todo["title"],
                "scope": {"paths": context.changed_files},
                "risk_category": todo.get("category", "general"),
                "acceptance_criteria": todo.get("criteria", []),
            }
    """
    return {
        "todo_id": todo.get("id"),
        "title": todo.get("title"),
        "scope": todo.get("scope", {"paths": context.changed_files}),
        "risk_category": todo.get("category", "general"),
        "acceptance_criteria": todo.get("criteria", []),
    }
```

### 4. `get_system_prompt()`

Return the system prompt that instructs the LLM on delegation responsibilities.

```python
def get_system_prompt(self) -> str:
    """Return system prompt for this skill.
    
    Returns system prompt instructing LLM on delegation responsibilities.
    """
    return """You are {DOMAIN} Delegation Skill.

You are in DELEGATE phase of {DOMAIN_LOWER} review FSM.

Output JSON format:
{
  "phase": "delegate",
  "data": {
    "subagent_requests": [
      {
        "todo_id": "1",
        "title": "Check {DOMAIN_LOWER} concern",
        "scope": {"paths": ["src/module/file.py"]},
        "risk_category": "category_name",
        "tools_to_use": ["grep", "read"],
        "acceptance_criteria": ["Criterion 1", "Criterion 2"]
      }
    ],
    "thinking": "Reasoning about delegation decisions"
  },
  "next_phase_request": "collect"
}

Your agent name is "{DOMAIN_LOWER}_delegation".

DELEGATE Phase:
Task:
1. For EVERY TODO, produce a subagent request object.
2. Each subagent will use tools to collect evidence.
3. You MUST populate "subagent_requests" array with one entry per TODO.
4. ALL analysis must be delegated to subagents.
"""
```

### 5. `review()`

Main orchestration method that:
1. Extracts todos from PLAN phase output
2. Builds delegation prompt
3. Executes LLM to generate subagent requests
4. Dispatches subagents concurrently
5. Collects and returns results

```python
async def review(self, context: ReviewContext) -> ReviewOutput:
    """Perform delegation review on given context.
    
    Args:
        context: ReviewContext containing changed files, diff, and metadata
    
    Returns:
        ReviewOutput with subagent_results
    """
    from dawn_kestrel.core.harness import SimpleReviewAgentRunner
    
    # Extract todos from plan phase
    plan_output = self._phase_outputs.get("plan", {}).get("data", {})
    todos = plan_output.get("todos", [])
    
    if not todos:
        return self._build_empty_review_output(context)
    
    # Build prompts
    system_prompt = self.get_system_prompt()
    user_message = self._build_delegate_message(context)
    
    # Execute LLM call
    runner = SimpleReviewAgentRunner(
        agent_name=self.get_agent_name(),
        allowed_tools=self.get_allowed_tools(),
    )
    
    response_text = await runner.run_with_retry(system_prompt, user_message)
    output = self._parse_response(response_text)
    
    # Build subagent requests
    subagent_requests = output.get("data", {}).get("subagent_requests", [])
    
    # Execute subagents concurrently using base class method
    results = await self.execute_subagents_concurrently(
        subagent_requests, context, max_concurrency=4
    )
    
    # Build and return ReviewOutput
    return self._build_review_output(context, results)
```

## Integration with Parent Reviewer

### How Parent Reviewer Calls the Skill

The parent reviewer (e.g., `SecurityReviewer`) calls the skill during the ACT phase:

```python
# In parent reviewer's _execute_act_phase():

# 1. Create skill instance with phase outputs
skill = {DOMAIN}DelegationSkill(
    phase_outputs={
        "plan": plan_phase_output,  # Contains todos
    },
    max_retries=3,
)

# 2. Execute skill
skill_output = await skill.review(context)

# 3. Extract results for next phase
subagent_results = skill_output.findings  # or custom extraction
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Parent Reviewer                          │
├─────────────────────────────────────────────────────────────┤
│  PLAN Phase                                                 │
│  ├── Generate todos based on intake analysis                │
│  └── Output: {todos: [...], next_phase: "delegate"}         │
│                                                             │
│  ACT Phase (Delegation)                                     │
│  ├── Create DelegationSkill with phase_outputs["plan"]      │
│  ├── skill.review(context)                                  │
│  │   ├── Extract todos from plan output                     │
│  │   ├── LLM generates subagent_requests                    │
│  │   ├── execute_subagents_concurrently()                   │
│  │   └── Return ReviewOutput with findings                  │
│  └── Collect skill_output.findings                          │
│                                                             │
│  SYNTHESIZE Phase                                           │
│  └── Aggregate findings from all subagents                  │
└─────────────────────────────────────────────────────────────┘
```

## Example Configuration

Here's a complete example for a hypothetical "Performance" delegation skill:

```python
# iron_rook/review/skills/performance_delegation.py

import asyncio
import json
import logging
from typing import Any, Dict, List, Type

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    Check,
    Finding,
    MergeGate,
    ReviewOutput,
    Scope,
    Skip,
)
from iron_rook.review.skills.base_delegation import BaseDelegationSkill
from iron_rook.review.subagents.performance_subagent import PerformanceSubagent

logger = logging.getLogger(__name__)


class PerformanceDelegationSkill(BaseDelegationSkill):
    """Skill for delegating performance analysis to specialized subagents."""
    
    def __init__(
        self,
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        phase_outputs: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            verifier=verifier,
            max_retries=max_retries,
            agent_runtime=agent_runtime,
        )
        self._phase_outputs = phase_outputs or {}
    
    def get_agent_name(self) -> str:
        return "performance_delegation"
    
    def get_subagent_class(self) -> Type[BaseReviewerAgent]:
        return PerformanceSubagent
    
    def build_subagent_request(
        self, todo: Dict[str, Any], context: ReviewContext
    ) -> Dict[str, Any]:
        return {
            "todo_id": todo.get("id"),
            "title": todo.get("title"),
            "scope": todo.get("scope", {"paths": context.changed_files}),
            "performance_category": todo.get("category", "general"),
            "acceptance_criteria": todo.get("criteria", []),
        }
    
    def get_allowed_tools(self) -> List[str]:
        return ["read", "grep", "file"]
    
    def get_relevant_file_patterns(self) -> List[str]:
        return []
    
    def get_system_prompt(self) -> str:
        return """You are Performance Delegation Skill.

You are in DELEGATE phase of performance review FSM.

Output JSON format:
{
  "phase": "delegate",
  "data": {
    "subagent_requests": [
      {
        "todo_id": "1",
        "title": "Check N+1 query patterns",
        "scope": {"paths": ["src/api/handlers.py"]},
        "performance_category": "database",
        "tools_to_use": ["grep", "read"],
        "acceptance_criteria": ["Find all database queries in loops"]
      }
    ],
    "thinking": "Reasoning about delegation decisions"
  },
  "next_phase_request": "collect"
}
"""
    
    async def review(self, context: ReviewContext) -> ReviewOutput:
        from dawn_kestrel.core.harness import SimpleReviewAgentRunner
        
        logger.info(f"[{self.__class__.__name__}] Starting DELEGATE phase")
        
        # Extract todos from plan phase
        plan_output = self._phase_outputs.get("plan", {}).get("data", {})
        todos = plan_output.get("todos", [])
        
        if not todos:
            return self._build_empty_review_output(context)
        
        # Build prompts and execute LLM
        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )
        
        system_prompt = self.get_system_prompt()
        user_message = self._build_delegate_message(context)
        
        response_text = await runner.run_with_retry(system_prompt, user_message)
        output = self._parse_response(response_text)
        
        # Execute subagents concurrently
        requests = output.get("data", {}).get("subagent_requests", [])
        results = await self.execute_subagents_concurrently(requests, context)
        
        return self._build_review_output(context, results)
    
    def _build_delegate_message(self, context: ReviewContext) -> str:
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
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        # Strip markdown code blocks if present
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        return json.loads(response_text)
    
    def _build_review_output(
        self, context: ReviewContext, subagent_results: List[Dict[str, Any]]
    ) -> ReviewOutput:
        findings: List[Finding] = []
        
        for result in subagent_results:
            if result.get("status") != "done":
                continue
            
            result_data = result.get("result", {})
            if not result_data:
                continue
            
            for finding_dict in result_data.get("findings", []):
                findings.append(
                    Finding(
                        id=f"perf-{len(findings)}-{finding_dict.get('title', 'unknown')[:20]}",
                        title=finding_dict.get("title", "Untitled"),
                        severity=finding_dict.get("severity", "warning"),
                        confidence="medium",
                        owner="performance",
                        estimate="M",
                        evidence=str(finding_dict.get("evidence", "")),
                        risk=finding_dict.get("risk", "Performance issue"),
                        recommendation=finding_dict.get("recommendation", "Review and optimize"),
                    )
                )
        
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary=f"Delegated {len(subagent_results)} tasks, found {len(findings)} issues",
            severity="critical" if any(f.severity == "critical" for f in findings) else "merge",
            scope=Scope(
                relevant_files=context.changed_files,
                reasoning="Delegated to performance subagents",
            ),
            findings=findings,
            merge_gate=MergeGate(
                decision="block" if any(f.severity == "critical" for f in findings) else "approve",
                must_fix=[f.title for f in findings if f.severity == "critical"],
                should_fix=[f.title for f in findings if f.severity == "warning"],
                notes_for_coding_agent=[f"Review {len(findings)} performance findings"],
            ),
        )
    
    def _build_empty_review_output(self, context: ReviewContext) -> ReviewOutput:
        return ReviewOutput(
            agent=self.get_agent_name(),
            summary="No todos to delegate",
            severity="merge",
            scope=Scope(
                relevant_files=[],
                reasoning="Empty plan output",
            ),
            findings=[],
            merge_gate=MergeGate(
                decision="approve",
                must_fix=[],
                should_fix=[],
                notes_for_coding_agent=[],
            ),
        )
```

## Checklist for New Delegation Skills

- [ ] Create file: `iron_rook/review/skills/{domain}_delegation.py`
- [ ] Inherit from `BaseDelegationSkill`
- [ ] Implement `__init__()` with `phase_outputs` parameter
- [ ] Implement `get_subagent_class()` returning your subagent class
- [ ] Implement `build_subagent_request()` for todo → request mapping
- [ ] Implement `get_agent_name()` returning unique identifier
- [ ] Implement `get_system_prompt()` with domain-specific delegation instructions
- [ ] Implement `get_allowed_tools()` (typically `["read", "grep", "file"]`)
- [ ] Implement `get_relevant_file_patterns()` (typically `[]` for delegation skills)
- [ ] Implement `review()` using `execute_subagents_concurrently()`
- [ ] Create corresponding subagent in `iron_rook/review/subagents/{domain}_subagent.py`
- [ ] Add tests in `tests/review/skills/test_{domain}_delegation.py`
