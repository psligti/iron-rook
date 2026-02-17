# Review Agents Subagent Unification

## TL;DR

> **Quick Summary**: Convert all 11 review agents to use FSM + subagent pattern (like SecurityReviewer), eliminate optional/core distinction, use TDD with dynamic subagents for domain-specific analysis.
>
> **Deliverables**:
> - `BaseDelegationSkill` abstract base class for delegation skills
> - `BaseDynamicSubagent` abstract base class for dynamic subagents
> - 10 new domain-specific subagent classes (one per reviewer type)
> - 10 new delegation skills (one per reviewer type)
> - 10 converted reviewers with FSM pattern
> - 10 new test files (one per reviewer)
> - Updated registry with all reviewers as core
> - Shared test fixtures in `conftest.py`
>
> **Estimated Effort**: XL (Large multi-phase refactoring)
> **Parallel Execution**: YES - 5 waves with parallel tasks within each
> **Critical Path**: Test Infrastructure → Base Classes → Pilot → Batch Conversion → Registry

---

## Context

### Original Request
"All of the review agents need to use subagents to execute the review. These need to follow the same pattern as the security and architecture. There shouldn't be any optional agents."

### Interview Summary
**Key Discussions**:
- **Pattern**: FSM + Subagents (SecurityReviewer's multi-phase pattern with DelegateTodoSkill)
- **Subagent Type**: Dynamic (ReAct-style with looping, task-driven, LLM-guided)
- **Delegation Structure**: Base class + inheritance for delegation skills
- **Test Strategy**: TDD with minimum viable coverage (1 unit test file per reviewer)
- **Optional Reviewers**: All become core (always run)
- **Architecture**: Gets full FSM + subagents like Security

**Research Findings**:
- SecurityReviewer is the reference implementation (1650+ lines, 6-phase FSM)
- DelegateTodoSkill handles delegation to SecuritySubagent instances
- SecuritySubagent uses dynamic ReAct-style FSM with looping
- Other 10 reviewers use simple inline pattern via `_execute_review_with_runner()`
- Only SecurityReviewer has tests (4 test files, ~1,760 lines)
- No shared test fixtures exist

### Metis Review
**Identified Gaps** (addressed):
- **Test infrastructure missing**: Create `conftest.py` FIRST with shared fixtures
- **Two subagent patterns exist**: Decided on Dynamic (ReAct-style)
- **Test coverage gap**: Decided on minimum viable (1 unit test file per reviewer)
- **Pilot recommendation**: Use DocumentationReviewer as pilot before batch conversion
- **Registry update timing**: Do LAST (easiest to revert)

---

## Work Objectives

### Core Objective
Convert all 11 review agents in Iron Rook to use the FSM + subagent pattern, following SecurityReviewer as the reference implementation. Eliminate the concept of "optional" reviewers by making all reviewers core.

### Concrete Deliverables
- `tests/conftest.py` - Shared test fixtures
- `iron_rook/review/skills/base_delegation.py` - BaseDelegationSkill abstract class
- `iron_rook/review/subagents/base_subagent.py` - BaseDynamicSubagent abstract class
- 10 domain-specific subagents in `iron_rook/review/subagents/`
- 10 delegation skills in `iron_rook/review/skills/`
- 10 converted reviewers in `iron_rook/review/agents/`
- 10 test files in `tests/unit/review/agents/`
- Updated `iron_rook/review/registry.py` with all reviewers as core

### Definition of Done
- [ ] All 11 reviewers use FSM pattern with `prefers_direct_review()` returning `True`
- [ ] All reviewers have delegation skill in ACT phase
- [ ] All reviewers have domain-specific subagent class
- [ ] All reviewers have at least 1 unit test file
- [ ] Registry has no `is_core=False` entries
- [ ] `pytest tests/` passes
- [ ] CLI review command runs all 11 reviewers

### Must Have
- FSM pattern: INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE
- Dynamic subagents with ReAct-style looping
- Base class for delegation skills (DRY)
- TDD: tests written before implementation
- All optional reviewers become core

### Must NOT Have (Guardrails)
- NO refactoring of SecurityReviewer (reference implementation)
- NO new test infrastructure beyond pytest + pytest-asyncio
- NO integration tests in initial scope (add later)
- NO static subagent pattern (use dynamic only)
- NO changes to existing `SimpleReviewAgentRunner` mock patterns

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest + pytest-asyncio)
- **Automated tests**: TDD (Tests First)
- **Framework**: pytest
- **Coverage Target**: Minimum viable (1 unit test file per reviewer)

### QA Policy
Every task includes agent-executed QA scenarios.

| Deliverable Type | Verification Tool | Method |
|------------------|-------------------|--------|
| Python modules | Bash (python -c) | Import verification |
| Test files | Bash (pytest) | Run specific test file |
| FSM conversion | Bash (pytest) | Phase transition tests |
| Registry | Bash (python -c) | Verify all core |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (Start Immediately — test infrastructure):
├── Task 1: Create shared test fixtures [quick]
└── Task 2: Create mock phase responses helper [quick]

