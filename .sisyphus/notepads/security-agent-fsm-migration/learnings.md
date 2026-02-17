# Learnings - Security Agent FSM Migration

## 2026-02-16 Session Start

### FSM Architecture Analysis

**Current iron_rook FSM** (`iron_rook/fsm/`):
- `LoopState` enum: INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED
- `LoopFSM` class with `transition_to()`, `run_loop()`, `run_loop_async()`
- Default transitions: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)

**Security Agent Custom FSM** (`iron_rook/review/agents/security.py`):
- Custom phases: `intake`, `plan_todos`, `act`, `collect`, `consolidate`, `evaluate`, `done`
- Defined in `SECURITY_FSM_TRANSITIONS` (lines 34-41)
- Has its own `_run_review_fsm()` loop that doesn't use `LoopFSM.run_loop()` directly
- 4 early-exit paths from `act`: `collect`, `consolidate`, `evaluate`, `done`

**Target dawn_kestrel FSM** (`dawn_kestrel/core/fsm.py`):
- `FSMBuilder` class with fluent API
- `FSMImpl` class implementing FSM protocol
- Generic state machine with configurable states/transitions
- Hooks: `with_entry_hook()`, `with_exit_hook()`

**Target dawn_kestrel workflow FSM** (`dawn_kestrel/workflow/fsm.py`):
- States: `intake`, `plan`, `act`, `synthesize`, `evaluate`, `done`, `failed`
- Transitions: `WORKFLOW_FSM_TRANSITIONS`
- `run_workflow_fsm()` function for complete execution

### Phase Mapping (7 → 6 states)
| Security Phase | Workflow State |
|----------------|----------------|
| `intake` | `intake` |
| `plan_todos` | `plan` |
| `act` | `act` |
| `collect` | `synthesize` (merged) |
| `consolidate` | `synthesize` (merged) |
| `evaluate` | `evaluate` |
| `done` | `done` |

### Key Insight: Security Agent Already Bypasses LoopFSM
The SecurityReviewer doesn't actually use `LoopFSM.run_loop()` - it has its own `_run_review_fsm()` method that:
- Creates `self._fsm = LoopFSM(...)` only for state tracking
- Manually runs phase methods in a `while` loop
- Has its own `SECURITY_FSM_TRANSITIONS` validation

This means the migration is about:
1. Creating an adapter that wraps dawn_kestrel's FSMBuilder
2. Updating the `_run_review_fsm()` loop to use the new adapter
3. Not about replacing `LoopFSM.run_loop()` usage

---

## 2026-02-15 Task 4: BaseReviewerAgent FSM-Agnostic Migration

### File: `iron_rook/review/base.py`

**Goal:** Make `BaseReviewerAgent` FSM-agnostic by removing `LoopFSM` dependency, allowing subclasses to use their own state management (e.g., `WorkflowFSMAdapter`).

### Changes Made:

**1. Removed Imports:**
```python
# REMOVED:
from iron_rook.fsm.loop_fsm import LoopFSM
from iron_rook.fsm.loop_state import LoopState

# KEPT (needed for type hints):
from iron_rook.fsm.state import AgentState
```

**2. Removed Helper Functions:**
- Removed `_map_loop_state_to_agent_state()` - no longer needed
- Removed `_map_agent_state_to_loop_state()` - no longer needed

**3. Updated `__init__`:**
```python
# Before:
self._fsm = LoopFSM(max_retries=max_retries, agent_runtime=agent_runtime)

# After:
self._fsm: object | None = None  # Optional - subclasses manage their own FSM
```

**4. Updated `state` Property:**
```python
# Before: Mapped from LoopFSM.current_state
# After: Returns AgentState.IDLE by default, subclasses can override
@property
def state(self) -> AgentState:
    return AgentState.IDLE
```

**5. Updated `get_valid_transitions()`:**
```python
# Before: Fell back to FSM_TRANSITIONS from loop_fsm
# After: Returns empty dict when no class-level FSM_TRANSITIONS defined
def get_valid_transitions(self) -> dict[AgentState, set[AgentState]]:
    if hasattr(self.__class__, "FSM_TRANSITIONS"):
        return cast(dict[AgentState, set[AgentState]], self.__class__.FSM_TRANSITIONS)
    return {}  # No transitions by default
```

