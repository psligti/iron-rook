# Plan: Refactor Security FSM - Replace Delegate Phase with Act

## TL;DR

> **Quick Summary**: Simplify security FSM by removing the separate "delegate" phase and merging its LLM-based delegation logic into a new "act" phase that uses a generic delegation skill.
>
> **Deliverables**:
> - Remove `delegate` phase from security FSM
> - Create `DelegateTodoSkill` (new) for LLM-based delegation
> - Update FSM to: intake → plan_todos → **act** → collect → consolidate → evaluate → done
> - Update contracts to remove delegate-specific models
> - Update tests to use new act phase
>
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential changes required
> **Critical Path**: Create skill → Update security.py → Update contracts → Update tests

---

## Context

### Original Request
Replace "delegate" phase with an "act" phase that:
- Uses a skill for delegation
- Has tool support for delegation
- Security agent uses todo management, delegation, and memory/context evaluation

### Interview Summary

**Key Discussions**:
- **Approach**: Keep LLM-based delegation (flexible decision making), not rule-based
- **Scope**: Remove delegate phase entirely, simplify FSM from 7 to 6 phases
- **Skills**: Create generic delegation skill (reuse SecuritySubagent)
- **Naming**: Use "act" as the phase name (generic, clear)

**Research Findings**:
- **Current delegate phase** (`security.py:406-538`):
  - Calls LLM to generate `subagent_requests` list
  - Actually executes subagents via `SecuritySubagent`
  - Returns `subagent_results` attached to output
  - Uses `SecurityTodo` objects with `todo_id` for tracking
- **Todo management** (`contracts.py:266-284`):
  - `SecurityTodo` model: id, description, priority, risk_category, acceptance_criteria, evidence_required
  - `TodoStatus` model: todo_id, status (done/blocked/deferred), explanation
  - Todo lifecycle: created in plan_todos, delegated, collected, consolidated, evaluated
- **Skills infrastructure** (`registry.py`, `base.py`, `executor.py`):
  - Dynamic skill loading via `ReviewerRegistry`
  - Skill contract: `BaseReviewerAgent` with `get_agent_name`, `get_system_prompt`, `get_allowed_tools`, `review()`
  - Tools executed via `CommandExecutor` with whitelisting
  - Existing `SecuritySubagent` can be reused
- **Memory/context flow** (`security.py`):
  - `_phase_outputs` stores per-phase outputs
  - LLM prompts built from ReviewContext + relevant phase outputs
  - `ThinkingFrame` and `RunLog` for audit trail

### Metis Review
**Identified Gaps** (addressed in this plan):
- Test coverage for new act phase
- Backward compatibility (tests expecting delegate phase)
- Documentation updates needed for new skill

---

## Work Objectives

### Core Objective
Simplify security reviewer FSM by removing the separate "delegate" phase and merging its LLM-based delegation logic into a new "act" phase, while maintaining all delegation functionality through a generic skill.

### Concrete Deliverables
- Removed `delegate` phase code from `iron_rook/review/agents/security.py`
- New `DelegateTodoSkill` class in `iron_rook/review/skills/delegate_todo.py`
- Updated FSM transitions: intake → plan_todos → **act** → collect → consolidate → evaluate → done
- Updated contracts: removed `DelegatePhaseOutput`, `DelegatePhaseData`, `SubagentRequest`, `SubagentResult`
- Updated `get_phase_output_schema()` to map "act" phase
- Updated tests for new act phase behavior
- New skill registered in `iron_rook/review/skills/__init__.py`

### Definition of Done
- [ ] Security FSM has 6 phases (delegate removed)
- [ ] New act phase successfully executes and delegates subagents
- [ ] All existing tests pass with new act phase
- [ ] Todo tracking works end-to-end (creation → delegation → collection → evaluation)
- [ ] ReviewOutput produced by act phase has correct structure for collect phase