Wave 1 (After Wave 0 — base classes):
├── Task 3: Create BaseDelegationSkill abstract class [unspecified-high]
├── Task 4: Create BaseDynamicSubagent abstract class [unspecified-high]
├── Task 5: Create domain subagent template/macro [quick]
└── Task 6: Create delegation skill template/macro [quick]

Wave 2 (After Wave 1 — pilot: DocumentationReviewer):
├── Task 7: Write tests for DocumentationFSM [deep]
├── Task 8: Create DocumentationDelegationSkill [unspecified-high]
├── Task 9: Create DocumentationSubagent [deep]
├── Task 10: Convert DocumentationReviewer to FSM [deep]
└── Task 11: Verify pilot end-to-end [quick]

Wave 3 (After Wave 2 — remaining core reviewers, MAX PARALLEL):
├── Task 12: Architecture FSM tests [deep]
├── Task 13: Architecture delegation skill + subagent [unspecified-high]
├── Task 14: Architecture reviewer conversion [deep]
├── Task 15: Telemetry FSM tests [deep]
├── Task 16: Telemetry delegation skill + subagent [unspecified-high]
├── Task 17: Telemetry reviewer conversion [deep]
├── Task 18: Linting FSM tests [deep]
├── Task 19: Linting delegation skill + subagent [unspecified-high]
├── Task 20: Linting reviewer conversion [deep]
├── Task 21: UnitTests FSM tests [deep]
├── Task 22: UnitTests delegation skill + subagent [unspecified-high]
└── Task 23: UnitTests reviewer conversion [deep]

Wave 4 (After Wave 3 — optional → core promotions, MAX PARALLEL):
├── Task 24: DiffScoper FSM tests + skill + subagent + conversion [deep]
├── Task 25: Requirements FSM tests + skill + subagent + conversion [deep]
├── Task 26: Performance FSM tests + skill + subagent + conversion [deep]
├── Task 27: Dependencies FSM tests + skill + subagent + conversion [deep]
└── Task 28: Changelog FSM tests + skill + subagent + conversion [deep]

Wave 5 (After Wave 4 — registry update):
├── Task 29: Update registry - mark all as core [quick]
├── Task 30: Update CLI - remove --include-optional [quick]
└── Task 31: Update documentation [writing]

Wave FINAL (After ALL tasks — verification):
├── Task F1: Full test suite run [quick]
├── Task F2: Integration smoke test [quick]
├── Task F3: Registry verification [quick]
└── Task F4: CLI verification [quick]

Critical Path: Task 1 → Task 3-4 → Task 7-11 → Task 12-23 → Task 24-28 → Task 29-31 → F1-F4
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 12 (Waves 3 & 4)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|------------|--------|------|
| 1-2 | — | 3-6 | 0 |
| 3-6 | 1-2 | 7-28 | 1 |
| 7-11 | 3-6 | 12-28 | 2 |
| 12-23 | 7-11 | 24-28 | 3 |
| 24-28 | 12-23 | 29-31 | 4 |
| 29-31 | 24-28 | F1-F4 | 5 |
| F1-F4 | 29-31 | — | FINAL |

### Agent Dispatch Summary

| Wave | # Parallel | Tasks → Agent Category |
|------|------------|------------------------|
| 0 | **2** | T1-T2 → `quick` |
| 1 | **4** | T3-T4 → `unspecified-high`, T5-T6 → `quick` |
| 2 | **5** | T7, T9-T10 → `deep`, T8 → `unspecified-high`, T11 → `quick` |
| 3 | **12** | T12, T14, T15, T17, T18, T20, T21, T23 → `deep`, T13, T16, T19, T22 → `unspecified-high` |
| 4 | **5** | T24-T28 → `deep` |
| 5 | **3** | T29-T30 → `quick`, T31 → `writing` |
| FINAL | **4** | F1-F4 → `quick` |

---

## TODOs

### Wave 0: Test Infrastructure

- [ ] 1. Create shared test fixtures in `tests/conftest.py`

  **What to do**:
  - Create `tests/conftest.py` with shared pytest fixtures
  - Add `mock_review_context` fixture for standard ReviewContext
  - Add `mock_phase_responses` fixture for FSM phase JSON responses
  - Add `assert_valid_review_output` helper function
  - Add `mock_simple_runner` fixture for SimpleReviewAgentRunner mocking

  **Must NOT do**:
  - Do NOT create new testing utilities beyond fixtures
  - Do NOT modify existing test files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple fixture creation, well-defined scope
  - **Skills**: []
    - No special skills needed for fixture creation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 0 (with Task 2)
  - **Blocks**: Tasks 3-6
  - **Blocked By**: None

  **References**:
  - `tests/unit/review/agents/test_security_fsm.py:15-50` - Existing fixture patterns
  - `tests/integration/test_security_fsm_integration.py:30-60` - ReviewContext construction

  **Acceptance Criteria**:
  - [ ] File created: `tests/conftest.py`
  - [ ] `pytest tests/conftest.py` imports successfully
  - [ ] `mock_review_context` fixture available
  - [ ] `mock_simple_runner` fixture available

  **QA Scenarios**:
  ```
  Scenario: Fixtures import successfully
    Tool: Bash (python -c)
    Steps:
      1. python -c "from tests.conftest import mock_review_context, mock_simple_runner; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-01-fixtures-import.txt

  Scenario: Fixtures work in test
    Tool: Bash (pytest)
    Steps:
      1. Create minimal test using fixtures
      2. pytest tests/test_fixture_verification.py -v
    Expected Result: 1 passed
    Evidence: .sisyphus/evidence/task-01-fixtures-work.txt
  ```

  **Commit**: YES
  - Message: `test: add shared fixtures for review agent tests`
  - Files: `tests/conftest.py`

