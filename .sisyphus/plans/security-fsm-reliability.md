# Security FSM Handoff and Continuation Reliability

## TL;DR

> **Quick Summary**: Harden the security FSM so phase handoffs are deterministic, required params cannot silently disappear, and execution reliably continues (or fails with explicit reasons) under both AgentRuntime and direct-LLM paths.
>
> **Deliverables**:
> - Deterministic transition validation and state progression checks
> - Required-field/context validation for every phase handoff
> - AgentRuntime-first phase execution path with tested direct-LLM fallback
> - Bounded retry (transient only) + fail-fast (structural errors)
> - Prompt/parser contract hardening for per-phase JSON outputs
> - Regression tests covering handoff continuity, missing params, malformed outputs, and non-continuation failures
> - Security CLI path continuity fixes that prevent duplicate/non-progressing runs
>
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 9

---

## Context

### Original Request
Review the security FSM and improve context handling, state management/transitions, prompt/process behavior, and handoff reliability because the application frequently stalls, misses params, or fails to continue processing.

### Interview Summary
**Key Discussions**:
- Execution model: **AgentRuntime-first** while keeping direct-LLM fallback explicit and tested.
- Continuation policy: **fail-fast** for missing required fields/structural contract failures; **bounded retry** for transient failures.
- Test strategy: **TDD with pytest** (existing infrastructure confirmed).

**Research Findings**:
- FSM transitions and phase schema contracts are defined, but runtime enforcement is incomplete in critical places.
- Handoff data is currently dict-heavy and mutable across phases, increasing missing-key/continuity risks.
- Runtime/tests and CLI wiring show continuity mismatches (duplicate run path and runtime bypass risk).

### Metis Review
**Identified Gaps (addressed in this plan)**:
- Missing explicit guardrails on what must not change (phase sequence, schema contracts, public API shape).
- Missing hard definition of transient vs structural failures for retry policy.
- Missing acceptance criteria for stall/non-continuation edge cases and malformed outputs.
- Potential scope creep into redesign; locked to targeted reliability hardening.

---

## Work Objectives

### Core Objective
Eliminate silent handoff failures and non-continuation in the security FSM by enforcing strict transition and parameter contracts, making execution-path behavior deterministic, and validating reliability with regression-first tests.

### Concrete Deliverables
- `iron_rook/review/fsm_security_orchestrator.py` hardened for context/state/transition reliability.
- `tests/test_fsm_orchestrator.py` expanded and corrected to encode current reliability expectations.
- `tests/test_schemas.py` extended for phase-output and continuity edge cases as needed.
- `iron_rook/review/security_review_agent.md` aligned to strict phase output contract and parser behavior.
- `iron_rook/review/cli.py` security path continuity fixed (single run, correct runtime wiring).

### Definition of Done
- [ ] `pytest -q tests/test_fsm_orchestrator.py` passes with new continuity and missing-param cases.
- [ ] `pytest -q tests/test_schemas.py` passes with contract validations unchanged/better.
- [x] Security FSM no longer silently advances on invalid phase transitions.
- [x] Missing required fields produce explicit failure path (partial report with reason), not stall.
- [x] Transient failure retry is bounded (default 3 attempts) and observable.
- [x] Security CLI path runs FSM once and uses intended runtime wiring.

### Must Have
- Transition enforcement against `FSM_TRANSITIONS` at runtime.
- Required param validation before phase execution/transition.
- AgentRuntime-first execution path working and covered by tests.
- Direct LLM fallback retained and covered by at least one reliability test.
- No human-intervention acceptance criteria.

### Must NOT Have (Guardrails)
- No phase sequence redesign beyond existing FSM semantics.
- No breaking schema change to `PhaseOutput`, `FSMState`, `SecurityReviewReport` contracts.
- No removal of direct LLM fallback.
- No public API signature changes for `SecurityReviewOrchestrator.__init__` or `run_review`.
- No unrelated architecture rewrites outside security FSM reliability path.

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> All verification is agent-executed via commands and tool outputs. No manual clicking or human validation steps are allowed.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: TDD
- **Framework**: `pytest` (+ async tests)

