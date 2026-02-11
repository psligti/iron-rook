# Learnings

### 2026-02-10 22:10 UTC
- Mapped active reviewer agents under iron_rook/review/agents (11 core + 0 extras per plan). Files enumerated:
- architecture.py, security.py, documentation.py, telemetry.py, linting.py, unit_tests.py, diff_scoper.py, requirements.py, performance.py, dependencies.py, changelog.py
- Base flow observed: All agents subclass BaseReviewerAgent; review() [implemented via _execute_review_with_runner] to call SimpleReviewAgentRunner; system prompts and allowed tools vary by agent but share common pattern.
- Wiring: PRReviewOrchestrator.run_subagents_parallel calls current_agent.review(context) for each agent; context built from get_changed_files/diff and filtered by is_relevant_to_changes; results aggregated via Orchestrator.
- Registry wiring: registry.py registers core vs optional reviewers; __init__ imports the agent classes; get_core_reviewers/get_all_reviewers used to instantiate.
2026-02-10T00:00:00Z - Exhaustive search note init.
2026-02-10T00:00:00Z — Automated note: Exhaustive search attempt for state-pattern implementations across iron-rook and harness-agent-rework

No explicit AgentState, AgentStateMachine, FSM_TRANSITIONS, or similar FSM-state modules were found in the code bases under /Users/parkersligting/develop/pt/iron-rook and /Users/parkersligting/develop/pt/worktrees/harness-agent-rework (grep searches returned no hits for those identifiers).

# Dawn-Kestrel Result Pattern Research
**Research Date**: 2026-02-10
**Purpose**: Understand Result pattern (Ok, Err, Pass) for use in AgentStateMachine.transition_to() and BaseReviewerAgent FSM integration

## Semantics of Result Types

### Ok[T]: Success with Value
- **Purpose**: Represents successful operation with a return value
- **Fields**: `_value: T` - the success value
- **Predicates**:
  - `is_ok()` → `True`
  - `is_err()` → `False`
  - `is_pass()` → `False`
- **Extraction**:
  - `unwrap()` → returns value, raises ValueError if not Ok
  - `unwrap_or(default)` → returns value (ignores default)
- **Equality**: Compares `_value` field

### Err: Failure with Error Information
- **Purpose**: Represents operation failure with detailed error context
- **Fields**:
  - `error: str` - error message describing what went wrong
  - `code: str | None` - optional error code for categorization
  - `retryable: bool` - whether error is retryable (default: `False`)
- **Predicates**:
  - `is_ok()` → `False`
  - `is_err()` → `True`
  - `is_pass()` → `False`
- **Extraction**:
  - `unwrap()` → raises ValueError with error message
  - `unwrap_or(default)` → returns default value
- **Equality**: Compares all three fields (error, code, retryable)

### Pass: Neutral Outcome
- **Purpose**: Represents "continue without value" - neither success nor failure
- **Fields**: `message: str | None` - optional message describing the pass-through
- **Predicates**:
  - `is_ok()` → `False`
  - `is_err()` → `False`
  - `is_pass()` → `True`
- **Extraction**:
  - `unwrap()` → raises ValueError("Cannot unwrap Pass result")
  - `unwrap_or(default)` → returns default value
- **Equality**: Compares `message` field

## State Machine Transition Method Pattern

