# Standardize Review Agents to FSM Pattern

## TL;DR

> **Quick Summary**: Refactor all 10 non-security review agents to follow the 6-phase FSM pattern (INTAKE → PLAN → ACT → SYNTHESIZE → CHECK → DONE) established by the security agent and now implemented for architecture.
> 
> **Deliverables**:
> - 9 refactored agent files with FSM pattern
> - Optional shared `FSMReviewerAgent` base class
> - Updated tests for FSM-based agents
> - Documentation updates
> 
> **Estimated Effort**: Large (9 agents × ~2 hours each = ~18 hours)
> **Parallel Execution**: YES - Each agent can be refactored independently
> **Critical Path**: Architecture (template) → Other agents → Integration testing

---

## Context

### Original Request
User requested creation of git worktrees for each review agent and implementation of the 6-phase FSM pattern across all agents to match the security reviewer's architecture.

### Interview Summary
**Key Discussions**:
- FSM Pattern: Security agent uses WorkflowFSMAdapter with 6 phases (intake, plan, act, synthesize, check, done)
- Subagent Delegation: DelegateTodoSkill dispatches parallel subagent tasks for evidence collection
- Worktrees: 10 agent worktrees created in `~/develop/pt/worktrees/iron-rook/`
- Template: Architecture agent selected as first implementation, completed and committed

**Research Findings**:
- All 11 agents currently use simple FSM_TRANSITIONS (IDLE → INITIALIZING → READY → RUNNING → COMPLETED)
- Only security and architecture use full 6-phase FSM with subagent delegation
- Finding.owner is constrained to Literal["dev", "docs", "devops", "security"]

### Current State

**Completed:**
| Agent | Worktree | Branch | Status |
|-------|----------|--------|--------|
| security | `~/develop/pt/worktrees/iron-rook-fsm` | `feature/iron-rook-use-harness-fsm` | ✓ FSM Done |
| architecture | `~/develop/pt/worktrees/iron-rook/architecture` | `feature/agent-architecture-fsm-pattern` | ✓ FSM Done (b6664cb) |

**Pending FSM Implementation:**
| Agent | Worktree | Branch |
|-------|----------|--------|
| linting | `~/develop/pt/worktrees/iron-rook/linting` | `feature/agent-linting-fsm-pattern` |
| documentation | `~/develop/pt/worktrees/iron-rook/documentation` | `feature/agent-documentation-fsm-pattern` |
| telemetry | `~/develop/pt/worktrees/iron-rook/telemetry` | `feature/agent-telemetry-fsm-pattern` |
| unit-tests | `~/develop/pt/worktrees/iron-rook/unit-tests` | `feature/agent-unit-tests-fsm-pattern` |
| performance | `~/develop/pt/worktrees/iron-rook/performance` | `feature/agent-performance-fsm-pattern` |
| dependencies | `~/develop/pt/worktrees/iron-rook/dependencies` | `feature/agent-dependencies-fsm-pattern` |
| requirements | `~/develop/pt/worktrees/iron-rook/requirements` | `feature/agent-requirements-fsm-pattern` |
| changelog | `~/develop/pt/worktrees/iron-rook/changelog` | `feature/agent-changelog-fsm-pattern` |
| diff-scoper | `~/develop/pt/worktrees/iron-rook/diff-scoper` | `feature/agent-diff-scoper-fsm-pattern` |

---

## Work Objectives

### Core Objective
Standardize all review agents to use the 6-phase FSM pattern with subagent delegation for consistent, evidence-based code reviews.

### Concrete Deliverables
- [ ] 9 refactored agent files with full FSM implementation
- [ ] Optional: Shared `FSMReviewerAgent` base class in `iron_rook/review/base_fsm.py`
- [ ] Updated `Finding.owner` enum to include new agent types
- [ ] Integration tests for FSM-based agents

### Definition of Done
- [ ] Each agent implements `_run_intake()`, `_run_plan()`, `_run_act()`, `_run_synthesize()`, `_run_check()`
- [ ] Each agent uses `WorkflowFSMAdapter` for phase management
- [ ] Each agent logs `ThinkingFrame` per phase
- [ ] Each agent delegates to subagents via `DelegateTodoSkill` in ACT phase
- [ ] All changes committed to respective feature branches

### Must Have
- All 9 remaining agents refactored to FSM pattern
- Phase-specific prompts for each agent's domain
- Backward compatibility with existing API