---

- [ ] 2. Create mock phase responses helper

  **What to do**:
  - Add `mock_phase_responses` fixture to `tests/conftest.py`
  - Create JSON response templates for each FSM phase:
    - intake_response, plan_response, act_response, synthesize_response, check_response
  - Add `create_mock_response(phase, overrides)` helper function

  **Must NOT do**:
  - Do NOT create domain-specific responses (keep generic)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple helper function creation
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 0 (with Task 1)
  - **Blocks**: Tasks 7-28
  - **Blocked By**: None

  **References**:
  - `tests/unit/review/agents/test_security_fsm.py:200-250` - Mock response patterns
  - `iron_rook/review/contracts.py` - ReviewOutput schema

  **Acceptance Criteria**:
  - [ ] `mock_phase_responses` fixture returns dict of phase → JSON
  - [ ] `create_mock_response("intake", {"custom": "data"})` works

  **QA Scenarios**:
  ```
  Scenario: Mock responses have correct structure
    Tool: Bash (python -c)
    Steps:
      1. python -c "from tests.conftest import mock_phase_responses; r = mock_phase_responses(); assert 'intake' in r; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-02-mock-responses.txt
  ```

  **Commit**: YES (groups with Task 1)
  - Message: `test: add mock phase response helpers`
  - Files: `tests/conftest.py`

---

### Wave 1: Base Classes

- [ ] 3. Create BaseDelegationSkill abstract class

  **What to do**:
  - Create `iron_rook/review/skills/base_delegation.py`
  - Define abstract base class `BaseDelegationSkill(BaseReviewerAgent)`
  - Abstract methods: `get_subagent_class()`, `build_subagent_request()`
  - Concrete method: `execute_subagents_concurrently()` using `asyncio.gather()`
  - Include error handling and result aggregation

  **Must NOT do**:
  - Do NOT include domain-specific logic
  - Do NOT modify existing DelegateTodoSkill

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires understanding of async patterns and FSM integration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 4-6)
  - **Blocks**: Tasks 8, 13, 16, 19, 22
  - **Blocked By**: Tasks 1-2

  **References**:
  - `iron_rook/review/skills/delegate_todo.py:186-251` - Concurrent execution pattern
  - `iron_rook/review/base.py` - BaseReviewerAgent interface
  - `iron_rook/review/subagents/security_subagent_dynamic.py:44-50` - FSM transitions

  **Acceptance Criteria**:
  - [ ] File created: `iron_rook/review/skills/base_delegation.py`
  - [ ] `BaseDelegationSkill` inherits from `BaseReviewerAgent`
  - [ ] `execute_subagents_concurrently()` uses `asyncio.gather()`
  - [ ] Unit tests pass

  **QA Scenarios**:
  ```
  Scenario: BaseDelegationSkill imports and instantiates
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.skills.base_delegation import BaseDelegationSkill; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-03-base-delegation-import.txt

  Scenario: Abstract methods enforced
    Tool: Bash (python -c)
    Steps:
      1. Try to instantiate BaseDelegationSkill directly
      2. Verify TypeError raised
    Expected Result: TypeError with "abstract" in message
    Evidence: .sisyphus/evidence/task-03-abstract-enforced.txt
  ```

  **Commit**: YES
  - Message: `feat(skills): add BaseDelegationSkill abstract class`
  - Files: `iron_rook/review/skills/base_delegation.py`

---

- [ ] 4. Create BaseDynamicSubagent abstract class

  **What to do**:
  - Create `iron_rook/review/subagents/base_subagent.py`
  - Define abstract base class `BaseDynamicSubagent(BaseReviewerAgent)`
  - Implement ReAct-style FSM: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)
  - Include looping capability with stop conditions:
    - MAX_ITERATIONS = 10
    - STAGNATION_THRESHOLD = 2
    - goal_met check
  - Abstract methods: `get_domain_tools()`, `get_domain_prompt()`

  **Must NOT do**:
  - Do NOT include security-specific logic
  - Do NOT modify existing SecuritySubagent

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Complex FSM implementation with async patterns
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 3, 5-6)
  - **Blocks**: Tasks 9, 13, 16, 19, 22
  - **Blocked By**: Tasks 1-2

  **References**:
  - `iron_rook/review/subagents/security_subagent_dynamic.py:44-200` - FSM structure
  - `iron_rook/review/subagents/security_subagent_dynamic.py:52-54` - Stop conditions
  - `iron_rook/review/base.py` - BaseReviewerAgent interface

  **Acceptance Criteria**:
  - [ ] File created: `iron_rook/review/subagents/base_subagent.py`
  - [ ] `BaseDynamicSubagent` inherits from `BaseReviewerAgent`
  - [ ] FSM transitions match SecuritySubagent
  - [ ] Stop conditions implemented

  **QA Scenarios**:
  ```
  Scenario: BaseDynamicSubagent imports successfully
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.subagents.base_subagent import BaseDynamicSubagent; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-04-base-subagent-import.txt

  Scenario: FSM transitions defined correctly
    Tool: Bash (python -c)
    Steps:
      1. Verify REACT_FSM_TRANSITIONS matches expected
    Expected Result: transitions = {"intake": ["plan"], "plan": ["act"], ...}
    Evidence: .sisyphus/evidence/task-04-fsm-transitions.txt
  ```

  **Commit**: YES
  - Message: `feat(subagents): add BaseDynamicSubagent abstract class`
  - Files: `iron_rook/review/subagents/base_subagent.py`

