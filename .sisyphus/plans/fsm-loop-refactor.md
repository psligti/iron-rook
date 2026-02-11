# FSM Loop Refactor - Intake → Plan → Act → Synthesize → Done

## TL;DR

> **Quick Summary**: Create a new FSM implementation in `iron_rook/fsm/` with intake→plan→act→synthesize→done loop pattern, where plan→act→synthesize is a sub-loop that repeats until goal achievement. This will be a drop-in replacement for dawn_kestrel's AgentStateMachine in BaseReviewerAgent, supporting async/parallel tool execution with rich todo management.

> **Deliverables**:
> - New FSM package with LoopFSM class, states, and todo management
> - Updated BaseReviewerAgent using new FSM
> - Complete TDD test suite

> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential implementation
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

---

## Context

### Original Request
User requested to update the FSM to use a loop where it is: intake, plan, act, synthesize, done. Where plan, act, synthesize is a sub-loop and:
- **plan**: create a todo list and prioritize that todo list
- **act**: using a tool
- **synthesize**: stating the progress made

### Interview Summary

**Key Discussions**:
- **FSM Scope**: New FSM implementation in separate package (iron_rook/fsm/), keeping dawn_kestrel unchanged
- **Integration Strategy**: Drop-in replacement for dawn_kestrel's AgentStateMachine in BaseReviewerAgent
- **Code Location**: New package at `iron_rook/fsm/`
- **Loop Exit Condition**: Goal achievement check via LLM after synthesize phase determines if goal met
- **Tool Failure Handling**: Retry with same action (up to configurable retry limit via constructor parameter)
- **Todo Management**: Update existing todos across iterations (rich model with id, description, priority, status, metadata, dependencies)
- **Error States**: DONE + FAILED + STOPPED (three terminal states)
- **Tool Integration**: Use AgentRuntime for tool execution and LLM calls
- **Concurrency Model**: Async/parallel execution support
- **Test Strategy**: TDD (test-first)

**Research Findings**:
- Current dawn_kestrel FSM uses linear states: IDLE → INITIALIZING → READY → RUNNING → PAUSED → COMPLETED/FAILED
- AgentStateMachine class provides transition validation and state management
- BaseReviewerAgent uses `_state_machine` internally with `_transition_to()` method
- Some agents (like security_fsm.py) have custom FSM_TRANSITIONS with complex phase-based state machines

### Metis Review

**Identified Gaps** (addressed):
- **Integration Strategy Clarified**: Confirmed drop-in replacement for dawn_kestrel's FSM in BaseReviewerAgent (affects all agents using BaseReviewerAgent)
- **Concurrency Model**: Async/parallel execution support required with proper state locking
- **AgentRuntime Interface**: Need to use existing AgentRuntime for tool/LLM execution without creating wrappers
- **Infinite Loop Prevention**: Must enforce max iterations or timeout
- **State Validation**: Must throw on invalid transitions
- **Error Propagation**: Must preserve original error context in FAILED state

**Guardrails Applied** (from Metis review):
- **Scope Lockdown**: ONLY `iron_rook/fsm/` - NO modifications to dawn_kestrel integration
- **State Set**: Exactly {INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED} - NO additional states
- **Agent Changes**: ONLY BaseReviewerAgent - NO touching other reviewer agents
- **Todo Model**: Use existing rich model structure - NO schema changes
- **AI-Slop Prevention**: FSM must be single-purpose, not generalized state machine framework

---

## Work Objectives

### Core Objective
Create a new FSM implementation with intake→plan→act→synthesize→done loop pattern where the plan→act→synthesize sub-cycle repeats until goal achievement, integrated as drop-in replacement for dawn_kestrel's AgentStateMachine in BaseReviewerAgent.

### Concrete Deliverables
- New package: `iron_rook/fsm/` containing:
  - LoopFSM class with state management and transitions
  - LoopState enum (INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED)
  - Todo model with rich fields (id, description, priority, status, metadata, dependencies)
  - Integration with AgentRuntime for tool/LLM execution
- Updated: `iron_rook/review/base.py` BaseReviewerAgent to use new LoopFSM
- Complete TDD test suite in `tests/test_loop_fsm.py`

### Definition of Done
- [x] `iron_rook/fsm/__init__.py` exports LoopFSM and LoopState
- [x] `iron_rook/fsm/loop_fsm.py` implements full FSM logic with state transitions
- [x] `iron_rook/fsm/todo.py` implements Todo model with rich fields
- [x] `iron_rook/review/base.py` BaseReviewerAgent uses LoopFSM instead of dawn_kestrel's AgentStateMachine
- [x] `tests/test_loop_fsm.py` has comprehensive TDD test coverage
- [x] `bun test tests/test_loop_fsm.py` → all tests pass
- [x] FSM successfully transitions: INTAKE → PLAN → (ACT → SYNTHESIZE)* → DONE

### Must Have
- LoopFSM class with intake→plan→act→synthesize→done loop pattern
- Sub-loop: PLAN → ACT → SYNTHESIZE repeats until goal achievement
- Goal achievement check via LLM call after SYNTHESIZE phase
- Rich todo model with id, description, priority, status, metadata, dependencies
- Todo updates persist across loop iterations
- Tool failure handling with configurable retry limit (constructor parameter)
- Async/parallel execution support with proper state locking
- Drop-in replacement for dawn_kestrel's AgentStateMachine in BaseReviewerAgent
- Three terminal states: DONE, FAILED, STOPPED
- Integration with AgentRuntime for tool execution and LLM calls

### Must NOT Have (Guardrails)
- NO modifications to dawn_kestrel's AgentState or AgentStateMachine
- NO additional states beyond INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED
- NO persistence/serialization (save/restore not required)
- NO event bus/middleware system
- NO debug tools beyond basic logging
- NO configuration files (constructor params only)
- NO metrics/telemetry features
- NO touching other reviewer agents beyond BaseReviewerAgent
- NO async/parallel execution complexity beyond what AgentRuntime provides
- NO PAUSED state (STOPPED covers pause/interrupt)

---

## Verification Strategy

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> This is NOT conditional — it applies to EVERY task, regardless of test strategy.
>
> **FORBIDDEN** — acceptance criteria that require:
> - "User manually tests..." / "사용자가 직접 테스트..."
> - "User visually confirms..." / "사용자가 눈으로 확인..."
> - "User interacts with..." / "사용자가 직접 조작..."
> - "Ask user to verify..." / "사용자에게 확인 요청..."
> - ANY step where a human must perform an action
>
> **ALL verification is executed by the agent** using tools (Playwright, interactive_bash, curl, etc.). No exceptions.

### Test Decision
- **Infrastructure exists**: YES (bun test framework)
- **Automated tests**: TDD (test-first)
- **Framework**: bun test

### TDD Workflow

Each TODO follows RED-GREEN-REFACTOR:

