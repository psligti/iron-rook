# Security Agent FSM Migration to WorkflowFSMBuilder

## TL;DR

> **Quick Summary**: Migrate iron-rook's security agent from custom `LoopFSM` to `dawn_kestrel.core.fsm.WorkflowFSMBuilder`, consolidating 7 phases to 6 standard workflow states while preserving all security review behavior.
>
> **Deliverables**:
> - Updated `SecurityReviewer` using `WorkflowFSMBuilder`
> - Updated subagents using `WorkflowFSMBuilder`
> - Removed `iron_rook/fsm/` module
> - Updated `BaseReviewerAgent` to be FSM-agnostic
> - All tests passing with no behavior changes
>
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential (dependencies between tasks)
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 5 → Task 8

---

## Context

### Original Request
Migrate security agent to use `WorkflowFSMBuilder` from `dawn_kestrel.core.fsm:824`.

### Interview Summary
**Key Discussions**:
- Phase mapping: 7 security phases → 6 workflow states
- `collect` + `consolidate` merged into `synthesize`
- `plan_todos` → `plan`, `evaluate` → `check`
- Remove `LoopFSM` completely
- Migrate all subagents

**Research Findings**:
- **Critical**: Security agent already uses custom `SECURITY_FSM_TRANSITIONS` that differ from both `LoopFSM` defaults and `WorkflowFSMBuilder`
- Security agent's `act` has 4 exit paths: `collect|consolidate|evaluate|done`
- `WorkflowFSMBuilder` forces `act → synthesize → check → (plan|act|done)`
- `LoopFSM.run_loop()` executes the loop; `WorkflowFSMBuilder` is just a builder

### Metis Review
**Identified Gaps** (addressed):
- **Transition mismatch**: Resolved by mapping early-exit paths through full workflow (synthesize/check can be minimal)
- **Loop execution**: Will create runner in security agent class
- **Sync vs async**: All phase methods already async
- **Phase skipping**: Synthesize/check phases will handle early-exit with minimal logic

---

## Work Objectives

### Core Objective
Replace custom `LoopFSM` with `dawn_kestrel.core.fsm.WorkflowFSMBuilder` in security agent and subagents, preserving all security review behavior and output structure.

### Concrete Deliverables
- `iron_rook/review/agents/security.py` - Uses WorkflowFSMBuilder
- `iron_rook/review/subagents/security_subagents.py` - Uses WorkflowFSMBuilder
- `iron_rook/review/subagents/security_subagent_dynamic.py` - Uses WorkflowFSMBuilder
- `iron_rook/review/base.py` - FSM-agnostic base class
- `iron_rook/fsm/` - Deleted entirely

### Definition of Done
- [ ] All existing tests pass without modification
- [ ] Security review produces identical output structure
- [ ] No `LoopFSM` imports remain in production code
- [ ] `WorkflowFSMBuilder` imported and used correctly

### Must Have
- All 7 phase method implementations preserved (renamed/merged as needed)
- Phase outputs structure (`_phase_outputs`) unchanged
- Timeout handling per phase preserved
- `DelegateTodoSkill` integration unchanged
- `_phase_logger` and `_thinking_log` preserved

### Must NOT Have (Guardrails)
- NO behavior changes in security review output
- NO modification to `dawn_kestrel` (external dependency)
- NO changes to JSON output schemas (API contracts)
- NO adding new states to WorkflowFSMBuilder
- NO changes to other reviewers (architecture, docs, etc.) unless they use LoopFSM

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (tests-after - existing tests verify behavior)
- **Framework**: pytest with pytest-asyncio

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

```
Scenario: Security review produces valid output with WorkflowFSMBuilder
  Tool: Bash (pytest)
  Preconditions:iron-rook installed, test fixtures available
  Steps:
    1. pytest tests/unit/review/agents/test_security_fsm.py -v
    2. Assert: All tests pass, exit code 0
  Expected Result: All security FSM tests pass
  Evidence: pytest output

Scenario: Integration test with actual review
  Tool: Bash (pytest)
  Preconditions: Integration test fixtures exist
  Steps:
    1. pytest tests/integration/test_security_fsm_integration.py -v
    2. Assert: Exit code 0
  Expected Result: Integration tests pass
  Evidence: pytest output

Scenario: No LoopFSM imports remain
  Tool: Bash (grep)
  Preconditions: Migration complete
  Steps:
    1. grep -r "from iron_rook.fsm.loop_fsm" iron_rook/ --include="*.py" | grep -v __pycache__
    2. grep -r "from iron_rook.fsm.loop_state" iron_rook/ --include="*.py" | grep -v __pycache__
    3. Assert: Both return empty
  Expected Result: No imports found
  Evidence: grep output shows empty

Scenario: WorkflowFSMBuilder is used
  Tool: Bash (grep)
  Preconditions: Migration complete
  Steps:
    1. grep -r "WorkflowFSMBuilder" iron_rook/review/agents/security.py
    2. Assert: Non-empty output
  Expected Result: WorkflowFSMBuilder imported and used
  Evidence: grep output
```