---

- [ ] 5. Create domain subagent template

  **What to do**:
  - Create `iron_rook/review/subagents/TEMPLATE_SUBAGENT.md`
  - Document the pattern for creating new domain subagents
  - Include code template with placeholder variables
  - Document required methods and their signatures

  **Must NOT do**:
  - Do NOT create actual subagent implementations

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Documentation task
  - **Skills**: [`writing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 3-4, 6)
  - **Blocks**: None (reference only)
  - **Blocked By**: Tasks 3-4

  **References**:
  - `iron_rook/review/subagents/security_subagent_dynamic.py` - Full implementation reference

  **Acceptance Criteria**:
  - [ ] Template file created
  - [ ] Includes all required method signatures
  - [ ] Includes example configuration

  **QA Scenarios**:
  ```
  Scenario: Template exists and is readable
    Tool: Bash (cat)
    Steps:
      1. cat iron_rook/review/subagents/TEMPLATE_SUBAGENT.md | head -20
    Expected Result: Template content displayed
    Evidence: .sisyphus/evidence/task-05-template-exists.txt
  ```

  **Commit**: YES
  - Message: `docs: add domain subagent creation template`
  - Files: `iron_rook/review/subagents/TEMPLATE_SUBAGENT.md`

---

- [ ] 6. Create delegation skill template

  **What to do**:
  - Create `iron_rook/review/skills/TEMPLATE_SKILL.md`
  - Document the pattern for creating new delegation skills
  - Include code template with placeholder variables
  - Document integration with parent reviewer

  **Must NOT do**:
  - Do NOT create actual skill implementations

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Documentation task
  - **Skills**: [`writing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 3-5)
  - **Blocks**: None (reference only)
  - **Blocked By**: Tasks 3-4

  **References**:
  - `iron_rook/review/skills/delegate_todo.py` - Full implementation reference

  **Acceptance Criteria**:
  - [ ] Template file created
  - [ ] Includes inheritance from BaseDelegationSkill
  - [ ] Includes example configuration

  **QA Scenarios**:
  ```
  Scenario: Template exists and is readable
    Tool: Bash (cat)
    Steps:
      1. cat iron_rook/review/skills/TEMPLATE_SKILL.md | head -20
    Expected Result: Template content displayed
    Evidence: .sisyphus/evidence/task-06-skill-template-exists.txt
  ```

  **Commit**: YES
  - Message: `docs: add delegation skill creation template`
  - Files: `iron_rook/review/skills/TEMPLATE_SKILL.md`

---

### Wave 2: Pilot - DocumentationReviewer

- [ ] 7. Write tests for DocumentationFSM

  **What to do**:
  - Create `tests/unit/review/agents/test_documentation_fsm.py`
  - Test FSM phase transitions (INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE)
  - Test `prefers_direct_review()` returns `True`
  - Test each phase handler exists
  - Test error handling for invalid transitions
  - Use shared fixtures from conftest.py

  **Must NOT do**:
  - Do NOT test DocumentationSubagent (separate task)
  - Do NOT create implementation yet (TDD)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requires understanding FSM patterns and test design
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (first task in pilot)
  - **Parallel Group**: Wave 2 (sequential: 7 → 8 → 9 → 10 → 11)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 3-4

  **References**:
  - `tests/unit/review/agents/test_security_fsm.py` - Full test pattern reference
  - `tests/conftest.py` - Shared fixtures

  **Acceptance Criteria**:
  - [ ] File created: `tests/unit/review/agents/test_documentation_fsm.py`
  - [ ] At least 10 test functions
  - [ ] All tests initially FAIL (TDD red phase)

  **QA Scenarios**:
  ```
  Scenario: Test file has required tests
    Tool: Bash (grep)
    Steps:
      1. grep -c "def test_" tests/unit/review/agents/test_documentation_fsm.py
    Expected Result: Count >= 10
    Evidence: .sisyphus/evidence/task-07-test-count.txt

  Scenario: Tests initially fail (TDD red)
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_documentation_fsm.py -v 2>&1 | head -30
    Expected Result: Import errors or assertion failures (expected in TDD red)
    Evidence: .sisyphus/evidence/task-07-tdd-red.txt
  ```

  **Commit**: YES
  - Message: `test(documentation): add FSM tests (TDD red phase)`
  - Files: `tests/unit/review/agents/test_documentation_fsm.py`

