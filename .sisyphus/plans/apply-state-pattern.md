# Apply State Pattern and Result Pattern to Iron Rook Agents

## TL;DR

> **Quick Summary**: Create dawn-kestrel State Pattern module from scratch, import Result pattern from dawn_kestrel, then integrate both into all review agents
> **Deliverables**:
> - `dawn_kestrel/agents/state.py` - NEW: AgentState enum and AgentStateMachine class (created from scratch)
> - Updated `iron_rook/review/base.py` - Import Result from dawn_kestrel.core.result
> - Updated `iron_rook/review/base.py` - Import AgentState and AgentStateMachine from dawn_kestrel.agents.state
> - Updated `iron_rook/review/base.py` - Integrate both patterns into BaseReviewerAgent
> - Updated all 11 active agent files with FSM transitions
> - Updated `iron_rook/review/agents/__init__.py` - Export new imports
>
> **Estimated Effort**: Large
> **Parallel Execution**: NO - sequential due to dependencies
> **Critical Path**: Create state.py → Update base.py → Update agents → Update exports → Test

---

## Context

### Original Request
Apply dawn-kestrel State Pattern (FSM) and Result Pattern to all agents in iron-rook/review/agents/. Pattern includes:

1. **State Pattern**: `AgentState` enum (IDLE, INITIALIZING, READY, RUNNING, PAUSED, COMPLETED, FAILED) and `AgentStateMachine` class with transition validation
2. **Result Pattern**: `Result` union type with `Ok`, `Err`, and `Pass` variants for explicit error handling

### Interview Summary

**Key Discussions**:
- **FSM Approach**: Confirmed "Common states with custom transitions per agent" - All agents share the same AgentState enum but define their own valid transitions based on workflow
- **Result Pattern**: Confirmed "Use full dawn-kestrel Result/Ok/Err/Pass pattern" - User wants railway-oriented programming style
- **Integration**: Confirmed "Integrate state machine into BaseReviewerAgent" - State machine should be inherited capability in base class
- **Updated Source**: User confirmed dawn_kestrel was updated to `/Users/parkersligting/develop/pt/worktrees/harness-agent-rework`

**Research Findings**:
- **Result Pattern EXISTS**: Found `dawn_kestrel/core/result.py` with Result, Ok, Err, Pass types
- **State Pattern MISSING**: `dawn_kestrel/agents/state.py` does NOT exist - must create from scratch
- **AgentState Structure**: Create enum with IDLE, INITIALIZING, READY, RUNNING, PAUSED, COMPLETED, FAILED states
- **AgentStateMachine Structure**: Create class with transition_to() method and _is_valid_transition() validation
- **Current Agent Count**: 11 active agents (SecurityReviewer is deprecated, excluded from updates)
- **All agents use**: `_execute_review_with_runner()` which wraps `SimpleReviewAgentRunner` from dawn-kestrel

### Metis Review

**Identified Gaps** (addressed in plan):

**Critical Questions Clarified**:
1. **Where to create state module?** Create `dawn_kestrel/agents/state.py` in `/Users/parkersligting/develop/pt/worktrees/harness-agent-rework/dawn_kestrel`
2. **How to import Result?** Import from `dawn_kestrel.core.result` into iron-rook/base.py
3. **State machine integration point?** Integrate both Result and AgentStateMachine into BaseReviewerAgent
4. **Valid transitions definition?** Each agent defines class-level `FSM_TRANSITIONS` dict attribute
5. **Testing strategy?** Add unit tests for state machine and result pattern, integration tests for agents

**Guardrails Applied**:
- **AI-Slop Prevention** - NOT create complex state machines for simple single-pass reviews
- **No State Persistence** - In-memory only, no disk/database storage
- **Preserve Existing Logic** - Do NOT modify SimpleReviewAgentRunner or existing error handling
- **Maintain API Compatibility** - `ReviewOutput` return type unchanged, FSM is internal plumbing
- **Exclude Deprecated Agent** - SecurityReviewer excluded from updates
- **Shared Pattern Location** - state.py in dawn_kestrel (not per-agent files)
- **No Observability Expansion** - Standard DEBUG logging only, no metrics/tracing additions
- **No System Prompt Changes** - FSM is internal plumbing, doesn't change LLM behavior
- **No Configuration Explosion** - Transitions are hard-coded per agent via class attribute