**Evidence to Capture:**
- [ ] pytest output for unit tests
- [ ] pytest output for integration tests
- [ ] grep output showing no LoopFSM imports
- [ ] grep output showing WorkflowFSMBuilder usage

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
└── Task 1: Create adapter for WorkflowFSMBuilder

Wave 2 (After Wave 1):
├── Task 2: Update SecurityReviewer to use adapter
└── Task 3: Merge collect+consolidate into synthesize

Wave 3 (After Wave 2):
├── Task 4: Update BaseReviewerAgent
├── Task 5: Update security_subagents.py
└── Task 6: Update security_subagent_dynamic.py

Wave 4 (After Wave 3):
├── Task 7: Update tests for new phase names
└── Task 8: Delete iron_rook/fsm/ module

Critical Path: Task 1 → Task 2 → Task 3 → Task 5 → Task 8
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | None |
| 2 | 1 | 4, 5, 6 | 3 |
| 3 | 1 | 4, 5, 6 | 2 |
| 4 | 2, 3 | 8 | 5, 6 |
| 5 | 2, 3 | 8 | 4, 6 |
| 6 | 2, 3 | 8 | 4, 5 |
| 7 | 4, 5, 6 | 8 | None |
| 8 | 7 | None | None (final) |

---

## TODOs

- [x] 1. Create WorkflowFSMAdapter for Security Agent

  **What to do**:
  - Create `iron_rook/review/workflow_adapter.py`
  - Wrap `WorkflowFSMBuilder` to provide security-agent-specific functionality
  - Implement phase name mapping (plan_todos→plan, evaluate→check)
  - Implement `run_workflow()` method to execute the state loop
  - Handle early-exit paths (act→done via minimal synthesize/check)
  - Preserve `_phase_outputs` accumulation

  **Must NOT do**:
  - Do NOT modify dawn_kestrel code
  - Do NOT add new states to WorkflowFSMBuilder
  - Do NOT change transition semantics

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Requires understanding two FSM architectures and creating clean abstraction
  - **Skills**: []
    - No specific skills needed - pure Python refactoring

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential
  - **Blocks**: Tasks 2, 3
  - **Blocked By**: None

  **References**:
  - `dawn_kestrel/core/fsm.py:824-893` - WorkflowFSMBuilder implementation
  - `dawn_kestrel/core/fsm.py:764-774` - WORKFLOW_STATES and WORKFLOW_TRANSITIONS
  - `iron_rook/review/agents/security.py:34-41` - Current SECURITY_FSM_TRANSITIONS
  - `iron_rook/review/agents/security.py:123-197` - Current _run_review_fsm loop
  - `iron_rook/fsm/loop_fsm.py:412-507` - Current run_loop implementation

  **Acceptance Criteria**:
  - [ ] `WorkflowFSMAdapter` class created
  - [ ] `build()` method returns `Result[FSM]` from WorkflowFSMBuilder
  - [ ] `run_workflow()` async method executes state loop
  - [ ] Phase name mapping works: `plan_todos`→`plan`, `evaluate`→`check`
  - [ ] `_phase_outputs` dict accumulated across phases
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Adapter builds valid FSM
    Tool: Bash (python)
    Steps:
      1. python -c "
         from iron_rook.review.workflow_adapter import WorkflowFSMAdapter
         adapter = WorkflowFSMAdapter()
         result = adapter.build()
         assert result.is_ok(), f'Build failed: {result.error}'
         print('PASS: FSM built successfully')
         "
    Expected Result: PASS message printed
    Evidence: stdout output
  ```

  **Commit**: YES
  - Message: `refactor(review): add WorkflowFSMAdapter for security agent`
  - Files: `iron_rook/review/workflow_adapter.py`

---

- [x] 2. Update SecurityReviewer to use WorkflowFSMAdapter

  **What to do**:
  - Replace `self._fsm = LoopFSM(...)` with `self._adapter = WorkflowFSMAdapter()`
  - Update `_run_review_fsm()` to use `adapter.run_workflow()`
  - Rename `_run_plan_todos()` → `_run_plan()`
  - Rename `_run_evaluate()` → `_run_check()`
  - Update `_transition_to_phase()` to use adapter
  - Update `_phase_to_loop_state` mapping to use workflow state names

  **Must NOT do**:
  - Do NOT change phase prompt content (LLM behavior depends on exact prompts)
  - Do NOT change timeout handling logic
  - Do NOT modify DelegateTodoSkill integration

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Mechanical changes following adapter interface
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with Task 3)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: Task 1

  **References**:
  - `iron_rook/review/agents/security.py:59-98` - Current __init__
  - `iron_rook/review/agents/security.py:123-197` - Current _run_review_fsm
  - `iron_rook/review/agents/security.py:223-240` - Current _transition_to_phase
  - `iron_rook/review/workflow_adapter.py` - New adapter (from Task 1)

  **Acceptance Criteria**:
  - [ ] `SecurityReviewer.__init__` creates `WorkflowFSMAdapter`
  - [ ] `_run_review_fsm()` uses adapter's `run_workflow()`
  - [ ] `_run_plan_todos()` renamed to `_run_plan()`
  - [ ] `_run_evaluate()` renamed to `_run_check()`
  - [ ] `_phase_to_loop_state` updated for workflow states
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: SecurityReviewer initializes correctly
    Tool: Bash (python)
    Steps:
      1. python -c "
         from iron_rook.review.agents.security import SecurityReviewer
         reviewer = SecurityReviewer()
         assert hasattr(reviewer, '_adapter')
         print('PASS: SecurityReviewer initialized')
         "
    Expected Result: PASS message printed
    Evidence: stdout output
  ```

  **Commit**: YES
  - Message: `refactor(review): update SecurityReviewer to use WorkflowFSMAdapter`
  - Files: `iron_rook/review/agents/security.py`