**6. Updated `_transition_to()` - Now a No-Op:**
```python
# Before: Mapped AgentState to LoopState and called fsm.transition_to()
# After: Logs debug message, subclasses with FSM should override
def _transition_to(self, new_state: AgentState) -> None:
    logger.debug(f"[{self.__class__.__name__}] _transition_to({new_state}) - no FSM configured")
```

**7. Removed FSM Calls in `_execute_review_with_runner()`:**
- Removed `self._fsm.reset()` call
- Removed `self._transition_to(AgentState.INITIALIZING)` call
- Removed `self._transition_to(AgentState.RUNNING)` call
- Removed `self._transition_to(AgentState.COMPLETED)` calls (3 places)

### Key Design Decisions:

1. **Backward compatibility**: The public interface remains unchanged - other reviewers (architecture, docs, etc.) continue to work without modification

2. **Optional FSM pattern**: `_fsm` is `None` by default, subclasses that need state management should create their own adapter

3. **No-op transitions**: `_transition_to()` doesn't raise an error, just logs - this allows existing code to call it without breaking

4. **AgentState kept for type hints**: The `AgentState` enum is still used in type hints for the public interface

### Verification:
```bash
# Verify no LoopFSM/LoopState references
grep -E "LoopFSM|LoopState" iron_rook/review/base.py
# Output: (empty - no matches)

# Verify only AgentState import remains
grep "from iron_rook.fsm" iron_rook/review/base.py
# Output: from iron_rook.fsm.state import AgentState

# Verify module imports correctly
.venv/bin/python3 -c "from iron_rook.review.base import BaseReviewerAgent, ReviewContext; print('PASS')"
# Output: PASS

# Verify other reviewers still work
.venv/bin/python3 -c "from iron_rook.review.agents.architecture import ArchitectureReviewer; from iron_rook.review.agents.documentation import DocumentationReviewer; print('PASS')"
# Output: PASS
```

---

### Created File: `iron_rook/review/workflow_adapter.py`

**Components:**
1. `SECURITY_TO_WORKFLOW_PHASE` - Dict mapping 7 security phases → 6 workflow states
2. `WORKFLOW_TO_SECURITY_PHASE` - Reverse mapping
3. `SECURITY_FSM_TRANSITIONS` - Original security phase transitions
4. `WORKFLOW_FSM_TRANSITIONS` - Mapped workflow transitions (3 paths from act: synthesize/evaluate/done)
5. `PhaseHandler` - Dataclass for phase name, handler callable, timeout
6. `WorkflowResult` - Dataclass for final_state, phase_outputs, success, error
7. `WorkflowFSMAdapter` - Main adapter class

**WorkflowFSMAdapter API:**
```python
adapter = WorkflowFSMAdapter(initial_phase="intake", phase_timeout_seconds=30)
adapter.register_phase_handler("intake", handle_intake, timeout=30)
adapter.register_phase_handler("plan", handle_plan)

# Build FSM
result = adapter.build()  # Returns Result[FSM]

# Run workflow
workflow_result = await adapter.run_workflow(context, phase_handlers_dict)
```

**Key Design Decisions:**
1. `run_workflow()` manages its own phase loop (not delegating to FSM hooks) to properly accumulate `_phase_outputs`
2. Phase handlers receive `(context, phase_outputs)` and return dict with `next_phase_request`
3. Timeout handled per-phase via `asyncio.wait_for()`
4. Early-exit from `act` phase preserved (3 workflow paths: synthesize, evaluate, done)
5. FSM entry hooks are set but actual execution in `run_workflow()` for output accumulation control

**Transition Mapping Applied:**
```
Security: act → [collect, consolidate, evaluate, done]
Workflow: act → [synthesize, evaluate, done]  # collect/consolidate merged to synthesize
```

**Verification:**
```bash
.venv/bin/python3 -c "from iron_rook.review.workflow_adapter import WorkflowFSMAdapter; adapter = WorkflowFSMAdapter(); print('PASS')"
# Output: PASS
```

---

## 2026-02-15 Task 2: SecurityReviewer Migration to WorkflowFSMAdapter

### Changes Made to `iron_rook/review/agents/security.py`