### If TDD Enabled

Each task follows RED-GREEN-REFACTOR:

1. **RED**: Add/adjust failing test(s) for the specific reliability issue.
   - Expected: targeted pytest invocation fails for intended reason.
2. **GREEN**: Implement minimum code to satisfy failing tests.
   - Expected: targeted pytest invocation passes.
3. **REFACTOR**: Clean implementation while keeping tests green.
   - Expected: targeted + full FSM test invocations pass.

### Agent-Executed QA Scenarios (MANDATORY)

Deliverable type in this plan is backend/CLI, so QA uses Bash/pytest (and optional interactive_bash for CLI runtime smoke where needed).

Scenario template used in each task:

Scenario: [name]
  Tool: Bash (pytest/python command)
  Preconditions: [test environment and file prerequisites]
  Steps:
    1. [Exact command]
    2. [Assertion command/expected output]
  Expected Result: [Concrete verifiable result]
  Failure Indicators: [Specific mismatch]
  Evidence: [.sisyphus/evidence/task-N-*.txt]

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Start Immediately):
- Task 1: Write failing reliability regression tests (RED baseline)
- Task 7: Prompt/parser contract hardening tests and prompt edits

Wave 2 (After Wave 1):
- Task 2: Typed context + required param guardrails
- Task 3: Deterministic transition enforcement + state counter continuity
- Task 8: CLI continuity wiring fixes

Wave 3 (After Wave 2):
- Task 4: AgentRuntime-first execution path + fallback parity
- Task 5: Retry/continuation policy implementation
- Task 6: Session lifecycle reliability and release semantics
- Task 9: Final regression pack and reliability evidence capture

Critical Path: Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 9
Parallel Speedup: ~30-35% faster than full sequential execution.

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|----------------------|
| 1 | None | 2,3,4,5,6,9 | 7 |
| 2 | 1 | 4,5,9 | 3,8 |
| 3 | 1 | 4,5,9 | 2,8 |
| 4 | 2,3 | 5,6,9 | 8 |
| 5 | 2,3,4 | 9 | 6 |
| 6 | 4 | 9 | 5 |
| 7 | None | 4,9 | 1 |
| 8 | 1 | 9 | 2,3,4 |
| 9 | 2,3,4,5,6,8 | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|--------------------|
| 1 | 1, 7 | `task(category="unspecified-high", load_skills=["napkin"], run_in_background=false)` |
| 2 | 2, 3, 8 | same category; dispatch in parallel after wave 1 |
| 3 | 4, 5, 6, 9 | run 4/5/6 in dependency order, then 9 as integration gate |

---

## TODOs