**Scope Boundaries**:
- **INCLUDE**: Creating state.py module in dawn_kestrel/agents/; importing Result and State patterns into BaseReviewerAgent; updating 11 active agent files with FSM transitions; updating __init__.py exports
- **EXCLUDE**: Modifying dawn_kestrel core.result module; touching deprecated SecurityReviewer; adding external documentation; changing ReviewOutput contract; adding state persistence; adding observability beyond DEBUG logging

---

## Work Objectives

### Core Objective
Create dawn-kestrel State Pattern module (since it doesn't exist), then import both Result pattern and State pattern into iron-rook BaseReviewerAgent, enabling explicit state transitions and error handling for all review agents.

### Concrete Deliverables
- `dawn_kestrel/agents/state.py` - NEW: AgentState enum and AgentStateMachine class
- Updated `iron_rook/review/base.py` - Import Result from dawn_kestrel.core.result
- Updated `iron_rook/review/base.py` - Import AgentState and AgentStateMachine from dawn_kestrel.agents.state
- Updated `iron_rook/review/base.py` - Integrate both patterns into BaseReviewerAgent
- Updated 11 agent files - Each with FSM_TRANSITIONS and state machine usage
- Updated `iron_rook/review/agents/__init__.py` - Export new imports

### Definition of Done
- All imports of new modules work without errors
- State machine transitions work correctly for all agents
- Result pattern passes type checking and basic usage tests
- All existing tests still pass
- No state persistence code added
- SimpleReviewAgentRunner logic preserved
- ReviewOutput contract unchanged

### Must Have
- AgentState enum with all 6 states (IDLE, INITIALIZING, READY, RUNNING, PAUSED, COMPLETED, FAILED)
- AgentStateMachine with transition_to() method and validation
- Result/Ok/Err/Pass types imported from dawn_kestrel
- BaseReviewerAgent must have state_machine instance
- Each agent must define FSM_TRANSITIONS class attribute
- State machine must catch exceptions and transition to FAILED state
- Unit tests for state transition validation
- Unit tests for Result pattern

### Must NOT Have (Guardrails)
- **State persistence** - No pickle, JSON dump, or database writes
- **External documentation** - Only inline docstrings
- **Observability expansion** - No metrics, tracing, or custom logging hooks
- **SimpleReviewAgentRunner modifications** - Preserve retry, error handling, JSON validation
- **ReviewOutput contract changes** - External API unchanged
- **Abstract base class inheritance** - State machine has-a relationship with BaseReviewerAgent
- **Per-agent state files** - Shared state.py in dawn_kestrel only
- **Deprecated agent updates** - SecurityReviewer excluded
- **Agent-specific configuration** - Transitions hard-coded per agent, no runtime config
- **System prompt modifications** - FSM internal plumbing only

---

## Execution Strategy

### Parallel Execution Waves

> Sequential dependencies: Each task builds on the previous

```
Wave 1 (Create State Pattern):
├── Task 1: Create state.py module in dawn_kestrel/agents/

Wave 2 (Integrate Patterns):
├── Task 2: Import Result pattern into base.py
├── Task 3: Import AgentState and AgentStateMachine into base.py
├── Task 4: Integrate both patterns into BaseReviewerAgent

Wave 3 (Update Agents):
├── Task 5: Update DocumentationReviewer
├── Task 6: Update ArchitectureReviewer
├── Task 7: Update LintingReviewer
├── Task 8: Update TelemetryMetricsReviewer
├── Task 9: Update UnitTestsReviewer
├── Task 10: Update DiffScoperReviewer
├── Task 11: Update RequirementsReviewer
├── Task 12: Update PerformanceReliabilityReviewer
├── Task 13: Update DependencyLicenseReviewer
├── Task 14: Update ReleaseChangelogReviewer

Wave 4 (Finalize):
├── Task 15: Update agents/__init__.py
├── Task 16: Run full test suite

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Tasks 5-14 → Task 15 → Task 16
Parallel Speedup: Tasks 5-14 can be parallel (sequential due to Wave 2 dependency)
```

---

## TODOs

- [x] 1. Create state.py module with AgentState enum and AgentStateMachine

  **What to do**:
  - Create `dawn_kestrel/agents/state.py` with AgentState enum (IDLE, INITIALIZING, READY, RUNNING, PAUSED, COMPLETED, FAILED)
  - Create AgentStateMachine class with state tracking and transition validation
  - Implement transition_to() method using Result pattern
  - Implement _is_valid_transition() private method for validation logic
  - Add FSM_TRANSITIONS dict defining valid state transitions

  **Must NOT do**:
  - Do NOT add state persistence (pickle, JSON, database)
  - Do NOT add observability (metrics, tracing, custom logging)

  **Recommended Agent Profile**:
  > Category: `unspecified-low`
  > Skills: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (solo foundation task)
  - **Blocks**: 2, 3, 4
  - **Blocked By**: None

  **Acceptance Criteria**:
  - [ ] Test file created: tests/test_state_machine.py
  - [ ] pytest tests/test_state_machine.py -v → PASS (all tests)

  **Agent-Executed QA Scenarios**:
  - [ ] Verify AgentState enum values: idle, initializing, ready, running, paused, completed, failed
  - [ ] Verify AgentStateMachine initializes to IDLE
  - [ ] Verify valid transition: IDLE → INITIALIZING
  - [ ] Verify invalid transition: IDLE → COMPLETED fails with error

- [x] 2. Import Result pattern from dawn_kestrel.core.result into base.py

  **What to do**:
  - Add import: `from dawn_kestrel.core.result import Result, Ok, Err, Pass`

  **Recommended Agent Profile**: Same as Task 1

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3, 4)
  - **Blocks**: 5-14 (agent updates)
  - **Blocked By**: 1 (must create state.py first)

  **Acceptance Criteria**:
  - [ ] Import works: python3 -c "from dawn_kestrel.core.result import Result, Ok, Err, Pass"
  - [ ] Existing tests pass: pytest tests/ -v

