# Draft: Replace Delegate Phase with Act Phase

## User's Request

Replace the "delegate" phase with an "act" phase that:
- Uses a skill for delegation
- Has tool support for delegation
- Security agent uses todo management, delegation, and memory/context evaluation

## Current Architecture Analysis

### 1. Delegate Phase (_run_delegate)

**Location**: `iron_rook/review/agents/security.py:406-538`

**Current Flow**:
```python
async def _run_delegate(self, context: ReviewContext) -> Dict[str, Any]:
    # 1. Call LLM for delegate phase
    system_prompt = self._get_phase_prompt("delegate")
    user_message = self._build_delegate_message(context)
    response_text = await self._execute_llm(system_prompt, user_message)

    # 2. Parse LLM output
    output = self._parse_phase_response(response_text, "delegate")
    subagent_requests = output.get("data", {}).get("subagent_requests", [])

    # 3. ACTUALLY EXECUTE SUBAGENTS
    subagent_results = []
    for request in subagent_requests:
        subagent = SecuritySubagent(task=request, max_retries=self._fsm.max_retries)
        result = await subagent.review(context)
        subagent_results.append({
            "todo_id": request.get("todo_id"),
            "title": request.get("title"),
            "subagent_type": "security_subagent",
            "status": "done" if result else "blocked",
            "result": result.model_dump() if result else None
        })

    # 4. Attach results back to delegate output
    output["data"]["subagent_results"] = subagent_results

    # 5. Create thinking frame and return
    self._create_thinking_frame(...)
    return output
```

**Key Points**:
- Delegate phase is ALREADY executing subagents via `SecuritySubagent` from `security_subagent_dynamic.py`
- It uses `SecurityTodo` objects created in PLAN_TODOS phase
- Subagents execute and return structured results
- Results are attached to delegate output as `subagent_results`

### 2. Todo Management System

**Location**: `iron_rook/review/contracts.py:266-284`

**SecurityTodo Structure**:
```python
class SecurityTodo(pd.BaseModel):
    """Security TODO item model."""
    id: str
    description: str
    priority: Literal["high", "medium", "low"]
    risk_category: str
    acceptance_criteria: str
    evidence_required: List[str] = pd.Field(default_factory=list)
```

**Current Flow**:
1. PLAN_TODOS phase creates `SecurityTodo` objects
2. Each todo has `id`, `description`, `priority`, `risk_category`, `acceptance_criteria`, `evidence_required`
3. Todos are passed through FSM phases via phase outputs
4. Delegate phase uses `todo_id` to track which todo each subagent handles

### 3. Skills/Tools Infrastructure

**Current Architecture**:
- **Skill Loading**: Dynamic via `ReviewerRegistry` in `iron_rook/review/registry.py`
- **Skill Contract**: `BaseReviewerAgent` in `iron_rook/review/base.py`
  - `get_agent_name()`: string identifier
  - `get_system_prompt()`: LLM prompt
  - `get_relevant_file_patterns()`: glob patterns
  - `get_allowed_tools()`: tool prefixes
  - `review(context)`: async method
- **Tool Execution**: `CommandExecutor` in `iron_rook/review/utils/executor.py`
  - Whitelisted tools: `DEFAULT_ALLOWED_TOOLS`
  - Sandboxed async execution with timeouts
  - Output parsing: `ParsedResult`

**Existing SecuritySubagent**:
- Location: `iron_rook/review/subagents/security_subagent_dynamic.py`
- Uses `LoopFSM` for internal state management
- Has `get_allowed_tools()` returning security tools (grep, rg, bandit, semgrep, safety)
- Implements `review(context)` with todo-based execution

### 4. Memory/Context Flow

**Key Structures**:
- **ReviewContext**: Contains changed files, diff, repo metadata, PR info
- **_phase_outputs**: Dictionary storing outputs from each FSM phase
  ```python
  self._phase_outputs = {
      "intake": {...},
      "plan_todos": {...},
      "delegate": {...},
      "collect": {...},
      "consolidate": {...},
      "evaluate": {...},
  }
  ```
- **Thinking logging**: `SecurityPhaseLogger` and `RunLog` for audit trail
- **LLM Context**: Built from ReviewContext + phase outputs, managed by token budget

### 5. Current FSM Transitions

**Current Map**:
```python
SECURITY_FSM_TRANSITIONS = {
    "intake": ["plan_todos"],
    "plan_todos": ["delegate"],
    "delegate": ["collect", "consolidate", "evaluate", "done"],
    "collect": ["consolidate"],
    "consolidate": ["evaluate"],
    "evaluate": ["done"],
}
```

## Proposed Change: Replace "delegate" with "act"

### New FSM Flow

```
intake → plan_todos → act → collect → consolidate → evaluate → done
```

**Changes Required**:
1. Remove "delegate" phase entirely
2. Create new "act" phase that:
   - Uses existing delegation skill/tool
   - Manages todos directly (no LLM delegation planning)
   - Evaluates memory/context for what tasks need delegation
   - Dispatches subagents for each todo
   - Collects results without additional LLM call

### Key Differences: Current vs Proposed