### Must NOT Have (Guardrails)
- Do NOT change the security agent (already complete)
- Do NOT change the architecture agent (already complete)
- Do NOT add new dependencies
- Do NOT break existing tests

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: YES (TDD approach)
- **Framework**: pytest

### Agent-Executed QA Scenarios

**Scenario: FSM Phase Transitions**
```
Tool: Bash (pytest)
Preconditions: Agent file exists, imports work
Steps:
  1. pytest tests/unit/review/agents/test_{agent}_fsm.py -v
  2. Assert: all phase transition tests pass
  3. Assert: ThinkingFrame logging works
Expected Result: All tests pass with proper phase transitions
Evidence: test_output.log
```

**Scenario: Subagent Delegation**
```
Tool: Bash (pytest)
Preconditions: Agent has DelegateTodoSkill integration
Steps:
  1. pytest tests/unit/review/agents/test_{agent}_delegation.py -v
  2. Assert: subagent tasks are created from PLAN output
  3. Assert: findings are collected from subagent results
Expected Result: Delegation tests pass
Evidence: delegation_test_output.log
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Core Agents - High Priority):
├── linting: Most frequently used, needs early validation
└── documentation: Similar complexity to architecture

Wave 2 (Quality Agents - Medium Priority):
├── unit-tests: Test infrastructure, important for coverage
├── telemetry: Monitoring infrastructure
└── performance: Reliability checks

Wave 3 (Optional Agents - Lower Priority):
├── dependencies: Dependency management
├── requirements: Requirements traceability
├── changelog: Release hygiene
└── diff-scoper: Change scope analysis
```

### Dependency Matrix

| Agent | Depends On | Blocks | Can Parallelize With |
|-------|------------|--------|---------------------|
| linting | architecture (template) | None | Wave 1 agents |
| documentation | architecture (template) | None | Wave 1 agents |
| unit-tests | architecture (template) | None | Wave 2 agents |
| telemetry | architecture (template) | None | Wave 2 agents |
| performance | architecture (template) | None | Wave 2 agents |
| dependencies | architecture (template) | None | Wave 3 agents |
| requirements | architecture (template) | None | Wave 3 agents |
| changelog | architecture (template) | None | Wave 3 agents |
| diff-scoper | architecture (template) | None | Wave 3 agents |

---

## TODOs

### Phase 1: Optional Shared Base Class

- [ ] 1. Create FSMReviewerAgent Base Class (Optional - Reduces Duplication)

  **What to do**:
  - Create `iron_rook/review/base_fsm.py` with shared FSM infrastructure
  - Extract common methods: `_execute_llm()`, `_extract_thinking_from_response()`, `_parse_phase_response()`
  - Define abstract methods for domain-specific prompts
  - Update architecture agent to inherit from base class

  **Must NOT do**:
  - Break existing security agent
  - Add new dependencies

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: [] (standard Python refactoring)

  **Parallelization**:
  - **Can Run In Parallel**: NO - Foundation for other agents
  - **Blocks**: All other agent refactorings
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/iron-rook/iron_rook/review/base.py` - Existing base class
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/architecture/iron_rook/review/agents/architecture.py` - Template implementation
  - `/Users/parkersligting/develop/pt/iron-rook/iron_rook/review/agents/security.py` - Security reference

  **Acceptance Criteria**:
  - [ ] File created: `iron_rook/review/base_fsm.py`
  - [ ] Base class defines `_run_review_fsm()`, `_get_phase_prompt()`, `_get_phase_specific_instructions()`
  - [ ] Abstract methods: `_get_domain_name()`, `_get_allowed_tools()`, `_get_relevant_patterns()`
  - [ ] pytest tests/unit/review/test_base_fsm.py passes

---

### Phase 2: Core Agent Refactoring (Wave 1)