### Must Have
- Act phase uses LLM to analyze todos and create delegation plan
- Act phase dispatches subagents via delegation skill
- Act phase output includes `subagent_results` matching current format
- All existing functionality (todo tracking, subagent execution) preserved
- FSM transitions work correctly: plan_todos → act → collect → consolidate → evaluate → done

### Must NOT Have (Guardrails)
- Do NOT create rule-based dispatch without LLM
- Do NOT remove LLM delegation entirely (keep flexible decision making)
- Do NOT break existing todo tracking mechanism
- Do NOT break existing subagent infrastructure
- Do NOT create specialized subagents (reuse SecuritySubagent)
- Do NOT rename existing phases beyond delegate removal
- Do NOT change collect phase logic (it expects subagent_results)

---

## Verification Strategy (MANDATORY)

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
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD)
- **Framework**: pytest (existing)

### If TDD Enabled

Each TODO follows RED-GREEN-REFACTOR:

**Task Structure**:
1. **RED**: Write failing test first
   - Test file: `tests/unit/review/agents/test_security_fsm_act_phase.py`
   - Test command: `pytest tests/unit/review/agents/test_security_fsm_act_phase.py`
   - Expected: FAIL (implementation doesn't exist yet)

2. **GREEN**: Implement minimum code to pass
   - Create skill: `iron_rook/review/skills/delegate_todo.py`
   - Create/update act phase: `iron_rook/review/agents/security.py`
   - Update contracts: `iron_rook/review/contracts.py`
   - Command: `pytest tests/unit/review/agents/test_security_fsm_act_phase.py`
   - Expected: PASS

3. **REFACTOR**: Clean up while keeping green
   - Remove old delegate code
   - Update transitions
   - Clean up unused imports
   - Command: `pytest tests/unit/review/agents/test_security_fsm_act_phase.py`
   - Expected: PASS (all tests pass)

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

**Task: Create DelegateTodoSkill**
```yaml
Scenario: Skill is registered and discoverable
  Tool: Bash
  Preconditions: iron-rook installed locally
  Steps:
    1. python -c "from iron_rook.review.registry import ReviewerRegistry; r = ReviewerRegistry(); print('Available skills:', r.get_all_names())"
    2. Assert: 'delegate_todo' appears in output
    3. Assert: import works without errors
  Expected Result: Output contains 'delegate_todo' in available skills list, no import errors
  Failure Indicators: Import error, 'delegate_todo' not in list
  Evidence: Command output captured
```

**Task: Update Security FSM - Remove Delegate Phase**
```yaml
Scenario: Act phase correctly handles todos and delegates subagents
  Tool: Bash (pytest)
  Preconditions: Code changes applied, skill registered
  Steps:
    1. pytest tests/unit/review/agents/test_security_fsm.py::test_security_fsm_transitions -v
    2. Assert: Transitions map does NOT contain 'delegate' key
    3. Assert: 'plan_todos' maps to ['act'] instead of ['delegate']
    4. pytest tests/unit/review/agents/test_security_fsm.py::test_security_fsm_intake_flow -v
    5. Assert: Intake transitions to plan_todos, which transitions to act
    6. pytest tests/integration/test_security_fsm_integration.py -v
    7. Assert: Full FSM flow completes (intake → plan_todos → act → collect → consolidate → evaluate → done)
  Expected Result: All transitions pass, FSM completes successfully
  Failure Indicators: Transition errors, FSM stops at wrong phase
  Evidence: Test output captured
```

**Task: Update Contracts - Remove Delegate Models**
```yaml
Scenario: Contracts only contain 6 phase models
  Tool: Bash (python -c)
  Preconditions: Code changes applied
  Steps:
    1. python -c "from iron_rook.review.contracts import phase_schemas; print('Available phases:', list(phase_schemas.keys()))"
    2. Assert: Output is ['intake', 'plan_todos', 'act', 'collect', 'consolidate', 'evaluate']
    3. Assert: 'delegate' NOT in list
    4. Assert: DelegatePhaseOutput, DelegatePhaseData, SubagentRequest, SubagentResult NOT defined in namespace
  Expected Result: 6 phases, no delegate models
  Failure Indicators: 'delegate' in phase_schemas, delegate models imported
  Evidence: Python output captured
```

**Task: Update Tests - Replace Delegate with Act**
```yaml
Scenario: Tests use new act phase instead of delegate
  Tool: Bash (pytest)
  Preconditions: Code changes applied
  Steps:
    1. pytest tests/unit/review/agents/test_security_fsm.py -v
    2. Assert: All tests pass (no failures)
    3. pytest tests/integration/test_security_fsm_integration.py -v
    4. Assert: Integration tests pass
  Expected Result: All tests pass
  Failure Indicators: Any test failures
  Evidence: Test output captured
```

**Task: Full FSM Integration Test**
```yaml
Scenario: End-to-end FSM execution from intake to done
  Tool: Bash (pytest)
  Preconditions: Code changes applied
  Steps:
    1. pytest tests/integration/test_security_fsm_integration.py -v -k "full_fsm_flow"
    2. Assert: FSM executes all 6 phases
    3. Assert: Todo tracking works end-to-end
    4. Assert: Findings are produced
  Expected Result: FSM completes successfully with findings
  Failure Indicators: FSM fails mid-flow, no findings produced
  Evidence: Test output captured
```

**Evidence to Capture:**
- [ ] Skill registration output (.sisyphus/evidence/skill-registration.txt)
- [ ] FSM transition test output (.sisyphus/evidence/fsm-transitions.txt)
- [ ] Full integration test output (.sisyphus/evidence/full-fsm-test.txt)
- [ ] Contract validation output (.sisyphus/evidence/contract-validation.txt)
- [ ] All test run output (.sisyphus/evidence/all-tests-pass.txt)

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Create DelegateTodoSkill
├── Task 2: Update Security FSM - Remove Delegate Phase
└── Task 3: Update Contracts - Remove Delegate Models

Wave 2 (After Wave 1):
├── Task 4: Update Tests - Create Act Phase Tests
└── Task 5: Run All Tests

Critical Path: Task 1 → Task 2 → Task 3 → Task 4 → Task 5
Parallel Speedup: Minimal (sequential dependencies between waves)
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|----------------------|
| 1 | None | 2, 3, 4, 5 | - (start of chain) |
| 2 | 1 | 4, 5 | 3, 4, 5 |
| 3 | 1, 2 | 4, 5 | 4, 5 |
| 4 | 1, 2, 3 | 5 | 5 |
| 5 | 1, 2, 3, 4 | - (end of chain) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2, 3 | task(category="quick", load_skills=["git-master"]) |
| 2 | 4, 5 | task(category="quick", load_skills=["frontend-ui-ux"]) |

---

## TODOs

- [ ] 1. Create DelegateTodoSkill class

  **What to do**:
  - Create new file `iron_rook/review/skills/delegate_todo.py`
  - Implement `DelegateTodoSkill` class inheriting from `BaseReviewerAgent`
  - Implement `get_agent_name()` returning "delegate_todo"
  - Implement `get_allowed_tools()` returning delegation tools: ["grep", "rg", "ast-grep", "python", "bandit", "semgrep"]
  - Implement `review(context)` method:
    - Extract todos from `self._phase_outputs.get("plan_todos", {}).get("data", {}).get("todos", [])`
    - Call LLM to analyze todos and create delegation plan
    - Build delegation prompt using existing LLM methods
    - Execute LLM and parse response
    - Create subagent requests based on LLM response
    - Dispatch subagents (reuse `SecuritySubagent`)
    - Collect subagent results
    - Build `ActPhaseOutput` with `subagent_results`
    - Return output with `next_phase_request: "collect"`

  **Must NOT do**:
  - Do NOT create rule-based dispatch (use LLM for decisions)
  - Do NOT modify todo structure (use existing `SecurityTodo`)
  - Do NOT break subagent execution (use `SecuritySubagent` as-is)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: New skill file creation following existing patterns
  - **Skills**: [`git-master`]
    - `git-master`: For skill registration pattern

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4 (tests need updated contracts first)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `iron_rook/review/subagents/security_subagents.py:1-120` - How `SecuritySubagent` is instantiated and used
  - `iron_rook/review/agents/security.py:456-473` - Current delegate phase subagent dispatch pattern
  - `iron_rook/review/agents/architecture.py` - Example of skill structure using `SimpleReviewAgentRunner`

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/base.py:BaseReviewerAgent` - Skill interface contract
  - `iron_rook/review/contracts.py:ActPhaseOutput:194-296` - Output model for act phase
  - `iron_rook/review/contracts.py:SecurityTodo:266-284` - Todo data model
  - `iron_rook/review/contracts.py:SubagentResult:352-360` - Result model from subagents
  - `iron_rook/review/contracts.py:ReviewOutput:76-164` - Final review output structure

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - How to test LLM thinking patterns
  - `tests/unit/review/agents/test_security_fsm.py:40-114` - Existing FSM transition tests

  **Documentation References** (specs and requirements):
  - `iron_rook/review/readme.md` - Review agent documentation
  - `.sisyphus/drafts/delegate-to-act-refactor.md` - This planning document

  **WHY Each Reference Matters**:
  - Don't just list files - explain what pattern/information the executor should extract
  - `SecuritySubagent` pattern: Shows how to pass task to subagent, collect result.model_dump(), handle errors
  - `BaseReviewerAgent`: Contract methods must be implemented correctly for skill registration
  - `ActPhaseOutput`: Structure includes `subagent_results` that collect phase consumes
  - `ReviewOutput`: Final output must merge findings from act phase

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/unit/review/agents/test_security_fsm_act_phase.py
  - [ ] Test covers: skill registration (delegate_todo in registry)
  - [ ] Test covers: act phase LLM delegation
  - [ ] Test covers: subagent dispatch and result collection
  - [ ] pytest tests/unit/review/agents/test_security_fsm_act_phase.py → PASS (3 tests, 0 failures)

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > **Scenario: Skill is registered and discoverable**
  > ```yaml
  > Tool: Bash
  > Preconditions: iron-rook installed locally
  > Steps:
  >   1. python -c "from iron_rook.review.registry import ReviewerRegistry; r = ReviewerRegistry(); print('Available skills:', r.get_all_names())"
  >   2. Assert: 'delegate_todo' appears in output
  >   3. Assert: import works without errors
  > Expected Result: Output contains 'delegate_todo' in available skills list, no import errors
  > Failure Indicators: Import error, 'delegate_todo' not in list
  > Evidence: Command output captured
  > ```

  **Commit**: NO (groups with Task 2)
  - Message: (after Task 2: Update contracts and tests together)

- [ ] 2. Update Security FSM transitions

  **What to do**:
  - Update `SECURITY_FSM_TRANSITIONS` dictionary
    - Remove "delegate" key and transitions
    - Add "act" key: `{"plan_todos": ["act"]}`
    - Update "act" transitions: `{"act": ["collect"]}`
  - Remove `_run_delegate()` method entirely
  - Add `_run_act()` method:
    - Set `self._current_security_phase = "act"` before execution
    - Call `DelegateTodoSkill` review method
    - Store output as `self._phase_outputs["act"] = output`
    - Remove delegate-specific thinking logs
  - Remove `_build_delegate_message()` method
  - Update `_get_phase_prompt()` to remove "delegate" case
  - Update `_get_phase_specific_instructions()` to remove "delegate" case
  - Update docstrings to reflect 6-phase FSM

  **Must NOT do**:
  - Do NOT keep any delegate-related code
  - Do NOT break other phase logic (collect, consolidate, evaluate)
  - Do NOT change SecurityTodo model

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: FSM transition updates and method removal
  - **Skills**: [`git-master`]
    - `git-master`: For git operations if needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 1)
  - **Blocks**: Task 3 (contracts), Task 4 (tests)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:32-38` - Current `SECURITY_FSM_TRANSITIONS` definition
  - `iron_rook/review/agents/security.py:220-241` - `_transition_to_phase` method
  - `iron_rook/review/agents/security.py:125-183` - FSM loop structure

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py:30-38` - `SECURITY_FSM_TRANSITIONS` constant definition
  - `iron_rook/review/contracts.py:231-246` - `PlanTodosPhaseOutput` with next_phase_request
  - `iron_rook/review/contracts.py:428-467` - `get_phase_output_schema` function

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_fsm.py:62-98` - Test `SECURITY_FSM_TRANSITIONS` transitions
  - `tests/unit/review/agents/test_security_fsm.py:113-124` - Test for FSM loop behavior

  **Documentation References** (specs and requirements):
  - `iron_rook/review/readme.md` - Review agent documentation

  **WHY Each Reference Matters**:
  - FSM transitions must be updated consistently across both constants and review loop
  - `_transition_to_phase` validates against `SECURITY_FSM_TRANSITIONS`
  - Phase prompts and instructions must not reference removed phase
  - Tests validate exact transition mappings

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Updated `SECURITY_FSM_TRANSITIONS` has NO "delegate" key
  - [ ] `plan_todos` maps to `["act"]` instead of `["delegate"]`
  - [ ] `_run_delegate()` method removed entirely
  - [ ] `_run_act()` method exists and uses DelegateTodoSkill
  - [ ] Review method updated to call `_run_act` instead of `_run_delegate`
  - [ ] pytest tests/unit/review/agents/test_security_fsm.py::test_security_fsm_transitions -v - PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > **Scenario: Act phase correctly handles todos and delegates subagents**
  > ```yaml
  > Tool: Bash (pytest)
  > Preconditions: Code changes applied
  > Steps:
  >   1. pytest tests/unit/review/agents/test_security_fsm.py::test_security_fsm_transitions -v
  >   2. Assert: Transitions map does NOT contain 'delegate' key
  >   3. Assert: 'plan_todos' maps to ['act'] instead of ['delegate']
  >   4. pytest tests/unit/review/agents/test_security_fsm.py::test_security_fsm_intake_flow -v
  >   5. Assert: Intake transitions to plan_todos, which transitions to act
  >   6. pytest tests/integration/test_security_fsm_integration.py -v
  >   7. Assert: Full FSM flow completes (intake → plan_todos → act → collect → consolidate → evaluate → done)
  > Expected Result: All transitions pass, FSM completes successfully
  > Failure Indicators: Transition errors, FSM stops at wrong phase
  > Evidence: Test output captured
  > ```

  **Commit**: NO (groups with Task 3)

- [ ] 3. Update contracts - remove delegate models

  **What to do**:
  - Remove `DelegatePhaseOutput`, `DelegatePhaseData`, `SubagentRequest`, `SubagentResult` classes
  - Update `PlanTodosPhaseOutput.next_phase_request` from `"delegate"` to `"act"`
  - Update `get_phase_output_schema()` phase_schemas dictionary:
    - Remove "delegate" entry
    - Add "act" entry mapping to `ActPhaseOutput`
  - Update imports if needed

  **Must NOT do**:
  - Do NOT keep delegate models in public API
  - Do NOT break existing act/collect/consolidate/evaluate models
  - Do NOT modify SecurityTodo or TodoStatus (todo lifecycle unchanged)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Contract cleanup and schema updates
  - **Skills**: [`git-master`, `frontend-ui-ux`]
    - `git-master`: For any git operations
    - `frontend-ui-ux`: For JSON schema structure validation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 2)
  - **Blocks**: Task 4 (tests)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `iron_rook/review/contracts.py:344-368` - Delegate models to remove
  - `iron_rook/review/contracts.py:440-473` - `get_phase_output_schema` implementation

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py:441-466` - phase_schemas dictionary structure
  - `iron_rook/review/contracts.py:258-266` - `PlanTodosPhaseOutput` model

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Uses delegate-specific tests

  **Documentation References** (specs and requirements):
  - `iron_rook/review/readme.md` - Review agent documentation

  **WHY Each Reference Matters**:
  - Removing unused models keeps contracts clean and prevents confusion
  - Schema mapping must align with FSM transitions
  - Tests will need updates to avoid referencing delegate phase

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] DelegatePhaseOutput, DelegatePhaseData, SubagentRequest, SubagentResult removed from contracts.py
  - [ ] PlanTodosPhaseOutput.next_phase_request is Literal["act"]
  - [ ] get_phase_output_schema() returns 6 phases: intake, plan_todos, act, collect, consolidate, evaluate
  - [ ] No "delegate" in phase_schemas keys
  - [ ] python -c "from iron_rook.review.contracts import *; print([x for x in dir() if 'Delegate' in x])" returns nothing
  - [ ] pytest tests/unit/review/agents/test_security_fsm.py -v - PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > **Scenario: Contracts only contain 6 phase models**
  > ```yaml
  > Tool: Bash (python -c)
  > Preconditions: Code changes applied
  > Steps:
  >   1. python -c "from iron_rook.review.contracts import phase_schemas; print('Available phases:', list(phase_schemas.keys()))"
  >   2. Assert: Output is ['intake', 'plan_todos', 'act', 'collect', 'consolidate', 'evaluate']
  >   3. Assert: 'delegate' NOT in list
  >   4. Assert: DelegatePhaseOutput, DelegatePhaseData, SubagentRequest, SubagentResult NOT defined in namespace
  > Expected Result: 6 phases, no delegate models
  > Failure Indicators: 'delegate' in phase_schemas, delegate models imported
  > Evidence: Python output captured
  > ```

  **Commit**: YES (groups with Task 4)

- [ ] 4. Create act phase tests

  **What to do**:
  - Create new test file `tests/unit/review/agents/test_security_fsm_act_phase.py`
  - Write tests for act phase behavior:
    - Test that act phase uses DelegateTodoSkill
    - Test LLM delegation logic
    - Test subagent dispatch and result collection
    - Test todo extraction from plan_todos output
  - Update existing tests to reference act instead of delegate:
    - TestSecurityFSMTransitions: Update transition expectations
    - TestSecurityFSMIntakeFlow: Update expected transitions
  - Update integration tests:
    - TestSecurityFSMIntegration: Update to test act phase

  **Must NOT do**:
  - Do NOT create tests that expect delegate phase to still exist
  - Do NOT break existing test infrastructure

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: New test creation following existing patterns
  - **Skills**: [`git-master`]
    - `git-master`: For test file creation

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Tasks 2-3)
  - **Blocks**: Task 5 (full integration test)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `tests/unit/review/agents/test_security_fsm.py:113-124` - Existing FSM loop test pattern
  - `tests/unit/review/agents/test_security_thinking.py:266-273` - Delegate phase thinking test

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/agents/security.py:review()` - Review method contract
  - `iron_rook/review/contracts.py:ActPhaseOutput` - Output structure for act phase

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - How to structure phase tests
  - `tests/integration/test_security_fsm_integration.py` - Integration test patterns

  **Documentation References** (specs and requirements):
  - `iron_rook/review/readme.md` - Review agent documentation

  **WHY Each Reference Matters**:
  - Act phase tests verify core delegation functionality
  - Integration tests ensure full FSM flow works
  - Following existing test patterns maintains consistency

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] Test file created: tests/unit/review/agents/test_security_fsm_act_phase.py
  - [ ] Test covers: skill loading and registration
  - [ ] Test covers: act phase LLM delegation and subagent dispatch
  - [ ] Test covers: todo extraction and processing
  - [ ] pytest tests/unit/review/agents/test_security_fsm_act_phase.py → PASS
  - [ ] Existing tests updated: no references to delegate phase
  - [ ] pytest tests/integration/test_security_fsm_integration.py -v - PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > **Scenario: Act phase tests pass**
  > ```yaml
  > Tool: Bash (pytest)
  > Preconditions: Code changes applied
  > Steps:
  >   1. pytest tests/unit/review/agents/test_security_fsm.py -v
  >   2. Assert: All tests pass (no failures)
  >   3. pytest tests/integration/test_security_fsm_integration.py -v
  >   4. Assert: Integration tests pass
  > Expected Result: All tests pass
  > Failure Indicators: Any test failures
  > Evidence: Test output captured
  > ```

  **Commit**: YES (groups with Task 5)

