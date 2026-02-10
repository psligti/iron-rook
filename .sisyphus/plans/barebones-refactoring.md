# Barebones Refactoring - Strip Down Iron Rook to Dawn-Kestrel FSM

## TL;DR

> **Quick Summary**: Strip Iron Rook PR review system to barebones by removing bloat (streaming, discovery, dual execution paths, custom FSM) while preserving CLI interface and all 11 reviewers. Replace custom SecurityReviewOrchestrator with dawn-kestrel SDK's Session/AgentTask for FSM-based review flows. Use TDD approach (RED-GREEN-REFACTOR).
>
> **Deliverables**:
> - Simplified PR review system using dawn-kestrel SDK primitives
> - All 11 reviewers (6 core + 5 optional) working via dawn-kestrel FSM
> - CLI-only interface (no Python API pattern)
> - Single execution path via AgentRuntime (no dual paths)
> - Complete test coverage with TDD approach
>
> **Estimated Effort**: Medium (1-2 days)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Remove components → Replace FSM → Simplify orchestrator → Verify all reviewers work

---

## Context

### Original Request
User: "This project has gotten out of hand. Strip it down to barebones. Use Dawn kestrel to create the review fsm with all the agents and delegate subagents."

### Interview Summary

**Key Discussions**:
- **Primary concern**: "Bloat/unused features" - remove unnecessary complexity while preserving core functionality
- **Scope decisions**:
  - CLI only: Keep CLI entry point, remove Python API usage pattern
  - All reviewers: Keep all 6 core + 5 optional reviewers (11 total)
  - Test strategy: TDD (Red-Green-Refactor) with pytest
  - FSM approach: Use dawn-kestrel's built-in FSM (not custom security FSM)

**Research Findings**:
- **Dawn kestrel SDK**: Local/private Python SDK for AI agents with AgentRuntime, SessionManager, ToolRegistry, AgentTask
- **Current architecture**:
  - 11 specialized review agents (security, architecture, documentation, telemetry, linting, unit_tests, diff_scoper, requirements, performance, dependencies, changelog)
  - Complex orchestrator (~700 lines) with dual execution paths (direct vs AgentRuntime)
  - Custom security FSM (~900 lines) with 6 phases, 3 terminal states
  - Second-wave delegation system with BudgetConfig/BudgetTracker
  - Streaming infrastructure (ReviewStreamManager)
  - Discovery module (EntryPointDiscovery, ~659 lines)
- **Test infrastructure**: Pytest exists in tests/ directory

### Metis Review

**Identified Gaps (addressed in plan)**:
- **Behavior preservation questions**:
  - Parallel vs sequential execution → Will verify dawn-kestrel preserves parallelism
  - Failure isolation → Will ensure one reviewer failure doesn't stop others
  - Execution order → Will verify dawn-kestrel maintains reviewer ordering
  - Graceful degradation → Will ensure partial reviewer sets work
- **Configuration questions**:
  - Reviewer configuration (JSON/YAML) → Will inline context building in CLI
  - Reviewer selection → Will preserve CLI args for reviewer selection
  - Default behavior → Will ensure default reviewers run when none specified
- **Integration questions**:
  - Git operations → Will verify Git integration remains functional
  - Environment variables → Will preserve env var usage for API keys
  - Secret management → Will verify dawn-kestrel supports env vars for secrets
  - **Output format**:
  - CLI output format → Will preserve ReviewOutput contract structure
  - Report aggregation → Will ensure all 11 reviewer outputs aggregated correctly
  - **Performance**:
  - Timeout behavior → Will verify dawn-kestrel matches current timeout semantics
  - Memory usage → Will monitor memory after simplification
- **Guardrails Applied** (from Metis):

**MUST NOT** (Explicit prohibitions):
- Change reviewer behavior (logic, prompts, outputs)
- Remove or modify any of the 11 reviewer implementations
- Change BaseReviewerAgent contract (must verify dawn-kestrel compatibility)
- Remove ReviewOutput contracts without verifying dawn-kestrel equivalent exists
- Introduce new dependencies beyond dawn-kestrel SDK
- Change CLI argument parsing for reviewer selection
- Break existing environment variable configuration
- Remove tool registration logic without dawn-kestrel replacement verified

**MUST** (Explicit requirements):
- Preserve all 11 reviewers' exact behavior
- Use dawn-kestrel Session/AgentTask for orchestration (no custom FSM)
- Standardize on AgentRuntime only (no dual execution paths)
- Run pytest before and after each major component removal
- Document any API changes (if CLI args change)
- Verify dawn-kestrel can register all tools currently used by reviewers

**Pattern Guardrails**:
- Follow dawn-kestrel SDK examples for Session/AgentTask usage
- Keep CLI structure similar to current (args should map 1:1 where possible)

**Scope Boundaries** (Explicitly Locked):

**DEFINITELY EXCLUDED** (No scope creep):
- Documentation updates (user guides, README) - unless CLI args change
- Error handling enhancements - preserve current behavior only
- Performance optimizations - maintain current performance, don't optimize
- Logging improvements - preserve current log format/levels
- Configuration format changes (JSON→YAML, etc.) - keep current format
- New reviewers or reviewer modifications
- Integration tests beyond existing pytest suite
- CI/CD pipeline changes
- Deployment scripts changes
- Monitoring/observability additions
- Feature flags or configuration options for future features
- Python API re-implementation (explicitly CLI-only)

**Assumptions to Validate** (incorporated as acceptance criteria):
- Dawn-kestrel Session can replace custom SecurityReviewOrchestrator (1058 lines) → Will verify parallel execution support
- Dawn-kestrel AgentRuntime can replace both execution paths (use_agent_runtime flag) → Will verify tool type support
- Dawn-kestrel has built-in timeout/failure handling → Will match current timeout semantics
- Dawn-kestrel ToolRegistry can handle all tools currently registered → Will verify tool compatibility
- ContextBuilder can be inlined into CLI without complexity explosion → Will verify no side effects
- Dawn-kestrel output format is compatible with current ReviewOutput → Will adapt or change ReviewOutput
- Existing pytest tests cover all 11 reviewers → Will verify test coverage

---

## Work Objectives

### Core Objective
Simplify Iron Rook PR review system by removing bloat (streaming, discovery, dual execution paths, custom FSM) while preserving CLI interface and all 11 reviewers. Replace custom SecurityReviewOrchestrator with dawn-kestrel SDK's Session/AgentTask for stateful review flows.

### Concrete Deliverables
- Simplified CLI (`iron_rook/review/cli.py`) with single execution path via AgentRuntime
- All 11 reviewers (6 core + 5 optional) working via dawn-kestrel Session/AgentTask
- Removed: ReviewStreamManager, EntryPointDiscovery, BudgetTracker, BudgetConfig, second-wave delegation
- Removed: Dual execution paths (`use_agent_runtime` flag, direct LLM path)
- Removed: Custom SecurityReviewOrchestrator (~1058 lines), FSMSecurityOrchestrator
- Removed: Security FSM contracts (`PhaseOutput`, `SecurityTodo`, `SubagentResult`)
- Removed: ContextBuilder, DefaultContextBuilder (inlined into CLI)
- Preserved: dawn-kestrel SDK integration (AgentRuntime, SessionManager, ToolRegistry)
- Preserved: BaseReviewerAgent, ReviewOutput contracts, ReviewInputs, OrchestratorOutput
- Test coverage: All tests pass (pre-refactor baseline + post-refactor regression tests)

### Definition of Done
- [x] All 11 reviewers run successfully on test PR (no regressions)
- [x] CLI works with existing commands (`iron-rook review`, `iron-rook docs`)
- [x] dawn-kestrel Session replaces custom SecurityReviewOrchestrator (deleted)
- [x] ReviewStreamManager, EntryPointDiscovery, BudgetTracker removed (files deleted)
- [x] Second-wave delegation removed
- [x] Dual execution paths removed (AgentRuntime only)
- [x] ContextBuilder inlined into CLI (no separate module)
- [x] All pytest tests pass (pre-refactor baseline + post-refactor regression tests)
- [x] No dead imports or unreachable code
- [x] pyflakes shows clean code
- [x] CLI output format matches current structure

### Must Have
- All 11 reviewers (6 core + 5 optional) preserved exactly as-is
- CLI interface works with existing commands
- dawn-kestrel SDK integration for agent execution
- dawn-kestrel Session for FSM-based review flows
- AgentRuntime for single execution path
- ReviewOutput, ReviewInputs, OrchestratorOutput contracts preserved
- All pytest tests pass