---

- [x] 3. Merge collect + consolidate into synthesize phase

  **What to do**:
  - Create `_run_synthesize()` method combining `_run_collect()` and `_run_consolidate()` logic
  - Update synthesize prompt to handle both collection and consolidation
  - Remove separate `_run_collect()` and `_run_consolidate()` methods
  - Update synthesize output schema to include both collection and consolidation fields
  - Handle early-exit case where act determines done (synthesize becomes minimal)

  **Must NOT do**:
  - Do NOT lose any functionality from collect or consolidate phases
  - Do NOT change the final output structure
  - Do NOT skip evidence collection

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Requires merging two phases while preserving all behavior
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (with Task 2)
  - **Blocks**: Tasks 4, 5, 6
  - **Blocked By**: Task 1

  **References**:
  - `iron_rook/review/agents/security.py:155-173` - Current _run_collect
  - `iron_rook/review/agents/security.py:175-193` - Current _run_consolidate
  - `dawn_kestrel/agents/workflow.py` - SynthesizeOutput schema

  **Acceptance Criteria**:
  - [ ] `_run_synthesize()` created combining collect + consolidate
  - [ ] Synthesize prompt handles both collection and consolidation
  - [ ] `_run_collect()` and `_run_consolidate()` removed
  - [ ] Early-exit case handled (minimal synthesize when done)
  - [ ] All findings still collected and consolidated
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: Synthesize phase produces correct output
    Tool: Bash (python)
    Steps:
      1. python -c "
         from iron_rook.review.agents.security import SecurityReviewer
         reviewer = SecurityReviewer()
         # Verify _run_synthesize exists and has correct signature
         assert hasattr(reviewer, '_run_synthesize')
         print('PASS: _run_synthesize exists')
         "
    Expected Result: PASS message printed
    Evidence: stdout output
  ```

  **Commit**: YES
  - Message: `refactor(review): merge collect+consolidate into synthesize phase`
  - Files: `iron_rook/review/agents/security.py`

---

- [x] 4. Update BaseReviewerAgent to be FSM-agnostic

  **What to do**:
  - Remove `from iron_rook.fsm.loop_fsm import LoopFSM` import
  - Remove `self._fsm = LoopFSM(...)` initialization
  - Make `_fsm` attribute optional or remove entirely
  - Update `_transition_to()` to be abstract or delegate to subclass
  - Update type hints to not require `LoopFSM`

  **Must NOT do**:
  - Do NOT break other reviewers (architecture, docs, etc.)
  - Do NOT change the public interface of `BaseReviewerAgent`
  - Do NOT remove methods that other code depends on

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward removal of LoopFSM dependency
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 5, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `iron_rook/review/base.py:12` - Current LoopFSM import
  - `iron_rook/review/base.py:161` - Current _fsm initialization
  - `iron_rook/review/base.py:194-220` - Current _transition_to

  **Acceptance Criteria**:
  - [ ] No `LoopFSM` import in base.py
  - [ ] `_fsm` attribute removed or made optional
  - [ ] Other reviewers (architecture, docs) still work
  - [ ] Type hints updated
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: BaseReviewerAgent has no LoopFSM dependency
    Tool: Bash (grep)
    Steps:
      1. grep "from iron_rook.fsm" iron_rook/review/base.py
      2. Assert: Empty output
    Expected Result: No LoopFSM import found
    Evidence: grep output
  ```

  **Commit**: YES
  - Message: `refactor(review): make BaseReviewerAgent FSM-agnostic`
  - Files: `iron_rook/review/base.py`

