# Decisions
# FSM Pattern Research - 2026-02-10

## Research Scope
Researching robust, minimal Python patterns for implementing a finite-state machine for dawn_kestrel/agents/state.py, focusing on:
- Enum states
- Transition map (dict[from_state] -> set[to_states])
- Validated transitions
- Non-exception control flow (Result-like type)

## Sources Consulted

### 1. Python Official Documentation
- **URL**: https://docs.python.org/3/library/enum.html
- **URL**: https://docs.python.org/3/howto/enum.html
- **Key Takeaways**:
  - Enum provides type-safe symbolic names with unique values
  - Supports iteration, membership testing, and programmatic access
  - Can be used with dataclasses for richer state objects
  - Upper-case member names recommended for constants

### 2. Refactoring.Guru State Pattern
- **URL**: https://refactoring.guru/design-patterns/state
- **Key Takeaways**:
  - State pattern delegates state-specific behavior to state objects
  - Context maintains reference to current state
  - States can initiate transitions
  - Reduces conditional complexity in context classes

### 3. Dawn-Kestrel Result Pattern (existing)
- **File**: /Users/parkersligting/develop/pt/worktrees/harness-agent-rework/dawn_kestrel/core/result.py
- **Key Components**:
  - Ok[T]: Success with value
  - Err: Failure with error message, code, retryable flag
  - Pass: Neutral outcome with optional message
  - Supports composition via bind(), map_result(), fold()

## Implementation Patterns

### Pattern 1: Simple Dict Map with Enum States (Minimal)

```python
from enum import Enum, auto
from typing import Dict, Set

class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()

class SimpleStateMachine:
    """Minimal FSM with transition validation."""
    
    def __init__(self, transitions: Dict[AgentState, Set[AgentState]]):
        self._state = AgentState.IDLE
        self._transitions = transitions
    
    def _is_valid_transition(self, to_state: AgentState) -> bool:
        """Check if transition is allowed."""
        return to_state in self._transitions.get(self._state, set())
    
    def transition_to(self, to_state: AgentState):
        """Transition to new state if valid."""
        if not self._is_valid_transition(to_state):
            raise ValueError(
                f"Invalid transition from {self._state.name} to {to_state.name}. "
                f"Valid transitions: {[s.name for s in self._transitions.get(self._state, set())]}"
            )
        self._state = to_state
    
    @property
    def state(self) -> AgentState:
        return self._state
```

**Pros:**
- Simple and minimal (~30 LOC)
- Easy to understand and maintain
- Type-safe with Enum
- Clear error messages for invalid transitions

**Cons:**
- Uses exceptions for control flow (violates non-exception requirement)
- No built-in Result pattern integration
- Transition map is mutable (pitfall risk)

**Pitfalls:**
1. **Mutable transition map**: If transitions dict is shared across instances, modifications affect all instances
2. **Poor error messages**: Generic "Invalid transition" doesn't help debugging
3. **Missing terminal states**: No validation that COMPLETED/FAILED are final

---

### Pattern 2: Class-Based Validator with Result Integration (Recommended)

```python
from enum import Enum, auto
from typing import Dict, Set, ClassVar
from dawn_kestrel.core.result import Result, Ok, Err

class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()

class ValidatedStateMachine:
    """FSM with Result-based transition validation."""
    
    # Terminal states that cannot transition further
    TERMINAL_STATES: ClassVar[Set[AgentState]] = {
        AgentState.COMPLETED, 
        AgentState.FAILED
    }
    
    def __init__(self, transitions: Dict[AgentState, Set[AgentState]]):
        # Deep copy to prevent mutation of shared transition map
        self._state = AgentState.IDLE
        self._transitions = {k: set(v) for k, v in transitions.items()}
    
    def _is_valid_transition(self, to_state: AgentState) -> bool:
        """Check if transition is allowed."""
        # Terminal states cannot transition
        if self._state in self.TERMINAL_STATES:
            return False
        # Check if transition is in allowed set
        return to_state in self._transitions.get(self._state, set())
    
    def transition_to(self, to_state: AgentState) -> Result[AgentState]:
        """Transition to new state, returning Result."""
        # Check terminal state restriction
        if self._state in self.TERMINAL_STATES:
            return Err(
                error=f"Cannot transition from terminal state {self._state.name}",
                code="TERMINAL_STATE_VIOLATION",
                retryable=False
            )
        
        # Validate transition
        if not self._is_valid_transition(to_state):
            valid_transitions = self._transitions.get(self._state, set())
            return Err(
                error=(
                    f"Invalid transition from {self._state.name} to {to_state.name}. "
                    f"Valid transitions: {sorted([s.name for s in valid_transitions])}"
                ),
                code="INVALID_TRANSITION",
                retryable=False
            )
        
        # Apply transition
        old_state = self._state
        self._state = to_state
        return Ok(to_state)
    
    def can_transition(self, to_state: AgentState) -> bool:
        """Check if transition is valid without changing state."""
        return self._is_valid_transition(to_state)
    
    @property
    def state(self) -> AgentState:
        return self._state
    
    @property
    def is_terminal(self) -> bool:
        return self._state in self.TERMINAL_STATES
```