### Must NOT Have (Guardrails)
- Changes to reviewer logic, prompts, or outputs
- Removal of any reviewer implementations
- New dependencies beyond dawn-kestrel SDK
- Breaking changes to CLI argument parsing
- Changes to environment variable handling
- Removal of tool registration without dawn-kestrel replacement verified
- Scope creep (documentation, CI/CD, monitoring, etc.)
- Feature flags or configuration options for future features

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
> **ALL verification is executed by the agent** using tools (pytest, bash, etc.). No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest in tests/ directory)
- **Automated tests**: YES (TDD)
- **Framework**: pytest
- **Approach**: RED-GREEN-REFACTOR per task

### TDD Workflow (All Tasks Follow This Pattern)

**For Each Task**:
1. **RED**: Write failing test first
   - Test file: `tests/{module}_test.py`
   - Test command: `pytest tests/{module}_test.py -v`
   - Expected: FAIL (test exists, implementation doesn't)

2. **GREEN**: Implement minimum code to pass
   - Command: `pytest tests/{module}_test.py -v`
   - Expected: PASS

3. **REFACTOR**: Clean up while keeping green
   - Command: `pytest tests/{module}_test.py -v`
   - Expected: PASS (still)

**Test Setup Task** (if infrastructure issues):
- [x] 0. Verify Test Infrastructure
  - Run: `pytest --version`
  - Expected: pytest version shown
  - Run: `pytest tests/ --collect-only`
  - Expected: All existing tests collected

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

> Whether TDD is enabled or not, EVERY task MUST include Agent-Executed QA Scenarios.
> - **With TDD**: QA scenarios complement unit tests at integration/E2E level
> - **Without TDD**: QA scenarios are the PRIMARY verification method
>
> These describe how the executing agent DIRECTLY verifies the deliverable
> by running it — executing CLI commands, running pytest, verifying file existence.

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|-------|---------------------|
| **Frontend/UI** | Playwright | Navigate, interact, assert DOM, screenshot |
| **TUI/CLI** | interactive_bash | Run command, send keystrokes, validate output, check exit code |
| **API/Backend** | Bash (curl/httpie) | Send requests, parse responses, assert fields/status |
| **Library/Module** | Bash (REPL/load) | Import module, call functions, compare output |

**Each Scenario MUST Follow This Format:**
```
Scenario: [Descriptive name]
  Tool: [Playwright / interactive_bash / Bash]
  Preconditions: [What must be true before this scenario runs]
  Steps:
    1. [Exact command/test/action with specific values]
    2. [Next action with expected intermediate state]
    3. [Assertion with exact expected value]
  Expected Result: [Concrete, observable outcome]
  Failure Indicators: [What would indicate failure]
  Evidence: [Test output path / CLI output / file existence]
```

**Anti-patterns (NEVER write scenarios like this):**
- ❌ "Verify the login page works correctly"
- ❌ "Check that the API returns the right data"
- ✅ `Navigate to /login → Fill input[name="test@example.com"] → Click button[type="submit"] → Wait for /dashboard → Assert h1 contains "Welcome"`
- ✅ `POST /api/users → Parse response → Assert status is 201 → Assert response.id is UUID`

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.

```
Wave 1 (Start Immediately):
├── Task 1: Verify Test Infrastructure
├── Task 2: Map Reviewer Dependencies
├── Task 3: Explore ContextBuilder Complexity

Wave 2 (After Wave 1):
├── Task 4: Remove ReviewStreamManager
├── Task 5: Remove EntryPointDiscovery
├── Task 6: Remove BudgetTracker and BudgetConfig
└── Task 7: Remove second-wave delegation

Wave 3 (After Wave 2):
├── Task 8: Remove Dual Execution Paths
├── Task 9: Inline ContextBuilder into CLI
└── Task 10: Remove custom security FSM orchestrator

Wave 4 (After Wave 3):
├── Task 11: Remove Security FSM Contracts
├── Task 12: Remove FSMSecurityOrchestrator (if exists)
├── Task 13: Simplify PRReviewOrchestrator

Wave 5 (After Wave 4):
├── Task 14: Update CLI to Use Dawn-Kestrel Session
├── Task 15: Test All 11 Reviewers with Dawn-Kestrel

Critical Path: Task 8 (remove dual paths) → Task 14 (update CLI) → Task 15 (test reviewers) → Task 16 (regression tests)
Parallel Speedup: ~45% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3 | 2, 3 |
| 2 | 1 | 4, 5, 6 | 4, 5, 6, 7 |
| 3 | 1 | 8, 9 | 8, 9 | 8, 9 |
| 4 | 1 | 8, 9, 10, 11, 12, 13 | 8, 9, 10, 11, 12, 13 |
| 5 | 1 | 8, 9, 10 | 8, 9, 10 | 4, 5, 6, 7 |
| 6 | 1 | 8, 9 | 8, 9 | 4, 5 | 7 |
| 7 | 1 | 8, 9 | 8, 9 | 4, 5, 6 | 7 |
| 8 | 2, 3 | 14, 15 | 14, 15 | 14, 15 | 11, 12, 13, 14, 15 |
| 9 | 2, 3 | 13, 14 | 14, 15 | 13, 14, 15 | 11, 12, 13, 14, 15 |
| 10 | 2, 3 | 13, 14 | 13, 14, 15 | 14, 15 | 11, 12, 13, 14, 15 |
| 11 | 4, 5, 6, 7, 8 | 14, 15 | 14, 15 | 15, 16 | 11, 12, 13, 14, 15 |
| 12 | 4, 5, 6, 7, 8 | 14, 15 | 14, 15 | 15, 16 | 11, 12, 13, 14, 15, 16 |
| 13 | 8, 9 | 14, 15 | 14, 15 | 15, 16 | 11, 12, 13, 14, 15 |
| 14 | 9, 10 | 15 | 16 | 15, 16 | 11, 12, 13, 14, 15, 16 |
| 15 | 11, 12, 13, 14 | 16 | 16 | None | None (final) |
| 16 | 9, 10, 11, 12, 13, 14, 15 | 15 | None (final) | None (final verification) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2, 3 | task(category="quick", load_skills=[], run_in_background=false) |
| 2 | 4, 5, 6, 7 | task(category="unspecified-low", load_skills=[], run_in_background=false) |
| 3 | 8, 9 | task(category="unspecified-low", load_skills=[], run_in_background=false) |
| 4 | 11, 12, 13 | task(category="unspecified-low", load_skills=["playwright"], run_in_background=false) |
| 5 | 14, 15, 16 | task(category="unspecified-low", load_skills=["playwright"], run_in_background=false) |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

---

- [x] 1. Verify Test Infrastructure

  **What to do**:
  - Verify pytest is installed and working
  - Verify existing tests can be collected
  - Document pytest version and test count

  **Must NOT do**:
  - Modify existing test files
  - Install additional testing frameworks
  - Change test structure or organization

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Simple verification task, single commands, low complexity
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (task doesn't require specialized skills)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 1 (with Tasks 2, 3) | Sequential
  - **Blocks**: Tasks 4, 5, 6, 7
  - **Blocked By**: None | Task 1
  - **Can Parallelize With**: Tasks 2, 3 (in Wave 1)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `tests/` directory - Existing test structure to preserve

  **Test References** (testing patterns to follow):
  - `tests/test_orchestrator.py` - Test patterns for orchestrator testing

  **Documentation References** (specs and requirements):
  - pytest docs: `https://docs.pytest.org/` - pytest usage patterns

  **WHY Each Reference Matters** (explain the relevance):
  - tests/ directory: Shows existing test structure to follow when adding new tests
  - test_orchestrator.py: Examples of how orchestrator is currently tested
  - Metis guardrails: Explicit prohibitions on what must NOT be changed

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Verify pytest installation
    Tool: Bash (pytest command)
    Preconditions: Python installed, environment activated
    Steps:
      1. Run: `pytest --version`
      2. Assert: Output contains pytest version number (e.g., "pytest 7.x.x")
    Expected Result: pytest is installed and shows version
    Evidence: Command output captured

  Scenario: Collect all existing tests
    Tool: Bash (pytest command)
    Preconditions: tests/ directory exists
    Steps:
      1. Run: `pytest tests/ --collect-only`
      2. Assert: No collection errors, test count shown
    Expected Result: All existing tests collected successfully
    Evidence: Collection output captured

  Scenario: Document test infrastructure status
    Tool: Bash
    Preconditions: Pytest verified
    Steps:
      1. Run: `echo "Pytest version:" && pytest --version`
      2. Run: `echo "Test count:" && pytest tests/ --collect-only 2>&1 | grep -i "test session"`
    Expected Result: Both pytest version and test count documented
    Evidence: Combined output captured

  **Evidence to Capture**:
  - [ ] Pytest version output
  - [ ] Test collection output
  - [ ] Test infrastructure status document

  **Commit**: NO (this is a verification task, not a code change)

---

- [x] 2. Map Reviewer Dependencies

  **What to do**:
  - Search for imports between all 11 reviewer modules
  - Verify reviewers are independent (no shared state)
  - Document reviewer dependency graph
  - Identify any circular dependencies between reviewers

  **Must NOT do**:
  - Modify reviewer implementations
  - Add new dependencies between reviewers
  - Change reviewer imports (only observe, not modify)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: File search and import analysis task, low complexity
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (task uses grep/ast tools)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 1 (with Tasks 2, 3) | Sequential
  - **Blocks**: Tasks 4, 5, 6, 7
  - **Blocked By**: Task 1
  - **Can Parallelize With**: Tasks 2, 3 (in Wave 1)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/*.py` - All reviewer implementations to scan
  - `grep` pattern: `from iron_rook.review.agents import` - Find inter-reviewer imports

  **Test References** (testing patterns to follow):
  - None - No specific test file for this task

  **Documentation References** (specs and requirements):
  - Metis guardrails in Context section - MUST NOT change reviewer behavior

  **WHY Each Reference Matters** (explain the relevance):
  - agents/*.py: Need to scan all reviewer files for imports to identify dependencies
  - import pattern grep: Finds how reviewers import from each other (shared state risk)

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Find all reviewer imports
    Tool: Bash (grep command)
    Preconditions: iron_rook/review/agents/ directory exists
    Steps:
      1. Run: `grep -rh "^from iron_rook.review.agents import" iron_rook/review/agents/*.py`
      2. Assert: All imports found and logged
      3. Run: `grep -rh "^from iron_rook.review.agents\. import" iron_rook/review/agents/*.py`
      4. Assert: All imports captured
    Expected Result: Complete list of all reviewer imports found
    Evidence: Grep output captured

  Scenario: Verify no circular dependencies
    Tool: Bash
    Preconditions: All reviewer imports found
    Steps:
      1. Analyze import graph: Find any cycles (e.g., A imports B, B imports A)
      2. Assert: No circular dependencies found
      3. Document dependency graph structure
    Expected Result: Confirmed reviewers are independent or dependency tree documented
    Evidence: Dependency analysis output captured

  Scenario: Document reviewer independence
    Tool: Bash
    Preconditions: Dependency analysis complete
    Steps:
      1. Create: `.sisyphus/evidence/reviewer-dependencies.md`
      2. Write: "All 11 reviewers are independent (no shared state)" if true
      3. Write: Dependency tree if any dependencies found
    Expected Result: Reviewer independence documented
    Evidence: .sisyphus/evidence/reviewer-dependencies.md exists with content

  **Evidence to Capture**:
  - [ ] Grep output of reviewer imports
  - [ ] Dependency analysis documentation
  - [ ] .sisyphus/evidence/reviewer-dependencies.md

  **TDD Tests** (for this mapping task):
  - [ ] Test file created: tests/test_reviewer_dependencies.py
  - [ ] Test covers: All reviewer imports found, dependency analysis, independence verified
  - [ ] pytest tests/test_reviewer_dependencies.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: NO (verification/documentation task, not a code change)

---

- [x] 3. Explore ContextBuilder Complexity

  **What to do**:
  - Read ContextBuilder and DefaultContextBuilder implementations
  - Understand what ContextBuilder actually does (reviewer loading vs complex state management)
  - Verify if ContextBuilder has side effects or hidden dependencies
  - Assess complexity: line count, number of methods, external dependencies

  **Must NOT do**:
  - Modify ContextBuilder implementation
  - Remove ContextBuilder yet (that's a later task)
  - Add new methods or functionality

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Code reading and analysis task, understanding complexity before removal
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (task uses Read tool)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 1 (with Task 1, 2) | Sequential
  - **Blocks**: Tasks 4, 5, 6, 7, 8, 9
  - **Blocked By**: Tasks 1, 2, 3
  - **Can Parallelize With**: Tasks 1, 2 (in Wave 1)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - This is exploration task, no pattern to follow

  **Code References** (for understanding ContextBuilder):
  - `iron_rook/review/context_builder.py` - ContextBuilder implementation
  - `iron_rook/review/context_builder.py` - DefaultContextBuilder implementation

  **Test References** (testing patterns to follow):
  - None - No specific test file for this task

  **Documentation References** (specs and requirements):
  - Metis guardrails - MUST NOT change reviewer behavior

  **WHY Each Reference Matters** (explain the relevance):
  - context_builder.py: Need to understand what ContextBuilder does before inlining
  - DefaultContextBuilder: Need to understand default behavior to preserve after inlining

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Analyze ContextBuilder complexity
    Tool: Read (file reading)
    Preconditions: context_builder.py file exists
    Steps:
      1. Read: `iron_rook/review/context_builder.py`
      2. Analyze: Line count, method count, class count
      3. Identify: External dependencies and imports
      4. Document: Complexity metrics (lines, methods, dependencies)
    Expected Result: ContextBuilder complexity documented
    Evidence: Complexity analysis captured

  Scenario: Document ContextBuilder findings
    Tool: Bash
    Preconditions: Complexity analysis complete
    Steps:
      1. Create: `.sisyphus/evidence/contextbuilder-complexity.md`
      2. Write: Complexity metrics and findings
      3. Write: Assessment of inlining feasibility
    Expected Result: ContextBuilder findings documented
    Evidence: .sisyphus/evidence/contextbuilder-complexity.md exists with content

  **Evidence to Capture**:
  - [ ] ContextBuilder line count and structure
  - [ ] Complexity metrics (methods, classes, dependencies)
  - [ ] .sisyphus/evidence/contextbuilder-complexity.md

  **TDD Tests** (for this exploration task):
  - [ ] Test file created: tests/test_contextbuilder_complexity.py
  - [ ] Test covers: ContextBuilder complexity analysis, feasibility assessment
  - [ ] pytest tests/test_contextbuilder_complexity.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: NO (verification/exploration task, not a code change)

---

- [x] 4. Remove ReviewStreamManager

  **What to do**:
  - Delete `iron_rook/review/streaming.py` file
  - Remove all imports of ReviewStreamManager from other files
  - Remove ReviewStreamManager parameter from PRReviewOrchestrator.__init__
  - Remove stream_manager parameter from run_review() method
  - Remove all calls to stream_manager methods (emit_progress, emit_result, emit_error)

  **Must NOT do**:
  - Modify any reviewer implementations
  - Change ReviewOutput or other contracts
  - Keep streaming functionality (must be fully removed)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: File deletion and import cleanup, straightforward refactoring
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple file operations)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6, 7) | Sequential
  - **Blocks**: Tasks 8, 9, 10, 11, 12, 13, 14
  - **Blocked By**: Tasks 2, 3
  - **Can Parallelize With**: Tasks 4, 5, 6, 7 (in Wave 2)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Simple file deletion

  **Code References** (for removal):
  - `iron_rook/review/streaming.py` - File to delete
  - `iron_rook/review/orchestrator.py:31` - Import of ReviewStreamManager to remove
  - `iron_rook/review/orchestrator.py:49-55` - stream_manager parameter in __init__ to remove
  - `iron_rook/review/orchestrator.py:91, 171, 233` - stream_manager method calls to remove
  - `iron_rook/review/orchestrator.py:95` - stream_callback parameter to remove

  **WHY Each Reference Matters** (explain the relevance):
  - streaming.py: File to delete as part of bloat removal
  - orchestrator.py:31: Import to remove when deleting streaming.py
  - orchestrator.py:49-55: Constructor parameter to remove
  - orchestrator.py method calls: All uses of stream_manager to remove

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Delete streaming.py file
    Tool: Bash (rm command)
    Preconditions: streaming.py exists
    Steps:
      1. Run: `rm iron_rook/review/streaming.py`
      2. Assert: Exit code 0 (success)
      3. Run: `ls iron_rook/review/streaming.py`
      4. Assert: File not found (error: No such file or directory)
    Expected Result: streaming.py deleted successfully
    Evidence: Deletion command output

  Scenario: Verify no imports of ReviewStreamManager
    Tool: Bash (grep command)
    Preconditions: streaming.py deleted
    Steps:
      1. Run: `grep -r "from.*ReviewStreamManager" iron_rook/review/`
      2. Assert: No matches found (exit code 1)
    Expected Result: No imports of ReviewStreamManager remain
    Evidence: Grep exit code 1

  Scenario: Verify orchestrator has no stream_manager
    Tool: Bash (grep command)
    Preconditions: Imports removed
    Steps:
      1. Run: `grep -n "stream_manager" iron_rook/review/orchestrator.py`
      2. Assert: No matches found
    Expected Result: orchestrator.py has no stream_manager references
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Deletion command output
  - [ ] Grep verification outputs
  - [ ] orchestrator.py shows no streaming references

  **TDD Tests** (for this deletion task):
  - [ ] Test file created: tests/test_streaming_removal.py
  - [ ] Test covers: streaming.py file deleted, imports removed, orchestrator updated
  - [ ] pytest tests/test_streaming_removal.py → PASS (1 test, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove ReviewStreamManager (bloat removal)`
  - Files: `iron_rook/review/streaming.py`, `iron_rook/review/orchestrator.py`
  - Pre-commit: `pytest tests/`

---

- [x] 5. Remove EntryPointDiscovery

  **What to do**:
  - Delete `iron_rook/review/discovery.py` file (~659 lines)
  - Remove all imports of EntryPointDiscovery from other files
  - Remove discovery parameter from PRReviewOrchestrator.__init__
  - Remove all calls to discovery methods
  - Remove discovery logic from context building (now inlined in CLI)

  **Must NOT do**:
  - Keep any discovery functionality
  - Modify reviewer implementations
  - Preserve AST/content pattern matching logic

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: File deletion and import cleanup, removing 659 lines of bloat
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple file operations)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6) | Sequential
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: Tasks 2, 3
  - **Can Parallelize With**: Tasks 4, 5, 6 (in Wave 2)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Simple file deletion

  **Code References** (for removal):
  - `iron_rook/review/discovery.py` - File to delete (659 lines)
  - `iron_rook/review/orchestrator.py:30` - Import of EntryPointDiscovery to remove
  - `iron_rook/review/orchestrator.py:54` - discovery parameter in __init__ to remove
  - `iron_rook/review/orchestrator.py:68` - discovery usage in context building to remove

  **WHY Each Reference Matters** (explain the relevance):
  - discovery.py: 659-line file removing AST/content pattern matching bloat
  - orchestrator.py:30: Import to remove when deleting discovery.py
  - orchestrator.py:54: discovery parameter in __init__ to remove
  - orchestrator.py:68: Context building usage to remove

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Delete discovery.py file
    Tool: Bash (rm command)
    Preconditions: discovery.py exists
    Steps:
      1. Run: `rm iron_rook/review/discovery.py`
      2. Assert: Exit code 0 (success)
      3. Run: `ls iron_rook/review/discovery.py`
      4. Assert: File not found (error: No such file or directory)
    Expected Result: discovery.py deleted successfully (659 lines removed)
    Evidence: Deletion command output

  Scenario: Verify no imports of EntryPointDiscovery
    Tool: Bash (grep command)
    Preconditions: discovery.py deleted
    Steps:
      1. Run: `grep -rn "EntryPointDiscovery" iron_rook/review/`
      2. Assert: No matches found (exit code 1)
    Expected Result: No imports of EntryPointDiscovery remain
    Evidence: Grep exit code 1

  Scenario: Verify orchestrator has no discovery
    Tool: Bash (grep command)
    Preconditions: Imports removed
    Steps:
      1. Run: `grep -n "discovery" iron_rook/review/orchestrator.py`
      2. Assert: No matches found
    Expected Result: orchestrator.py has no discovery references
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Deletion command output
  - [ ] Grep verification outputs
  - [ ] orchestrator.py shows no discovery references

  **TDD Tests** (for this deletion task):
  - [ ] Test file created: tests/test_discovery_removal.py
  - [ ] Test covers: discovery.py file deleted, imports removed, orchestrator updated
  - [ ] pytest tests/test_discovery_removal.py → PASS (1 test, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove EntryPointDiscovery (659 lines of bloat)`
  - Files: `iron_rook/review/discovery.py`, `iron_rook/review/orchestrator.py`
  - Pre-commit: `pytest tests/`

---

- [x] 6. Remove BudgetTracker and BudgetConfig

  **What to do**:
  - Delete `BudgetConfig` and `BudgetTracker` classes from `iron_rook/review/contracts.py` (lines 371-412)
  - Remove all imports of BudgetTracker, BudgetConfig from other files
  - Remove budget_config parameter from PRReviewOrchestrator.__init__
  - Remove budget_tracker from orchestrator methods

  **Must NOT do**:
  - Keep any budget tracking functionality
  - Add new budget enforcement mechanism
  - Preserve second-wave delegation logic that uses budgets

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: File deletion and import cleanup, removing over-engineered budget tracking
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple file operations)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 7) | Sequential
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: Tasks 2, 3
  - **Can Parallelize With**: Tasks 4, 5, 7 (in Wave 2)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Simple file deletion

  **Code References** (for removal):
  - `iron_rook/review/contracts.py:371-412` - Contains BudgetConfig, BudgetTracker classes to remove
  - `iron_rook/review/orchestrator.py:70` - Import of BudgetTracker to remove
  - `iron_rook/review/orchestrator.py:67-70` - budget_config parameter in __init__ to remove
  - `iron_rook/review/orchestrator.py:573` - budget_tracker usage to remove

  **WHY Each Reference Matters** (explain the relevance):
  - contracts.py:371-412: File containing budget tracking classes to remove
  - orchestrator.py:70: Import of BudgetTracker to remove when deleting budget tracking
  - orchestrator.py:67-70: Constructor parameter to remove
  - orchestrator.py:573: Method usage to remove

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Delete budget tracking from contracts.py
    Tool: Bash (grep + sed or edit)
    Preconditions: contracts.py exists
    Steps:
      1. Run: `grep -c "class Budget" iron_rook/review/contracts.py`
      2. Assert: At least 1 Budget class found (BudgetConfig, BudgetTracker)
      3. Remove: All budget-related classes from config.py (verify file still has other content)
      4. Assert: No "class Budget" remains in config.py
    Expected Result: BudgetConfig and BudgetTracker removed from config.py
    Evidence: Modified config.py verified

  Scenario: Verify no imports of Budget classes
    Tool: Bash (grep command)
    Preconditions: Budget classes removed
    Steps:
      1. Run: `grep -r "BudgetConfig\|BudgetTracker" iron_rook/review/`
      2. Assert: No matches found (exit code 1)
    Expected Result: No imports of removed Budget classes
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Modified config.py verification
  - [ ] Grep verification outputs
  - [ ] orchestrator.py shows no budget tracking references

  **TDD Tests** (for this deletion task):
  - [ ] Test file created: tests/test_budget_removal.py
  - [ ] Test covers: BudgetConfig removed, imports removed, orchestrator updated
  - [ ] pytest tests/test_budget_removal.py → PASS (1 test, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove BudgetTracker and BudgetConfig (bloat removal)`
  - Files: `iron_rook/review/contracts.py`, `iron_rook/review/orchestrator.py`
  - Pre-commit: `pytest tests/`

---

- [x] 7. Remove Second-Wave Delegation System

  **What to do**:
  - Remove `second_wave_delegated_followups` method from PRReviewOrchestrator (~175 lines)
  - Remove delegation-related imports from contracts.py (DelegationRequest, parse_delegation_requests, ALLOWLISTED_DELEGATION_AGENTS)
  - Remove delegation logic from run_review method
  - Remove delegation calls from all reviewer outputs

  **Must NOT do**:
  - Keep any delegation functionality
  - Modify reviewer implementations (allow_delegation output)
  - Preserve second-wave followup logic

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Method deletion and import cleanup, removing over-engineered delegation system
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple code removal)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 2 (with Tasks 4, 5, 6) | Sequential
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: Tasks 2, 3
  - **Can Parallelize With**: Tasks 4, 5, 6 (in Wave 2)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Simple method deletion

  **Code References** (for removal):
  - `iron_rook/review/orchestrator.py:517-692` - second_wave_delegated_followups method to remove (~175 lines)
  - `iron_rook/review/orchestrator.py:98-100` - Call to second_wave_delegated_followups in run_review to remove
  - `iron_rook/review/contracts.py` - DelegationRequest, parse_delegation_requests, ALLOWLISTED_DELEGATION_AGENTS to remove

  **WHY Each Reference Matters** (explain the relevance):
  - orchestrator.py:517-692: 175-line method removing second-wave delegation system
  - orchestrator.py:98-100: Call to delegation method to remove from run_review
  - contracts.py: Delegation contracts to remove from contracts module

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Verify second_wave_delegated_followups method removed
    Tool: Bash (grep command)
    Preconditions: orchestrator.py file exists
    Steps:
      1. Run: `grep -n "second_wave_delegated_followups" iron_rook/review/orchestrator.py`
      2. Assert: No matches found (exit code 1)
    Expected Result: Method completely removed from orchestrator
    Evidence: Grep exit code 1

  Scenario: Verify no delegation calls in run_review
    Tool: Bash (grep command)
    Preconditions: Method removed
    Steps:
      1. Run: `grep -n "second_wave_delegated_followups" iron_rook/review/orchestrator.py`
      2. Assert: No matches found (exit code 1)
    Expected Result: No calls to delegation method in run_review
    Evidence: Grep exit code 1

  Scenario: Verify delegation contracts removed
    Tool: Bash (grep command)
    Preconditions: Method removed
    Steps:
      1. Run: `grep -n "DelegationRequest\|parse_delegation_requests\|ALLOWLISTED_DELEGATION_AGENTS" iron_rook/review/contracts.py`
      2. Assert: No matches found (exit code 1)
    Expected Result: All delegation contracts removed
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Grep verification outputs
  - [ ] contracts.py shows no delegation contracts
  - [ ] No delegation method references in orchestrator

  **TDD Tests** (for this deletion task):
  - [ ] Test file created: tests/test_delegation_removal.py
  - [ ] Test covers: second_wave_delegated_followups removed, delegation contracts removed
  - [ ] pytest tests/test_delegation_removal.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove second-wave delegation system (bloat removal)`
  - Files: `iron_rook/review/orchestrator.py`, `iron_rook/review/contracts.py`
  - Pre-commit: `pytest tests/`

---

- [x] 8. Remove Dual Execution Paths

  **What to do**:
  - Remove `use_agent_runtime` parameter from PRReviewOrchestrator.__init__
  - Remove `agent_runtime`, `session_manager`, `agent_registry` parameters from __init__
  - Remove dual path logic from _execute_via_agent_runtime method (if exists)
  - Remove direct LLM path from run_subagents_parallel (keep AgentRuntime path only)
  - Remove `prefers_direct_review()` method from all reviewers (if exists)
  - Standardize on AgentRuntime.execute_agent() for all reviewers

  **Must NOT do**:
  - Keep dual execution paths
  - Preserve direct LLM calling logic
  - Keep prefers_direct_review() methods

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Parameter removal and code path simplification, removing dual path complexity
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple code modification)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 3 (with Tasks 9, 10) | Sequential
  - **Blocks**: Tasks 4, 5, 6, 7, 8
  - **Blocked By**: Tasks 4, 5, 6, 7, 8
  - **Can Parallelize With**: Tasks 9, 10 (in Wave 3)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Code path simplification

  **Code References** (for removal):
  - `iron_rook/review/orchestrator.py:58-59` - use_agent_runtime parameter to remove
  - `iron_rook/review/orchestrator.py:75-76` - agent_runtime, session_manager, agent_registry params to remove
  - `iron_rook/review/orchestrator.py:196-207` - Direct LLM path (else branch) to remove
  - `iron_rook/review/base.py` - prefers_direct_review() method to remove (if exists)

  **WHY Each Reference Matters** (explain the relevance):
  - orchestrator.py:58-59: use_agent_runtime flag controlling dual execution paths - remove
  - orchestrator.py:75-76: AgentRuntime-related parameters - remove dual path support
  - orchestrator.py:196-207: Direct LLM calling branch in run_subagents_parallel - remove
  - base.py: prefers_direct_review() method controlling execution path selection - remove

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Verify use_agent_runtime parameter removed
    Tool: Bash (grep command)
    Preconditions: orchestrator.py modified
    Steps:
      1. Run: `grep -n "use_agent_runtime" iron_rook/review/orchestrator.py`
      2. Assert: No matches found (exit code 1)
    Expected Result: use_agent_runtime parameter removed from orchestrator
    Evidence: Grep exit code 1

  Scenario: Verify direct LLM path removed
    Tool: Bash (grep command)
    Preconditions: Parameter removed
    Steps:
      1. Run: `grep -B5 -A10 "if self.use_agent_runtime and not prefers_direct_review" iron_rook/review/orchestrator.py | head -20`
      2. Run: `grep -B5 -A10 "else:\s*logger.info" iron_rook/review/orchestrator.py | head -20`
      3. Assert: Direct LLM branch (else clause) removed
      4. Assert: No matches found (exit code 1)
    Expected Result: Direct LLM execution path removed
    Evidence: Grep shows no dual path logic

  Scenario: Verify prefers_direct_review removed
    Tool: Bash (grep command)
    Preconditions: Direct path removed
    Steps:
      1. Run: `grep -rn "prefers_direct_review" iron_rook/review/agents/`
      2. Assert: No matches found (exit code 1)
    Expected Result: prefers_direct_review() method removed from all reviewers
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Grep verification outputs
  - [ ] orchestrator.py shows no use_agent_runtime
  - [ ] No prefers_direct_review methods in agents/
  - [ ] No dual path logic in orchestrator.py

  **TDD Tests** (for this code change task):
  - [ ] Test file created: tests/test_dual_path_removal.py
  - [ ] Test covers: use_agent_runtime removed, direct LLM path removed, single AgentRuntime path
  - [ ] pytest tests/test_dual_path_removal.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove dual execution paths, standardize on AgentRuntime`
  - Files: `iron_rook/review/orchestrator.py`, `iron_rook/review/base.py`
  - Pre-commit: `pytest tests/`

---

- [x] 9. Inline ContextBuilder into CLI

  **What to do**:
  - Read ContextBuilder and DefaultContextBuilder to understand implementation
  - Move context building logic from PRReviewOrchestrator._build_context into CLI
  - Delete `iron_rook/review/context_builder.py` file
  - Delete `iron_rook/review/context_builder.py` file
  - Update CLI to build ReviewContext directly from ReviewInputs
  - Remove context_builder parameter from PRReviewOrchestrator.__init__

  **Must NOT do**:
  - Keep ContextBuilder as separate module
  - Change ReviewContext contract structure
  - Modify reviewer behavior based on context changes

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Code inlining and file deletion, removing abstraction layer
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple code refactoring)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 3 (with Task 8) | Sequential
  - **Blocks**: Tasks 14, 15
  - **Blocked By**: Tasks 4, 5, 6, 7, 8, 9
  - **Can Parallelize With**: Task 10 (in Wave 3)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Code inlining

  **Code References** (for inlining):
  - `iron_rook/review/orchestrator.py:389-400` - _build_context method to inline
  - `iron_rook/review/orchestrator.py:68-69` - context_builder parameter in __init__ to remove
  - `iron_rook/review/cli.py` - CLI file to add context building logic

  **WHY Each Reference Matters** (explain the relevance):
  - context_builder.py files: Need to understand implementation before inlining
  - orchestrator.py:389-400: _build_context method to inline into CLI
  - orchestrator.py:68-69: context_builder parameter to remove from __init__
  - cli.py: File to add inlined context building logic

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: ContextBuilder files deleted
    Tool: Bash (rm command)
    Preconditions: ContextBuilder implementation understood
    Steps:
      1. Run: `rm iron_rook/review/context_builder.py`
      2. Run: `rm iron_rook/review/context_builder.py`
      3. Assert: Exit code 0 (success)
      4. Run: `ls iron_rook/review/context_builder.py 2>&1 || echo "File removed"`
    Expected Result: Both ContextBuilder files deleted
    Evidence: Deletion command output

  Scenario: Verify context building inlined into CLI
    Tool: Read (file reading)
    Preconditions: ContextBuilder deleted
    Steps:
      1. Read: `iron_rook/review/cli.py`
      2. Search: "ReviewContext(" to find ReviewContext construction
      3. Assert: Context building logic present in CLI (not calling context_builder module)
    Expected Result: CLI has inlined context building logic
    Evidence: cli.py contains ReviewContext construction

  Scenario: Verify orchestrator has no context_builder
    Tool: Bash (grep command)
    Preconditions: ContextBuilder deleted
    Steps:
      1. Run: `grep -n "context_builder" iron_rook/review/orchestrator.py`
      2. Assert: No matches found
    Expected Result: orchestrator.py has no context_builder references
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Deletion command output
  - [ ] cli.py shows inlined context building
  - [ ] orchestrator.py shows no context_builder references

  **TDD Tests** (for this inlining task):
  - [ ] Test file created: tests/test_context_inlining.py
  - [ ] Test covers: ContextBuilder deleted, CLI inlines context, orchestrator updated
  - [ ] pytest tests/test_context_inlining.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: inline ContextBuilder into CLI (simplification)`
  - Files: `iron_rook/review/context_builder.py` (x2), `iron_rook/review/context_builder.py`, `iron_rook/review/orchestrator.py`, `iron_rook/review/cli.py`
  - Pre-commit: `pytest tests/`

---

- [x] 10. Remove Custom Security Review Orchestrator

  **What to do**:
  - Delete `iron_rook/review/fsm_security_orchestrator.py` file
  - Remove all imports of SecurityReviewOrchestrator from other files

  **Must NOT do**:
  - Keep custom FSM implementation
  - Preserve custom state transition logic

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: File deletion and import cleanup, removing ~900 lines of custom FSM
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple file operations)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 4 (with Tasks 11, 12) | Sequential
  - **Blocks**: Tasks 13, 14, 15
  - **Blocked By**: Tasks 4, 5, 6, 7, 8, 9
  - **Can Parallelize With**: Task 11, 12 (in Wave 4)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Simple file deletion

  **Code References** (for removal):
  - `iron_rook/review/fsm_security_orchestrator.py` - 900-line custom FSM to delete
  - `iron_rook/review/agents/security_fsm.py` - Security FSM agent using fsm_security_orchestrator (may need removal)
  - `iron_rook/review/orchestrator.py` - Any imports of SecurityReviewOrchestrator to remove

  **WHY Each Reference Matters** (explain the relevance):
  - fsm_security_orchestrator.py: 900-line custom FSM replaced by dawn-kestrel Session
  - security_fsm.py: Security agent using custom FSM (check if can be removed or kept with dawn-kestrel)
  - orchestrator.py imports: Remove any SecurityReviewOrchestrator imports

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Delete fsm_security_orchestrator.py
    Tool: Bash (rm command)
    Preconditions: fsm_security_orchestrator.py exists
    Steps:
      1. Run: `rm iron_rook/review/fsm_security_orchestrator.py`
      2. Assert: Exit code 0 (success)
      3. Run: `ls iron_rook/review/fsm_security_orchestrator.py`
      4. Assert: File not found
    Expected Result: Custom FSM orchestrator deleted (900 lines removed)
    Evidence: Deletion command output

  Scenario: Verify no imports of SecurityReviewOrchestrator
    Tool: Bash (grep command)
    Preconditions: File deleted
    Steps:
      1. Run: `grep -r "SecurityReviewOrchestrator" iron_rook/review/`
      2. Assert: No matches found (exit code 1)
    Expected Result: No imports of removed FSM orchestrator remain
    Evidence: Grep exit code 1

  Scenario: Verify security agent no longer uses custom FSM
    Tool: Bash (grep command)
    Preconditions: File deleted
    Steps:
      1. Run: `grep "from.*fsm_security" iron_rook/review/agents/security_fsm.py`
      2. Assert: No matches found (exit code 1)
    Expected Result: Security agent no longer uses custom FSM
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Deletion command output
  - [ ] Grep verification outputs
  - [ ] No FSM orchestrator imports
  - [ ] No imports in security_fsm.py

  **TDD Tests** (for this deletion task):
  - [ ] Test file created: tests/test_custom_fsm_removal.py
  - [ ] Test covers: fsm_security_orchestrator deleted, imports removed, security agent updated
  - [ ] pytest tests/test_custom_fsm_removal.py → PASS (1 test, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove custom SecurityReviewOrchestrator (use dawn-kestrel FSM)`
  - Files: `iron_rook/review/fsm_security_orchestrator.py`, `iron_rook/review/contracts.py`, `iron_rook/review/orchestrator.py`, `iron_rook/review/agents/security_fsm.py` (if modified)
  - Pre-commit: `pytest tests/`

---

- [x] 11. Remove Security FSM Contracts

  **What to do**:
  - Remove FSM-specific contracts from contracts.py: PhaseOutput, SecurityTodo, SubagentResult, PullRequestChangeList, SecurityReviewReport, FSMState
  - Verify no other code uses these contracts

  **Must NOT do**:
  - Keep FSM contracts if dawn-kestrel provides equivalents
  - Preserve custom state transition logic

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Contract deletion, removing unused data structures from custom FSM
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple code deletion)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 4 (with Tasks 11, 13) | Sequential
  - **Blocks**: Tasks 14, 15
  - **Blocked By**: Tasks 4, 5, 6, 7, 8, 9, 10
  - **Can Parallelize With**: Tasks 11, 12 (in Wave 4)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Contract deletion

  **Code References** (for removal):
  - `iron_rook/review/contracts.py` - FSM-specific contracts to identify and remove
  - All files importing FSM contracts - Search and verify if imports need removal

  **WHY Each Reference Matters** (explain the relevance):
  - contracts.py: Contains FSM-specific contracts (PhaseOutput, SecurityTodo, etc.) to remove
  - Importing files: Need to verify if any other code uses FSM contracts

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Verify FSM contracts removed
    Tool: Bash (grep command)
    Preconditions: contracts.py modified
    Steps:
      1. Run: `grep -n "class PhaseOutput\|class SecurityTodo\|class SubagentResult" iron_rook/review/contracts.py`
      2. Assert: No matches found (exit code 1)
    Expected Result: FSM-specific contracts removed
    Evidence: Grep exit code 1

  Scenario: Verify no imports of FSM contracts
    Tool: Bash (grep command)
    Preconditions: Contracts removed
    Steps:
      1. Run: `grep -rn "from.*PhaseOutput\|from.*SecurityTodo\|from.*SubagentResult" iron_rook/review/`
      2. Assert: No matches found (exit code 1)
    Expected Result: No imports of removed FSM contracts
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Grep verification outputs
  - [ ] contracts.py shows no FSM contracts
  - [ ] No imports of FSM contracts in codebase

  **TDD Tests** (for this contract deletion task):
  - [ ] Test file created: tests/test_fsm_contracts_removal.py
  - [ ] Test covers: FSM contracts removed, imports cleaned
  - [ ] pytest tests/test_fsm_contracts_removal.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove custom FSM contracts (use dawn-kestrel primitives)`
  - Files: `iron_rook/review/contracts.py`
  - Pre-commit: `pytest tests/`

---

- [x] 12. Remove FSMSecurityOrchestrator

  **What to do**:
  - Delete `iron_rook/review/FSMSecurityOrchestrator.py` file (if exists)
  - Remove all imports of FSMSecurityOrchestrator from other files
  - Verify security agent no longer uses FSMSecurityOrchestrator

  **Must NOT do**:
  - Keep FSMSecurityOrchestrator module
  - Preserve custom FSM orchestration logic

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: File deletion and import cleanup, removing duplicate FSM orchestrator
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple file operations)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 4 (with Tasks 11, 12) | Sequential
  - **Blocks**: Tasks 13, 14
  - **Blocked By**: Tasks 4, 5, 6, 7, 8, 9, 10
  - **Can Parallelize With**: Task 11, 12 (in Wave 4)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Simple file deletion

  **Code References** (for removal):
  - `iron_rook/review/FSMSecurityOrchestrator.py` - File to delete (if exists)
  - `iron_rook/review/agents/security_fsm.py` - May import FSMSecurityOrchestrator (verify)
  - `iron_rook/review/orchestrator.py` - Any imports of FSMSecurityOrchestrator to remove

  **WHY Each Reference Matters** (explain the relevance):
  - FSMSecurityOrchestrator.py: Duplicate FSM orchestrator to delete
  - security_fsm.py: Security agent using custom FSM (check if can be removed or kept with dawn-kestrel)

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Delete FSMSecurityOrchestrator.py
    Tool: Bash (rm command)
    Preconditions: File exists
    Steps:
      1. Run: `rm iron_rook/review/FSMSecurityOrchestrator.py`
      2. Assert: Exit code 0 (success)
      3. Run: `ls iron_rook/review/FSMSecurityOrchestrator.py`
      4. Assert: File not found
    Expected Result: FSMSecurityOrchestrator deleted
    Evidence: Deletion command output

  Scenario: Verify no imports of FSMSecurityOrchestrator
    Tool: Bash (grep command)
    Preconditions: File deleted
    Steps:
      1. Run: `grep -rn "FSMSecurityOrchestrator" iron_rook/review/`
      2. Assert: No matches found (exit code 1)
    Expected Result: No imports of removed FSM orchestrator
    Evidence: Grep exit code 1

  **Evidence to Capture**:
  - [ ] Deletion command output
  - [ ] Grep verification outputs
  - [ ] No FSMSecurityOrchestrator imports

  **TDD Tests** (for this deletion task):
  - [ ] Test file created: tests/test_fsm_orchestrator_removal.py
  - [ ] Test covers: FSMSecurityOrchestrator deleted, imports cleaned
  - [ ] pytest tests/test_fsm_orchestrator_removal.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: remove FSMSecurityOrchestrator (duplicate FSM)`
  - Files: `iron_rook/review/FSMSecurityOrchestrator.py`, `iron_rook/review/agents/security_fsm.py` (if modified)
  - Pre-commit: `pytest tests/`

---

- [x] 13. Simplify PRReviewOrchestrator

  **What to do**:
  - Review orchestrator after all removals (streaming, discovery, budget, dual paths, custom FSM)
  - Remove any remaining dead imports or unused code
  - Simplify orchestrator to single execution path via AgentRuntime
  - Ensure orchestrator uses dawn-kestrel Session for FSM orchestration
  - Add dawn-kestrel Session import and usage

  **Must NOT do**:
  - Keep any dual execution path remnants
  - Preserve unused parameters or methods
  - Add new functionality beyond simplification

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Code cleanup and simplification after major removals
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (simple code refactoring)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 3 (with Task 8) | Sequential
  - **Blocks**: Tasks 14, 15
  - **Blocked By**: Tasks 4, 5, 6, 7, 8, 9, 10
  - **Can Parallelize With**: Task 13 (in Wave 3)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Code cleanup

  **Code References** (for simplification):
  - `iron_rook/review/orchestrator.py` - Main file to simplify after all removals
  - `dawn_kestrel` SDK documentation - Session and AgentTask usage patterns

  **Test References** (testing patterns to follow):
  - `tests/test_orchestrator.py` - Existing orchestrator tests
  - Dawn-kestrel SDK: AgentRuntime, Session, Session usage patterns

  **Documentation References** (specs and requirements):
  - iron_rook/review/README.md - Understanding of review FSM phases

  **WHY Each Reference Matters** (explain the relevance):
  - orchestrator.py: Main orchestrator file needing cleanup and simplification
  - dawn-kestrel SDK: Reference for proper Session/AgentTask usage
  - README.md: Understanding of review FSM phases

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Verify no dead imports in orchestrator
    Tool: Bash (grep + python -m pyflakes or similar)
    Preconditions: All removals complete
    Steps:
      1. Run: `python -m pyflakes iron_rook/review/orchestrator.py`
      2. Assert: No unused import warnings
    Expected Result: No dead imports in orchestrator
    Evidence: pyflakes output (clean)

  Scenario: Verify orchestrator uses dawn-kestrel Session
    Tool: Bash (grep command)
    Preconditions: Simplification complete
    Steps:
      1. Run: `grep -n "from dawn_kestrel.*Session\|from dawn_kestrel.*AgentRuntime" iron_rook/review/orchestrator.py`
      2. Assert: dawn-kestrel imports present
      3. Run: `grep -n "Session(" iron_rook/review/orchestrator.py`
      4. Assert: Session usage for FSM orchestration
    Expected Result: Orchestrator uses dawn-kestrel Session
    Evidence: Grep shows Session imports and usage

  **Evidence to Capture**:
  - [ ] pyflakes output (clean)
  - [ ] Grep outputs show dawn-kestrel Session usage

  **TDD Tests** (for this simplification task):
  - [ ] Test file created: tests/test_orchestrator_simplification.py
  - [ ] Test covers: orchestrator simplified, dawn-kestrel Session used
  - [ ] pytest tests/test_orchestrator_simplification.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: YES
  - Message: `refactor: simplify PRReviewOrchestrator (use dawn-kestrel Session)`
  - Files: `iron_rook/review/orchestrator.py`
  - Pre-commit: `pytest tests/`

---

- [x] 14. Update CLI to Use Dawn-Kestrel Session

  **What to do**:
  - Import dawn-kestrel SessionManager in CLI
  - Replace orchestrator call with dawn-kestrel Session-based orchestration
  - Create Session for FSM-based review (intake → plan → delegate → evaluate)
  - Run agents via dawn-kestrel AgentRuntime with filtered tool registry
  - Ensure all 11 reviewers work with dawn-kestrel Session

  **Must NOT do**:
  - Keep old PRReviewOrchestrator class as public API
  - Use dual execution paths
  - Change reviewer behavior or prompts

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: CLI refactoring with dawn-kestrel SDK integration, moderate complexity
  - **Skills**: None needed
  - **Skills Evaluated but Omitted**: None (no specialized skills required)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 5 (with Task 14, 15) | Sequential
  - **Blocks**: None (final testing)
  - **Blocked By**: Tasks 13
  - **Can Parallelize With**: Task 16 (final) | None (final)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Code refactoring

  **Code References** (for CLI update):
  - `iron_rook/review/orchestrator.py` - Old orchestrator to replace with Session-based approach
  - `iron_rook/review/cli.py` - Current CLI to refactor for dawn-kestrel integration
  - `dawn_kestrel` SDK: AgentRuntime, Session, ToolRegistry documentation

  **Test References** (testing patterns to follow):
  - `tests/test_cli.py` - Existing CLI tests (if any)
  - `dawn_kestrel` SDK: AgentRuntime, Session, ToolRegistry usage patterns
  - `iron_rook/review/README.md` - Reviewer behavior specifications

  **Documentation References** (specs and requirements):
  - Metis guardrails in Context section - MUST NOT change reviewer behavior

  **WHY Each Reference Matters** (explain the relevance):
  - cli.py: Main CLI entry point needing dawn-kestrel integration
  - orchestrator.py: Pattern to replace (old orchestrator calls)
  - Dawn-kestrel SDK: Reference for proper Session/AgentTask usage
  - README.md: Understanding of review FSM phases

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** - No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: CLI creates dawn-kestrel Session
    Tool: Bash (CLI invocation)
    Preconditions: CLI updated with dawn-kestrel integration
    Steps:
      1. Run: `python -m iron_rook review --help`
      2. Assert: Help text shows (no errors)
      3. Run: `python -m iron_rook review --repo-root /path/to/test/repo --base-ref main --head-ref HEAD`
      4. Assert: Review starts, all 11 reviewers run via dawn-kestrel Session
      5. Assert: ReviewOutput contains findings from all reviewers
    Expected Result: CLI successfully orchestrates review with dawn-kestrel Session
    Evidence: CLI output shows all reviewers executed

  Scenario: Verify dawn-kestrel Session used
    Tool: Bash (grep command)
    Preconditions: CLI running
    Steps:
      1. Run: `grep -n "from dawn_kestrel" iron_rook/review/cli.py`
      2. Assert: dawn-kestrel imports present
    Expected Result: CLI uses dawn-kestrel Session
    Evidence: Grep output shows dawn-kestrel imports

  **Evidence to Capture**:
  - [ ] CLI help output
  - [ ] CLI review execution output
  - [ ] Grep outputs show dawn-kestrel usage

  **TDD Tests** (for this CLI integration task):
  - [ ] Test file created: tests/test_cli_dawn_kestrel.py
  - [ ] Test covers: CLI creates dawn-kestrel Session, all 11 reviewers run
  - [ ] pytest tests/test_cli_dawn_kestrel.py → PASS (2 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: NO (testing task, not a code change)

---

- [x] 15. Test All 11 Reviewers with Dawn-Kestrel

  **What to do**:
  - Run each reviewer individually with dawn-kestrel Session
  - Verify each reviewer's output matches expected ReviewOutput format
  - Verify all 11 reviewers work in parallel (if that's intended behavior)
  - Test edge cases: empty PR, large PR, reviewer timeout

  **Must NOT do**:
  - Modify reviewer implementations
  - Change reviewer prompts or outputs
  - Remove or skip any reviewers

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Comprehensive testing of all 11 reviewers with dawn-kestrel integration
  - **Skills**: `playwright` - Needed for CLI testing and verification
    - **Skills Evaluated but Omitted**: None (comprehensive testing needs browser automation)

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 5 (final) | Sequential
  - **Blocks**: None (final testing)
  - **Blocked By**: Tasks 14
  - **Can Parallelize With**: None (final)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/*.py` - All 11 reviewer implementations to test

  **Test References** (testing patterns to follow):
  - All existing reviewer tests (if any)
  - `dawn_kestrel` SDK: AgentRuntime, Session, ToolRegistry documentation

  **Documentation References** (specs and requirements):
  - iron_rook/review/README.md - Reviewer behavior specifications

  **WHY Each Reference Matters** (explain the relevance):
  - agents/*.py: All 11 reviewers need to be tested with dawn-kestrel integration
  - Dawn-kestrel SDK: Reference for proper AgentRuntime/Session usage
  - README.md: Reviewer specifications to verify against test results

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Test security reviewer with dawn-kestrel
    Tool: Bash (pytest)
    Preconditions: dawn-kestrel integration complete
    Steps:
      1. Run: `pytest tests/ -k security -v`
      2. Assert: Security reviewer test passes
    Expected Result: Security reviewer works with dawn-kestrel Session
    Evidence: pytest output shows PASS

  Scenario: Test all 11 reviewers in parallel
    Tool: Bash (CLI invocation)
    Preconditions: Individual reviewer tests pass
    Steps:
      1. Run: `python -m iron_rook review --repo-root /path/to/test/repo --reviewers security,architecture,documentation,telemetry,linting,unit_tests,diff_scoper,requirements,performance,dependencies,changelog`
      2. Assert: All 11 reviewers run successfully
      3. Assert: ReviewOutput contains findings from all reviewers
    Expected Result: All 11 reviewers run in parallel, outputs aggregated
    Evidence: CLI output shows all reviewers executed

  Scenario: Test edge case - empty PR
    Tool: Bash (CLI invocation)
    Preconditions: Normal review working
    Steps:
      1. Run: `python -m iron_rook review --repo-root /path/to/test/repo --base-ref main --head-ref main`
      2. Assert: Review completes with "no changes" message
    Expected Result: CLI handles empty PR gracefully
    Evidence: CLI output shows no changes detected

  Scenario: Test edge case - reviewer timeout
    Tool: Bash (CLI invocation with timeout)
    Preconditions: Normal review working
    Steps:
      1. Run: `timeout 30s python -m iron_rook review --repo-root /path/to/test/repo`
      2. Assert: Review stops at timeout with partial results
    Expected Result: Timeout handled gracefully, partial results returned
    Evidence: CLI output shows timeout message

  **Evidence to Capture**:
  - [ ] pytest outputs for each reviewer
  - [ ] CLI output for parallel review
  - [ ] CLI output for empty PR scenario
  - [ ] CLI output for timeout scenario

  **TDD Tests** (for this testing task):
  - [ ] Test file created: tests/test_all_reviewers_dawn_kestrel.py
  - [ ] Test covers: All 11 reviewers work, parallel execution, edge cases
  - [ ] pytest tests/test_all_reviewers_dawn_kestrel.py → PASS (4 tests, 0 failures)
  - [ ] pytest tests/ (all tests still pass)

  **Commit**: NO (testing task, commits already done by earlier tasks)

---

- [x] 16. Full Regression Test Suite

  **What to do**:
  - Run complete pytest test suite (all tests)
  - Verify no regressions introduced by refactoring
  - Verify all reviewers still work correctly
  - Check code quality (pyflakes, mypy if used)

  **Must NOT do**:
  - Skip any existing tests
  - Modify test structure
  - Add new tests beyond regression verification

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Final regression testing, running complete test suite
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES | NO
  - **Parallel Group**: Wave 5 (final) | Sequential
  - **Blocks**: None (final)
  - **Blocked By**: Tasks 15

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - N/A - Final testing task

  **Code References** (for regression testing):
  - `tests/` directory - Complete test suite to run

  **Test References** (testing patterns to follow):
  - All existing test files - Verify all pass after refactoring

  **Documentation References** (specs and requirements):
  - pytest docs - Running full test suite

  **WHY Each Reference Matters** (explain the relevance):
  - tests/: Complete test suite verifies no regressions
  - pytest docs: How to run full test suite

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.
  > REPLACE all placeholders with actual values from task context.

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  Scenario: Run full pytest test suite
    Tool: Bash (pytest)
    Preconditions: All refactoring complete
    Steps:
      1. Run: `pytest tests/ -v`
      2. Assert: All tests pass (exit code 0)
      3. Assert: Test summary shows X tests passed
    Expected Result: Complete test suite passes with no regressions
    Evidence: pytest output shows PASS

  Scenario: Verify code quality (pyflakes)
    Tool: Bash (pyflakes)
    Preconditions: pytest passes
    Steps:
      1. Run: `python -m pyflakes iron_rook/review/`
      2. Assert: No unused imports or undefined variables
    Expected Result: No code quality issues
    Evidence: pyflakes output (clean)

  **Evidence to Capture**:
  - [ ] pytest full test output
  - [ ] pyflakes output
  - [ ] Final regression verification complete

  **Commit**: NO (final verification, no commits needed)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 4 | `refactor: remove ReviewStreamManager (bloat removal)` | streaming.py, orchestrator.py | pytest tests/ |
| 5 | `refactor: remove EntryPointDiscovery (659 lines of bloat)` | discovery.py, orchestrator.py | pytest tests/ |
| 6 | `refactor: remove BudgetTracker and BudgetConfig (bloat removal)` | contracts.py, orchestrator.py | pytest tests/ |
| 7 | `refactor: remove second-wave delegation system (bloat removal)` | orchestrator.py, contracts.py | pytest tests/ |
| 8 | `refactor: remove dual execution paths, standardize on AgentRuntime` | orchestrator.py, base.py | pytest tests/ |
| 9 | `refactor: inline ContextBuilder into CLI (simplification)` | context_builder.py (x2), orchestrator.py, cli.py | pytest tests/ |
| 10 | `refactor: remove custom security FSM orchestrator (use dawn-kestrel FSM)` | fsm_security_orchestrator.py, contracts.py, orchestrator.py | pytest tests/ |
| 11 | `refactor: remove security FSM contracts (use dawn-kestrel primitives)` | contracts.py, pytest tests/ |
| 12 | `refactor: remove FSMSecurityOrchestrator (duplicate FSM)` | FSMSecurityOrchestrator.py, security_fsm.py (if needed) | pytest tests/ |
| 13 | `refactor: simplify PRReviewOrchestrator (use dawn-kestrel Session)` | orchestrator.py | pytest tests/ |
| 14 | `refactor: update CLI to use dawn-kestrel Session` | cli.py | pytest tests/ |
| 15 | `refactor: test all 11 reviewers with dawn-kestrel` | tests/test_all_reviewers_dawn_kestrel.py | pytest tests/ |
| 16 | `refactor: final regression test suite` | tests/ (verification only) | pyflakes |

---

## Success Criteria

### Verification Commands
```bash
# Final verification - run after all tasks complete
pytest tests/ -v --tb=short  # Expected: All tests pass, 0 failures
python -m pyflakes iron_rook/review/  # Expected: Clean (no warnings)
python -m iron_rook review --help  # Expected: Help text shows successfully
```

### Final Checklist
- [x] All 11 reviewers preserved and working
- [x] ReviewStreamManager, EntryPointDiscovery, BudgetTracker removed (files deleted)
- [x] Second-wave delegation removed
- [x] Dual execution paths removed (AgentRuntime only)
- [x] ContextBuilder inlined into CLI (no separate module)
- [x] dawn-kestrel Session replaces custom SecurityReviewOrchestrator (deleted)
- [x] CLI uses dawn-kestrel Session for FSM orchestration
- [x] All pytest tests pass (pre-refactor baseline + post-refactor regression)
- [x] No dead imports or unreachable code
- [x] pyflakes shows clean code
- [x] CLI works with existing commands
- [x] CLI output format matches current structure

