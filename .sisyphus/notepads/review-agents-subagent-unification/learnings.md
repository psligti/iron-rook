
## Task 2: Mock Phase Responses Helper (2026-02-16)

### Implementation
- Created `tests/conftest.py` with:
  - `_PHASE_TEMPLATES`: Dict containing default response structures for all 5 FSM phases
  - `create_mock_response(phase, overrides)`: Helper function that creates JSON responses with optional overrides
  - `mock_phase_responses`: Pytest fixture returning dict of phase → JSON string

### Key Patterns
- Phase structure: `{"phase": "...", "data": {...}, "next_phase_request": "..."}`
- Phases: intake → plan → act → synthesize → check → done
- Overrides support dot notation for nested keys (e.g., `"data.summary"`)

### Usage Examples
```python
# Basic usage
response = create_mock_response("intake")

# With overrides
response = create_mock_response("intake", {"data": {"summary": "Custom"}})

# Nested overrides
response = create_mock_response("check", {"data.findings.high": ["issue1"]})
```

### Notes
- LSP diagnostics clean on new file (pre-existing errors in other test files)
- Docstrings kept for public API (create_mock_response, mock_phase_responses fixture)
# Learnings - Review Agents Subagent Unification

## 2026-02-16

### Task 1: Shared Test Fixtures

**Created:** `tests/conftest.py` (extended existing file)

**Added Fixtures:**
1. `mock_review_context` - Standard ReviewContext with changed_files, diff, repo_root, base_ref, head_ref, pr_title, pr_description
2. `mock_simple_runner` - Fixture factory returning `AsyncMock` with configurable `run_with_retry` response
3. `assert_valid_review_output(output)` - Helper function validating ReviewOutput structure (agent, summary, severity, scope, merge_gate, findings, checks, skips)

**Test Patterns:**
- Pytest fixtures use `@pytest.fixture` decorator
- Factory fixtures return inner function that creates configured mocks
- Validation helpers raise AssertionError with descriptive messages
- Use `isinstance()` checks for type validation in assertion helpers

**Imports Used:**
```python
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput, Scope, MergeGate, Finding, Check, Skip, RunLog
)
from unittest.mock import AsyncMock
```

## Task 4: BaseDynamicSubagent Abstract Class (2026-02-16)

### Implementation
- Created `iron_rook/review/subagents/base_subagent.py` with:
  - `REACT_FSM_TRANSITIONS`: Dict mapping phases to valid next phases
  - `MAX_ITERATIONS = 10`: Prevents infinite loops
  - `STAGNATION_THRESHOLD = 2`: Detects no-progress iterations
  - `BaseDynamicSubagent`: Abstract class inheriting from `BaseReviewerAgent`

### Class Structure
```
BaseDynamicSubagent(BaseReviewerAgent)
├── Abstract Methods (subclasses MUST implement)
│   ├── get_domain_tools() -> List[str]
│   └── get_domain_prompt() -> str
├── Phase Methods (subclasses override)
│   ├── _run_intake_phase(context) -> Dict
│   ├── _run_plan_phase(context) -> Dict
│   ├── _run_act_phase(context) -> Dict
│   └── _run_synthesize_phase(context) -> Dict
├── Output Methods (subclasses override)
│   ├── _build_review_output(context) -> ReviewOutput
│   └── _build_error_output(context, error) -> ReviewOutput
└── FSM Infrastructure
    ├── _run_subagent_fsm(context) -> ReviewOutput
    ├── _transition_to_phase(next_phase) -> None
    ├── _should_stop() -> bool
    └── _check_stagnation() -> bool
```

### FSM Loop Pattern
- Phases: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
- INTAKE runs once at start
- PLAN/ACT/SYNTHESIZE loop until done
- Max iteration check happens BEFORE PLAN phase
- Stagnation check happens in SYNTHESIZE phase

### Stagnation Detection Logic
```python
# Type 1: Zero findings for STAGNATION_THRESHOLD iterations
if all(count == 0 for count in recent):
    return True

# Type 2: After 3+ iterations with any findings (diminishing returns)
if len(_findings_per_iteration) >= 3 and sum(recent) > 0:
    return True
```

### Key Design Decisions
- Distinct from existing `BaseSubagent` (simple single-phase) vs `BaseDynamicSubagent` (multi-phase FSM)
- Phase methods raise `NotImplementedError` by default (not abstract) to allow partial overrides
- Accumulated evidence/findings stored across iterations
- `_original_intent` preserved from INTAKE for goal checking

### Differences from SecuritySubagent
- No security-specific logic (abstracted to `get_domain_tools()` and `get_domain_prompt()`)
- No tool execution methods (subclasses implement `_run_act_phase()`)
- Cleaner separation: base provides FSM loop, subclass provides domain logic


## Task 3: BaseDelegationSkill Abstract Class (2026-02-16)

### Implementation
- Created `iron_rook/review/skills/base_delegation.py`
- `BaseDelegationSkill` inherits from `BaseReviewerAgent`
- Abstract methods: `get_subagent_class()`, `build_subagent_request()`
- Concrete methods: `execute_subagents_concurrently()`, `_aggregate_results()`