- [ ] 5. Register DelegateTodoSkill

  **What to do**:
  - Update `iron_rook/review/skills/__init__.py`:
    - Add `DelegateTodoSkill` to `__all__`
  - Update `iron_rook/review/registry.py`:
    - Add `from .skills.delegate_todo import DelegateTodoSkill`
    - Add registration: `registry.register("delegate_todo", DelegateTodoSkill, is_core=False)`

  **Must NOT do**:
  - Do NOT modify existing skill registration pattern
  - Do NOT break other skills (security, architecture, etc.)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Skill registration following existing pattern
  - **Skills**: [`git-master`]
    - `git-master`: For updating skills init file and registry

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Tasks 1-4)
  - **Blocks**: Task 5 (full integration test)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `iron_rook/review/skills/__init__.py` - Existing skill exports
  - `iron_rook/review/registry.py:65-105` - `_register_default_reviewers()` pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/base.py:BaseReviewerAgent` - Skill interface
  - `iron_rook/review/registry.py:ReviewerRegistry.register()` - Registration method

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Skills registration tests (if any)

  **Documentation References** (specs and requirements):
  - `iron_rook/review/readme.md` - Review agent documentation

  **WHY Each Reference Matters**:
  - Following existing registration pattern ensures skills are discoverable
  - Proper import structure prevents module load errors
  - Registry pattern provides consistent skill initialization

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] skills/__init__.py updated with DelegateTodoSkill
  - [ ] Registry registration added for delegate_todo skill
  - [ ] python -c "from iron_rook.review.registry import ReviewerRegistry; r = ReviewerRegistry(); print([x for x in r.get_all_names() if 'delegate' in x.lower()])" returns nothing
  - [ ] python -c "from iron_rook.review.registry import ReviewerRegistry; r = ReviewerRegistry(); assert 'delegate_todo' in r.get_all_names()" succeeds
  - [ ] pytest tests/unit/review/agents/test_security_fsm.py -v - PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > **Scenario: New skill registered and discoverable**
  > ```yaml
  > Tool: Bash
  > Preconditions: Code changes applied
  > Steps:
  >   1. python -c "from iron_rook.review.registry import ReviewerRegistry; r = ReviewerRegistry(); print('Available skills:', r.get_all_names())"
  >   2. Assert: 'delegate_todo' appears in output
  >   3. Assert: import works without errors
  > Expected Result: Output contains 'delegate_todo' in available skills list, no import errors
  > Failure Indicators: Import error, 'delegate_todo' not in list
  > Evidence: Command output captured
  > ```

  **Commit**: YES (groups with Task 5)

- [ ] 6. Full integration test

  **What to do**:
  - Run complete FSM integration test with new act phase
  - Verify end-to-end flow: intake → plan_todos → act → collect → consolidate → evaluate → done
  - Verify todo tracking works across all phases
  - Verify findings are produced

  **Must NOT do**:
  - Do NOT modify test to require delegate phase

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Full FSM flow verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (final task after all code changes)
  - **Blocks**: None (end of work)

  **References** (CRITICAL - Be Exhaustive):

  **Pattern References** (existing code to follow):
  - `tests/integration/test_security_fsm_integration.py:199-410` - Full FSM integration test
  - `iron_rook/review/agents/security.py:review()` - FSM entry point

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py:ReviewOutput` - Final output structure
  - `iron_rook/review/contracts.py:ActPhaseOutput` - Act phase output

  **Test References** (testing patterns to follow):
  - Existing integration test pattern for FSM flow

  **Documentation References** (specs and requirements):
  - `iron_rook/review/readme.md` - Review agent documentation

  **WHY Each Reference Matters**:
  - Full integration test ensures all phases work together
  - Todo tracking must persist through entire flow
  - Findings must be produced by evaluate phase

  **Acceptance Criteria**:

  **If TDD (tests enabled):**
  - [ ] FSM executes all 6 phases
  - [ ] Transitions: intake → plan_todos → act → collect → consolidate → evaluate → done
  - [ ] Todo tracking: created in plan_todos, delegated in act, collected, consolidated, evaluated
  - [ ] Findings produced by evaluate phase
  - [ ] pytest tests/integration/test_security_fsm_integration.py -v - PASS
  - [ ] All evidence files captured

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  > **Scenario: End-to-end FSM execution from intake to done**
  > ```yaml
  > Tool: Bash (pytest)
  > Preconditions: Code changes applied, skill registered
  > Steps:
  >   1. pytest tests/integration/test_security_fsm_integration.py -v -k "full_fsm_flow"
  >   2. Assert: FSM executes all 6 phases
  >   3. Assert: Todo tracking works end-to-end
  >   4. Assert: Findings are produced
  > Expected Result: FSM completes successfully with findings
  > Failure Indicators: FSM fails mid-flow, no findings produced
  > Evidence: Test output captured
  > ```

  **Commit**: YES (final task)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | feat(security): Add DelegateTodoSkill for generic delegation | `iron_rook/review/skills/delegate_todo.py`, `iron_rook/review/skills/__init__.py`, `iron_rook/review/registry.py` | pytest tests/unit/review/agents/test_security_fsm.py -v -k "skill_registration" |