---

- [ ] 8. Create DocumentationDelegationSkill

  **What to do**:
  - Create `iron_rook/review/skills/documentation_delegation.py`
  - Inherit from `BaseDelegationSkill`
  - Implement `get_subagent_class()` returning `DocumentationSubagent`
  - Implement `build_subagent_request()` for documentation-specific requests
  - Override `get_system_prompt()` with documentation delegation instructions

  **Must NOT do**:
  - Do NOT include non-documentation concerns
  - Do NOT modify BaseDelegationSkill

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires understanding delegation pattern and domain
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 7)
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: Task 10
  - **Blocked By**: Task 3, Task 7

  **References**:
  - `iron_rook/review/skills/delegate_todo.py` - Reference implementation
  - `iron_rook/review/skills/base_delegation.py` - Base class
  - `iron_rook/review/agents/documentation.py:26-50` - Documentation domain

  **Acceptance Criteria**:
  - [ ] File created: `iron_rook/review/skills/documentation_delegation.py`
  - [ ] Inherits from `BaseDelegationSkill`
  - [ ] `get_subagent_class()` returns `DocumentationSubagent`

  **QA Scenarios**:
  ```
  Scenario: Skill imports and instantiates
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.skills.documentation_delegation import DocumentationDelegationSkill; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-08-skill-import.txt
  ```

  **Commit**: YES
  - Message: `feat(skills): add DocumentationDelegationSkill`
  - Files: `iron_rook/review/skills/documentation_delegation.py`

---

- [ ] 9. Create DocumentationSubagent

  **What to do**:
  - Create `iron_rook/review/subagents/documentation_subagent.py`
  - Inherit from `BaseDynamicSubagent`
  - Implement `get_domain_tools()` returning documentation tools
  - Implement `get_domain_prompt()` with documentation-specific instructions
  - Tools: grep, read, file, python (for docstring extraction)

  **Must NOT do**:
  - Do NOT include non-documentation concerns
  - Do NOT modify BaseDynamicSubagent

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Full subagent implementation with FSM
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 8)
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: Task 10
  - **Blocked By**: Task 4, Task 8

  **References**:
  - `iron_rook/review/subagents/security_subagent_dynamic.py` - Reference implementation
  - `iron_rook/review/subagents/base_subagent.py` - Base class
  - `iron_rook/review/agents/documentation.py` - Domain context

  **Acceptance Criteria**:
  - [ ] File created: `iron_rook/review/subagents/documentation_subagent.py`
  - [ ] Inherits from `BaseDynamicSubagent`
  - [ ] FSM phases implemented
  - [ ] Domain tools configured

  **QA Scenarios**:
  ```
  Scenario: Subagent imports and instantiates
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.subagents.documentation_subagent import DocumentationSubagent; s = DocumentationSubagent(task={'todo_id': 'test'}); print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-09-subagent-import.txt

  Scenario: Subagent has correct tools
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.subagents.documentation_subagent import DocumentationSubagent; s = DocumentationSubagent(task={}); tools = s.get_allowed_tools(); assert 'read' in tools; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-09-subagent-tools.txt
  ```

  **Commit**: YES
  - Message: `feat(subagents): add DocumentationSubagent`
  - Files: `iron_rook/review/subagents/documentation_subagent.py`

---