| Aspect | Current (delegate) | Proposed (act) |
|---------|------------------|----------------|
| **LLM Usage** | 1 LLM call to plan delegation | Direct todo dispatch (no planning LLM) |
| **Control** | LLM decides which subagents to run | Skill logic decides which subagents to run |
| **Phase Outputs** | `subagent_requests` from LLM | `subagent_results` from actual execution |
| **Next Phase** | "collect", "consolidate", "evaluate", or "done" | "collect" always (standard flow) |
| **Purpose** | Plan AND execute | Execute AND collect |

## Implementation Plan

### Phase 1: Create Delegation Skill

**New File**: `iron_rook/review/skills/delegate_todo.py`

**Purpose**: A skill that handles todo-based delegation without LLM planning.

**Interface**:
```python
class DelegateTodoSkill(BaseReviewerAgent):
    """Skill for managing and delegating security review todos."""

    def get_agent_name(self) -> str:
        return "delegate_todo"

    def get_allowed_tools(self) -> List[str]:
        return ["grep", "rg", "ast-grep", "python", "bandit", "semgrep"]

    async def review(self, context: ReviewContext) -> ReviewOutput:
        # 1. Extract todos from plan_todos phase output
        todos = self._phase_outputs.get("plan_todos", {}).get("data", {}).get("todos", [])

        # 2. Evaluate memory/context for delegation decisions
        #    - Check which todos need tool-based analysis
        #    - Check which can be dispatched to subagents
        #    - Check dependencies between todos

        # 3. Dispatch subagents for each todo
        subagent_results = []
        for todo in todos:
            subagent = SecuritySubagent(task=todo, max_retries=3)
            result = await subagent.review(context)
            subagent_results.append(...)

        # 4. Build ReviewOutput with findings
        return ReviewOutput(...)
```

**Why this approach**:
- No LLM planning overhead - direct delegation based on todo attributes
- Skill can implement custom logic for which subagents to run
- Uses existing `SecuritySubagent` infrastructure
- Results flow directly into collect phase

### Phase 2: Update Security FSM

**File**: `iron_rook/review/agents/security.py`

**Changes**:
1. Update `SECURITY_FSM_TRANSITIONS`:
   ```python
   SECURITY_FSM_TRANSITIONS = {
       "intake": ["plan_todos"],
       "plan_todos": ["act"],  # Changed from "delegate"
       "act": ["collect"],  # New phase
       "collect": ["consolidate"],
       "consolidate": ["evaluate"],
       "evaluate": ["done"],
   }
   ```

2. Replace `_run_delegate()` with `_run_act()`:
   ```python
   async def _run_act(self, context: ReviewContext) -> Dict[str, Any]:
       # Use delegate_todo skill
       # Pass todos directly, no LLM planning
       # Return results ready for collect phase
   ```

3. Remove delegate-specific code:
   - Delete `_build_delegate_message()`
   - Delete delegate phase prompt from `_get_phase_prompt()` or `_get_phase_specific_instructions()`
   - Remove delegate-related data structures

### Phase 3: Register New Skill

**File**: `iron_rook/review/skills/__init__.py`

**Change**:
```python
from .delegate_todo import DelegateTodoSkill

__all__ = ["DelegateTodoSkill"]
```

**File**: `iron_rook/review/registry.py`

**Change**:
```python
def _register_default_reviewers():
    # Existing registrations...
    registry.register("delegate_todo", DelegateTodoSkill, is_core=False)
```

### Phase 4: Update Contracts

**File**: `iron_rook/review/contracts.py`

**Changes**:
1. Update `PlanTodosPhaseOutput`:
   ```python
   next_phase_request: Literal["act"]  # Changed from "delegate"
   ```

2. Remove `DelegatePhaseOutput`, `DelegatePhaseData`, `SubagentRequest`, `SubagentResult` classes:
   - These were specific to delegate phase
   - Act phase will use skill results directly

3. Update `get_phase_output_schema()`:
   ```python
   phase_schemas = {
       "intake": IntakePhaseOutput,
       "plan_todos": PlanTodosPhaseOutput,
       "act": ActPhaseOutput,  # Changed from "delegate"
       "collect": CollectPhaseOutput,
       "consolidate": ConsolidatePhaseOutput,
       "evaluate": EvaluatePhaseOutput,
   }
   ```

### Phase 5: Update Tests

**Files to Update**:
1. `tests/unit/review/agents/test_security_fsm.py`
   - Replace `_run_delegate` tests with `_run_act` tests
   - Update transition tests
   - Remove delegate-specific tests

2. `tests/integration/test_security_fsm_integration.py`
   - Update integration tests for new act phase

## Questions for User

### Scope Clarification

1. **Todo Evaluation Logic**: Should the `act` phase skill:
   - Delegate ALL todos to subagents unconditionally?
   - Or evaluate and decide which need delegation based on context?

2. **Subagent Selection**: Should subagents be:
   - Same as current (SecuritySubagent)?
   - New specialized subagents per todo type?

3. **Error Handling**: How should act phase handle:
   - Subagent failures?
   - Empty todo list?

4. **Backward Compatibility**: Should we keep delegate phase for:
   - Existing tests that expect it?
   - Or migrate fully to act?

5. **Phase Name**: Are you set on "act" or open to other naming?
   - "execute" might be clearer than "act"
   - Or "dispatch" for delegation-focused phase

## Open Questions

- What specific logic should the `delegate_todo` skill implement for evaluating when/how to delegate?
- Should we remove delegate phase entirely or keep it as an alternative path?
- How should the skill integrate with existing todo management?