---

- [x] 5. Update security_subagents.py to use WorkflowFSMBuilder

  **What to do**:
  - Replace `LoopFSM` with `WorkflowFSMAdapter`
  - Update `BaseSubagent` to not inherit `LoopFSM` behavior
  - Update `_run_subagent_fsm()` to use adapter
  - Remove `from iron_rook.fsm.loop_fsm import LoopFSM` import

  **Must NOT do**:
  - Do NOT change subagent behavior or output
  - Do NOT break subagent delegation from main agent

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Follow same pattern as main security agent
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 4, 6)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `iron_rook/review/subagents/security_subagents.py:25` - Current LoopFSM import
  - `iron_rook/review/subagents/security_subagents.py:97-100` - Current run_loop usage
  - `iron_rook/review/workflow_adapter.py` - New adapter

  **Acceptance Criteria**:
  - [ ] No `LoopFSM` import in security_subagents.py
  - [ ] `WorkflowFSMAdapter` used instead
  - [ ] Subagent behavior unchanged
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: security_subagents.py has no LoopFSM
    Tool: Bash (grep)
    Steps:
      1. grep "from iron_rook.fsm.loop" iron_rook/review/subagents/security_subagents.py
      2. Assert: Empty output
    Expected Result: No LoopFSM import found
    Evidence: grep output
  ```

  **Commit**: YES
  - Message: `refactor(review): update security_subagents to use WorkflowFSMAdapter`
  - Files: `iron_rook/review/subagents/security_subagents.py`

---

- [x] 6. Update security_subagent_dynamic.py to use WorkflowFSMBuilder

  **What to do**:
  - Replace phase transitions with workflow state transitions
  - Update `_run_subagent_fsm()` to use WorkflowFSMAdapter
  - Update `_transition_to_phase()` to use adapter
  - Remove any LoopFSM references

  **Must NOT do**:
  - Do NOT change dynamic subagent behavior
  - Do NOT break delegation from main agent

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Follow same pattern as other subagents
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 4, 5)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `iron_rook/review/subagents/security_subagent_dynamic.py:176-265` - Current FSM usage
  - `iron_rook/review/subagents/security_subagent_dynamic.py:337` - Current _transition_to_phase

  **Acceptance Criteria**:
  - [ ] No `LoopFSM` import in security_subagent_dynamic.py
  - [ ] Phase transitions use workflow states
  - [ ] Dynamic subagent behavior unchanged
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: security_subagent_dynamic.py has no LoopFSM
    Tool: Bash (grep)
    Steps:
      1. grep "from iron_rook.fsm.loop" iron_rook/review/subagents/security_subagent_dynamic.py
      2. Assert: Empty output
    Expected Result: No LoopFSM import found
    Evidence: grep output
  ```

  **Commit**: YES
  - Message: `refactor(review): update security_subagent_dynamic to use WorkflowFSMAdapter`
  - Files: `iron_rook/review/subagents/security_subagent_dynamic.py`

---