**Task Structure:**
1. **RED**: Write failing test first
   - Test file: `tests/test_loop_fsm.py`
   - Test command: `bun test tests/test_loop_fsm.py --grep "test_name"`
   - Expected: FAIL (test exists, implementation doesn't)
2. **GREEN**: Implement minimum code to pass
   - Command: `bun test tests/test_loop_fsm.py --grep "test_name"`
   - Expected: PASS
3. **REFACTOR**: Clean up while keeping green
   - Command: `bun test tests/test_loop_fsm.py --grep "test_name"`
   - Expected: PASS (still)

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

> Whether TDD is enabled or not, EVERY task MUST include Agent-Executed QA Scenarios.
> - **With TDD**: QA scenarios complement unit tests at integration level
> - **Without TDD**: QA scenarios are the PRIMARY verification method
>
> These describe how the executing agent DIRECTLY verifies the deliverable
> by running it — importing modules, calling methods, asserting outputs.

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Python Library/Module** | Bash (bun/python REPL) | Import, instantiate, call methods, compare outputs |
| **FSM Logic** | Bash (bun test) | Run test suite, assert state transitions |
| **Integration** | Bash (bun test) | Run tests with BaseReviewerAgent integration |

**Each Scenario MUST Follow This Format:**

```
Scenario: [Descriptive name — what behavior is being verified]
  Tool: [Bash (bun test) / Bash (python REPL)]
  Preconditions: [What must be true before this scenario runs]
  Steps:
    1. [Exact action with specific function/method call]
    2. [Next action with expected intermediate state]
    3. [Assertion with exact expected value]
  Expected Result: [Concrete, observable outcome]
  Failure Indicators: [What would indicate failure]
  Evidence: [Output capture / test log path]
```

**Anti-patterns (NEVER write scenarios like this):**
- ❌ "Verify the FSM transitions correctly"
- ❌ "Check that todos are updated properly"
- ❌ "Test the retry logic works"
- ❌ "User confirms that..."

**Write scenarios like this instead:**
- ✅ `from iron_rook.fsm import LoopFSM; fsm = LoopFSM(); fsm.transition_to(LoopState.PLAN); assert fsm.current_state == LoopState.PLAN`
- ✅ `bun test tests/test_loop_fsm.py --grep "test_intake_to_plan"` → Assert exit code 0
- ✅ `fsm.add_todo("test"); assert len(fsm.todos) == 1; assert fsm.todos[0].status == "pending"`

**Evidence Requirements:**
- Test output captured for all test verifications
- Python REPL output captured for direct module testing
- All evidence referenced by specific pattern/command in acceptance criteria

---

## Execution Strategy

### Parallel Execution Waves

> This is a sequential implementation - tasks must be done in order due to dependencies.

```
Wave 1 (Start Immediately):
├── Task 1: Create FSM package structure and LoopState enum
└── Task 2: Implement Todo model with rich fields

Wave 2 (After Wave 1):
├── Task 3: Implement LoopFSM class skeleton
└── Task 4: Implement state transition logic

Wave 3 (After Wave 2):
├── Task 5: Implement sub-loop logic (PLAN → ACT → SYNTHESIZE)
├── Task 6: Implement goal achievement LLM check
└── Task 7: Implement retry logic for tool failures

├── Task 8: Implement async/parallel execution support
├── Task 9: Add state locking mechanisms
- [x] 10. Update tests for BaseReviewerAgent integration

  **What to do**:

Wave 5 (After Wave 4):
└── Task 11: Update tests for BaseReviewerAgent integration

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10 → Task 11
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | None |
| 2 | None | 3, 4 | 1 |
| 3 | 1, 2 | 4, 5 | None |
| 4 | 3 | 5, 6, 7 | 2 |
| 5 | 4 | 6, 7, 8 | None |
| 6 | 4 | 7, 8, 9 | 5 |
| 7 | 4 | 8, 9, 10 | 5, 6 |
| 8 | 5, 6, 7 | 9, 10 | None |
| 9 | 4, 7, 8 | 10, 11 | None |
| 10 | 8, 9 | 11 | None |
| 11 | 9, 10 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2 | task(category="quick", load_skills=[], run_in_background=false) |
| 2 | 3, 4 | task(category="unspecified-low", load_skills=[], run_in_background=false) |
| 3 | 5, 6, 7 | task(category="unspecified-low", load_skills=[], run_in_background=false) |
| 4 | 8, 9 | task(category="unspecified-low", load_skills=[], run_in_background=false) |
| 5 | 10, 11 | task(category="unspecified-low", load_skills=[], run_in_background=false) |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

- [x] 1. Create FSM package structure and LoopState enum

  **What to do**:
  - Create directory: `iron_rook/fsm/`
  - Create `__init__.py` with exports
  - Create `loop_state.py` with LoopState enum
  - Define states: INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED
  - Each state must have string value matching lowercase name

  **Must NOT do**:
  - Do NOT add any additional states beyond the six defined
  - Do NOT create PAUSED state (STOPPED covers pause/interrupt)
  - Do NOT modify dawn_kestrel's AgentState enum

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Simple file and enum creation, straightforward
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3, Task 4
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `dawn_kestrel/agents/state.py:AgentState` - Follow enum pattern for state definitions

  **API/Type References** (contracts to implement against):
  - N/A - This is a foundational enum

  **Test References** (testing patterns to follow):
  - `tests/test_state_machine.py:class TestAgentStateEnum` - Follow enum validation test patterns

  **Documentation References** (specs and requirements):
  - N/A - New implementation based on user requirements

  **External References** (libraries and frameworks):
  - N/A - Python enum built-in

  **WHY Each Reference Matters** (explain the relevance):
  - `AgentState` enum shows the pattern dawn_kestrel uses for state definitions, ensure consistency with codebase conventions

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_loop_fsm.py
  - [ ] Test covers: LoopState enum has all 6 states (INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED)
  - [ ] Test covers: All state values are lowercase strings
  - [ ] bun test tests/test_loop_fsm.py --grep "test_loop_state_enum" → PASS (1 test, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: LoopState enum has all required states
    Tool: Bash (python -c)
    Preconditions: iron_rook/fsm/loop_state.py exists
    Steps:
      1. python -c "from iron_rook.fsm.loop_state import LoopState; print([s.value for s in LoopState])"
      2. Assert: Output contains ["intake", "plan", "act", "synthesize", "done", "failed", "stopped"]
      3. Assert: len([s for s in LoopState]) == 6
    Expected Result: All 6 state values printed
    Evidence: Python REPL output captured

  Scenario: LoopState enum values are lowercase strings
    Tool: Bash (python -c)
    Preconditions: LoopState enum defined
    Steps:
      1. python -c "from iron_rook.fsm.loop_state import LoopState; print(LoopState.PLAN.value)"
      2. Assert: Output is "plan" (lowercase)
      3. python -c "from iron_rook.fsm.loop_state import LoopState; print(LoopState.ACT.value)"
      4. Assert: Output is "act" (lowercase)
    Expected Result: All state values are lowercase strings
    Evidence: Python REPL output captured

  Scenario: LoopState enum matches dawn_kestrel AgentState pattern
    Tool: Bash (python -c)
    Preconditions: Both enums defined
    Steps:
      1. python -c "from iron_rook.fsm.loop_state import LoopState; from dawn_kestrel.agents.state import AgentState; print(hasattr(AgentState, 'value'))"
      2. Assert: Output is True (AgentState has .value attribute)
      3. python -c "from iron_rook.fsm.loop_state import LoopState; print(hasattr(LoopState.PLAN, 'value'))"
      4. Assert: Output is True (LoopState has .value attribute matching pattern)
    Expected Result: LoopState follows same enum pattern as AgentState
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for enum verification
  - [ ] Test output for enum tests

  **Commit**: NO
  - Reason: Part of multi-task wave, will commit after Wave 1 completion

- [x] 2. Implement Todo model with rich fields

  **What to do**:
  - Create `iron_rook/fsm/todo.py` with Todo class
  - Fields: id (str), description (str), priority (int), status (str), metadata (dict), dependencies (list[str])
  - Status values: "pending", "in_progress", "done", "failed"
  - Implement `__repr__` for debugging
  - Follow pydantic BaseModel pattern from existing codebase

  **Must NOT do**:
  - Do NOT modify existing TodoWrite tool/schema
  - Do NOT add additional fields beyond those specified
  - Do NOT create persistence layer

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Simple data model creation, straightforward
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 3, Task 4
  - **Blocked By**: Task 1

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/contracts.py` - Look for pydantic BaseModel patterns used in codebase
  - `pydantic.BaseModel` - Follow standard pydantic patterns for data models

  **API/Type References** (contracts to implement against):
  - N/A - This is a new data model based on user requirements

  **Test References** (testing patterns to follow):
  - `tests/test_state_machine.py` - Look for how model/enum tests are structured

  **Documentation References** (specs and requirements):
  - User requirements: "rich model with id, description, priority, status, metadata, dependencies"

  **External References** (libraries and frameworks):
  - Pydantic documentation: https://docs.pydantic.dev/latest/usage/models/

  **WHY Each Reference Matters** (explain the relevance):
  - Pydantic patterns in codebase ensure Todo model integrates seamlessly with existing contracts and validation

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_loop_fsm.py
  - [ ] Test covers: Todo class creation with all required fields
  - [ ] Test covers: Status values validation (pending/in_progress/done/failed)
  - [ ] Test covers: Metadata and dependencies fields
  - [ ] bun test tests/test_loop_fsm.py --grep "test_todo_model" → PASS (4 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: Todo model accepts all required fields
    Tool: Bash (python -c)
    Preconditions: iron_rook/fsm/todo.py exists
    Steps:
      1. python -c "from iron_rook.fsm.todo import Todo; t = Todo(id='1', description='test', priority=1, status='pending', metadata={}, dependencies=[]); print('success')"
      2. Assert: Output is "success" (no validation error)
      3. python -c "from iron_rook.fsm.todo import Todo; print(Todo.model_fields)"
      4. Assert: Output contains 'id', 'description', 'priority', 'status', 'metadata', 'dependencies'
    Expected Result: Todo instance created successfully with all fields
    Evidence: Python REPL output captured

  Scenario: Todo status values are validated
    Tool: Bash (python -c)
    Preconditions: Todo model defined
    Steps:
      1. python -c "from iron_rook.fsm.todo import Todo; t = Todo(id='1', description='test', priority=1, status='invalid_status', metadata={}, dependencies=[])"
      2. Assert: ValidationError raised (status must be one of pending/in_progress/done/failed)
      3. python -c "from iron_rook.fsm.todo import Todo; t = Todo(id='1', description='test', priority=1, status='pending', metadata={}, dependencies=[]); print(t.status)"
      4. Assert: Output is "pending" (valid status accepted)
    Expected Result: Invalid status rejected, valid status accepted
    Evidence: Python REPL error output captured

  Scenario: Todo model follows pydantic BaseModel pattern
    Tool: Bash (python -c)
    Preconditions: Todo class inherits from pydantic.BaseModel
    Steps:
      1. python -c "from iron_rook.fsm.todo import Todo; print(Todo.__mro__)"
      2. Assert: pydantic.BaseModel in output (inheritance correct)
      3. python -c "from iron_rook.fsm.todo import Todo; import json; t = Todo(id='1', description='test', priority=1, status='pending', metadata={}, dependencies=[]); print(json.loads(t.model_dump_json()))"
      4. Assert: JSON serialization works (pydantic BaseModel method)
    Expected Result: Todo model follows pydantic BaseModel pattern
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for Todo model verification
  - [ ] Test output for Todo model tests

  **Commit**: NO
  - Reason: Part of multi-task wave, will commit after Wave 1 completion

- [x] 3. Implement LoopFSM class skeleton

  **What to do**:
  - Create `iron_rook/fsm/loop_fsm.py` with LoopFSM class
  - Constructor accepts: `max_retries` parameter (default=3), `agent_runtime` parameter
  - Initialize: `current_state = LoopState.INTAKE`, `todos = []`, `iteration_count = 0`
  - Implement: `transition_to(target_state)` method with validation
  - Implement: `can_transition_to(target_state)` method for preflight check
  - Implement: `reset()` method to return to INTAKE state
  - Follow existing AgentStateMachine pattern from dawn_kestrel

  **Must NOT do**:
  - Do NOT implement transition logic yet (Task 4)
  - Do NOT implement sub-loop logic yet (Task 5)
  - Do NOT implement retry logic yet (Task 7)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Class skeleton creation following existing patterns, straightforward
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 4
  - **Blocked By**: Task 1, Task 2

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `dawn_kestrel/agents/state.py:AgentStateMachine` - Follow class initialization and state management patterns
  - `dawn_kestrel/agents/state.py:AgentStateMachine.transition_to()` - Follow transition validation pattern
  - `dawn_kestrel/agents/state.py:AgentStateMachine.reset()` - Follow reset pattern

  **API/Type References** (contracts to implement against):
  - `dawn_kestrel/agents.state:AgentStateMachine.__init__()` - Constructor signature pattern
  - `dawn_kestrel/agents.state:AgentStateMachine.transition_to()` - Method signature for transitions
  - `dawn_kestrel/agents.state:AgentStateMachine.reset()` - Reset method pattern

  **Test References** (testing patterns to follow):
  - `tests/test_state_machine.py:class TestAgentStateMachine` - Follow state machine initialization and transition tests

  **Documentation References** (specs and requirements):
  - User requirements: "constructor parameter (max_retries passed when creating FSM instance)"

  **External References** (libraries and frameworks):
  - N/A - Following existing dawn_kestrel patterns

  **WHY Each Reference Matters** (explain the relevance):
  - AgentStateMachine shows the established pattern for state machine implementation in this codebase
  - Ensures drop-in replacement is consistent with existing conventions

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: LoopFSM initializes to INTAKE state
  - [ ] Test covers: Constructor accepts max_retries parameter (default=3)
  - [ ] Test covers: Constructor accepts agent_runtime parameter
  - [ ] Test covers: transition_to() method exists and is callable
  - [ ] Test covers: can_transition_to() method exists and returns bool
  - [ ] Test covers: reset() method exists and returns to INTAKE
  - [ ] bun test tests/test_loop_fsm.py --grep "test_loop_fsm_skeleton" → PASS (6 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: LoopFSM initializes to INTAKE state
    Tool: Bash (python -c)
    Preconditions: iron_rook/fsm/loop_fsm.py exists, LoopFSM class defined
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); print(fsm.current_state)"
      2. Assert: Output is LoopState.INTAKE
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); print(fsm.current_state.value)"
      4. Assert: Output is "intake"
    Expected Result: FSM starts in INTAKE state
    Evidence: Python REPL output captured

  Scenario: LoopFSM constructor accepts max_retries parameter
    Tool: Bash (python -c)
    Preconditions: LoopFSM class defined
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm1 = LoopFSM(max_retries=5); print(fsm1.max_retries)"
      2. Assert: Output is 5 (custom value)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm2 = LoopFSM(); print(fsm2.max_retries)"
      4. Assert: Output is 3 (default value)
    Expected Result: max_retries parameter accepted with default=3
    Evidence: Python REPL output captured

  Scenario: LoopFSM transition_to validates state transitions
    Tool: Bash (python -c)
    Preconditions: LoopFSM class with transition_to() method
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); result = fsm.transition_to(LoopState.DONE); print(result)"
      2. Assert: Result contains error (INTAKE→DONE is invalid transition)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); result = fsm.transition_to(LoopState.PLAN); print(fsm.current_state); print(result)"
      4. Assert: current_state is LoopState.PLAN, result indicates success
    Expected Result: Invalid transitions rejected, valid transitions succeed
    Evidence: Python REPL output captured

  Scenario: LoopFSM reset() returns to INTAKE state
    Tool: Bash (python -c)
    Preconditions: LoopFSM with current state not INTAKE
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); fsm.transition_to(LoopState.ACT); fsm.reset(); print(fsm.current_state.value)"
      2. Assert: Output is "intake" (state reset)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); fsm.transition_to(LoopState.ACT); print(fsm.iteration_count)"
      4. Assert: iteration_count is 0 (reset also clears iteration count)
    Expected Result: reset() returns to INTAKE state and clears iteration count
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for LoopFSM initialization
  - [ ] Test output for LoopFSM skeleton tests

  **Commit**: NO
  - Reason: Skeleton only, more implementation needed