- [x] 1. Build RED baseline for handoff/continuation regressions

  **What to do**:
  - Add failing tests that encode current reliability bugs:
    - invalid transition request must fail deterministically,
    - missing required phase fields must not silently continue,
    - malformed JSON must return partial report or explicit error path,
    - non-continuation/stall paths must terminate with explicit stop reason.
  - Fix obvious test harness defects preventing meaningful RED phase (fixture invocation mistakes, impossible assertions, incompatible expectations).

  **Must NOT do**:
  - Do not weaken assertions to force green.
  - Do not delete existing behavior tests unless replaced with equivalent/higher-signal checks.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: test suite needs non-trivial cleanup and new reliability scenarios.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: track discovered regressions and test assumptions.
    - `git-master`: keep atomic test-first commits.
  - **Skills Evaluated but Omitted**:
    - `playwright`: no browser workflow in this task.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 7)
  - **Blocks**: 2, 3, 4, 5, 6, 9
  - **Blocked By**: None

  **References**:
  - `tests/test_fsm_orchestrator.py:13` - existing async lifecycle test scaffold and mocked runtime/session setup.
  - `tests/test_fsm_orchestrator.py:126` - current full-run assertion shape to preserve/upgrade.
  - `tests/test_fsm_orchestrator.py:159` - transition validation expectation that must become real behavior.
  - `tests/test_schemas.py:289` - schema-level report validation expectations to preserve contract integrity.
  - `iron_rook/review/contracts.py:968` - `PhaseOutput` contract that tests must target.

  **Acceptance Criteria**:
  - [ ] RED tests exist for invalid transition, missing field, malformed JSON, and continuation stop behavior.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "transition or missing or malformed or continuation"` fails before implementation.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: RED reliability tests fail as expected
    Tool: Bash (pytest)
    Preconditions: dev env with pytest installed
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "transition or missing or malformed or continuation"
      2. Assert: exit code != 0
      3. Capture output: .sisyphus/evidence/task-1-red-baseline.txt
    Expected Result: New reliability tests fail in RED phase
    Failure Indicators: command exits 0 or failures unrelated to targeted scenarios
    Evidence: .sisyphus/evidence/task-1-red-baseline.txt

  Scenario: Existing contract tests still execute
    Tool: Bash (pytest)
    Preconditions: same
    Steps:
      1. Run: pytest -q tests/test_schemas.py -k "SecurityReviewReport or PhaseOutput"
      2. Capture output: .sisyphus/evidence/task-1-schema-baseline.txt
    Expected Result: schema tests run with stable contract behavior
    Failure Indicators: import/contract breakages introduced during test edits
    Evidence: .sisyphus/evidence/task-1-schema-baseline.txt
  ```

  **Commit**: YES (group A)
  - Message: `test(security-fsm): add red coverage for handoff continuity failures`
  - Files: `tests/test_fsm_orchestrator.py`, `tests/test_schemas.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "transition or missing or malformed or continuation"`

- [x] 2. Add typed phase context and required-field handoff guards

  **What to do**:
  - Introduce a typed internal phase context model/dataclass for required handoff payloads (`pr`, `changes`, `intake_output`, `plan_todos_output`, etc.).
  - Validate required keys/fields before each phase construction and before transition assignment.
  - Ensure `_construct_phase_user_message()` reads from validated context and emits deterministic payload shape.

  **Must NOT do**:
  - Do not change public contract models in `contracts.py`.
  - Do not alter semantic content of phase payloads beyond reliability/consistency fixes.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: core orchestrator refactor with high regression risk.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: track assumptions and validation edge-cases.
    - `git-master`: maintain atomic progression after RED.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: not relevant to backend FSM logic.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 3 and 8)
  - **Blocks**: 4, 5, 9
  - **Blocked By**: 1

  **References**:
  - `iron_rook/review/fsm_security_orchestrator.py:196` - phase user-message construction that currently depends on mutable dict shape.
  - `iron_rook/review/fsm_security_orchestrator.py:594` - root context initialization and propagation.
  - `iron_rook/review/contracts.py:589` - `PullRequestChangeList` required fields to mirror in internal handoff checks.
  - `iron_rook/review/contracts.py:968` - `PhaseOutput` structure to preserve while validating required phase data.

  **Acceptance Criteria**:
  - [ ] Missing required handoff fields fail deterministically with explicit reason.
  - [ ] New/updated RED tests for missing params turn GREEN.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "missing"` passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Required handoff fields are enforced
    Tool: Bash (pytest)
    Preconditions: tests from Task 1 committed
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "missing"
      2. Assert: exit code 0
      3. Capture output: .sisyphus/evidence/task-2-missing-fields-green.txt
    Expected Result: missing-field paths are explicitly handled and tested
    Failure Indicators: silent continuation or unhandled key errors
    Evidence: .sisyphus/evidence/task-2-missing-fields-green.txt

  Scenario: Handoff payload shape remains contract-safe
    Tool: Bash (pytest)
    Preconditions: same
    Steps:
      1. Run: pytest -q tests/test_schemas.py -k "PullRequestChangeList or PhaseOutput"
      2. Assert: exit code 0
      3. Capture output: .sisyphus/evidence/task-2-contract-safety.txt
    Expected Result: schema compatibility preserved
    Failure Indicators: changed payload schema expectations
    Evidence: .sisyphus/evidence/task-2-contract-safety.txt
  ```

  **Commit**: YES (group B)
  - Message: `fix(security-fsm): validate required handoff context before phase execution`
  - Files: `iron_rook/review/fsm_security_orchestrator.py`, `tests/test_fsm_orchestrator.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "missing"`