**Pros:**
- Non-exception control flow via Result type
- Immutable transition maps (deep copy on init)
- Terminal state validation prevents logic errors
- Actionable error messages with error codes
- Retryable flag for transient errors
- Type-safe with Python 3.11+ type annotations

**Cons:**
- More verbose (~70 LOC)
- Requires Result pattern dependency
- Slightly more complex API

**Pitfalls Addressed:**
1. **Immutable transitions**: Deep copy prevents mutation
2. **Actionable errors**: Error codes (INVALID_TRANSITION, TERMINAL_STATE_VIOLATION)
3. **Terminal state behavior**: Explicit TERMINAL_STATES set

---

### Pattern 3: Dataclass Wrapper with Transition History

```python
from enum import Enum, auto
from typing import Dict, Set, List, ClassVar
from dataclasses import dataclass, field
from dawn_kestrel.core.result import Result, Ok, Err

class AgentState(Enum):
    """Agent lifecycle states."""
    IDLE = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class TransitionEvent:
    """Record of state transition."""
    from_state: AgentState
    to_state: AgentState
    timestamp: float = field(default_factory=lambda: time.time())

@dataclass
class HistoryStateMachine:
    """FSM with transition history and validation."""
    
    TERMINAL_STATES: ClassVar[Set[AgentState]] = {
        AgentState.COMPLETED,
        AgentState.FAILED
    }
    
    def __init__(self, transitions: Dict[AgentState, Set[AgentState]]):
        self._state = AgentState.IDLE
        self._transitions = {k: set(v) for k, v in transitions.items()}
        self._history: List[TransitionEvent] = []
    
    def transition_to(self, to_state: AgentState) -> Result[AgentState]:
        """Transition with history tracking."""
        if self._state in self.TERMINAL_STATES:
            return Err(
                error=f"Cannot transition from terminal state {self._state.name}",
                code="TERMINAL_STATE_VIOLATION"
            )
        
        if not self._is_valid_transition(to_state):
            valid = self._transitions.get(self._state, set())
            return Err(
                error=f"Invalid transition from {self._state.name} to {to_state.name}. "
                      f"Valid: {sorted([s.name for s in valid])}",
                code="INVALID_TRANSITION"
            )
        
        # Record transition
        event = TransitionEvent(from_state=self._state, to_state=to_state)
        self._history.append(event)
        self._state = to_state
        
        return Ok(to_state)
    
    def _is_valid_transition(self, to_state: AgentState) -> bool:
        return to_state in self._transitions.get(self._state, set())
    
    @property
    def state(self) -> AgentState:
        return self._state
    
    @property
    def history(self) -> List[TransitionEvent]:
        return self._history.copy()
    
    @property
    def is_terminal(self) -> bool:
        return self._state in self.TERMINAL_STATES
```

**Pros:**
- Full transition history for debugging
- Dataclass provides immutability guarantees
- Same Result pattern benefits
- Easy to serialize history for debugging

**Cons:**
- Most verbose (~80 LOC)
- History tracking adds memory overhead
- Overkill for simple use cases

**Use When:**
- Debugging complex state flows
- Auditing agent behavior
- Reproducing issues from logs

---

## Common Pitfalls

### 1. Mutating Shared Transition Maps
**Problem**: Using shared dict as default parameter or class variable leads to mutations affecting all instances.

```python
# BAD: Shared mutable default
class BadFSM:
    def __init__(self, transitions: Dict[AgentState, Set[AgentState]] = {}):
        self._transitions = transitions  # Shared across instances!

# BAD: Class variable mutation
class BadFSM2:
    TRANSITIONS = {AgentState.IDLE: {AgentState.READY}}
    def __init__(self):
        self._transitions = self.TRANSITIONS  # Mutable!
```

**Solution**: Always deep copy on initialization.

```python
# GOOD: Deep copy
class GoodFSM:
    def __init__(self, transitions: Dict[AgentState, Set[AgentState]]):
        self._transitions = {k: set(v) for k, v in transitions.items()}
```

---

### 2. Poor Error Messages
**Problem**: Generic errors make debugging difficult.

```python
# BAD: Generic error
raise ValueError("Invalid transition")
```

**Solution**: Include context and valid alternatives.

```python
# GOOD: Actionable error
return Err(
    error=(
        f"Invalid transition from {self._state.name} to {to_state.name}. "
        f"Valid transitions: {sorted([s.name for s in valid_transitions])}"
    ),
    code="INVALID_TRANSITION",
    retryable=False
)
```

---

### 3. Missing Terminal State Behavior
**Problem**: No validation that terminal states cannot transition further.

```python
# BAD: Allows transitions from COMPLETED
if state == AgentState.COMPLETED:
    do_something_else()
```

**Solution**: Explicit terminal state set with validation.

```python
# GOOD: Terminal state enforcement
TERMINAL_STATES = {AgentState.COMPLETED, AgentState.FAILED}

if current_state in TERMINAL_STATES:
    return Err(error="Terminal state reached", code="TERMINAL_STATE")
```