**1. Import Changes:**
- Removed: `from iron_rook.fsm.loop_state import LoopState`
- Removed: `from iron_rook.fsm.loop_fsm import LoopFSM`
- Added: `from iron_rook.review.workflow_adapter import WorkflowFSMAdapter`

**2. `__init__` Changes:**
- Replaced `self._fsm = LoopFSM(...)` with `self._adapter = WorkflowFSMAdapter(initial_phase="intake", phase_timeout_seconds=phase_timeout_seconds)`
- Removed `self._phase_to_loop_state` mapping (no longer needed)
- Added `self._max_retries` attribute (was accessed via `self._fsm.max_retries`)

**3. Removed Constants:**
- Removed module-level `SECURITY_FSM_TRANSITIONS` constant (adapter provides it)

**4. `_run_review_fsm()` Rewrite:**
- Now uses `self._adapter.run_workflow()` instead of manual while loop
- Creates wrapper handlers that sync `self._phase_outputs` with adapter's passed outputs
- Maps workflow state names to phase handlers:
  - `intake` → `handle_intake`
  - `plan` → `handle_plan` (calls `_run_plan_todos`)
  - `act` → `handle_act`
  - `synthesize` → `handle_synthesize` (routes to `_run_collect` or `_run_consolidate`)
  - `evaluate` → `handle_evaluate`
- Uses `WorkflowResult` for error handling

**5. `_transition_to_phase()` Update:**
- Uses `self._adapter.get_valid_transitions()` instead of removed constant

**6. Added Alias:**
- `_run_plan = _run_plan_todos` for compatibility with workflow state naming

**7. Fixed DelegateTodoSkill:**
- Changed `self._fsm.max_retries` → `self._max_retries`

### Key Insights from Migration

1. **Phase outputs sync pattern**: Handler wrappers sync `self._phase_outputs = phase_outputs` before calling existing methods so they can read from the expected location

2. **synthesize handler logic**: Routes to either `_run_collect` or `_run_consolidate` based on what's in phase_outputs (keeps existing methods for Task 3 to merge)

3. **Error handling**: `Result` type from dawn_kestrel uses `is_err()` check and `str(result)` for error message extraction

### Verification:
```bash
.venv/bin/python3 -c "from iron_rook.review.agents.security import SecurityReviewer; reviewer = SecurityReviewer(); assert hasattr(reviewer, '_adapter'); print('PASS')"
# Output: PASS
```

---

## 2026-02-16 Task 3: Merge COLLECT and CONSOLIDATE into SYNTHESIZE

### Changes Made to `iron_rook/review/agents/security.py`

**Goal:** Reduce 7-phase FSM to 6-phase FSM by merging `collect` and `consolidate` phases into a single `synthesize` phase.

**1. Updated `_run_synthesize()` method:**
- Combined logic from both `_run_collect()` and `_run_consolidate()`
- Now handles:
  1. Validate subagent results and findings (from COLLECT)
  2. Mark TODO statuses based on completion (from COLLECT)
  3. Merge findings into structured evidence list (from CONSOLIDATE)
  4. De-duplicate findings by severity and finding_id (from CONSOLIDATE)
  5. Synthesize summary of issues found (from CONSOLIDATE)
- Added early-exit detection: checks if act phase returned `next_phase_request="done"` and runs minimal synthesis
- Updated `next_phase_request` default from `"check"` to `"evaluate"`

**2. Updated `_get_phase_specific_instructions("SYNTHESIZE")`:**
- Combined COLLECT and CONSOLIDATE instructions into a single comprehensive prompt
- Added Part A (Validation from COLLECT) and Part B (Consolidation from CONSOLIDATE) sections
- Added early-exit handling instructions
- Updated output JSON format to include `todo_status`, `findings` by severity, `gates`, `summary`, and `issues_with_results`
- Changed `next_phase_request` from `"check"` to `"evaluate"`

**3. Updated `_build_synthesize_message()`:**
- Now includes both ACT output (findings) and PLAN_TODOS output (TODO list)
- Added early-exit detection and note when act phase returned `next_phase_request="done"`
- Uses `act_output.get("data", {})` for findings data

**4. Removed methods:**
- Removed `_run_collect()` method entirely
- Removed `_run_consolidate()` method entirely