- [x] 3. Enforce deterministic transition guards and state continuity

  **What to do**:
  - Enforce transition checks against `FSM_TRANSITIONS` at every phase boundary.
  - Ensure `self.state.phase`, `self.state.iterations`, and `stop_reason` are updated consistently.
  - Add explicit handling for unexpected/invalid `next_phase_request` values.

  **Must NOT do**:
  - Do not alter allowed transition graph unless strictly required by existing contract.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: correctness-critical control-flow changes.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: record transition-edge discoveries.
    - `git-master`: isolate control-flow changes.
  - **Skills Evaluated but Omitted**:
    - `playwright`: not applicable.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2 and 8)
  - **Blocks**: 4, 5, 9
  - **Blocked By**: 1

  **References**:
  - `iron_rook/review/fsm_security_orchestrator.py:134` - transition validator helper to harden and actually apply.
  - `iron_rook/review/fsm_security_orchestrator.py:634` - direct phase assignment currently bypassing strict guard checks.
  - `iron_rook/review/fsm_security_orchestrator.py:719` - canonical transition map.
  - `iron_rook/review/contracts.py:848` - FSM state phase enum and stop states.
  - `tests/test_fsm_orchestrator.py:159` - expected invalid-transition failure behavior.

  **Acceptance Criteria**:
  - [ ] Invalid transition attempts raise `FSMPhaseError` with actionable message.
  - [ ] Iteration and stop-reason continuity tests pass.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "transition or iteration"` passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Invalid transition is blocked
    Tool: Bash (pytest)
    Preconditions: transition tests exist from Task 1
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "phase_transition_validation"
      2. Assert: output contains "FSMPhaseError" and "Invalid transition"
      3. Capture output: .sisyphus/evidence/task-3-transition-guard.txt
    Expected Result: invalid next phase cannot silently continue
    Failure Indicators: fallback to done/collect without raising
    Evidence: .sisyphus/evidence/task-3-transition-guard.txt

  Scenario: Stop-gate behavior remains deterministic
    Tool: Bash (pytest)
    Preconditions: stop-path tests added
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "stopped_budget or stopped_human"
      2. Capture output: .sisyphus/evidence/task-3-stop-gates.txt
    Expected Result: partial report path used with explicit stop reason
    Failure Indicators: hangs, unknown phase, or missing stop_reason
    Evidence: .sisyphus/evidence/task-3-stop-gates.txt
  ```

  **Commit**: YES (group C)
  - Message: `fix(security-fsm): enforce runtime transition guards and state continuity`
  - Files: `iron_rook/review/fsm_security_orchestrator.py`, `tests/test_fsm_orchestrator.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "transition or stopped"`