- [x] 3. Import AgentState and AgentStateMachine from dawn_kestrel.agents.state into base.py

  **What to do**:
  - Add import: `from dawn_kestrel.agents.state import AgentState, AgentStateMachine`

  **Recommended Agent Profile**: Same as Task 1

  **Parallelization**::
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2, 4)
  - **Blocks**: 5-14 (agent updates)
  - **Blocked By**: 1, 2 (must create state.py and import Result)

  **Acceptance Criteria**:
  - [ ] Import works: python3 -c "from dawn_kestrel.agents.state import AgentState, AgentStateMachine"
  - [ ] Existing tests pass: pytest tests/ -v

- [x] 4. Integrate Result and AgentStateMachine into BaseReviewerAgent

  **What to do**:
  - Add state_machine to __init__
  - Add state property
  - Implement get_valid_transitions() abstract
  - Wrap _execute_review_with_runner with state transitions

  **Must NOT do**:
  - Do NOT change ReviewOutput
  - Do NOT modify SimpleReviewAgentRunner

  **Recommended Agent Profile**: Same as Task 1

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (final integration)
  - **Blocks**: 5-14 (all agent updates)
  - **Blocked By**: 2, 3 (must import both patterns)

  **Acceptance Criteria**:
  - [ ] BaseReviewerAgent has state_machine
  - [ ] Existing tests pass: pytest tests/ -v

- [x] 5-14. Update all 11 agents with FSM transitions

  **What to do for each agent**:
  - Import AgentState, AgentStateMachine
  - Define FSM_TRANSITIONS class attribute
  - Add state machine usage in review() method
  - Add logging for state transitions

  **Must NOT do**:
  - Do NOT change system prompt or agent behavior
  - Do NOT modify external API

  **Recommended Agent Profile**:
  > Category: `unspecified-low`
  > Skills: `[]`

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (all 11 agents together)
  - **Blocks**: 15 (exports)
  - **Blocked By**: 4 (base integration)

  **Acceptance Criteria**:
  - [ ] Each agent has FSM_TRANSITIONS
  - [ ] Each agent can import and use state machine
  - [ ] Existing tests pass: pytest tests/ -v

- [x] 15. Update agents/__init__.py to export new modules

  **What to do**:
  - Update __init__.py exports
  - Ensure backward compatibility

  **Recommended Agent Profile**: Same as Task 1

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: 16 (final test)
  - **Blocked By**: 5-14 (all agents)

  **Acceptance Criteria**:
  - [ ] New exports added
  - [ ] All existing imports still work
  - [ ] Existing tests pass: pytest tests/ -v

- [x] 16. Run full test suite

  **What to do**:
  - Run pytest on all tests
  - Verify all tests pass

  **Recommended Agent Profile**: Same as Task 1

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None (final task)
  - **Blocked By**: 15 (must export first)

  **Acceptance Criteria**:
  - [ ] All new tests pass
  - [ ] All existing tests pass
  - [ ] No breaking changes