- [ ] 2. Refactor Linting Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure to linting agent
  - Update class name: `LintingReviewer`
  - Update agent name: `linting_fsm`
  - Customize phase prompts for linting domain (formatting, style, type hints)
  - Update tools: ruff, black, isort, mypy

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - With documentation agent
  - **Parallel Group**: Wave 1 (with Task 3)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/linting/iron_rook/review/agents/linting.py` - Current implementation
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/architecture/iron_rook/review/agents/architecture.py` - Template

  **Phase Prompt Customization**:
  ```
  INTAKE: Analyze lint/style surfaces (formatting, imports, type hints)
  PLAN: Create TODOs for lint violations, formatting issues
  ACT: Run ruff/black/isort via subagents, collect violation evidence
  SYNTHESIZE: Merge lint findings, de-duplicate by file
  CHECK: Assess severity (critical=CI-blocking, warning=style)
  ```

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/linting.py`
  - [ ] All 5 phase methods implemented
  - [ ] `prefers_direct_review()` returns `True`
  - [ ] Commit: `feat(linting): implement 6-phase FSM review pattern`

---

- [ ] 3. Refactor Documentation Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure to documentation agent
  - Update class name: `DocumentationReviewer`
  - Update agent name: `documentation_fsm`
  - Customize phase prompts for documentation domain (docstrings, README, API docs)
  - Update tools: grep, read

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - With linting agent
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/documentation/iron_rook/review/agents/documentation.py`
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/architecture/iron_rook/review/agents/architecture.py` - Template

  **Phase Prompt Customization**:
  ```
  INTAKE: Analyze documentation surfaces (docstrings, README, CHANGELOG)
  PLAN: Create TODOs for missing docs, outdated content
  ACT: Check docstring coverage, README accuracy via subagents
  SYNTHESIZE: Merge documentation findings
  CHECK: Assess severity (critical=breaking, warning=incomplete)
  ```

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/documentation.py`
  - [ ] All 5 phase methods implemented
  - [ ] Commit: `feat(documentation): implement 6-phase FSM review pattern`

---

### Phase 3: Quality Agent Refactoring (Wave 2)

- [ ] 4. Refactor Unit Tests Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for test quality (coverage, assertions, mocking)
  - Update tools: pytest, coverage

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 2 agents
  - **Parallel Group**: Wave 2 (with Tasks 5, 6)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/unit-tests/iron_rook/review/agents/unit_tests.py`
  - Template: architecture agent

  **Phase Prompt Customization**:
  ```
  INTAKE: Analyze test surfaces (test files, coverage reports)
  PLAN: Create TODOs for missing tests, weak assertions
  ACT: Run pytest --collect, coverage analysis via subagents
  SYNTHESIZE: Merge test quality findings
  CHECK: Assess severity (critical=no tests, warning=low coverage)
  ```

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/unit_tests.py`
  - [ ] Commit: `feat(unit-tests): implement 6-phase FSM review pattern`

---

- [ ] 5. Refactor Telemetry Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for telemetry/metrics (logging, tracing, metrics)
  - Update tools: grep, python

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 2 agents
  - **Parallel Group**: Wave 2 (with Tasks 4, 6)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/telemetry/iron_rook/review/agents/telemetry.py`
  - Template: architecture agent

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/telemetry.py`
  - [ ] Commit: `feat(telemetry): implement 6-phase FSM review pattern`

---

- [ ] 6. Refactor Performance Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for performance (N+1 queries, memory leaks, slow operations)
  - Update tools: grep, python, pytest

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 2 agents
  - **Parallel Group**: Wave 2 (with Tasks 4, 5)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/performance/iron_rook/review/agents/performance.py`
  - Template: architecture agent

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/performance.py`
  - [ ] Commit: `feat(performance): implement 6-phase FSM review pattern`

---

### Phase 4: Optional Agent Refactoring (Wave 3)

- [ ] 7. Refactor Dependencies Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for dependency analysis (licenses, vulnerabilities, outdated packages)
  - Update tools: pip-audit, safety, pip

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 3 agents
  - **Parallel Group**: Wave 3 (with Tasks 8, 9, 10)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/dependencies/iron_rook/review/agents/dependencies.py`
  - Template: architecture agent

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/dependencies.py`
  - [ ] Commit: `feat(dependencies): implement 6-phase FSM review pattern`

---

- [ ] 8. Refactor Requirements Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for requirements traceability (ticket linkage, acceptance criteria)
  - Update tools: grep, read

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 3 agents
  - **Parallel Group**: Wave 3 (with Tasks 7, 9, 10)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/requirements/iron_rook/review/agents/requirements.py`
  - Template: architecture agent

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/requirements.py`
  - [ ] Commit: `feat(requirements): implement 6-phase FSM review pattern`

---

- [ ] 9. Refactor Changelog Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for changelog compliance (version bumps, breaking changes)
  - Update tools: grep, read

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 3 agents
  - **Parallel Group**: Wave 3 (with Tasks 7, 8, 10)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/changelog/iron_rook/review/agents/changelog.py`
  - Template: architecture agent

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/changelog.py`
  - [ ] Commit: `feat(changelog): implement 6-phase FSM review pattern`