Based on `dawn_kestrel/core/agent_fsm.py` ([source](https://github.com/psligti/agentic_coding/blob/3523c6166da668b1561008b95430d194ec305963/dawn_kestrel/core/agent_fsm.py)):

### Recommended Pattern for `transition_to()`

```python
async def transition_to(self, new_state: str) -> Result[None]:
    """
    Transition agent to new state.
    
    Returns:
        Result[None]: Ok on successful transition, Err if transition invalid.
    
    Usage Pattern:
        - Return Ok(None) on successful transition (no new state value needed)
        - Return Err(...) with code for invalid transitions
        - Never return Pass() - transitions should be binary (success/failure)
    """
    # Validate transition before applying
    if not await self.is_transition_valid(self._state, new_state):
        return Err(
            f"Invalid state transition: {self._state} -> {new_state}. "
            f"Valid transitions from {self._state}: {sorted(self.VALID_TRANSITIONS.get(self._state, set()))}",
            code="INVALID_TRANSITION",
        )
    
    # Apply transition
    self._state = new_state
    return Ok(None)
```

### Key Design Decisions

1. **Return Type**: `Result[None]` not `Result[str]`
   - State machines don't need to return the new state - the state is stored internally
   - Caller can check `is_ok()` and retrieve state via `get_state()` if needed

2. **Invalid Transition Handling**: Use `Err` with descriptive message and `code`
   - Always include the attempted transition in error message
   - Always include valid transitions from current state in error message
   - Use a specific `code` value (e.g., `"INVALID_TRANSITION"`) for programmatic handling

3. **No Pass Usage**: State transitions should be binary
   - Either succeed (`Ok(None)`) or fail (`Err(...)`)
   - Pass doesn't make sense for state transitions

## Concrete Usage Examples

### Example 1: FSM State Transition (Source: agent_fsm.py)

```python
# File: dawn_kestrel/core/agent_fsm.py
# Lines: 153-179

async def transition_to(self, new_state: str) -> Result[None]:
    """Transition agent to new state.

    Args:
        new_state: Target state to transition to.

    Returns:
        Result[None]: Ok on successful transition, Err if transition invalid.
    """
    # Validate transition
    if not await self.is_transition_valid(self._state, new_state):
        return Err(
            f"Invalid state transition: {self._state} -> {new_state}. "
            f"Valid transitions from {self._state}: {sorted(self.VALID_TRANSITIONS.get(self._state, set()))}",
            code="INVALID_TRANSITION",
        )

    # Apply transition
    self._state = new_state
    return Ok(None)
```

### Example 2: Retry Logic with Retryable Flag (Source: llm/retry.py)

```python
# File: dawn_kestrel/llm/retry.py
# Lines: 336-363

if result.is_ok():
    self._stats["successful_calls"] += 1
    return result
else:
    # Check if error is retryable
    if hasattr(result, "retryable") and not result.retryable:
        # Non-retryable error, return immediately
        self._stats["failed_calls"] += 1
        return result
    last_error = result
# ...
except Exception as e:
    # Transient error, retry
    last_error = Err(str(e), code="EXECUTION_ERROR", retryable=True)
    # Permanent error, return immediately
    return Err(str(e), code="PERMANENT_ERROR", retryable=False)
```

**Pattern Note**: The `retryable` flag controls retry logic in the executor. Non-retryable errors are returned immediately without retry attempts.

### Example 3: Facade Layer with Code-Based Error Handling (Source: core/facade.py)

```python
# File: dawn_kestrel/core/facade.py
# Lines: 184-194

async def create_session(self, title: str) -> Result[Session]:
    """Create a new session.

    Returns:
        Result with created Session object on success, or Err on failure.
    """
    try:
        service = self._container.service()
        result = await service.create_session(title)

        if result.is_err():
            err_result = cast(Any, result)
            return Err(f"Failed to create session: {err_result.error}", code="SessionError")

        return result
    except Exception as e:
        return Err(f"Failed to create session: {e}", code="SessionError")
```

**Pattern Note**: Facade wraps service errors with consistent error codes while preserving the original error message.

### Example 4: Strategy Pattern with No-Providers Error (Source: core/strategies.py)

```python
# File: dawn_kestrel/core/strategies.py
# Lines: 84-100

async def select_provider(self, providers: list[Any], context: dict[str, Any]) -> Result[Any]:
    """Select provider using round-robin algorithm.

    Returns:
        Result[Any]: Selected provider on success, Err if no providers.
    """
    if not providers:
        return Err("No providers available", code="NO_PROVIDERS")

    provider = providers[self._index]
    self._index = (self._index + 1) % len(providers)

    return Ok(provider)
```

**Pattern Note**: Returns `Ok(provider)` with the actual value, not `Ok(None)`. This differs from state transitions where the new state isn't returned.

### Example 5: Command Queue with Multiple Error Scenarios (Source: core/commands.py)

```python
# File: dawn_kestrel/core/commands.py
# Lines: 298-308, 270-296

async def process_next(self) -> Result[Any]:
    """Process next command from queue."""
    if not self._queue:
        return Err("No commands in queue", code="QUEUE_EMPTY")
    # ... execution logic ...

async def enqueue(self, command: Command) -> Result[None]:
    """Add command to queue and publish enqueued event."""
    try:
        self._queue.append(command)
        self._history.append(command)
        # ... event publishing ...
        return Ok(None)
    except Exception as e:
        return Err(f"Failed to enqueue command: {e}", code="QUEUE_ERROR")
```

**Pattern Note**: Different error codes for different failure scenarios (`QUEUE_EMPTY` vs `QUEUE_ERROR`).

## Composition Functions (Rarely Used)

The Result pattern includes composition functions, but they're **NOT widely used** in the codebase:

### bind() / result.bind()
```python
# Chaining functions that return Result
result = Ok(10)
doubled = result.bind(lambda x: Ok(x * 2))
```
- If Ok: applies function and returns new Result
- If Err/Pass: returns self unchanged (short-circuits)

### map_result()
```python
# Transform value inside Ok
result = Ok(10)
mapped = map_result(result, lambda x: x * 2)
```
- If Ok: returns Ok(func(value))
- If Err/Pass: returns self unchanged

### fold()
```python
# Collapse Result to single value
fold(result,
     on_ok=lambda x: f"success: {x}",
     on_err=lambda e: f"error: {e}")
```
- Applies appropriate function based on Result type

**Finding**: These functions exist in `result.py` but are only used in docstring examples, not in production code.

## JSON Serialization Support

All Result types support `to_json()` and static `from_json()`:

```python
# Ok serialization
Ok(42).to_json()
# → '{"type": "ok", "value": 42}'

# Err serialization
Err("failed", code="ERROR_CODE", retryable=False).to_json()
# → '{"type": "err", "error": "failed", "code": "ERROR_CODE", "retryable": false}'

# Pass serialization
Pass("skipped").to_json()
# → '{"type": "pass", "message": "skipped"}'

# Deserialization
Result.from_json('{"type": "ok", "value": 42}')
# → Ok(42)
```

**Usage Note**: The `default=str` parameter in `to_json()` handles non-JSON-serializable values by converting to string.

## Pitfalls and Gotchas

### 1. Type Inference Challenges
**Issue**: `Result[T]` type parameter is lost when using pattern matching
```python
# Type checker may complain here
if result.is_err():
    err_result = cast(Any, result)  # cast needed
    return Err(f"Failed: {err_result.error}", code="WrapperError")
```
**Solution**: Use `cast(Any, result)` to access `error`, `code`, `retryable` fields

### 2. unwrap() on Non-Ok Results Raises ValueError
```python
result = Err("failed")
value = result.unwrap()  # Raises ValueError("failed")
```
**Solution**: Always check `is_ok()` before calling `unwrap()`, or use `unwrap_or(default)`

### 3. Pass Results Don't Contain Values
```python
result = Pass("no value")
value = result.unwrap()  # Raises ValueError("Cannot unwrap Pass result")
```
**Gotcha**: Pass is a third distinct outcome, not just "optional success"
**Use Case**: "Continue without value" scenarios (rarely used in current codebase)

### 4. Code Field is Optional but Valuable
```python
# Minimal usage (less informative)
Err("Something went wrong")

# Better usage (enables programmatic handling)
Err("Something went wrong", code="SESSION_NOT_FOUND")
```
**Recommendation**: Always include `code` for errors that need programmatic handling

### 5. Retryable Flag Only Used in Retry Logic
```python
# Only useful if caller checks retryable field
Err("failed", code="TEMP_ERROR", retryable=True)
```
**Finding**: Only `RetryExecutorImpl` checks `retryable` flag
**Implication**: If your code doesn't use retry logic, `retryable` field has no effect

### 6. Equality Checks Include All Fields
```python
Err("failed", code="ERROR") == Err("failed", code="ERROR")
# → True

Err("failed", code="ERROR") == Err("failed", code="DIFFERENT")
# → False (different code)

Err("failed") == Err("failed", code=None)
# → True (code defaults to None)
```
**Gotcha**: Equality is structural, not based on identity

### 7. Composition Functions Not Widely Adopted
**Finding**: `bind()`, `map_result()`, `fold()` defined but rarely used
**Recommendation**: Prefer explicit `if/elif` pattern matching for clarity:
```python
# Preferred pattern
if result.is_ok():
    value = result.unwrap()
    # handle success
elif result.is_err():
    error = cast(Any, result).error
    # handle error
```

### 8. Type Checking with Generic Result
```python
def get_session(self) -> Result[Session | None]:
    """Returns Ok(Session) or Ok(None) or Err(...)"""
    # ...
    
result = await get_session()
if result.is_ok():
    session = result.unwrap()  # Type: Session | None
    if session:
        # session is not None
```
**Gotcha**: `Result[Session | None]` means Ok can contain `None`, not that `None` represents Err

### 9. JSON Serialization Limitations
```python
Ok(complex_object).to_json()
# May fail if complex_object is not JSON-serializable
# Uses default=str but may produce unexpected results
```
**Recommendation**: Only serialize Results with JSON-serializable values, or implement custom serialization

### 10. State Transition Return Value
**Wrong**: `Result[str]` returning new state
```python
# Don't do this - redundant
async def transition_to(self, new_state: str) -> Result[str]:
    self._state = new_state
    return Ok(self._state)  # Redundant - state already set
```

**Right**: `Result[None]` signaling success
```python
# Do this - pattern from dawn-kestrel
async def transition_to(self, new_state: str) -> Result[None]:
    self._state = new_state
    return Ok(None)  # Success signaled, caller gets state via get_state()
```

## Recommended Usage for Iron Rook FSM Integration

### For AgentStateMachine.transition_to():

```python
from dawn_kestrel.core.result import Result, Ok, Err

class AgentStateMachine:
    # ... state and transition definitions ...
    
    async def transition_to(self, new_state: str) -> Result[None]:
        """Transition to new state with validation.
        
        Returns:
            Result[None]: Ok(None) on success, Err(code="INVALID_TRANSITION") on failure.
        """
        # Validate transition
        if not await self._is_transition_valid(self._current_state, new_state):
            return Err(
                f"Invalid state transition: {self._current_state} -> {new_state}. "
                f"Valid transitions: {sorted(self._valid_transitions.get(self._current_state, set()))}",
                code="INVALID_TRANSITION",
            )
        
        # Apply transition
        self._current_state = new_state
        self._transition_history.append(new_state)
        return Ok(None)
```

### For BaseReviewerAgent FSM Integration:

```python
from dawn_kestrel.core.result import Result, Ok, Err

class BaseReviewerAgent:
    # ... existing code ...
    
    async def execute_fsm(self, context: ReviewContext) -> Result[ReviewOutput]:
        """Execute review using state machine pattern.
        
        Returns:
            Result[ReviewOutput]: Ok(output) on success, Err on failure.
        """
        # Initialize FSM
        fsm = AgentStateMachine(initial_state="idle")
        
        # Transition to running
        start_result = await fsm.transition_to("running")
        if start_result.is_err():
            return cast(Any, start_result)  # Propagate Err
        
        # Execute review logic
        try:
            output = await self.review(context)
            
            # Transition to completed
            await fsm.transition_to("completed")
            
            return Ok(output)
        except Exception as e:
            # Transition to failed
            await fsm.transition_to("failed")
            return Err(f"Review failed: {e}", code="REVIEW_ERROR")
```

## Summary

1. **Ok[T]**: Success with value - use `Ok(value)` or `Ok(None)` for no-return operations
2. **Err**: Failure with context - always include `code` for programmatic handling, use `retryable` for transient errors
3. **Pass**: Neutral outcome - rarely used, mostly for "continue without value" scenarios
4. **State Transitions**: Return `Result[None]`, validate before applying, use descriptive errors with `code`
5. **Pattern Matching**: Prefer explicit `if/elif` over composition functions for clarity
6. **Type Safety**: Use `cast(Any, result)` to access Err fields, always check `is_ok()` before `unwrap()`


Next steps:
- Review for explicit FSM/state patterns and map to plan constraints.

### 2026-02-10 21:30 UTC - State Machine Implementation Design Notes

## AgentStateMachine Design Decisions

### Transition Map Type Signature

```python
FSM_TRANSITIONS: Dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.INITIALIZING},
    AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
    AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
    AgentState.RUNNING: {AgentState.PAUSED, AgentState.COMPLETED, AgentState.FAILED},
    AgentState.PAUSED: {AgentState.RUNNING, AgentState.COMPLETED, AgentState.FAILED},
    AgentState.COMPLETED: set(),  # Terminal state
    AgentState.FAILED: set(),  # Terminal state
}
```

**Rationale**:
- Type: `Dict[AgentState, set[AgentState]]` - maps each source state to a set of valid target states
- Using `set[AgentState]` instead of `list[AgentState]` for O(1) membership testing
- `set()` for terminal states (COMPLETED, FAILED) - no outgoing transitions allowed
- Module-level constant allows agents to provide custom maps while maintaining safe default

### transition_to() Return Value

```python
def transition_to(self, next_state: AgentState) -> Result[AgentState]:
    """Attempt to transition to a new state.

    Returns:
        Result[AgentState]: Ok with new state, or Err with error message.
    """
    if self._is_valid_transition(self._current_state, next_state):
        self._current_state = next_state
        return Ok(next_state)  # Returns the target state
```

**Rationale**:
- Returns `Result[AgentState]` not `Result[None]` - differs from dawn-kestrel's agent_fsm.py pattern
- **Ok value**: The target state (next_state) - allows callers to confirm what state was reached
- **Benefit**: Enables chaining and verification: `result = fsm.transition_to(S); assert result.unwrap() == S`
- **Note**: Could also use `Result[None]` pattern from dawn-kestrel (state is stored internally), but returning state provides better API ergonomics

### Invalid Transition Encoding in Err

```python
def transition_to(self, next_state: AgentState) -> Result[AgentState]:
    if not self._is_valid_transition(self._current_state, next_state):
        error_msg = (
            f"Invalid transition: {self._current_state.value} -> {next_state.value}. "
            f"Valid transitions from {self._current_state.value}: "
            f"{[s.value for s in self._transitions.get(self._current_state, set())]}"
        )
        return Err(error=error_msg, code="INVALID_TRANSITION")
```

**Err Structure**:
- **error field**: Multi-part descriptive message:
  1. Attempted transition: `"Invalid transition: idle -> completed"`
  2. Valid alternatives: `"Valid transitions from idle: ['initializing']"`
- **code field**: `"INVALID_TRANSITION"` - constant for programmatic handling
- **retryable field**: `False` (default) - state validation errors are permanent

**Example Err output**:
```
Err(
  error="Invalid transition: idle -> completed. Valid transitions from idle: ['initializing']",
  code="INVALID_TRANSITION",
  retryable=False
)
```

**Rationale**:
- Descriptive message helps debugging (shows what was attempted and what's allowed)
- Code field enables programmatic error handling (switch on code, not message parsing)
- retryable=False because invalid transitions are logic errors, not transient failures

## Key Implementation Notes

### State Isolation
- `_current_state` is private (underscore prefix) - use `current_state` property for read access
- `_transitions` is private after construction - immutable once FSM is created
- Terminal states (COMPLETED, FAILED) have empty transition sets - no way out without reset()

### Thread Safety
- **NOT thread-safe** - single-threaded design
- In-memory only (no persistence) - state lost on restart
- Simple lock-free implementation appropriate for single-agent execution

### Custom Transition Maps
Agents can provide custom transition maps:
```python
custom_transitions = {
    AgentState.IDLE: {AgentState.RUNNING},  # Skip initialization
    AgentState.RUNNING: {AgentState.COMPLETED},
    AgentState.COMPLETED: set(),
    AgentState.FAILED: set(),
}
fsm = AgentStateMachine(transitions=custom_transitions)
```

This enables per-agent flexibility while maintaining safe defaults.

### 2026-02-10 22:19:05 UTC - Result Pattern Narrowing in Tests
Fixed static typing issues in `tests/test_state_machine.py` by using proper narrowing pattern:

```python
# Pattern for accessing Err variant attributes from Result[T]
result = fsm.transition_to(AgentState.COMPLETED)
assert result.is_err()
assert isinstance(result, Err)  # Narrow to Err
err = cast(Err[AgentState], result)  # Cast to access variant-specific fields

# Now safely access error, code, retryable
assert err.error is not None
assert "Invalid transition" in err.error
assert err.code == "INVALID_TRANSITION"
assert err.retryable is False
```

**Why this works**: Type checker sees `Result[AgentState]` and doesn't know which variant. The pattern:
1. `isinstance(result, Err)` narrows type at runtime
2. `cast(Err[AgentState], result)` tells type checker it's safe to access Err fields
3. Local `err` variable has proper type for static analysis

**Key requirement**: Must import `cast` from `typing` module.


### 2026-02-10: Import Result Pattern (Task 2)

**What**: Added `from dawn_kestrel.core.result import Result, Ok, Err, Pass` to `iron_rook/review/base.py`

**Where**: Line 9 (between standard library imports and local iron_rook imports)

**Why**: Prepares base.py for state pattern integration (Task 3 will import AgentState/AgentStateMachine, Task 4 will integrate them into BaseReviewerAgent)

**Verification**: 
- `.venv/bin/python -c "from dawn_kestrel.core.result import Result, Ok, Err, Pass"` ✅
- `pytest tests/test_state_machine.py` (41 passed) ✅

**Import order followed**:
1. `__future__` import
2. Standard library imports (typing, abc, pathlib)
3. pydantic import
4. **dawn_kestrel import** ← new (line 9)
5. Local iron_rook imports

### 2026-02-10: Import State Pattern (Task 3)

**What**: Added `from dawn_kestrel.agents.state import AgentState, AgentStateMachine` to `iron_rook/review/base.py`

**Where**: Line 10 (immediately after dawn_kestrel.core.result import, grouped with other dawn_kestrel imports)

**Why**: Prepares base.py for state machine integration - Task 4 will integrate AgentStateMachine into BaseReviewerAgent

**Verification**:
- `.venv/bin/python -c "from dawn_kestrel.agents.state import AgentState, AgentStateMachine"` ✅
- `.venv/bin/ty check iron_rook/review/base.py` ✅

**Import structure**:
```python
from dawn_kestrel.core.result import Result, Ok, Err, Pass
from dawn_kestrel.agents.state import AgentState, AgentStateMachine  # ← new
```

Both dawn_kestrel imports now grouped together at line 9-10, before local iron_rook imports at line 12+.

### 2026-02-10 23:30 UTC: Integrate Result and AgentStateMachine into BaseReviewerAgent (Task 4)

**What**: Integrated dawn_kestrel's Result pattern and AgentStateMachine into BaseReviewerAgent

**Changes to iron_rook/review/base.py**:

1. **State machine instance in __init__**: Created `self._state_machine = AgentStateMachine()` in BaseReviewerAgent.__init__()

2. **State property**: Added `@property state(self) -> AgentState` that returns the current state from the internal state machine

3. **get_valid_transitions() as non-abstract method**: 
   - Implemented as a concrete method (not abstract) to allow agent instantiation before per-agent FSM_TRANSITIONS are added (Tasks 5-14)
   - Uses hasattr() to check for class-level FSM_TRANSITIONS attribute
   - Falls back to dawn_kestrel.agents.state.FSM_TRANSITIONS if no per-agent override exists
   - Uses type cast to satisfy mypy since hasattr doesn't narrow types

4. **_transition_to() helper method**: 
   - Wraps `self._state_machine.transition_to()` with error handling
   - Raises RuntimeError with descriptive message on invalid transitions
   - Uses Result.is_err() and cast(Err) pattern for type-safe error access

5. **State transitions in _execute_review_with_runner()**:
   - At method start: IDLE → INITIALIZING → READY → RUNNING
   - On all normal return paths: transition to COMPLETED
   - On unhandled exceptions: transition to FAILED, then re-raise

**Why get_valid_transitions() is non-abstract**:
- Tasks 5-14 will add per-agent FSM_TRANSITIONS class attributes to 11 agent files
- Making this method abstract would break instantiation until all agents are updated
- Non-abstract with fallback to default FSM_TRANSITIONS allows gradual migration
- Once all agents have FSM_TRANSITIONS, this method returns agent-specific transitions

**Where state transitions occur**:
- Initialization: In __init__, AgentStateMachine starts in IDLE state (from dawn_kestrel.agents.state)
- Active transitions: In _execute_review_with_runner(), method body performs deterministic transitions
  - Entry sequence: IDLE → INITIALIZING → READY → RUNNING (lines 140-142)
  - Exit on success: COMPLETED (before each return statement)
  - Exit on error: FAILED (in exception handlers before re-raise)
- Read access: Via `self.state` property returns `self._state_machine.current_state`

**Verification**:
- `.venv/bin/ty check iron_rook/review/base.py` ✅ (all checks passed)
- `.venv/bin/python -c "from iron_rook.review.agents.architecture import ArchitectureReviewer; a=ArchitectureReviewer(); print(a.state.value)"` → "idle" ✅
- `.venv/bin/python -c "from iron_rook.review.registry import ReviewerRegistry; ReviewerRegistry.get_all_reviewers(); print('registry-ok')"` → "registry-ok" ✅
- `.venv/bin/python -m pytest -q tests/test_state_machine.py` → 41 passed ✅

**Key design decisions**:
- State transitions are deterministic and synchronous (no async transitions needed for current use case)
- Transitions occur in base class _execute_review_with_runner(), not in individual agents
- SimpleReviewAgentRunner logic unchanged - state transitions wrap existing behavior
- ReviewOutput public contract preserved - FSM is internal plumbing
### 2026-02-10 23:35 UTC: Fix Task 4 bug - actually wire get_valid_transitions() into AgentStateMachine

**Bug**: BaseReviewerAgent.__init__ was instantiating AgentStateMachine() without passing transitions, so get_valid_transitions() was unused.

**Fix**: Changed line 97 from `self._state_machine = AgentStateMachine()` to `self._state_machine = AgentStateMachine(self.get_valid_transitions())`.

**Why this matters**: Now per-agent FSM_TRANSITIONS class attributes (to be added in Tasks 5-14) will actually be enforced by the state machine.

**Verification**:
- `.venv/bin/ty check iron_rook/review/base.py` ✅
- `.venv/bin/python -c "from iron_rook.review.agents.architecture import ArchitectureReviewer; a=ArchitectureReviewer(); print(a.state.value)"` → "idle" ✅
- `.venv/bin/python -m pytest -q tests/test_state_machine.py` → 41 passed ✅
### 2026-02-10 23:45 UTC: Fix integration bug - wire get_valid_transitions() and add reset for reusability

**Bug**: BaseReviewerAgent instantiated AgentStateMachine with transitions but didn't reset state before each run, making instances non-reusable.

**Fix 1 - Pass transitions to state machine**: 
- Line 97: `self._state_machine = AgentStateMachine(self.get_valid_transitions())`
- Why: Ensures per-agent FSM_TRANSITIONS class attributes (added in Tasks 5-14) are actually enforced by the state machine
- Before: Transitions were ignored, always using dawn_kestrel's default FSM_TRANSITIONS

**Fix 2 - Reset state at run start**:
- Line 341: Added `self._state_machine.reset()` before first transition in _execute_review_with_runner()
- Why: Agent instances can now be reused across multiple runs by resetting to IDLE state
- Before: Once an agent reached COMPLETED or FAILED, subsequent calls would fail or have undefined behavior

**Verification**:
- `.venv/bin/ty check iron_rook/review/base.py` ✅
- `.venv/bin/python -c "from iron_rook.review.agents.architecture import ArchitectureReviewer; a=ArchitectureReviewer(); print('state:', a.state.value)"` → "state: idle" ✅
- `.venv/bin/python -m pytest -q` → 41 passed ✅
### 2026-02-10 23:33:07 UTC - Task 5-14: FSM Transitions Added to 10 Agents

Updated 10 agent files with class-level FSM_TRANSITIONS and AgentState import:
- documentation.py
- architecture.py
- linting.py
- telemetry.py
- unit_tests.py
- diff_scoper.py
- requirements.py
- performance.py
- dependencies.py
- changelog.py

Note: SecurityReviewer (security.py) was intentionally excluded per plan.

Each agent now defines:
```python
FSM_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.INITIALIZING},
    AgentState.INITIALIZING: {AgentState.READY, AgentState.FAILED},
    AgentState.READY: {AgentState.RUNNING, AgentState.FAILED},
    AgentState.RUNNING: {AgentState.COMPLETED, AgentState.FAILED},
    AgentState.COMPLETED: set(),  # Terminal
    AgentState.FAILED: set(),      # Terminal
}
```

This transition map matches the base lifecycle used by BaseReviewerAgent._execute_review_with_runner():
- IDLE → INITIALIZING → READY → RUNNING → COMPLETED (success path)
- Any state → FAILED (error path)

Additional fix: changelog.py __init__ now calls super().__init__() to ensure _state_machine is initialized.

Verification:
- ty check: All checks passed
- All 11 agents start in "idle" state (including security.py which uses default transitions)
- pytest: 41 passed

### 2026-02-10 23:36:35 UTC - Export AgentState and AgentStateMachine from agents package (Task 15)

**What**: Added imports and __all__ exports for `AgentState` and `AgentStateMachine` from `dawn_kestrel.agents.state` to `iron_rook/review/agents/__init__.py`

**Why**: BaseReviewerAgent now exposes `.state: AgentState` property, so re-exporting these types via `iron_rook.review.agents` makes it easy for callers to type-check without importing directly from dawn_kestrel.

**Changes**:
- Added import: `from dawn_kestrel.agents.state import AgentState, AgentStateMachine`
- Added to __all__: `"AgentState", "AgentStateMachine"`
- Kept all existing agent-class exports and ordering stable

**Verification**:
- `.venv/bin/python -c "from iron_rook.review.agents import AgentState, AgentStateMachine; print('ok', AgentState.IDLE.value)"` → "ok idle" ✅
- `.venv/bin/python -c "from iron_rook.review.agents import ArchitectureReviewer"` → ✅
- `.venv/bin/ty check iron_rook/review/agents/__init__.py` → All checks passed ✅

**Usage pattern**: Callers can now import state types from `iron_rook.review.agents` alongside agent classes:
```python
from iron_rook.review.agents import ArchitectureReviewer, AgentState
agent = ArchitectureReviewer()
print(f"Agent state: {agent.state.value}")  # "idle"
```