| 2 | refactor(security): Replace delegate phase with act in FSM | `iron_rook/review/agents/security.py`, `iron_rook/review/contracts.py` | pytest tests/unit/review/agents/test_security_fsm.py::test_security_fsm_transitions -v |
| 3 | refactor(contracts): Remove delegate phase models | `iron_rook/review/contracts.py` | python -c "from iron_rook.review.contracts import phase_schemas; assert 'delegate' not in phase_schemas" |
| 4 | test(security): Create tests for act phase | `tests/unit/review/agents/test_security_fsm_act_phase.py`, `tests/unit/review/agents/test_security_fsm.py` (updates), `tests/integration/test_security_fsm_integration.py` (updates) | pytest tests/unit/review/agents/test_security_fsm.py -v && pytest tests/integration/test_security_fsm_integration.py -v |
| 5 | test(integration): Full FSM integration test | (no files) | pytest tests/integration/test_security_fsm_integration.py -v -k "full_fsm_flow" |

---

## Success Criteria

### Verification Commands
```bash
# Verify no delegate phase remains
python -c "from iron_rook.review.contracts import phase_schemas; assert 'delegate' not in phase_schemas and set(phase_schemas.keys()) == {'intake', 'plan_todos', 'act', 'collect', 'consolidate', 'evaluate'}"

# Verify skill is registered
python -c "from iron_rook.review.registry import ReviewerRegistry; r = ReviewerRegistry(); assert 'delegate_todo' in r.get_all_names()"

# Run FSM tests
pytest tests/unit/review/agents/test_security_fsm.py -v
pytest tests/integration/test_security_fsm_integration.py -v -k "full_fsm_flow"
```

### Final Checklist
- [ ] FSM has 6 phases (delegate removed)
- [ ] Act phase successfully executes and delegates subagents
- [ ] DelegateTodoSkill is registered and discoverable
- [ ] All existing tests pass with new act phase
- [ ] Todo tracking works end-to-end (creation → delegation → collection → evaluation)
- [ ] ReviewOutput produced by act phase has correct structure for collect phase
- [ ] No delegate-related code or models remain in codebase