### Key Patterns
- Concurrent execution: `asyncio.gather(*tasks, return_exceptions=True)` for parallel subagent execution
- Semaphore-based concurrency limiting (default max 4 concurrent)
- Exception handling: Convert exceptions to error result dicts
- Result structure: `{"todo_id", "title", "subagent_type", "status", "result", "error"}`
- Type narrow with `isinstance(item, Exception)` check after gather

### Type Safety Notes
- `subagent_class(task=request, ...)` uses `type: ignore[call-arg]` because subagent classes have different constructor signatures
- `asyncio.gather` with `return_exceptions=True` returns `Union[Result, BaseException]` - explicit type check required
- `results.append(item)` needs `type: ignore[arg-type]` after type narrowing in else branch

### Aggregation Structure
```python
{
    "total_tasks": int,
    "completed_tasks": int,
    "blocked_tasks": int,
    "total_findings": int,
    "findings_by_severity": Dict[str, int],
    "errors": List[Dict[str, str]],
}
```

### Usage Pattern
```python
class MyDelegationSkill(BaseDelegationSkill):
    def get_subagent_class(self) -> Type[BaseReviewerAgent]:
        return SecuritySubagent

    def build_subagent_request(self, todo: dict, context: ReviewContext) -> dict:
        return {"todo_id": todo["id"], "title": todo["title"], ...}
```


## Task 6: Delegation Skill Template (2026-02-16)

### Implementation
- Created `iron_rook/review/skills/TEMPLATE_SKILL.md`
- Markdown documentation file (not Python code)
- Template uses placeholder variables: `{DOMAIN}`, `{DOMAIN_LOWER}`

### Template Contents
1. **Quick Start** - Minimal class skeleton
2. **Required Methods** - Full signatures and implementations:
   - `__init__()`: Initialize with phase_outputs reference
   - `get_subagent_class()`: Return the subagent class
   - `build_subagent_request()`: Build request dict from todo
   - `get_system_prompt()`: Return delegation instructions
   - `review()`: Main orchestration method
3. **Integration with Parent Reviewer** - Data flow diagram and usage example
4. **Complete Example** - Full "PerformanceDelegationSkill" implementation
5. **Checklist** - Verification list for new delegation skills

### Key Design Patterns Documented
- Parent reviewer passes `phase_outputs["plan"]` to skill constructor
- Skill extracts todos from plan output: `plan_output.get("data", {}).get("todos", [])`
- LLM generates `subagent_requests` array from todos
- `execute_subagents_concurrently()` handles parallel execution
- Result aggregation into `ReviewOutput`

### Template Placeholder Variables
- `{DOMAIN}`: PascalCase domain name (e.g., "Performance", "Security")
- `{DOMAIN_LOWER}`: lowercase domain name (e.g., "performance", "security")

### File Location
- Templates are markdown files in `iron_rook/review/skills/`
- Actual skill implementations are `.py` files in same directory
- Subagent implementations go in `iron_rook/review/subagents/`


## Task 5: Domain Subagent Template (2026-02-16)

### Implementation
- Created `iron_rook/review/subagents/TEMPLATE_SUBAGENT.md`
- Markdown documentation file with code templates and examples
- ~25KB comprehensive template covering all aspects of domain subagent creation

### Template Contents
1. **Overview** - FSM loop structure and key characteristics
2. **FSM Loop Structure** - Phase transitions table
3. **Stop Conditions** - Max iterations, goal met, stagnation, diminishing returns
4. **Required Method Signatures** (10 methods):
   - `__init__()`: Initialize with task dict
   - `get_domain_tools()`: Return list of tool names
   - `get_domain_prompt()`: Return domain-specific instructions
   - `get_system_prompt()`: Return full system prompt
   - `_run_intake_phase()`: Capture intent from task
   - `_run_plan_phase()`: Plan tool usage
   - `_run_act_phase()`: Execute tools, collect evidence
   - `_run_synthesize_phase()`: Analyze and decide next step
   - `_build_review_output()`: Build final ReviewOutput
   - `_build_error_output()`: Build error ReviewOutput
5. **Code Template** - Full Python class with placeholder variables
6. **Example Configuration** - Performance subagent example
7. **Phase Prompt Guidelines** - Key points for each phase prompt
8. **Testing Checklist** - Verification list for new subagents
9. **Common Pitfalls** - Issues to avoid

### Key Design Patterns Documented
- Inheritance from `BaseDynamicSubagent`
- FSM phases: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
- Evidence must include file:line: references
- BIAS TOWARD DONE prevents infinite loops
- Findings deduplicated by title

### Template Placeholder Variables
- `{DOMAIN}`: PascalCase domain name (e.g., "Performance")
- `{DOMAIN_LOWER}`: lowercase domain name (e.g., "performance")
- `{DOMAIN_CLASS}`: Class name suffix (e.g., "Performance")
- `{DOMAIN_UPPER}`: Uppercase for constants (e.g., "PERF")
- `{DOMAIN_SPECIFIC_GUIDANCE}`: Custom domain analysis instructions

### File Location
- Templates are markdown files in `iron_rook/review/subagents/`
- Base class is `base_subagent.py`
- Full implementation reference: `security_subagent_dynamic.py`