- [x] 7. Update tests for new phase names

  **What to do**:
  - Update test assertions that reference old phase names
  - `plan_todos` → `plan`
  - `collect`/`consolidate` → `synthesize`
  - `evaluate` → `check`
  - Add tests for WorkflowFSMAdapter
  - Verify all existing tests still pass

  **Must NOT do**:
  - Do NOT change test behavior expectations
  - Do NOT remove any test cases

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Mechanical string replacements in tests
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 4, 5, 6

  **References**:
  - `tests/unit/review/agents/test_security_fsm.py` - Security FSM tests
  - `tests/integration/test_security_fsm_integration.py` - Integration tests
  - `tests/unit/review/subagents/` - Subagent tests

  **Acceptance Criteria**:
  - [ ] All phase name references updated in tests
  - [ ] New tests for WorkflowFSMAdapter added
  - [ ] `pytest tests/` passes with exit code 0
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: All tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_security_fsm.py -v
      2. pytest tests/unit/review/subagents/ -v
      3. Assert: Exit code 0 for both
    Expected Result: All tests pass
    Evidence: pytest output
  ```

  **Commit**: YES
  - Message: `test(review): update tests for workflow phase names`
  - Files: `tests/unit/review/agents/test_security_fsm.py`, `tests/unit/review/subagents/`, etc.

---

- [ ] 8. Delete iron_rook/fsm/ module

  **What to do**:
  - Verify no remaining imports of `iron_rook.fsm.loop_fsm` or `iron_rook.fsm.loop_state`
  - Delete `iron_rook/fsm/loop_fsm.py`
  - Delete `iron_rook/fsm/loop_state.py`
  - Delete `iron_rook/fsm/todo.py`
  - Delete `iron_rook/fsm/state.py`
  - Delete `iron_rook/fsm/__init__.py`
  - Delete `iron_rook/fsm/` directory
  - Run full test suite to verify nothing broke

  **Must NOT do**:
  - Do NOT delete until ALL imports are removed
  - Do NOT delete any dawn_kestrel FSM code

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file deletion after verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (final)
  - **Blocks**: None
  - **Blocked By**: Task 7

  **References**:
  - `iron_rook/fsm/` - Directory to delete
  - Use `grep -r "from iron_rook.fsm" iron_rook/` to verify no imports

  **Acceptance Criteria**:
  - [ ] `grep -r "from iron_rook.fsm.loop" iron_rook/` returns empty
  - [ ] `iron_rook/fsm/` directory deleted
  - [ ] Full test suite passes
  
  **Agent-Executed QA Scenarios**:
  ```
  Scenario: No LoopFSM imports anywhere
    Tool: Bash (grep)
    Steps:
      1. grep -r "from iron_rook.fsm.loop" iron_rook/ --include="*.py" | grep -v __pycache__
      2. Assert: Empty output
    Expected Result: No imports found
    Evidence: grep output

  Scenario: fsm directory deleted
    Tool: Bash (ls)
    Steps:
      1. ls iron_rook/fsm/ 2>&1
      2. Assert: "No such file or directory" in output
    Expected Result: Directory does not exist
    Evidence: ls output
  ```

  **Commit**: YES
  - Message: `refactor(fsm): remove LoopFSM module`
  - Files: Deleted `iron_rook/fsm/`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `refactor(review): add WorkflowFSMAdapter for security agent` | `workflow_adapter.py` | Unit test of adapter |
| 2 | `refactor(review): update SecurityReviewer to use WorkflowFSMAdapter` | `security.py` | Security reviewer initializes |
| 3 | `refactor(review): merge collect+consolidate into synthesize phase` | `security.py` | _run_synthesize exists |
| 4 | `refactor(review): make BaseReviewerAgent FSM-agnostic` | `base.py` | No LoopFSM in base |
| 5 | `refactor(review): update security_subagents to use WorkflowFSMAdapter` | `security_subagents.py` | No LoopFSM in subagents |
| 6 | `refactor(review): update security_subagent_dynamic to use WorkflowFSMAdapter` | `security_subagent_dynamic.py` | No LoopFSM in dynamic |
| 7 | `test(review): update tests for workflow phase names` | `tests/` | All tests pass |
| 8 | `refactor(fsm): remove LoopFSM module` | Deleted `fsm/` | Directory gone |

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
pytest tests/unit/review/agents/test_security_fsm.py -v
pytest tests/unit/review/subagents/ -v
pytest tests/integration/test_security_fsm_integration.py -v

# No LoopFSM imports
grep -r "from iron_rook.fsm.loop" iron_rook/ --include="*.py" | grep -v __pycache__ || echo "PASS"

# WorkflowFSMBuilder is used
grep -r "WorkflowFSMBuilder" iron_rook/review/agents/security.py
```

### Final Checklist
- [ ] All "Must Have" present (phase methods, outputs, timeouts, delegation)
- [ ] All "Must NOT Have" absent (behavior changes, dawn_kestrel mods, schema changes)
- [ ] All tests pass
- [ ] LoopFSM module deleted
- [ ] WorkflowFSMBuilder used throughout