---

### 4. Using Exceptions for Control Flow
**Problem**: Exceptions for expected conditions break the type system and require try/catch everywhere.

```python
# BAD: Exception for expected case
try:
    fsm.transition_to(to_state)
except ValueError as e:
    handle_error(e)  # Expected but treated as exceptional
```

**Solution**: Use Result type for railway-oriented programming.

```python
# GOOD: Result for expected cases
result = fsm.transition_to(to_state)
if result.is_err():
    handle_error(result.error)  # Explicit, no try/catch needed
```

---

## Recommended Type Signature (Python 3.11+)

```python
from __future__ import annotations
from enum import Enum
from typing import Dict, Set, ClassVar
from dawn_kestrel.core.result import Result

T_State = Enum  # Generic type variable for State enums

class AgentStateMachine:
    """Generic finite state machine for agent lifecycle."""
    
    # Class variables for shared configuration
    TERMINAL_STATES: ClassVar[Set[T_State]]
    
    def __init__(
        self,
        transitions: Dict[T_State, Set[T_State]],
        initial_state: T_State | None = None
    ) -> None:
        """Initialize state machine.
        
        Args:
            transitions: Transition map from_state -> set[to_states]
            initial_state: Starting state (defaults to first enum value)
        """
        # Deep copy to prevent mutation
        self._transitions = {k: set(v) for k, v in transitions.items()}
        self._state = initial_state or list(type(list(transitions.keys())[0])[0]
    
    def _is_valid_transition(self, to_state: T_State) -> bool:
        """Check if transition is valid."""
        if self._state in self.TERMINAL_STATES:
            return False
        return to_state in self._transitions.get(self._state, set())
    
    def transition_to(self, to_state: T_State) -> Result[T_State]:
        """Transition to new state, returning Result.
        
        Returns:
            Ok(new_state) on success
            Err(error, code, retryable) on failure
        """
        if self._state in self.TERMINAL_STATES:
            return Err(
                error=f"Cannot transition from terminal state {self._state.name}",
                code="TERMINAL_STATE_VIOLATION",
                retryable=False
            )
        
        if not self._is_valid_transition(to_state):
            valid = self._transitions.get(self._state, set())
            return Err(
                error=(
                    f"Invalid transition from {self._state.name} to {to_state.name}. "
                    f"Valid transitions: {sorted([s.name for s in valid])}"
                ),
                code="INVALID_TRANSITION",
                retryable=False
            )
        
        self._state = to_state
        return Ok(to_state)
    
    def can_transition(self, to_state: T_State) -> bool:
        """Check if transition is valid without changing state."""
        return self._is_valid_transition(to_state)
    
    @property
    def state(self) -> T_State:
        """Current state."""
        return self._state
    
    @property
    def is_terminal(self) -> bool:
        """Whether current state is terminal."""
        return self._state in self.TERMINAL_STATES
```

**Key Features:**
- Python 3.11+ type annotations with `|` union syntax
- Generic type variable `T_State` for any Enum
- ClassVar for shared constants
- Result type for non-exception control flow
- Immutable transition maps (deep copy)
- Terminal state validation
- Comprehensive error codes

---

## Recommended Error Messages (Actionable)

### Invalid Transition
```
Invalid transition from IDLE to COMPLETED. 
Valid transitions: ['INITIALIZING', 'READY']
Code: INVALID_TRANSITION
Retryable: False
```

### Terminal State Violation
```
Cannot transition from terminal state COMPLETED.
Terminal states: COMPLETED, FAILED
Code: TERMINAL_STATE_VIOLATION
Retryable: False
```

### Transient Error (with retryable=True)
```
Failed to transition from READY to RUNNING: Connection timeout.
Code: TRANSIENT_ERROR
Retryable: True
```

### Missing Transition Definition
```
No transition defined from state DELEGATE.
Ensure FSM_TRANSITIONS includes 'delegate' key.
Code: MISSING_TRANSITION_DEFINITION
Retryable: False
```

---

## Pattern Choice Recommendation

**For dawn_kestrel/agents/state.py: Use Pattern 2 (Class-Based Validator with Result Integration)**

**Rationale:**
1. **Non-exception control flow**: Matches dawn-kestrel's Result pattern philosophy
2. **Actionable errors**: Error codes and retryable flags enable robust error handling
3. **Terminal state validation**: Prevents logic errors in agent lifecycle
4. **Immutable transitions**: Deep copy prevents shared state bugs
5. **Python 3.11+ compatibility**: Uses modern type syntax
6. **Type safety**: Enum-based states with full type checking
7. **Minimal but complete**: ~70 LOC is manageable and maintainable

**Next Steps:**
1. Implement AgentStateMachine in dawn_kestrel/agents/state.py
2. Define AgentState enum with 7 states (IDLE, INITIALIZING, READY, RUNNING, PAUSED, COMPLETED, FAILED)
3. Add FSM_TRANSITIONS as class attribute in BaseReviewerAgent
4. Update 11 agents to define their specific transition maps
5. Integrate Result pattern for all transition operations