**5. Updated `handle_synthesize` in `_run_review_fsm()`:**
- Simplified from routing to `_run_collect` or `_run_consolidate` based on phase_outputs
- Now directly calls `_run_synthesize()` for all cases

### Key Design Decisions

1. **Single LLM call in synthesize**: Instead of two separate LLM calls (collect + consolidate), now uses one combined call that handles both validation and consolidation

2. **Early-exit handling**: When act phase determines no security issues, synthesize can run minimally - just validate outputs and produce empty findings before proceeding to evaluate

3. **Output schema unification**: Combined output includes both `todo_status` (from collect) and `findings` by severity (from consolidate)

4. **Phase flow simplification**: 
   - Before: act → collect → consolidate → evaluate
   - After: act → synthesize → evaluate

### Verification:
```bash
.venv/bin/python3 -c "
from iron_rook.review.agents.security import SecurityReviewer
reviewer = SecurityReviewer()
assert hasattr(reviewer, '_run_synthesize'), '_run_synthesize should exist'
assert not hasattr(reviewer, '_run_collect'), '_run_collect should NOT exist'
assert not hasattr(reviewer, '_run_consolidate'), '_run_consolidate should NOT exist'
print('PASS')
"
# Output: PASS
```

---

## 2026-02-15 Task 6: SecuritySubagent (Dynamic) Verification

### File: `iron_rook/review/subagents/security_subagent_dynamic.py`

**Finding:** This file already has NO `LoopFSM`, `LoopState`, or `iron_rook.fsm` module references.

**Self-Contained FSM Implementation:**
```python
# Module-level transitions (lines 44-50)
REACT_FSM_TRANSITIONS: Dict[str, List[str]] = {
    "intake": ["plan"],
    "plan": ["act"],
    "act": ["synthesize"],
    "synthesize": ["plan", "done"],
    "done": [],
}

# Own transition method (lines 337-346)
def _transition_to_phase(self, next_phase: str) -> None:
    valid_transitions = REACT_FSM_TRANSITIONS.get(self._current_phase, [])
    if next_phase not in valid_transitions:
        raise ValueError(...)
    self._phase_logger.log_transition(self._current_phase, next_phase)
    self._current_phase = next_phase

# Own FSM loop (lines 178-282)
async def _run_subagent_fsm(self, context: ReviewContext) -> ReviewOutput:
    while self._current_phase != "done":
        # Phase-specific handlers...
```

**Key Insight:** The dynamic subagent uses a **5-phase ReAct FSM** (`intake → plan → act → synthesize → done`) that is independent of:
- The main `SecurityReviewer`'s 6-phase FSM
- The `iron_rook.fsm.loop_fsm.LoopFSM` class

**No Changes Required:** The file is already fully self-contained and requires no modifications.

### Verification:
```bash
grep -n "from iron_rook.fsm" iron_rook/review/subagents/security_subagent_dynamic.py
# Output: (empty - no matches)

grep -n "LoopFSM\|LoopState\|loop_fsm" iron_rook/review/subagents/security_subagent_dynamic.py
# Output: (empty - no matches)
```

---

## 2026-02-15 Task 5: Security Subagents FSM Cleanup

### File: `iron_rook/review/subagents/security_subagents.py`

**Goal:** Remove unused LoopFSM imports and dead FSM code from security subagents.

**Key Discovery:**
The `BaseSubagent.review()` method had FSM code that was **never executed** because:
1. `self._fsm` was never initialized (no `LoopFSM()` constructor call)
2. All concrete subagents override `review()` and call `_execute_review_with_runner()` directly
3. The FSM code path would have crashed at `self._fsm.run_loop(fsm_context)` anyway

**1. Removed Imports:**
```python
# REMOVED:
from iron_rook.fsm.loop_fsm import LoopFSM
from iron_rook.fsm.loop_state import LoopState
from iron_rook.fsm.todo import Todo
```

**2. Updated Module Docstring:**
- Changed "LoopFSM pattern" → "SimpleReviewAgentRunner" to reflect actual implementation

**3. Simplified `BaseSubagent` Class:**
- Removed FSM phase documentation from class docstring
- Removed "with LoopFSM" from `__init__` docstring
- Replaced 60+ lines of dead FSM code in `review()` with direct call to `_execute_review_with_runner()`
- Kept `_execute_action_subagent()` method (may be used by subclasses)