- [x] 4. Implement state transition logic

  **What to do**:
  - Implement `FSM_TRANSITIONS` dictionary mapping valid transitions
  - Transitions:
    - INTAKE → [PLAN]
    - PLAN → [ACT]
    - ACT → [SYNTHESIZE]
    - SYNTHESIZE → [PLAN, DONE]
    - DONE → []
    - FAILED → []
    - STOPPED → []
  - Implement transition validation in `transition_to()` method
  - Throw descriptive error on invalid transitions

  **Must NOT do**:
  - Do NOT implement sub-loop decision logic (when SYNTHESIZE goes to PLAN vs DONE) yet (Task 5)
  - Do NOT add any additional transitions beyond those specified
  - Do NOT create PAUSED state transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Transition logic implementation following FSM patterns
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 5
  - **Blocked By**: Task 3

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `dawn_kestrel/agents/state.py:FSM_TRANSITIONS` - Follow transition map pattern
  - `dawn_kestrel/agents/state.py:AgentStateMachine.transition_to()` - Follow transition validation implementation

  **API/Type References** (contracts to implement against):
  - `dawn_kestrel/agents.state:FSM_TRANSITIONS` - Dictionary structure pattern

  **Test References** (testing patterns to follow):
  - `tests/test_state_machine.py:class TestValidTransitions` - Follow valid transition test patterns
  - `tests/test_state_machine.py:class TestInvalidTransitions` - Follow invalid transition test patterns

  **Documentation References** (specs and requirements):
  - N/A - Transition pattern based on user requirements and Metis guardrails

  **External References** (libraries and frameworks):
  - N/A - Following existing dawn_kestrel patterns

  **WHY Each Reference Matters** (explain the relevance):
  - FSM_TRANSITIONS in dawn_kestrel shows the established pattern for defining valid state transitions
  - Ensures consistency with existing codebase conventions

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: All valid transitions succeed
  - [ ] Test covers: All invalid transitions fail with error
  - [ ] Test covers: SYNTHESIZE can transition to both PLAN and DONE
  - [ ] Test covers: Terminal states (DONE, FAILED, STOPPED) have empty transition sets
  - [ ] bun test tests/test_loop_fsm.py --grep "test_state_transitions" → PASS (10 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: Valid state transitions succeed
    Tool: Bash (python -c)
    Preconditions: LoopFSM with FSM_TRANSITIONS defined
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.PLAN); print(fsm.current_state.value)"
      2. Assert: Output is "plan" (INTAKE→PLAN succeeded)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.PLAN); fsm.transition_to(LoopState.ACT); print(fsm.current_state.value)"
      4. Assert: Output is "act" (PLAN→ACT succeeded)
    Expected Result: All valid transitions succeed
    Evidence: Python REPL output captured

  Scenario: Invalid state transitions fail with error
    Tool: Bash (python -c)
    Preconditions: LoopFSM with transition validation
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); import sys; result = fsm.transition_to(LoopState.DONE); sys.exit(0) if not result.is_err() else None; print(result.error)"
      2. Assert: Error contains "Invalid transition" or "intake -> done" (rejected)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.INTAKE); fsm.transition_to(LoopState.ACT); import sys; result = fsm.transition_to(LoopState.PLAN); sys.exit(0) if not result.is_err() else None; print(result.error)"
      4. Assert: Error contains "Invalid transition" or "act -> plan" (not valid from ACT)
    Expected Result: Invalid transitions throw descriptive errors
    Evidence: Python REPL error output captured

  Scenario: SYNTHESIZE can transition to both PLAN and DONE
    Tool: Bash (python -c)
    Preconditions: LoopFSM with valid transitions
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.INTAKE); fsm.transition_to(LoopState.PLAN); fsm.transition_to(LoopState.ACT); fsm.transition_to(LoopState.SYNTHESIZE); fsm.transition_to(LoopState.PLAN); print(fsm.current_state.value)"
      2. Assert: Output is "plan" (SYNTHESIZE→PLAN succeeded)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.INTAKE); fsm.transition_to(LoopState.PLAN); fsm.transition_to(LoopState.ACT); fsm.transition_to(LoopState.SYNTHESIZE); fsm.transition_to(LoopState.DONE); print(fsm.current_state.value)"
      4. Assert: Output is "done" (SYNTHESIZE→DONE succeeded)
    Expected Result: SYNTHESIZE can go to PLAN (loop) or DONE (exit)
    Evidence: Python REPL output captured

  Scenario: Terminal states have no valid transitions
    Tool: Bash (python -c)
    Preconditions: LoopFSM with terminal states defined
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.INTAKE); fsm.transition_to(LoopState.PLAN); fsm.transition_to(LoopState.ACT); fsm.transition_to(LoopState.SYNTHESIZE); fsm.transition_to(LoopState.DONE); import sys; result = fsm.transition_to(LoopState.ACT); sys.exit(0) if not result.is_err() else None; print(result.error)"
      2. Assert: Error contains "Invalid transition" or "done has no valid transitions" (terminal state)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.loop_state import LoopState; fsm = LoopFSM(); fsm.transition_to(LoopState.INTAKE); fsm.transition_to(LoopState.PLAN); fsm.transition_to(LoopState.ACT); fsm.transition_to(LoopState.SYNTHESIZE); fsm.transition_to(LoopState.FAILED); import sys; result = fsm.transition_to(LoopState.ACT); sys.exit(0) if not result.is_err() else None; print(result.error)"
      4. Assert: Error contains "Invalid transition" or "failed has no valid transitions" (terminal state)
    Expected Result: Terminal states cannot transition anywhere
    Evidence: Python REPL error output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for transition logic verification
  - [ ] Test output for state transition tests

  **Commit**: NO
  - Reason: Transition logic only, sub-loop not yet implemented