- [x] 4. Implement AgentRuntime-first phase execution with direct-fallback parity

  **What to do**:
  - Implement/verify `_execute_phase()` path that uses `agent_runtime.execute_agent(...)` as primary when runtime is available.
  - Normalize agent response extraction and JSON parsing path parity for both runtime and direct-LLM execution.
  - Preserve fallback path when runtime is `None`.

  **Must NOT do**:
  - Do not remove direct LLM path.
  - Do not hardcode provider/model assumptions into orchestration logic.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: execution-path reliability and integration with external runtime.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: track runtime-vs-fallback differences and pitfalls.
    - `git-master`: safe commit slicing by path.
  - **Skills Evaluated but Omitted**:
    - `dev-browser`: no browser interaction.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 sequential start
  - **Blocks**: 5, 6, 9
  - **Blocked By**: 2, 3, 7

  **References**:
  - `iron_rook/review/fsm_security_orchestrator.py:324` - phase execution entry point.
  - `iron_rook/review/fsm_security_orchestrator.py:347` - session acquisition pattern.
  - `tests/test_fsm_orchestrator.py:202` - runtime integration expectations.
  - `tests/test_fsm_orchestrator.py:237` - subagent dispatch expectations.
  - `iron_rook/review/cli.py:434` - caller wiring currently bypassing runtime path.

  **Acceptance Criteria**:
  - [ ] Runtime path executes when `agent_runtime` is present.
  - [ ] Fallback path executes when `agent_runtime is None` and remains contract-compliant.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "agent_runtime_integration"` passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: AgentRuntime path is exercised
    Tool: Bash (pytest)
    Preconditions: runtime integration tests configured
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "agent_runtime_integration"
      2. Assert: execute_agent call assertions pass
      3. Capture output: .sisyphus/evidence/task-4-runtime-path.txt
    Expected Result: runtime dispatch is primary and validated
    Failure Indicators: runtime path never called; fallback-only behavior
    Evidence: .sisyphus/evidence/task-4-runtime-path.txt

  Scenario: Direct fallback path still works
    Tool: Bash (pytest)
    Preconditions: fallback test exists
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "fallback or direct_llm"
      2. Capture output: .sisyphus/evidence/task-4-fallback-path.txt
    Expected Result: fallback produces valid phase output handling
    Failure Indicators: fallback returns None unexpectedly or schema mismatch
    Evidence: .sisyphus/evidence/task-4-fallback-path.txt
  ```

  **Commit**: YES (group D)
  - Message: `fix(security-fsm): make runtime execution primary with tested fallback parity`
  - Files: `iron_rook/review/fsm_security_orchestrator.py`, `tests/test_fsm_orchestrator.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "agent_runtime_integration or fallback"`

- [x] 5. Add bounded retry for transient failures and fail-fast for structural errors

  **What to do**:
  - Define failure classes:
    - structural: schema validation failure, missing required fields, invalid transition -> fail-fast,
    - transient: provider timeout/network/intermittent runtime errors -> retry up to 3.
  - Implement bounded retry wrapper in phase execution path with deterministic stop reason.
  - Add tests verifying retry count, eventual stop, and no infinite continuation.

  **Must NOT do**:
  - Do not retry structural/contract violations.
  - Do not create unbounded loops.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: error-classification and continuation policy touches control flow.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: capture retry-policy decisions and tradeoffs.
    - `git-master`: ensure rollback-friendly commit granularity.
  - **Skills Evaluated but Omitted**:
    - `artistry`: not needed for deterministic reliability logic.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 6 after Task 4)
  - **Blocks**: 9
  - **Blocked By**: 2, 3, 4

  **References**:
  - `iron_rook/review/fsm_security_orchestrator.py:422` - current exception handling branch where retry policy should be integrated.
  - `iron_rook/review/fsm_security_orchestrator.py:612` - orchestration loop continuation points.
  - `iron_rook/review/contracts.py:848` - stop states available for explicit continuation outcomes.
  - `tests/test_fsm_orchestrator.py:138` - budget/termination tests to extend for retry behavior.

  **Acceptance Criteria**:
  - [ ] Structural failures terminate immediately with explicit reason.
  - [ ] Transient failure retries are capped at 3 and observable in tests/logs.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "retry or transient or malformed"` passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Transient failures retry and then recover or stop
    Tool: Bash (pytest)
    Preconditions: retry tests implemented with controlled mock failures
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "retry"
      2. Assert: retry count <= 3 in assertions/log evidence
      3. Capture output: .sisyphus/evidence/task-5-retry-policy.txt
    Expected Result: no infinite loops, bounded retries only
    Failure Indicators: >3 retries, hang, or silent continuation
    Evidence: .sisyphus/evidence/task-5-retry-policy.txt

  Scenario: Structural errors fail-fast
    Tool: Bash (pytest)
    Preconditions: malformed/schema tests exist
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "malformed or validation"
      2. Capture output: .sisyphus/evidence/task-5-fail-fast.txt
    Expected Result: immediate fail path without retries
    Failure Indicators: retried malformed JSON/schema errors
    Evidence: .sisyphus/evidence/task-5-fail-fast.txt
  ```

  **Commit**: YES (group E)
  - Message: `fix(security-fsm): add bounded transient retries and fail-fast structural handling`
  - Files: `iron_rook/review/fsm_security_orchestrator.py`, `tests/test_fsm_orchestrator.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "retry or malformed or validation"`