- [ ] 10. Convert DocumentationReviewer to FSM

  **What to do**:
  - Modify `iron_rook/review/agents/documentation.py`
  - Add FSM phases: `_run_intake()`, `_run_plan()`, `_run_act()`, `_run_synthesize()`, `_run_check()`
  - Add `VALID_TRANSITIONS` dict
  - Add `_run_review_fsm()` method
  - Modify `review()` to call FSM
  - Add `prefers_direct_review()` returning `True`
  - Use `DocumentationDelegationSkill` in ACT phase
  - Keep existing `get_system_prompt()` for phase prompts

  **Must NOT do**:
  - Do NOT change the public interface (get_agent_name, get_system_prompt)
  - Do NOT remove existing functionality

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex refactoring with FSM integration
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 8-9)
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: Task 11
  - **Blocked By**: Tasks 7-9

  **References**:
  - `iron_rook/review/agents/security.py:100-160` - FSM structure
  - `iron_rook/review/agents/security.py:343-408` - ACT phase with delegation
  - `iron_rook/review/agents/documentation.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] `prefers_direct_review()` returns `True`
  - [ ] All 5 phase handlers exist
  - [ ] `review()` calls `_run_review_fsm()`
  - [ ] Tests from Task 7 now PASS (TDD green phase)

  **QA Scenarios**:
  ```
  Scenario: Reviewer uses FSM
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.agents.documentation import DocumentationReviewer; r = DocumentationReviewer(); assert r.prefers_direct_review() == True; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-10-fsm-enabled.txt

  Scenario: Tests pass (TDD green)
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_documentation_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-10-tdd-green.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert DocumentationReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/documentation.py`

---

- [ ] 11. Verify pilot end-to-end

  **What to do**:
  - Run full test suite for DocumentationReviewer
  - Verify import chain works: reviewer → skill → subagent
  - Verify FSM transitions work correctly
  - Create simple integration test

  **Must NOT do**:
  - Do NOT proceed to Wave 3 if any tests fail

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Verification task
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (verification gate)
  - **Parallel Group**: Wave 2 (final task)
  - **Blocks**: Tasks 12-28
  - **Blocked By**: Tasks 7-10

  **References**:
  - `tests/unit/review/agents/test_documentation_fsm.py`
  - `tests/integration/test_security_fsm_integration.py` - Integration pattern

  **Acceptance Criteria**:
  - [ ] All DocumentationReviewer tests pass
  - [ ] Import chain verified
  - [ ] FSM transitions verified

  **QA Scenarios**:
  ```
  Scenario: Full test suite passes
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_documentation_fsm.py -v --tb=short
    Expected Result: All tests pass, 0 failures
    Evidence: .sisyphus/evidence/task-11-full-pass.txt

  Scenario: Import chain works
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.agents.documentation import DocumentationReviewer; from iron_rook.review.skills.documentation_delegation import DocumentationDelegationSkill; from iron_rook.review.subagents.documentation_subagent import DocumentationSubagent; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-11-import-chain.txt
  ```

  **Commit**: NO (verification only)

---

### Wave 3: Remaining Core Reviewers

- [ ] 12-14. Architecture Reviewer Conversion

  **What to do** (3 subtasks):
  - 12: Create `tests/unit/review/agents/test_architecture_fsm.py` (TDD red)
  - 13: Create `ArchitectureDelegationSkill` + `ArchitectureSubagent`
  - 14: Convert `ArchitectureReviewer` to FSM (TDD green)

  **Must NOT do**:
  - Do NOT change architecture domain logic
  - Do NOT modify existing system prompt content

  **Recommended Agent Profile**:
  - **Category**: `deep` (12, 14), `unspecified-high` (13)
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with other Wave 3 tasks)
  - **Parallel Group**: Wave 3
  - **Blocks**: Wave 4
  - **Blocked By**: Wave 2 complete

  **References**:
  - Tasks 7-10 (pilot pattern to follow)
  - `iron_rook/review/agents/architecture.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created with FSM tests
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Architecture FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_architecture_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-12-14-architecture-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert ArchitectureReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/architecture.py`, `iron_rook/review/skills/architecture_delegation.py`, `iron_rook/review/subagents/architecture_subagent.py`, `tests/unit/review/agents/test_architecture_fsm.py`

---

- [ ] 15-17. Telemetry Reviewer Conversion

  **What to do** (3 subtasks):
  - 15: Create `tests/unit/review/agents/test_telemetry_fsm.py` (TDD red)
  - 16: Create `TelemetryDelegationSkill` + `TelemetrySubagent`
  - 17: Convert `TelemetryMetricsReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/telemetry.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Telemetry FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_telemetry_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-15-17-telemetry-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert TelemetryMetricsReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/telemetry.py`, `iron_rook/review/skills/telemetry_delegation.py`, `iron_rook/review/subagents/telemetry_subagent.py`, `tests/unit/review/agents/test_telemetry_fsm.py`

---

- [ ] 18-20. Linting Reviewer Conversion

  **What to do** (3 subtasks):
  - 18: Create `tests/unit/review/agents/test_linting_fsm.py` (TDD red)
  - 19: Create `LintingDelegationSkill` + `LintingSubagent`
  - 20: Convert `LintingReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/linting.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Linting FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_linting_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-18-20-linting-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert LintingReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/linting.py`, `iron_rook/review/skills/linting_delegation.py`, `iron_rook/review/subagents/linting_subagent.py`, `tests/unit/review/agents/test_linting_fsm.py`

---

- [ ] 21-23. UnitTests Reviewer Conversion

  **What to do** (3 subtasks):
  - 21: Create `tests/unit/review/agents/test_unit_tests_fsm.py` (TDD red)
  - 22: Create `UnitTestsDelegationSkill` + `UnitTestsSubagent`
  - 23: Convert `UnitTestsReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/unit_tests.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: UnitTests FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_unit_tests_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-21-23-unittests-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert UnitTestsReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/unit_tests.py`, `iron_rook/review/skills/unit_tests_delegation.py`, `iron_rook/review/subagents/unit_tests_subagent.py`, `tests/unit/review/agents/test_unit_tests_fsm.py`

---

### Wave 4: Optional → Core Promotions

- [ ] 24. DiffScoper Reviewer Conversion

  **What to do**:
  - Create test file (TDD red)
  - Create `DiffScoperDelegationSkill` + `DiffScoperSubagent`
  - Convert `DiffScoperReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/diff_scoper.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: DiffScoper FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_diff_scoper_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-24-diffscoper-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert DiffScoperReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/diff_scoper.py`, `iron_rook/review/skills/diff_scoper_delegation.py`, `iron_rook/review/subagents/diff_scoper_subagent.py`, `tests/unit/review/agents/test_diff_scoper_fsm.py`

---

- [ ] 25. Requirements Reviewer Conversion

  **What to do**:
  - Create test file (TDD red)
  - Create `RequirementsDelegationSkill` + `RequirementsSubagent`
  - Convert `RequirementsReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/requirements.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Requirements FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_requirements_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-25-requirements-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert RequirementsReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/requirements.py`, `iron_rook/review/skills/requirements_delegation.py`, `iron_rook/review/subagents/requirements_subagent.py`, `tests/unit/review/agents/test_requirements_fsm.py`

---

- [ ] 26. Performance Reviewer Conversion

  **What to do**:
  - Create test file (TDD red)
  - Create `PerformanceDelegationSkill` + `PerformanceSubagent`
  - Convert `PerformanceReliabilityReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/performance.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Performance FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_performance_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-26-performance-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert PerformanceReliabilityReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/performance.py`, `iron_rook/review/skills/performance_delegation.py`, `iron_rook/review/subagents/performance_subagent.py`, `tests/unit/review/agents/test_performance_fsm.py`

---

- [ ] 27. Dependencies Reviewer Conversion

  **What to do**:
  - Create test file (TDD red)
  - Create `DependenciesDelegationSkill` + `DependenciesSubagent`
  - Convert `DependencyLicenseReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/dependencies.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Dependencies FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_dependencies_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-27-dependencies-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert DependencyLicenseReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/dependencies.py`, `iron_rook/review/skills/dependencies_delegation.py`, `iron_rook/review/subagents/dependencies_subagent.py`, `tests/unit/review/agents/test_dependencies_fsm.py`

---

- [ ] 28. Changelog Reviewer Conversion

  **What to do**:
  - Create test file (TDD red)
  - Create `ChangelogDelegationSkill` + `ChangelogSubagent`
  - Convert `ReleaseChangelogReviewer` to FSM (TDD green)

  **References**:
  - Tasks 7-10 (pilot pattern)
  - `iron_rook/review/agents/changelog.py` - Current implementation

  **Acceptance Criteria**:
  - [ ] Test file created
  - [ ] Skill and subagent created
  - [ ] Reviewer converted to FSM
  - [ ] All tests pass

  **QA Scenarios**:
  ```
  Scenario: Changelog FSM tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/unit/review/agents/test_changelog_fsm.py -v
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-28-changelog-pass.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): convert ReleaseChangelogReviewer to FSM pattern`
  - Files: `iron_rook/review/agents/changelog.py`, `iron_rook/review/skills/changelog_delegation.py`, `iron_rook/review/subagents/changelog_subagent.py`, `tests/unit/review/agents/test_changelog_fsm.py`

---

### Wave 5: Registry Update

- [ ] 29. Update registry - mark all as core

  **What to do**:
  - Modify `iron_rook/review/registry.py`
  - Change all `is_core=False` to `is_core=True`
  - Update `_register_default_reviewers()` function
  - Keep `get_optional_names()` method for backward compatibility (returns empty list)

  **Must NOT do**:
  - Do NOT remove `get_optional_names()` method (backward compat)
  - Do NOT change method signatures

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple configuration change
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 30-31)
  - **Parallel Group**: Wave 5
  - **Blocks**: Tasks F1-F4
  - **Blocked By**: Tasks 24-28

  **References**:
  - `iron_rook/review/registry.py:266-296` - Current registration

  **Acceptance Criteria**:
  - [ ] All reviewers registered with `is_core=True`
  - [ ] `get_core_reviewers()` returns all 11 reviewers
  - [ ] `get_optional_names()` returns empty list

  **QA Scenarios**:
  ```
  Scenario: All reviewers are core
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.registry import ReviewerRegistry; core = ReviewerRegistry.get_core_names(); print(len(core)); assert len(core) == 11; print('OK')"
    Expected Result: "11\nOK" printed
    Evidence: .sisyphus/evidence/task-29-all-core.txt

  Scenario: Optional list is empty
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.registry import ReviewerRegistry; opt = ReviewerRegistry.get_optional_names(); assert len(opt) == 0; print('OK')"
    Expected Result: "OK" printed
    Evidence: .sisyphus/evidence/task-29-no-optional.txt
  ```

  **Commit**: YES
  - Message: `feat(registry): mark all reviewers as core`
  - Files: `iron_rook/review/registry.py`

---

- [ ] 30. Update CLI - remove --include-optional flag

  **What to do**:
  - Modify `iron_rook/review/cli.py`
  - Remove `--include-optional` flag (no longer needed)
  - Update help text to reflect all reviewers run by default
  - Keep `--agents` flag for selective reviewer selection

  **Must NOT do**:
  - Do NOT change other CLI behavior
  - Do NOT remove `--agents` flag

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple flag removal
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 29, 31)
  - **Parallel Group**: Wave 5
  - **Blocks**: Task F4
  - **Blocked By**: Tasks 24-28

  **References**:
  - `iron_rook/review/cli.py:350-380` - Current CLI flags

  **Acceptance Criteria**:
  - [ ] `--include-optional` flag removed
  - [ ] Help text updated
  - [ ] `--agents` flag still works

  **QA Scenarios**:
  ```
  Scenario: --include-optional flag removed
    Tool: Bash (iron-rook)
    Steps:
      1. iron-rook review --help | grep -c "include-optional" || echo "0"
    Expected Result: "0" (flag not found)
    Evidence: .sisyphus/evidence/task-30-flag-removed.txt
  ```

  **Commit**: YES
  - Message: `feat(cli): remove --include-optional flag`
  - Files: `iron_rook/review/cli.py`

---

- [ ] 31. Update documentation

  **What to do**:
  - Update `README.md` to reflect new architecture
  - Remove mention of "optional" reviewers
  - Document the FSM + subagent pattern
  - Update built-in reviewers table

  **Must NOT do**:
  - Do NOT add extensive new documentation (keep minimal)

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation task
  - **Skills**: [`writing`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 29-30)
  - **Parallel Group**: Wave 5
  - **Blocks**: None
  - **Blocked By**: Tasks 24-28

  **References**:
  - `README.md` - Current documentation

  **Acceptance Criteria**:
  - [ ] README updated
  - [ ] No mention of "optional" reviewers
  - [ ] Built-in reviewers table shows all 11

  **QA Scenarios**:
  ```
  Scenario: README has no optional mention
    Tool: Bash (grep)
    Steps:
      1. grep -ic "optional.*review" README.md || echo "0"
    Expected Result: "0" (no matches)
    Evidence: .sisyphus/evidence/task-31-readme-updated.txt
  ```

  **Commit**: YES
  - Message: `docs: update README for unified reviewer architecture`
  - Files: `README.md`

---

### Wave FINAL: Verification

- [ ] F1. Full test suite run

  **What to do**:
  - Run complete test suite
  - Verify all tests pass
  - Check coverage metrics

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **QA Scenarios**:
  ```
  Scenario: All tests pass
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/ -v --tb=short 2>&1 | tail -20
    Expected Result: "X passed, 0 failed"
    Evidence: .sisyphus/evidence/final-f1-all-pass.txt
  ```

  **Commit**: NO (verification only)

---

- [ ] F2. Integration smoke test

  **What to do**:
  - Run a simple PR review end-to-end
  - Verify all 11 reviewers execute
  - Check output format

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **QA Scenarios**:
  ```
  Scenario: Review command runs all reviewers
    Tool: Bash (iron-rook)
    Steps:
      1. iron-rook review --repo-root . --base-ref HEAD~1 --head-ref HEAD 2>&1 | grep -c "agent\|reviewer" || echo "0"
    Expected Result: Count >= 11
    Evidence: .sisyphus/evidence/final-f2-smoke-test.txt
  ```

  **Commit**: NO (verification only)

---

- [ ] F3. Registry verification

  **What to do**:
  - Verify all 11 reviewers are registered as core
  - Verify no optional reviewers exist
  - Verify reviewer names match expected

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **QA Scenarios**:
  ```
  Scenario: All 11 core reviewers
    Tool: Bash (python -c)
    Steps:
      1. python -c "from iron_rook.review.registry import ReviewerRegistry; names = sorted(ReviewerRegistry.get_core_names()); print('\\n'.join(names)); assert len(names) == 11"
    Expected Result: 11 reviewer names printed
    Evidence: .sisyphus/evidence/final-f3-registry.txt
  ```

  **Commit**: NO (verification only)

---

- [ ] F4. CLI verification

  **What to do**:
  - Verify CLI works with new architecture
  - Test --agents flag for selective review
  - Verify help output is correct

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **QA Scenarios**:
  ```
  Scenario: CLI help works
    Tool: Bash (iron-rook)
    Steps:
      1. iron-rook --help
    Expected Result: Help text displayed
    Evidence: .sisyphus/evidence/final-f4-cli-help.txt

  Scenario: Selective agent works
    Tool: Bash (iron-rook)
    Steps:
      1. iron-rook review --agents security --repo-root . --base-ref HEAD~1 --head-ref HEAD 2>&1 | head -10
    Expected Result: Only security reviewer runs
    Evidence: .sisyphus/evidence/final-f4-selective.txt
  ```

  **Commit**: NO (verification only)

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
pytest tests/ -v

# All reviewers are core
python -c "from iron_rook.review.registry import ReviewerRegistry; print(len(ReviewerRegistry.get_core_names()))"
# Expected: 11

# No optional reviewers
python -c "from iron_rook.review.registry import ReviewerRegistry; print(len(ReviewerRegistry.get_optional_names()))"
# Expected: 0

# CLI works
iron-rook review --help
```

### Final Checklist
- [ ] All 11 reviewers use FSM pattern with `prefers_direct_review()` = True
- [ ] All reviewers have delegation skill in ACT phase
- [ ] All reviewers have domain-specific subagent class
- [ ] All reviewers have at least 1 unit test file
- [ ] Registry has no `is_core=False` entries
- [ ] `pytest tests/` passes with 0 failures
- [ ] CLI `iron-rook review` runs all 11 reviewers