**4. Simplified `BaseSubagent.review()` Method:**
Before (dead code):
```python
async def review(self, context: ReviewContext) -> ReviewOutput:
    logger.info(f"[{self.__class__.__name__}] Starting FSM loop execution")
    fsm_context = {...}
    try:
        self._fsm.run_loop(fsm_context)  # Would crash - _fsm never initialized
    except Exception as e:
        return ReviewOutput(...)  # Error handling
    return await self._execute_review_with_runner(...)  # Never reached
```

After (actual behavior):
```python
async def review(self, context: ReviewContext) -> ReviewOutput:
    return await self._execute_review_with_runner(
        context,
        early_return_on_no_relevance=True,
        no_relevance_summary=f"No {self.get_agent_name()}-relevant files changed.",
    )
```

**5. Concrete Subagents Unchanged:**
- `AuthSecuritySubagent`, `InjectionScannerSubagent`, `SecretScannerSubagent`, `DependencyAuditSubagent`
- All already override `review()` to call `_execute_review_with_runner()` directly
- No behavior changes to these classes

### Key Insights

1. **Dead code detection**: When migrating FSM patterns, check if the FSM is actually instantiated and used, or if subclasses bypass it entirely

2. **Subagent architecture**: The security subagents use a simpler execution model than the main SecurityReviewer - they don't need FSM state management, just direct review execution via the runner

3. **Import cleanup opportunity**: Removing unused FSM imports reduces coupling and simplifies the dependency graph

### Verification:
```bash
# Verify no FSM references remain
grep -n "LoopFSM\|loop_fsm\|LoopState\|loop_state" iron_rook/review/subagents/security_subagents.py
# Output: (empty - no matches)

# Verify imports work
.venv/bin/python3 -c "from iron_rook.review.subagents.security_subagents import BaseSubagent, AuthSecuritySubagent; print('PASS')"
# Output: PASS
```

---

## 2026-02-16 Task 7: Test Updates for FSM Migration

### Key Finding: Internal Phase Names vs Workflow State Names

The FSM migration introduced a dual naming system:

1. **Internal Phase Names** (still used for LLM prompts and schemas):
   - `intake`, `plan_todos`, `act`, `collect`, `consolidate`, `evaluate`
   - Used by: `get_phase_output_schema()`, `_get_phase_prompt()`, internal phase methods

2. **Workflow State Names** (used by adapter for transition validation):
   - `intake`, `plan`, `act`, `synthesize`, `evaluate`
   - Used by: `WORKFLOW_FSM_TRANSITIONS`, `adapter.get_valid_transitions()`

### Test Update Requirements

1. **Transition tests**: Use WORKFLOW state names (`plan`, `synthesize`)
   - `_transition_to_phase()` validates against WORKFLOW_FSM_TRANSITIONS

2. **Schema/prompt tests**: Use internal phase names (`plan_todos`, `collect`, `consolidate`)
   - `get_phase_output_schema()` only recognizes internal names
   - LLM response parsing uses internal phase names

3. **Mock responses**: Use internal phase names
   - `next_phase_request` should be `plan_todos` not `plan`
   - Phase data schemas use internal names

### Files Updated

- `tests/unit/review/agents/test_security_fsm.py` - FSM initialization, transitions
- `tests/unit/review/agents/test_security_thinking.py` - Phase thinking tests
- `tests/unit/review/agents/test_security_transitions.py` - Transition validation
- `tests/test_security_phase_logger.py` - Logger tests
- `tests/unit/review/subagents/test_security_subagents.py` - Subagent tests (already updated in Task 5)
- `tests/unit/review/agents/test_subagent_fsm_execution.py` - Subagent FSM execution tests
- `tests/integration/test_security_fsm_integration.py` - Integration tests

### Tests Still Failing

The following tests fail because they require production code changes:
- Tests expecting `_fsm` attribute (SecurityReviewer now uses `_adapter`)
- Tests checking internal schema validation (need `synthesize` phase in `get_phase_output_schema`)

### Recommendation

To fully migrate to new phase names, production code changes needed:
1. Add `synthesize` to `get_phase_output_schema()` in contracts.py
2. Update `_get_phase_prompt()` to recognize `synthesize` phase
3. Update all LLM prompt templates for new phase names

---