- [x] 6. Harden session lifecycle and subagent handoff release semantics

  **What to do**:
  - Ensure session acquisition/release is explicit and balanced for orchestrator and subagent paths.
  - Add tests for release calls and failure cleanup behavior.
  - Guarantee no orphaned/never-released session IDs in happy and error paths.

  **Must NOT do**:
  - Do not redesign session manager architecture; focus on reliability of current lifecycle.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: lifecycle bugs are subtle and regression-prone.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: track lifecycle edge-cases.
    - `git-master`: isolate cleanup logic commits.
  - **Skills Evaluated but Omitted**:
    - `playwright`: not applicable.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Task 5 after Task 4)
  - **Blocks**: 9
  - **Blocked By**: 4

  **References**:
  - `iron_rook/review/fsm_security_orchestrator.py:347` - current session acquisition point.
  - `iron_rook/review/utils/session_helper.py:25` - session manager interface behavior.
  - `tests/test_fsm_orchestrator.py:180` - existing session-management expectation tests to stabilize/expand.

  **Acceptance Criteria**:
  - [ ] Session release assertions pass for normal and failure paths.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "session_management or subagent_dispatch"` passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Sessions are released after successful run
    Tool: Bash (pytest)
    Preconditions: session tests in place
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "session_management"
      2. Capture output: .sisyphus/evidence/task-6-session-success.txt
    Expected Result: release_session assertions pass
    Failure Indicators: missing release_session calls
    Evidence: .sisyphus/evidence/task-6-session-success.txt

  Scenario: Sessions are released on subagent/error paths
    Tool: Bash (pytest)
    Preconditions: subagent/error lifecycle tests in place
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "subagent_dispatch"
      2. Capture output: .sisyphus/evidence/task-6-session-subagents.txt
    Expected Result: subagent sessions released deterministically
    Failure Indicators: leaked subagent sessions or inconsistent IDs
    Evidence: .sisyphus/evidence/task-6-session-subagents.txt
  ```

  **Commit**: YES (group F)
  - Message: `fix(security-fsm): enforce session release across orchestrator and subagent flows`
  - Files: `iron_rook/review/fsm_security_orchestrator.py`, `tests/test_fsm_orchestrator.py`, `iron_rook/review/utils/session_helper.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "session_management or subagent_dispatch"`