---

- [ ] 10. Refactor Diff Scoper Agent to FSM Pattern

  **What to do**:
  - Copy architecture FSM structure
  - Customize for change scope analysis (file categorization, risk assessment)
  - Update tools: git, grep

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES - Wave 3 agents
  - **Parallel Group**: Wave 3 (with Tasks 7, 8, 9)
  - **Blocks**: None
  - **Blocked By**: None

  **References**:
  - `/Users/parkersligting/develop/pt/worktrees/iron-rook/diff-scoper/iron_rook/review/agents/diff_scoper.py`
  - Template: architecture agent

  **Acceptance Criteria**:
  - [ ] File updated: `iron_rook/review/agents/diff_scoper.py`
  - [ ] Commit: `feat(diff-scoper): implement 6-phase FSM review pattern`

---

### Phase 5: Integration and Cleanup

- [ ] 11. Update Finding.owner Enum

  **What to do**:
  - Update `Finding.owner` in `iron_rook/review/contracts.py` to include all agent types
  - Current: `Literal["dev", "docs", "devops", "security"]`
  - Target: `Literal["dev", "docs", "devops", "security", "architecture", "linting", "telemetry", "testing", "performance", "dependencies", "requirements", "changelog"]`

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Final integration
  - **Blocked By**: All agent refactorings

  **References**:
  - `/Users/parkersligting/develop/pt/iron-rook/iron_rook/review/contracts.py:169`

  **Acceptance Criteria**:
  - [ ] Finding.owner includes all agent types
  - [ ] No LSP errors in refactored agents
  - [ ] Commit: `feat(contracts): expand Finding.owner to all agent types`

---

- [ ] 12. Integration Testing

  **What to do**:
  - Run full test suite across all worktrees
  - Verify FSM phase transitions work correctly
  - Verify subagent delegation works correctly
  - Run `iron-rook --agent linting --output json -v` as integration test

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: None
  - **Blocked By**: All agent refactorings

  **Acceptance Criteria**:
  - [ ] All unit tests pass
  - [ ] Integration test with linting agent produces valid JSON output
  - [ ] ThinkingFrame logs visible in verbose output

---

## Commit Strategy

| After Task | Message | Files |
|------------|---------|-------|
| 1 | `refactor: add FSMReviewerAgent base class` | `iron_rook/review/base_fsm.py` |
| 2 | `feat(linting): implement 6-phase FSM review pattern` | `iron_rook/review/agents/linting.py` |
| 3 | `feat(documentation): implement 6-phase FSM review pattern` | `iron_rook/review/agents/documentation.py` |
| 4 | `feat(unit-tests): implement 6-phase FSM review pattern` | `iron_rook/review/agents/unit_tests.py` |
| 5 | `feat(telemetry): implement 6-phase FSM review pattern` | `iron_rook/review/agents/telemetry.py` |
| 6 | `feat(performance): implement 6-phase FSM review pattern` | `iron_rook/review/agents/performance.py` |
| 7 | `feat(dependencies): implement 6-phase FSM review pattern` | `iron_rook/review/agents/dependencies.py` |
| 8 | `feat(requirements): implement 6-phase FSM review pattern` | `iron_rook/review/agents/requirements.py` |
| 9 | `feat(changelog): implement 6-phase FSM review pattern` | `iron_rook/review/agents/changelog.py` |
| 10 | `feat(diff-scoper): implement 6-phase FSM review pattern` | `iron_rook/review/agents/diff_scoper.py` |
| 11 | `feat(contracts): expand Finding.owner to all agent types` | `iron_rook/review/contracts.py` |

---

## Success Criteria

### Verification Commands
```bash
# Verify all worktrees have commits
git worktree list | while read path commit branch; do
  echo "=== $branch ==="
  git -C "$path" log -1 --oneline
done

# Run integration test
iron-rook --agent linting --output json -v 2>&1 | head -100

# Verify FSM phases visible in output
iron-rook --agent architecture --output json -v 2>&1 | grep -E "\[INTAKE\]|\[PLAN\]|\[ACT\]|\[SYNTHESIZE\]|\[CHECK\]"
```

### Final Checklist
- [ ] All 9 remaining agents have FSM implementation
- [ ] Each agent has commit on its feature branch
- [ ] Finding.owner enum updated
- [ ] Integration tests pass
- [ ] No LSP errors in any agent file