- [x] 5. Implement sub-loop logic (PLAN → ACT → SYNTHESIZE)

  **What to do**:
  - Implement main loop method `run_loop(context)` that orchestrates PLAN → ACT → SYNTHESIZE cycle
  - After SYNTHESIZE: call LLM to check if goal achieved
  - If goal achieved: transition to DONE
  - If goal not achieved: transition back to PLAN
  - Increment `iteration_count` on each full cycle
  - Add infinite loop prevention: throw error if `iteration_count > MAX_ITERATIONS` (default=10)
  - Store context/data across loop iterations

  **Must NOT do**:
  - Do NOT implement tool execution yet (Task 6, 7)
  - Do NOT implement retry logic yet (Task 7)
  - Do NOT make decisions about when to call external LLM for goal check (that's part of state behavior)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Core loop logic implementation, moderate complexity
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 6
  - **Blocked By**: Task 4

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/README.md` - Section "2) The standard agent loop (control flow)" describes loop patterns

  **API/Type References** (contracts to implement against):
  - `dawn_kestrel/core/agent_runtime` - AgentRuntime interface for LLM calls

  **Test References** (testing patterns to follow):
  - N/A - Loop logic test patterns to be created

  **Documentation References** (specs and requirements):
  - User requirements: "intake → plan → act → synthesize → done. Where plan → act → synthesize is a sub-loop that repeats"

  **External References** (libraries and frameworks):
  - N/A - Loop pattern based on user requirements

  **WHY Each Reference Matters** (explain the relevance):
  - README.md section 2 describes the standard agent loop pattern that informs the sub-loop structure

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: Main loop cycles through PLAN → ACT → SYNTHESIZE
  - [ ] Test covers: After SYNTHESIZE, transitions to PLAN if goal not achieved
  - [ ] Test covers: After SYNTHESIZE, transitions to DONE if goal achieved
  - [ ] Test covers: iteration_count increments on each full cycle
  - [ ] Test covers: MAX_ITERATIONS prevents infinite loops
  - [ ] Test covers: Context is preserved across loop iterations
  - [ ] bun test tests/test_loop_fsm.py --grep "test_sub_loop_logic" → PASS (7 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: Main loop cycles through PLAN → ACT → SYNTHESIZE → PLAN (goal not achieved)
    Tool: Bash (bun test)
    Preconditions: LoopFSM with sub-loop implemented, AgentRuntime mock configured
    Steps:
      1. bun test tests/test_loop_fsm.py --grep "test_loop_cycles_when_goal_not_achieved"
      2. Assert: Exit code is 0 (test passes)
      3. Read test file to verify it cycles 3 times then reaches DONE (goal check returns True on 3rd iteration)
    Expected Result: Loop cycles correctly until goal achieved, then transitions to DONE
    Evidence: Test output captured

  Scenario: Main loop exits early when goal achieved
    Tool: Bash (bun test)
    Preconditions: LoopFSM with sub-loop implemented
    Steps:
      1. bun test tests/test_loop_fsm.py --grep "test_loop_exits_when_goal_achieved"
      2. Assert: Exit code is 0 (test passes)
      3. Read test file to verify it cycles only 1 time (goal check returns True immediately)
    Expected Result: Loop exits to DONE immediately when goal is achieved
    Evidence: Test output captured

  Scenario: iteration_count increments on each full cycle
    Tool: Bash (python -c)
    Preconditions: LoopFSM with run_loop() method
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); print('Iteration 1:'); fsm.run_loop({'goal_check': False}); print(f'Iterations after: {fsm.iteration_count}')"
      2. Assert: Output contains "Iterations after: 1"
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); print('Iteration 2:'); fsm.run_loop({'goal_check': False}); print(f'Iterations after: {fsm.iteration_count}')"
      4. Assert: Output contains "Iterations after: 2"
    Expected Result: iteration_count increments by 1 on each full cycle
    Evidence: Python REPL output captured

  Scenario: MAX_ITERATIONS prevents infinite loops
    Tool: Bash (python -c)
    Preconditions: LoopFSM with MAX_ITERATIONS=10
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(max_iterations=5); import sys; fsm.run_loop({'goal_check': False}); sys.exit(0) if fsm.current_state.value != 'failed' else None; print(f'Final state: {fsm.current_state.value}, iterations: {fsm.iteration_count}')"
      2. Assert: Final state is 'failed' or 'stopped' (max iterations exceeded)
      3. Assert: iteration_count is 5 (max reached)
    Expected Result: Loop fails gracefully when max iterations exceeded
    Evidence: Python REPL error output captured
  ```

  **Evidence to Capture:**
  - [ ] Test output for sub-loop logic tests
  - [ ] Python REPL output for iteration tracking

  **Commit**: NO
  - Reason: Sub-loop skeleton only, tool execution not yet implemented

- [x] 6. Implement goal achievement LLM check

  **What to do**:
  - Implement `_check_goal_achievement(context)` method that uses AgentRuntime for LLM call
  - Call LLM with prompt: "Based on the following progress, has the original goal been achieved? [provide todos status and context]"
  - Parse LLM response to extract True/False or similar boolean
  - Return result to loop logic for deciding PLAN vs DONE transition
  - Handle LLM errors gracefully (treat as "goal not achieved")

  **Must NOT do**:
  - Do NOT implement retry logic for LLM failures yet (part of tool failure handling)
  - Do NOT create complex prompt templates (keep simple question format)
  - Do NOT add logging beyond basic level

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: LLM integration with existing AgentRuntime
  - **Skills**: None required (using AgentRuntime directly)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 7
  - **Blocked By**: Task 5

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/base.py:SimpleReviewAgentRunner` - Follow how AgentRuntime is used for LLM calls

  **API/Type References** (contracts to implement against):
  - `dawn_kestrel/core/agent_runtime:AgentRuntime.call_llm()` - LLM call interface

  **Test References** (testing patterns to follow):
  - N/A - LLM integration test patterns to be created

  **Documentation References** (specs and requirements):
  - User requirements: "Goal achievement check (LLM check after synthesize determines if goal met)"

  **External References** (libraries and frameworks):
  - N/A - Using existing AgentRuntime interface

  **WHY Each Reference Matters** (explain the relevance):
  - SimpleReviewAgentRunner shows how to use AgentRuntime for LLM calls in this codebase

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: _check_goal_achievement() method exists
  - [ ] Test covers: LLM call returns True for achieved goal
  - [ ] Test covers: LLM call returns False for unachieved goal
  - [ ] Test covers: LLM errors are handled gracefully
  - [ ] bun test tests/test_loop_fsm.py --grep "test_goal_achievement" → PASS (4 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: Goal achievement check returns True for completed todos
    Tool: Bash (python -c)
    Preconditions: LoopFSM with _check_goal_achievement() method, AgentRuntime mock configured
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.todo import Todo; fsm = LoopFSM(); fsm.todos = [Todo(id='1', description='task1', priority=1, status='done', metadata={}, dependencies=[])]; result = fsm._check_goal_achievement({'todos': fsm.todos}); print(f'Goal achieved: {result}')"
      2. Assert: Output is True (all todos done indicates goal achieved)
    Expected Result: Method returns True when todos indicate completion
    Evidence: Python REPL output captured

  Scenario: Goal achievement check returns False for pending todos
    Tool: Bash (python -c)
    Preconditions: LoopFSM with _check_goal_achievement() method
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; from iron_rook.fsm.todo import Todo; fsm = LoopFSM(); fsm.todos = [Todo(id='1', description='task1', priority=1, status='pending', metadata={}, dependencies=[])]; result = fsm._check_goal_achievement({'todos': fsm.todos}); print(f'Goal achieved: {result}')"
      2. Assert: Output is False (pending todos indicate goal not achieved)
    Expected Result: Method returns False when todos indicate work remaining
    Evidence: Python REPL output captured

  Scenario: Goal achievement check handles LLM errors gracefully
    Tool: Bash (python -c)
    Preconditions: LoopFSM with AgentRuntime mock that throws error
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; import logging; logging.basicConfig(level=logging.ERROR); fsm = LoopFSM(); fsm._agent_runtime = None; result = fsm._check_goal_achievement({}); print(f'Goal check result: {result}')"
      2. Assert: Output is False (error treated as 'goal not achieved')
      3. Check stderr for logged error about LLM failure
    Expected Result: LLM errors result in False, allowing loop to continue
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for goal achievement checks
  - [ ] Test output for goal achievement tests

  **Commit**: NO
  - Reason: Goal check only, retry logic not yet implemented

- [x] 7. Implement retry logic for tool failures

  **What to do**:
  - Implement retry counter for each action in ACT phase
  - On tool failure: increment retry count, retry same action
  - If retry_count >= max_retries: transition to FAILED state
  - Preserve original error context in FAILED state
  - Reset retry count on successful action execution

  **Must NOT do**:
  - Do NOT implement complex fallback strategies (only retry same action)
  - Do NOT add retry logic for LLM goal checks (part of Task 6)
  - Do NOT create retry configuration files (constructor param only)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Retry logic with configurable max_retries
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 8
  - **Blocked By**: Task 6

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/base.py:SimpleReviewAgentRunner.run_with_retry()` - Follow retry patterns if they exist

  **API/Type References** (contracts to implement against):
  - N/A - Retry logic implementation based on user requirements

  **Test References** (testing patterns to follow):
  - N/A - Retry logic test patterns to be created

  **Documentation References** (specs and requirements):
  - User requirements: "Retry with same action (up to retry limit)"

  **External References** (libraries and frameworks):
  - N/A - Simple retry pattern based on requirements

  **WHY Each Reference Matters** (explain the relevance):
  - Ensures retry logic follows user requirements and maintains error context

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: Tool failure triggers retry
  - [ ] Test covers: Retry count increments on each failure
  - [ ] Test covers: Success resets retry count
  - [ ] Test covers: After max_retries, transition to FAILED state
  - [ ] Test covers: Original error context preserved in FAILED state
  - [ ] bun test tests/test_loop_fsm.py --grep "test_retry_logic" → PASS (5 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: Tool failure triggers retry
    Tool: Bash (python -c)
    Preconditions: LoopFSM with retry logic, AgentRuntime mock that fails 2 times
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(max_retries=3); fsm._agent_runtime = MockRuntime(fail_count=2); import logging; fsm.run_loop({}); print(f'Retries used: {len([c for c in fsm._retry_log if c])}')"
      2. Assert: Output contains 'Retries used: 2' (retried before success)
      3. Assert: Final state is DONE (not FAILED, retries within limit)
    Expected Result: Tool failures trigger retries until success or max_retries
    Evidence: Python REPL output captured

  Scenario: Retry count increments on each failure
    Tool: Bash (python -c)
    Preconditions: LoopFSM with retry logic
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(max_retries=3); fsm._agent_runtime = MockRuntime(fail_count=0); fsm.run_loop({'force_action': 'failing_action'}); print(f'Retry count: {fsm._current_retry_count}')"
      2. Assert: Output is 1 (first failure)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(max_retries=3); fsm._agent_runtime = MockRuntime(fail_count=0); fsm.run_loop({'force_action': 'failing_action'}); print(f'Retry count: {fsm._current_retry_count}')"
      4. Assert: Output is 1 (same action retried, count reset on new action)
    Expected Result: Retry count tracks per-action retries
    Evidence: Python REPL output captured

  Scenario: After max_retries, transition to FAILED state
    Tool: Bash (python -c)
    Preconditions: LoopFSM with max_retries=2, AgentRuntime mock that always fails
    Steps:
      1. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(max_retries=2); fsm._agent_runtime = MockRuntime(always_fail=True); fsm.run_loop({}); print(f'Final state: {fsm.current_state.value}')"
      2. Assert: Final state is "failed" (max retries exceeded)
      3. Assert: fsm._error_context is not None (error preserved)
    Expected Result: Max retries causes transition to FAILED with error preserved
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for retry logic verification
  - [ ] Test output for retry tests

  **Commit**: NO
  - Reason: Retry logic only, async support not yet implemented

- [x] 8. Implement async/parallel execution support

  **What to do**:
  - Implement state locking using asyncio.Lock or threading.Lock
  - Ensure ACT phase can handle multiple concurrent tool executions if AgentRuntime supports it
  - Serialize state transitions (only one transition at a time)
  - Allow parallel tool execution within ACT phase while maintaining state consistency
  - Use async/await patterns if AgentRuntime is async
  - Add `run_loop_async()` method that returns awaitable future

  **Must NOT do**:
  - Do NOT add complex concurrency primitives beyond simple locking
  - Do NOT implement event-driven execution (keep loop-driven)
  - Do NOT change the fundamental loop pattern (async is implementation detail)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Async/parallel execution support required by user
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 9
  - **Blocked By**: Task 7

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/README.md` - Check for async patterns mentioned
  - Python asyncio documentation for Lock usage patterns

  **API/Type References** (contracts to implement against):
  - `dawn_kestrel/core/agent_runtime` - Check if methods are async or sync

  **Test References** (testing patterns to follow):
  - N/A - Async execution test patterns to be created

  **Documentation References** (specs and requirements):
  - User requirements: "Async/parallel execution support"

  **External References** (libraries and frameworks):
  - Python asyncio documentation: https://docs.python.org/3/library/asyncio-sync.html#locks

  **WHY Each Reference Matters** (explain the relevance):
  - Ensures async implementation follows Python best practices

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: State locking prevents concurrent state mutations
  - [ ] Test covers: run_loop_async() method exists and is awaitable
  - [ ] Test covers: Parallel tool executions within ACT phase work correctly
  - [ ] Test covers: State transitions are serialized (only one at a time)
  - [ ] bun test tests/test_loop_fsm.py --grep "test_async_execution" → PASS (4 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: State locking prevents concurrent state mutations
    Tool: Bash (python -c)
    Preconditions: LoopFSM with state locking implemented
    Steps:
      1. python -c "import asyncio; from iron_rook.fsm.loop_fsm import LoopFSM; async def test_concurrent(): fsm = LoopFSM(); tasks = [asyncio.create_task(fsm.transition_to(LoopState.PLAN)) for _ in range(3)]; await asyncio.gather(*tasks); return fsm.current_state; result = asyncio.run(test_concurrent()); print(f'Final state: {result.value}')"
      2. Assert: Output is "plan" (concurrent transitions serialized by lock)
    Expected Result: State locking ensures only one transition at a time
    Evidence: Python REPL output captured

  Scenario: run_loop_async() method exists and is awaitable
    Tool: Bash (python -c)
    Preconditions: LoopFSM with async run_loop method
    Steps:
      1. python -c "import asyncio; from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); result = asyncio.run(fsm.run_loop_async({'goal_check': True})); print(f'Final state: {result.value}')"
      2. Assert: Output is "done" (async method works correctly)
    Expected Result: Async run_loop method executes correctly
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for async execution verification
  - [ ] Test output for async tests

  **Commit**: NO
  - Reason: Async support only, BaseReviewerAgent integration not yet done

- [x] 9. Add state locking mechanisms

  **What to do**:
  - Implement `_state_lock` as asyncio.Lock or threading.Lock
  - Protect all state mutations (transitions, todo updates) with lock
  - Ensure lock is reentrant-safe (use same lock instance for all FSM instances)
  - Document locking strategy in docstrings

  **Must NOT do**:
  - Do NOT use complex locking primitives beyond standard library
  - Do NOT create deadlock-prone patterns (multiple locks)
  - Do NOT lock around read operations (only write operations)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: State locking for concurrent access protection
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 10
  - **Blocked By**: Task 8

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - New state locking implementation

  **API/Type References** (contracts to implement against):
  - N/A - State locking based on standard library

  **Test References** (testing patterns to follow):
  - N/A - State locking test patterns to be created

  **Documentation References** (specs and requirements):
  - User requirements: "Async/parallel execution support" (locking implied)

  **External References** (libraries and frameworks):
  - Python threading.Lock documentation: https://docs.python.org/3/library/threading.html#lock-objects
  - Python asyncio.Lock documentation: https://docs.python.org/3/library/asyncio-sync.html#locks

  **WHY Each Reference Matters** (explain the relevance):
  - Ensures locking implementation follows Python best practices and avoids common pitfalls

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: _state_lock exists and is initialized
  - [ ] Test covers: State mutations are protected by lock
  - [ ] Test covers: Concurrent operations are serialized
  - [ ] bun test tests/test_loop_fsm.py --grep "test_state_locking" → PASS (3 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: State mutations are protected by lock
    Tool: Bash (python -c)
    Preconditions: LoopFSM with state locking
    Steps:
      1. python -c "import threading; from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); results = []; for _ in range(10): t = threading.Thread(target=lambda: fsm.transition_to(LoopState.PLAN)); t.start(); results.append(t); [r.join() for r in results]; print(f'Concurrent mutations: {len(results)}'); print(f'Final state: {fsm.current_state.value}')"
      2. Assert: Output contains 'Concurrent mutations: 10' (all operations attempted)
      3. Assert: Final state is "plan" (only one transition succeeded, others blocked by lock)
    Expected Result: Lock prevents concurrent state corruption
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for state locking verification
  - [ ] Test output for locking tests

  **Commit**: NO
  - Reason: Locking only, BaseReviewerAgent integration not yet done

└── Task 11: Update tests for BaseReviewerAgent integration

  **What to do**:
  - Modify `iron_rook/review/base.py` BaseReviewerAgent class
  - Replace `self._state_machine = AgentStateMachine(...)` with `self._fsm = LoopFSM(...)`
  - Pass `max_retries` parameter to LoopFSM (optional, can be None)
  - Pass `agent_runtime` to LoopFSM if available in BaseReviewerAgent
  - Update `state` property to return `self._fsm.current_state`
  - Update `_transition_to()` method to use `self._fsm.transition_to()`
  - Update `get_valid_transitions()` to return LoopFSM.FSM_TRANSITIONS
  - Ensure backward compatibility for methods that reference `_state_machine` (add alias if needed)
  - Do NOT modify dawn_kestrel import (use existing import)

  **Must NOT do**:
  - Do NOT modify dawn_kestrel's AgentState or AgentStateMachine imports
  - Do NOT break existing agents that inherit from BaseReviewerAgent (must be drop-in compatible)
  - Do NOT change BaseReviewerAgent's public API method signatures

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Integration with existing BaseReviewerAgent, careful refactoring
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Task 11
  - **Blocked By**: Task 9

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/base.py:BaseReviewerAgent.__init__()` - Follow initialization pattern
  - `iron_rook/review/base.py:BaseReviewerAgent.state` property - Follow state property pattern
  - `iron_rook/review/base.py:BaseReviewerAgent._transition_to()` - Follow transition method pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/base.py:BaseReviewerAgent` - Public API to maintain compatibility

  **Test References** (testing patterns to follow):
  - `tests/test_state_machine.py` - Look for how BaseReviewerAgent tests are structured

  **Documentation References** (specs and requirements):
  - User requirements: "Update base class (BaseReviewerAgent)"

  **External References** (libraries and frameworks):
  - N/A - Refactoring existing code

  **WHY Each Reference Matters** (explain the relevance):
  - Ensures BaseReviewerAgent integration is drop-in compatible and maintains backward compatibility

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/test_base_reviewer_integration.py
  - [ ] Test covers: BaseReviewerAgent initializes with LoopFSM instead of AgentStateMachine
  - [ ] Test covers: state property returns LoopFSM.current_state
  - [ ] Test covers: _transition_to() delegates to LoopFSM.transition_to()
  - [ ] Test covers: get_valid_transitions() returns LoopFSM.FSM_TRANSITIONS
  - [ ] Test covers: Backward compatibility maintained (existing methods still work)
  - [ ] bun test tests/test_base_reviewer_integration.py --grep "test_base_reviewer_loop_fsm_integration" → PASS (5 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with python -c):**

  ```
  Scenario: BaseReviewerAgent initializes with LoopFSM
    Tool: Bash (python -c)
    Preconditions: iron_rook/review/base.py modified to use LoopFSM
    Steps:
      1. python -c "from iron_rook.review.base import BaseReviewerAgent; from iron_rook.fsm.loop_state import LoopState; class TestAgent(BaseReviewerAgent): pass; agent = TestAgent(); print(f'State type: {type(agent.state).__name__}'); print(f'State value: {agent.state.value}')"
      2. Assert: Output contains 'LoopState' (using new FSM)
      3. Assert: State value is in ['intake', 'plan', 'act', 'synthesize', 'done', 'failed', 'stopped']
    Expected Result: BaseReviewerAgent uses LoopFSM instead of AgentStateMachine
    Evidence: Python REPL output captured

  Scenario: state property returns LoopFSM.current_state
    Tool: Bash (python -c)
    Preconditions: BaseReviewerAgent with updated state property
    Steps:
      1. python -c "from iron_rook.review.base import BaseReviewerAgent; class TestAgent(BaseReviewerAgent): pass; agent = TestAgent(); initial_state = agent.state; print(f'Initial state: {initial_state.value}')"
      2. Assert: Output is "intake" (LoopFSM initial state)
      3. python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); fsm.transition_to(LoopState.PLAN); from iron_rook.review.base import BaseReviewerAgent; class TestAgent(BaseReviewerAgent): def __init__(self): super().__init__(self._fsm=LoopFSM()); agent = TestAgent(); print(f'State from property: {agent.state.value}')"
      4. Assert: Output is "plan" (property returns LoopFSM.current_state)
    Expected Result: state property correctly returns LoopFSM.current_state
    Evidence: Python REPL output captured
  ```

  **Evidence to Capture:**
  - [ ] Python REPL output for BaseReviewerAgent integration
  - [ ] Test output for integration tests

  **Commit**: YES
  - Message: `refactor(base): replace dawn_kestrel FSM with LoopFSM for intake→plan→act→synthesize→done loop`
  - Files: `iron_rook/fsm/__init__.py`, `iron_rook/fsm/loop_state.py`, `iron_rook/fsm/todo.py`, `iron_rook/fsm/loop_fsm.py`, `iron_rook/review/base.py`
  - Pre-commit: `bun test tests/test_loop_fsm.py && bun test tests/test_base_reviewer_integration.py`

- [x] 11. Update tests for BaseReviewerAgent integration

  **What to do**:
  - Update `tests/test_loop_fsm.py` with integration tests for BaseReviewerAgent
  - Add tests verifying BaseReviewerAgent uses LoopFSM correctly
  - Add tests for backward compatibility with existing agents
  - Add tests for todo management through BaseReviewerAgent interface
  - Ensure all tests follow TDD pattern

  **Must NOT do**:
  - Do NOT modify other reviewer agents (security, architecture, etc.)
  - Do NOT add integration tests for dawn_kestrel FSM (focus on LoopFSM)
  - Do NOT create tests requiring manual verification

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Test updates only, straightforward additions
  - **Skills**: None required

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: None (final task)
  - **Blocked By**: Task 10

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `tests/test_state_machine.py` - Follow existing test patterns for BaseReviewerAgent

  **API/Type References** (contracts to implement against):
  - N/A - Test file additions only

  **Test References** (testing patterns to follow):
  - `tests/test_state_machine.py` - Follow existing test structure

  **Documentation References** (specs and requirements):
  - N/A - Test updates following existing patterns

  **External References** (libraries and frameworks):
  - N/A - Test patterns from existing test suite

  **WHY Each Reference Matters** (explain the relevance):
  - Ensures tests follow existing patterns and maintain consistency

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **If TDD (tests enabled):**
  - [ ] Test file updated: tests/test_loop_fsm.py
  - [ ] Test covers: BaseReviewerAgent integration tests added
  - [ ] Test covers: Backward compatibility with existing agents verified
  - [ ] Test covers: All integration tests pass
  - [ ] bun test tests/test_loop_fsm.py --grep "test_integration" → PASS (5 tests, 0 failures)
  - [ ] bun test tests/test_loop_fsm.py → ALL tests pass (no grep needed, full suite)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > Write MULTIPLE named scenarios per task: happy path AND failure cases.
  > Each scenario = exact tool + steps with real data + evidence path.

  **Example — Python Library/Module (bash with bun test):**

  ```
  Scenario: All integration tests pass
    Tool: Bash (bun test)
    Preconditions: tests/test_loop_fsm.py with integration tests
    Steps:
      1. bun test tests/test_loop_fsm.py
      2. Assert: Exit code is 0 (all tests passed)
      3. Assert: Output contains "N tests, 0 failures" (success pattern)
    Expected Result: Complete test suite passes
    Evidence: Test output captured

  Scenario: Specific integration tests can be run individually
    Tool: Bash (bun test)
    Preconditions: tests/test_loop_fsm.py with grep-able test names
    Steps:
      1. bun test tests/test_loop_fsm.py --grep "test_base_reviewer_loop_fsm_integration"
      2. Assert: Exit code is 0 (specific tests passed)
      3. Assert: Output contains "5 tests, 0 failures" (test count)
    Expected Result: Integration tests run successfully with grep filter
    Evidence: Test output captured
  ```

  **Evidence to Capture:**
  - [ ] Full test suite output
  - [ ] Individual test run output for integration tests

  **Commit**: YES
  - Message: `test(fsm): add integration tests for BaseReviewerAgent with LoopFSM`
  - Files: `tests/test_loop_fsm.py`
  - Pre-commit: `bun test tests/test_loop_fsm.py`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|--------------|
| Wave 1 (Tasks 1-2) | `feat(fsm): create FSM package with LoopState enum and Todo model` | `iron_rook/fsm/__init__.py`, `iron_rook/fsm/loop_state.py`, `iron_rook/fsm/todo.py` | `bun test tests/test_loop_fsm.py --grep "test_loop_state_enum\|test_todo_model"` |
| Wave 2-3 (Tasks 3-4) | `feat(fsm): implement LoopFSM class with state transitions` | `iron_rook/fsm/loop_fsm.py` | `bun test tests/test_loop_fsm.py --grep "test_loop_fsm_skeleton\|test_state_transitions"` |
| Wave 4 (Tasks 5-7) | `feat(fsm): implement sub-loop logic with goal check and retry` | `iron_rook/fsm/loop_fsm.py` | `bun test tests/test_loop_fsm.py --grep "test_sub_loop_logic\|test_goal_achievement\|test_retry_logic"` |
| Wave 4 (Tasks 8-9) | `feat(fsm): add async/parallel support with state locking` | `iron_rook/fsm/loop_fsm.py` | `bun test tests/test_loop_fsm.py --grep "test_async_execution\|test_state_locking"` |
| Wave 5 (Task 10) | `refactor(base): replace dawn_kestrel FSM with LoopFSM` | `iron_rook/review/base.py` | `bun test tests/test_base_reviewer_integration.py --grep "test_base_reviewer_loop_fsm_integration"` |
| Wave 5 (Task 11) | `test(fsm): add integration tests for BaseReviewerAgent` | `tests/test_loop_fsm.py` | `bun test tests/test_loop_fsm.py` |

---

## Success Criteria

### Verification Commands
```bash
# Verify FSM package structure exists
ls -la iron_rook/fsm/

# Verify all tests pass
bun test tests/test_loop_fsm.py

# Verify BaseReviewerAgent integration
python -c "from iron_rook.review.base import BaseReviewerAgent; from iron_rook.fsm.loop_fsm import LoopFSM; print('Integration OK')"

# Verify FSM can run full loop
python -c "from iron_rook.fsm.loop_fsm import LoopFSM; fsm = LoopFSM(); fsm.run_loop({'goal_check': True}); print(f'Final state: {fsm.current_state.value}')"
```

### Final Checklist
- [x] All "Must Have" present
- [x] All "Must NOT Have" absent
- [x] All tests pass (bun test)
- [x] FSM successfully transitions: INTAKE → PLAN → (ACT → SYNTHESIZE)* → DONE
- [x] Sub-loop repeats until goal achieved
- [x] Tool failures trigger retries up to max_retries
- [x] Async/parallel execution supported
- [x] State locking prevents concurrent mutations
- [x] BaseReviewerAgent uses LoopFSM as drop-in replacement
- [x] No modifications to dawn_kestrel's AgentState or AgentStateMachine