- [x] 7. Align prompt-phase contract and parser robustness

  **What to do**:
  - Tighten `security_review_agent.md` phase sections to match parser expectations exactly.
  - Harden `_load_phase_prompt()` behavior for missing/empty phase sections (explicit error path instead of silent empty prompt usage).
  - Add tests that verify missing phase section handling and required JSON envelope compliance.

  **Must NOT do**:
  - Do not broaden prompt responsibilities beyond phase-contract clarity.

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: contract-level prompt clarity with code-coupled parser rules.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: preserve decisions on parser strictness.
    - `git-master`: isolate prompt+parser changes.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: not relevant.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: 4, 9
  - **Blocked By**: None

  **References**:
  - `iron_rook/review/security_review_agent.md:41` - canonical phase block definitions.
  - `iron_rook/review/security_review_agent.md:5` - critical schema requirements to preserve.
  - `iron_rook/review/fsm_security_orchestrator.py:169` - phase prompt extraction logic.

  **Acceptance Criteria**:
  - [ ] Missing phase prompt sections are handled explicitly (test-covered).
  - [ ] Phase output envelope (`phase`, `data`, `next_phase_request`) remains enforced.
  - [ ] `pytest -q tests/test_fsm_orchestrator.py -k "prompt or phase section"` passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Parser rejects missing phase section cleanly
    Tool: Bash (pytest)
    Preconditions: prompt parser tests added
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py -k "phase section"
      2. Capture output: .sisyphus/evidence/task-7-phase-section.txt
    Expected Result: explicit controlled error for missing section
    Failure Indicators: empty prompt used silently
    Evidence: .sisyphus/evidence/task-7-phase-section.txt

  Scenario: Contract envelope remains required
    Tool: Bash (pytest)
    Preconditions: contract tests exist
    Steps:
      1. Run: pytest -q tests/test_schemas.py -k "PhaseOutput"
      2. Capture output: .sisyphus/evidence/task-7-envelope-contract.txt
    Expected Result: invalid envelope rejected by schema
    Failure Indicators: extra fields accepted or required fields skipped
    Evidence: .sisyphus/evidence/task-7-envelope-contract.txt
  ```

  **Commit**: YES (group G)
  - Message: `fix(security-fsm): align phase prompt sections with strict parser contract`
  - Files: `iron_rook/review/security_review_agent.md`, `iron_rook/review/fsm_security_orchestrator.py`, `tests/test_fsm_orchestrator.py`
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py -k "prompt or phase"`

- [x] 8. Fix security CLI continuity path (single execution, correct wiring)

  **What to do**:
  - Remove duplicate security FSM invocation in CLI path.
  - Ensure security CLI flow wires runtime/session as intended (AgentRuntime-first decision).
  - Add/adjust focused tests or integration checks for single execution and result handling.

  **Must NOT do**:
  - Do not alter non-security agent orchestration behavior.

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: localized but high-impact continuity fix.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: capture discovered CLI continuity pitfalls.
    - `git-master`: keep this isolated from core FSM refactor.
  - **Skills Evaluated but Omitted**:
    - `playwright`: CLI-only behavior.

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 2 and 3)
  - **Blocks**: 9
  - **Blocked By**: 1

  **References**:
  - `iron_rook/review/cli.py:434` - orchestrator invocation in security path.
  - `iron_rook/review/cli.py:440` - duplicate `run_review` call to remove/fix.
  - `iron_rook/review/cli.py:436` - runtime currently passed as `None`; align with runtime-first decision.

  **Acceptance Criteria**:
  - [ ] Security CLI path executes FSM once per invocation.
  - [ ] Runtime wiring for security path is explicit and tested/verified.
  - [ ] `pytest -q tests -k "security and cli"` (or nearest existing scope) passes.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Security CLI executes exactly once
    Tool: Bash (pytest or targeted python invocation)
    Preconditions: test harness or monkeypatch for call count
    Steps:
      1. Run: pytest -q tests -k "security and cli"
      2. Assert: call-count assertion equals 1
      3. Capture output: .sisyphus/evidence/task-8-cli-single-run.txt
    Expected Result: no duplicate run_review invocation
    Failure Indicators: call count > 1
    Evidence: .sisyphus/evidence/task-8-cli-single-run.txt

  Scenario: Security CLI runtime wiring path is valid
    Tool: Bash (targeted command)
    Preconditions: runtime mocks/config available
    Steps:
      1. Run: pytest -q tests -k "security and runtime"
      2. Capture output: .sisyphus/evidence/task-8-cli-runtime-path.txt
    Expected Result: security CLI can execute intended runtime path
    Failure Indicators: forced fallback despite runtime availability
    Evidence: .sisyphus/evidence/task-8-cli-runtime-path.txt
  ```

  **Commit**: YES (group H)
  - Message: `fix(cli): run security fsm once and align runtime wiring`
  - Files: `iron_rook/review/cli.py`, related tests
  - Pre-commit: `pytest -q tests -k "security and cli"`

- [x] 9. Final integration regression, evidence capture, and release-ready validation

  **What to do**:
  - Run full targeted security FSM regression set.
  - Run schema and broader test checks required for release confidence.
  - Capture evidence artifacts under `.sisyphus/evidence/` and summarize outcomes in commit notes.

  **Must NOT do**:
  - Do not ship if targeted continuity tests are flaky or nondeterministic.

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: final quality gate with cross-cutting verification.
  - **Skills**: [`napkin`, `git-master`]
    - `napkin`: record final risk and unresolved edge-cases.
    - `git-master`: clean final integration commit strategy.
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: not needed.

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 terminal task
  - **Blocks**: None
  - **Blocked By**: 2, 3, 4, 5, 6, 8

  **References**:
  - `tests/test_fsm_orchestrator.py` - end-to-end FSM reliability suite.
  - `tests/test_schemas.py` - contract integrity suite.
  - `pyproject.toml:29` - test tooling and dev deps.

  **Acceptance Criteria**:
  - [ ] `pytest -q tests/test_fsm_orchestrator.py` passes.
  - [ ] `pytest -q tests/test_schemas.py` passes.
  - [ ] `pytest -q` passes (or documented unrelated failures with explicit evidence).
  - [ ] Evidence files captured for all task-level scenarios.

  **Agent-Executed QA Scenarios**:

  ```bash
  Scenario: Full FSM reliability suite passes
    Tool: Bash (pytest)
    Preconditions: all prior tasks complete
    Steps:
      1. Run: pytest -q tests/test_fsm_orchestrator.py
      2. Assert: exit code 0
      3. Capture output: .sisyphus/evidence/task-9-fsm-suite.txt
    Expected Result: no handoff/continuation regressions remain
    Failure Indicators: phase stall, retry overflow, missing-param tests fail
    Evidence: .sisyphus/evidence/task-9-fsm-suite.txt

  Scenario: Full project test pass gate
    Tool: Bash (pytest)
    Preconditions: same
    Steps:
      1. Run: pytest -q
      2. Capture output: .sisyphus/evidence/task-9-full-suite.txt
    Expected Result: release-ready confidence
    Failure Indicators: new regressions outside security FSM changes
    Evidence: .sisyphus/evidence/task-9-full-suite.txt
  ```

  **Commit**: YES (group I)
  - Message: `test(security-fsm): validate end-to-end handoff reliability and continuation`
  - Files: integration test updates and any final orchestrator adjustments
  - Pre-commit: `pytest -q tests/test_fsm_orchestrator.py && pytest -q tests/test_schemas.py`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `test(security-fsm): add red coverage for handoff continuity failures` | tests only | targeted RED pytest run fails as expected |
| 2-3 | `fix(security-fsm): enforce context and transition reliability` | orchestrator + tests | targeted transition/missing tests pass |
| 4-6 | `fix(security-fsm): harden runtime path, retry policy, and session lifecycle` | orchestrator/session + tests | runtime/retry/session tests pass |
| 7-8 | `fix(security-fsm): align prompt/parser contract and cli continuity` | prompt/parser/cli + tests | prompt + cli targeted tests pass |
| 9 | `test(security-fsm): run final reliability gate` | test/evidence adjustments | full targeted suites pass |

---

## Success Criteria

### Verification Commands

```bash
pytest -q tests/test_fsm_orchestrator.py
# Expected: all FSM reliability tests pass

pytest -q tests/test_schemas.py
# Expected: all schema/contract tests pass

pytest -q
# Expected: full suite passes or any unrelated failures are explicitly documented
```

### Final Checklist
- [x] All handoff/continuation failures in request are directly covered by regression tests.
- [x] AgentRuntime-first + direct fallback behavior both validated.
- [x] Missing params cannot silently pass phase boundaries.
- [x] Transition and stop semantics are deterministic and explicit.
- [x] CLI security path no longer duplicates execution.
- [x] Evidence artifacts recorded for all QA scenarios.
