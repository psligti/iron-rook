# Security Agent 6-Phase FSM Implementation Plan

## TL;DR

> **Quick Summary**: Implement full 6-phase FSM with subagent delegation in SecurityReviewer to match documented architecture in `security_review_agent.md` and `README.md`.
> **Deliverables**:
> - `iron_rook/review/agents/security.py` - Upgraded with 6-phase FSM and subagent delegation
> - `iron_rook/review/subagents/security_subagents.py` - New subagent base classes (auth_security, injection_scanner, secret_scanner, dependency_audit)
> - `iron_rook/review/security_phase_logger.py` - Phase-specific logging infrastructure
> - `iron_rook/review/cli.py` - Updated with colored logging via RichHandler
>
> **Estimated Effort**: Large (8-12 hours)
> **Parallel Execution**: NO - Sequential implementation required
> **Critical Path**: Create phase logger → Update CLI → Create subagent base → Implement 6-phase FSM → Test

---

## Context

### Original Request
Based on log analysis of security review agent, following gaps were identified:
1. FSM Following: Documented 6-phase architecture vs implemented 3-state approach
2. Steps Logged: Steps ARE logged, but FSM transitions are not
3. Thinking Logged: NO per-phase thinking/output logged (only final JSON)
4. Logs Colored: Terminal UI uses Rich, but log messages are plain text
5. Multiple Agents Used: Only 1 agent in logs (single-agent mode)
6. Security Agent as Orchestrator: Currently a leaf agent, not an orchestrator

### Interview Summary
**Key Discussions**:
- **Approach Decision**: Implement full 6-phase FSM in SecurityReviewer to match `security_review_agent.md` specification
- **Subagent Strategy**: Create specialized security subagents (auth_security, injection_scanner, secret_scanner, dependency_audit)
- **Logging Strategy**: Add phase-specific logger for thinking output and use RichHandler for colored logs
- **FSM Foundation**: Use existing LoopFSM class with state mapping to security phases

**Research Findings**:
- LoopFSM exists in `iron_rook/fsm/loop_fsm.py` with states: INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED
- `security_review_agent.md` contains detailed phase specifications and output schemas
- Current SecurityReviewer uses simple 3-state FSM: IDLE → INITIALIZING → RUNNING → COMPLETED
- Rich console is only used for terminal progress, not for log messages
- No subagent delegation exists; SecurityReviewer is a leaf agent that makes single LLM call

### Metis Review
**Identified Gaps** (addressed):
- Need to implement subagent base classes with FSM loops
- Need to add phase transition logging for observability
- Need to create phase-specific thinking logger separate from operational logs
- Need to integrate LoopFSM with SecurityReviewer properly
- Need to handle subagent result aggregation in COLLECT phase
- Should ensure colored logging works for all log levels

---

## TODOs

### Wave 1: Logging Infrastructure (Tasks 1-2)

- [ ] 1. Create phase-specific logging infrastructure

**What to do**:
  - Create `iron_rook/review/security_phase_logger.py` with SecurityPhaseLogger class
  - Implement method `log_thinking(phase: str, message: str)` for structured output
  - Implement method `log_transition(from_state: str, to_state: str)` for FSM transitions
  - Add phase-specific log formatting with color support

**Must NOT do**:
  - Do NOT modify existing BaseReviewerAgent class
  - Do NOT create complex custom formatters beyond Rich's capabilities

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Simple file creation task following existing patterns in codebase
  - **Skills**: None required
    - Reason: No domain overlap - straightforward Python file following conventions

  - **Parallelization**:
    - **Can Run In Parallel**: YES
    - **Parallel Group**: Wave 1 (with Task 2)
    - **Blocks**: Task 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
    - **Blocked By**: None

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/review/cli.py:setup_logging()` - Current logging setup pattern (lines 219-231)
  - `iron_rook/review/base.py` - BaseReviewerAgent logger pattern (uses `logging.getLogger(__name__)`)
  - Any existing log formatters in codebase for consistency

**API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - ReviewOutput, SecurityReviewReport schemas for contract compliance
  - `iron_rook/review/security_review_agent.md` - Phase output specifications for data models

**Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security.py` - Existing SecurityReviewer tests for structure and patterns
  - `tests/unit/review/` - Directory structure for organizing new test files

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md` - Phase specifications and output schemas (complete reference)
  - `iron_rook/review/README.md` - Documentation of review agent architecture

**WHY Each Reference Matters** (explain its relevance):
  - `cli.py:setup_logging()` - Shows current pattern for log configuration; new RichHandler should integrate similarly
  - `base.py` - Demonstrates logger naming convention; phase logger should follow `logging.getLogger("security.thinking")`
  - `contracts.py` - Ensures new outputs match expected SecurityReviewReport schema
  - `security_review_agent.md` - Complete specification of each phase's input/output, critical for compliance

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/test_security_phase_logger.py
- [ ] Test covers: SecurityPhaseLogger initialization and thinking method
- [ ] Test covers: transition method with proper format
- [ ] pytest tests/unit/review/test_security_phase_logger.py → PASS (3 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: SecurityPhaseLogger properly formats and logs thinking output
    Tool: Bash (python test execution)
    Preconditions: SecurityPhaseLogger implementation completed
    Steps:
      1. Run: python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; logger = SecurityPhaseLogger(); logger.log_thinking('TEST', 'test thinking')"
      2. Assert: Output contains "[TEST] test thinking" with proper formatting
      3. Assert: No errors raised
    Expected Result: Phase logger accepts phase and message, formats output correctly
    Evidence: stdout capture
  \`\`\`

**Evidence to Capture**:
- [ ] Test files for all new code
- [ ] Log output showing phase transitions
- [ ] Terminal output demonstrating colored logging

**Commit**: YES (groups with 2)
- Message: `feat(logging): add phase-specific logging infrastructure for security reviewer`
- Files: `iron_rook/review/security_phase_logger.py`, tests for phase logger
- Pre-commit: `pytest tests/unit/review/test_security_phase_logger.py -q`

- [ ] 2. Update CLI with colored logging via RichHandler

**What to do**:
  - Modify `iron_rook/review/cli.py:setup_logging()` to use RichHandler
  - Add import: `from rich.logging import RichHandler`
  - Replace `logging.basicConfig()` to use RichHandler in handlers list
  - Ensure backward compatibility with --verbose flag

**Must NOT do**:
  - Do NOT remove existing log format strings
  - Do NOT break --verbose flag behavior
  - Do NOT change log level defaults

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Simple modification to existing CLI code, following logging patterns
  - **Skills**: `frontend-ui-ux`
    - `frontend-ui-ux`: Task involves CLI output formatting and colors
    - Reason: Rich library expertise for terminal formatting

  - **Skills Evaluated but Omitted**:
    - `playwright`: Not needed - no browser/UI testing involved
    - Other logging skills: No specialized logging skills beyond Rich

  - **Parallelization**:
    - **Can Run In Parallel**: YES
    - **Parallel Group**: Wave 1 (with Task 1)
    - **Blocks**: Task 3, 4, 5, 6, 7, 8, 9, 10, 11
    - **Blocked By**: None

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/review/cli.py:setup_logging()` - Lines 219-231 show current logging setup
  - `iron_rook/review/cli.py:console` usage - Lines 16, 266-273 show Rich console usage for terminal output

**API/Type References** (contracts to implement against):
  - RichHandler documentation for proper configuration options

**Test References** (testing patterns to follow):
  - `tests/unit/review/test_cli.py` - Existing CLI tests for regression testing
  - `tests/unit/review/agents/test_security.py` - End-to-end security reviewer tests

**Documentation References** (specs and requirements):
  - Rich library docs for RichHandler usage patterns
  - Python logging docs for integration points

**WHY Each Reference Matters** (explain its relevance):
  - `cli.py:setup_logging()` - Target of modification; need to preserve existing behavior while adding RichHandler
  - `cli.py:console` usage - Shows Rich is already imported and used; RichHandler follows same patterns
  - Existing CLI tests - Ensure modifications don't break existing functionality

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/test_cli_rich_logging.py
- [ ] Test covers: setup_logging with RichHandler enabled
- [ ] Test covers: --verbose flag works with colored output
- [ ] Test covers: backward compatibility with existing CLI behavior
- [ ] pytest tests/unit/review/test_cli_rich_logging.py → PASS (3 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: CLI properly colors log messages with RichHandler
    Tool: Bash (CLI execution)
    Preconditions: Rich logging implementation completed
    Steps:
      1. Run: iron-rook --agent security --output json -v 2>&1 | head -20
      2. Assert: Log messages contain ANSI color codes (detect with od -c or inspect with cat -v)
      3. Assert: Timestamp and log level formatting preserved
      4. Assert: Security-specific logs are visible with phase prefix
    Expected Result: All log messages show colors in terminal
    Evidence: Terminal output capture
  \`\`\`

**Evidence to Capture**:
- [ ] Test files for CLI modifications
- [ ] Terminal output showing colored logs
- [ ] No regressions in existing CLI functionality

**Commit**: YES (groups with 1)
- Message: `feat(logging): add RichHandler for colored log output in CLI`
- Files: `iron_rook/review/cli.py` (updated setup_logging), tests for CLI
- Pre-commit: `pytest tests/unit/review/test_cli_rich_logging.py -q`

### Wave 2: Subagent Base Classes (Tasks 3-4)

- [ ] 3. Create subagent base classes with FSM infrastructure

**What to do**:
  - Create `iron_rook/review/subagents/security_subagents.py`
  - Implement SecuritySubagent base class with FSM loop (intake → plan → act → synthesize → done)
  - Implement AuthSecuritySubagent for authentication/authorization security checks
  - Implement InjectionScannerSubagent for SQL/command injection detection
  - Implement SecretScannerSubagent for secret/credential scanning
  - Implement DependencyAuditSubagent for dependency security checks
  - Each subagent should have get_agent_name(), get_allowed_tools(), review() method

**Must NOT do**:
  - Do NOT create subagent types beyond 4 documented
  - Do NOT implement complex custom FSM - use existing LoopFSM pattern
  - Do NOT duplicate code from base.py - inherit from BaseReviewerAgent

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: Complex task requiring FSM implementation and multiple subagent types
  - **Skills**: None required
    - Reason: FSM pattern from codebase is clear; subagent patterns documented in security_review_agent.md

  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed - no UI component work
    - `git-master`: No git operations involved

  - **Parallelization**:
    - **Can Run In Parallel**: YES
    - **Parallel Group**: Wave 2 (with Task 4)
    - **Blocks**: Task 5, 6, 7, 8, 9, 10, 11
    - **Blocked By**: Tasks 1, 2

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/fsm/loop_fsm.py:LoopFSM` - FSM implementation pattern to follow (lines 32-655)
  - `iron_rook/review/base.py:BaseReviewerAgent` - Base class structure for agent inheritance (lines 1-495)
  - `iron_rook/review/contracts.py` - Data models for consistent return types

**API/Type References** (contracts to implement against):
  - `iron_rook.fsm.loop_state:LoopState` - State enum for FSM (INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED)
  - `iron_rook.fsm/todo:Todo` - Todo class for tracking subagent tasks
  - `iron_rook/review/security_review_agent.md` - Subagent specifications and output schemas

**Test References** (testing patterns to follow):
  - `tests/unit/fsm/test_loop_fsm.py` - Existing LoopFSM tests for pattern and coverage
  - `tests/unit/review/agents/test_security.py` - Base class tests for inheritance patterns

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md` - Subagent specifications and output schemas
  - `iron_rook/review/README.md` - Architecture overview with subagent delegation

**WHY Each Reference Matters** (explain its relevance):
  - `loop_fsm.py:LoopFSM` - Shows run_loop_async() pattern to follow for subagent FSM execution
  - `base.py:BaseReviewerAgent` - Provides get_agent_name(), get_allowed_tools(), review() interface
  - `loop_state.py:LoopState` - Defines states for FSM mapping
  - Existing tests - Demonstrate testing patterns for new subagent tests

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/subagents/test_security_subagents.py
- [ ] Test covers: SecuritySubagent base class initialization
- [ ] Test covers: AuthSecuritySubagent FSM execution
- [ ] Test covers: InjectionScannerSubagent FSM execution
- [ ] Test covers: SecretScannerSubagent FSM execution
- [ ] Test covers: DependencyAuditSubagent FSM execution
- [ ] Test covers: Subagent error handling and retry logic
- [ ] Test covers: Subagent returns proper ReviewOutput format
- [ ] pytest tests/unit/review/subagents/test_security_subagents.py → PASS (8 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: AuthSecuritySubagent runs FSM loop and produces findings
    Tool: Bash (python test execution)
    Preconditions: Subagent implementation completed
    Steps:
      1. Run: python -c "from iron_rook.review.subagents.security_subagents import AuthSecuritySubagent; import asyncio; result = asyncio.run(agent.review(MockContext())); print(result.findings)"
      2. Assert: Findings list is not empty for vulnerable JWT handling
      3. Assert: Each finding has severity field
      4. Assert: Each finding has evidence field with file refs
    Expected Result: Subagent completes FSM loop and returns structured findings
    Evidence: Test output captured
  \`\`\`

**Evidence to Capture**:
- [ ] Test files for all 4 subagent types
- [ ] Test output showing FSM state transitions
- [ ] Example findings from each subagent type

**Commit**: YES (groups with 4)
- Message: `feat(review): add subagent infrastructure for security reviewer`
- Files: `iron_rook/review/subagents/security_subagents.py`, tests for subagents
- Pre-commit: `pytest tests/unit/review/subagents/test_security_subagents.py -q`

### Wave 3: 6-Phase FSM Implementation (Tasks 5-6)

- [ ] 5. Implement 6-phase FSM in SecurityReviewer

**What to do**:
  - Create new FSM class `SecurityFSMAgent` or refactor existing SecurityReviewer
  - Map security phases to LoopFSM states: intake→INTAKE, plan_todos→PLAN, delegate→ACT, collect→SYNTHESIZE, consolidate→PLAN, evaluate→ACT, done→DONE
  - Implement phase methods: _run_intake(), _run_plan_todos(), _run_delegate(), _run_collect(), _run_consolidate(), _run_evaluate()
  - Each phase method should use SecurityPhaseLogger for thinking output
  - Integrate with existing BaseReviewerAgent interface (get_agent_name(), get_allowed_tools(), review())
  - Implement state transition logging at each phase change

**Must NOT do**:
  - Do NOT create new phase names - use exactly: intake, plan_todos, delegate, collect, consolidate, evaluate
  - Do NOT skip FSM validation - all transitions must follow documented rules
  - Do NOT break compatibility with PRReviewOrchestrator (must return ReviewOutput)

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: Core FSM implementation task requiring careful state management and phase orchestration
  - **Skills**: None required
    - Reason: FSM pattern and phase logic are well-documented in codebase

  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: No UI component work
    - `git-master`: No git operations

  - **Parallelization**:
    - **Can Run In Parallel**: NO
    - **Parallel Group**: Sequential (depends on Tasks 1, 2, 3, 4)
    - **Blocks**: Task 6, 7, 8, 9, 10, 11
    - **Blocked By**: Tasks 1, 2, 3, 4

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/fsm/loop_fsm.py:run_loop_async()` - FSM loop execution pattern (lines 509-615)
  - `iron_rook/review/security_review_agent.md` - Complete phase specifications with input/output schemas
  - `iron_rook/review/agents/security.py:review()` - Current simple implementation to replace/refactor (lines 38-56)

**API/Type References** (contracts to implement against):
  - `iron_rook.fsm.loop_state:LoopState` - State enum for transitions
  - `iron_rook.review.contracts:ReviewOutput` - Return type for orchestrator compatibility
  - `iron_rook.review.contracts:SecurityReviewReport` - Final report schema with findings

**Test References** (testing patterns to follow):
  - `tests/unit/fsm/test_loop_fsm.py` - FSM transition and loop tests for coverage
  - `tests/unit/review/agents/test_security.py` - SecurityReviewer tests to update

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md:lines 8-16` - Schema requirements and critical output rules
  - `iron_rook/review/security_review_agent.md:lines 41-359` - Detailed phase specifications for each phase

**WHY Each Reference Matters** (explain its relevance):
  - `loop_fsm.py:run_loop_async()` - Shows PLAN → ACT → SYNTHESIZE loop pattern to adapt for security phases
  - `security_review_agent.md` - Defines exact schema requirements for each phase; critical for compliance
  - `security.py:review()` - Current method signature to maintain for orchestrator compatibility
  - Existing tests - Ensure new implementation passes all existing SecurityReviewer tests

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/agents/test_security_fsm.py
- [ ] Test covers: FSM initialization with LoopFSM
- [ ] Test covers: State transitions follow documented rules from security_review_agent.md
- [ ] Test covers: Each phase method called in correct order (intake → plan_todos → delegate → collect → consolidate → evaluate)
- [ ] Test covers: Invalid transitions raise FSMPhaseError
- [ ] Test covers: DONE state reached after all phases complete
- [ ] pytest tests/unit/review/agents/test_security_fsm.py → PASS (12 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: SecurityFSMAgent executes all 6 phases and produces final report
    Tool: Bash (python test execution)
    Preconditions: SecurityFSMAgent implementation completed
    Steps:
      1. Run: python -m pytest tests/unit/review/agents/test_security_fsm.py -v
      2. Assert: All 12 tests pass
      3. Mock a ReviewContext with 3 changed files
      4. Run: python -c "from iron_rook.review.agents.security import SecurityFSMAgent; import asyncio; result = asyncio.run(SecurityFSMAgent().review(mock_context))"
      5. Parse result.findings
      6. Assert: Findings are structured with severity, evidence, recommendation
      7. Assert: Result.severity is set correctly based on findings
    Expected Result: Agent completes 6-phase FSM and returns valid ReviewOutput
    Evidence: Test output and result parsing
  \`\`\`

**Evidence to Capture**:
- [ ] Test file with 12 test cases covering FSM transitions
- [ ] Test output showing all phases executed
- [ ] Example final report with structured findings

**Commit**: YES (groups with 6)
- Message: `refactor(review): implement 6-phase FSM in SecurityReviewer with phase transitions`
- Files: `iron_rook/review/agents/security.py` (refactored), tests for FSM
- Pre-commit: `pytest tests/unit/review/agents/test_security_fsm.py -q`

### Wave 4: Phase-Specific Thinking Capture (Tasks 7-8)

- [ ] 7. Implement phase-specific thinking capture with phase logger

**What to do**:
  - Modify SecurityReviewer phase methods to use SecurityPhaseLogger
  - Add thinking logging at start of each phase: `[PHASE] Thinking: ...`
  - Capture LLM reasoning output separately from JSON result
  - Ensure thinking is logged BEFORE phase transition

**Must NOT do**:
  - Do NOT mix thinking with operational logs - use phase logger
  - Do NOT log empty thinking - only log substantial reasoning
  - Do NOT break existing phase method structure

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: Thinking capture requires understanding of LLM response parsing and log separation
  - **Skills**: None required
    - Reason: Phase logger provides log_thinking() method; straightforward integration

  - **Skills Evaluated but Omitted**:
    - Other skills not applicable

  - **Parallelization**:
    - **Can Run In Parallel**: NO
    - **Parallel Group**: Sequential (part of Task 5)
    - **Blocks**: Task 6, 7, 8, 9, 10, 11
    - **Blocked By**: Task 4

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/review/security_phase_logger.py:SecurityPhaseLogger` - Logger class created in Task 1
  - `iron_rook/review/agents/security.py:_run_phase()` - Pattern for wrapping phase execution with logging
  - Existing SimpleReviewAgentRunner usage (base.py lines 467-473) - shows LLM response handling

**API/Type References** (contracts to implement against):
  - `iron_rook.review.security_phase_logger:SecurityPhaseLogger` - Class interface for phase-specific logging
  - Existing LLM response patterns - Response parsing for thinking extraction

**Test References** (testing patterns to follow):
  - `tests/unit/review/test_security_phase_logger.py` - Phase logger tests from Task 1
  - `tests/unit/review/agents/test_security_fsm.py` - FSM tests from Task 5

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md:lines 25-68` - Shows example thinking output format for each phase

**WHY Each Reference Matters** (explain its relevance):
  - `security_phase_logger.py:SecurityPhaseLogger` - Provides log_thinking() method that formats output with phase prefix
  - `_run_phase()` - Shows where to integrate thinking extraction (before/after JSON parsing)
  - Existing LLM handling - Shows where to integrate thinking extraction (before/after JSON parsing)

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/agents/test_security_thinking.py
- [ ] Test covers: Thinking logged for INTAKE phase
- [ ] Test covers: Thinking logged for PLAN_TODOS phase
- [ ] Test covers: Thinking logged for DELEGATE phase
- [ ] Test covers: Thinking logged for COLLECT phase
- [ ] Test covers: Thinking logged for CONSOLIDATE phase
- [ ] Test covers: Thinking logged for EVALUATE phase
- [ ] Test covers: Thinking parsed correctly from LLM response with ## Thinking section
- [ ] Test covers: Empty thinking doesn't log to avoid noise
- [ ] pytest tests/unit/review/agents/test_security_thinking.py → PASS (6 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: Phase logger captures and formats thinking output from LLM
    Tool: Bash (log inspection)
    Preconditions: Thinking capture implementation completed
    Steps:
      1. Run: iron-rook --agent security --output json -v 2>&1 | grep -E "\[INTAKE|PLAN_TODOS|DELEGATE|COLLECT|CONSOLIDATE|EVALUATE\].*Thinking"
      2. Assert: "[INTAKE] Thinking:" appears in logs
      3. Assert: Thinking content follows with security-related reasoning
      4. Repeat for other phases (PLAN_TODOS, DELEGATE, COLLECT, CONSOLIDATE, EVALUATE)
    Expected Result: All 6 phases show thinking output with phase prefix
    Evidence: Log output file
  \`\`\`

**Evidence to Capture**:
- [ ] Log output showing thinking for all 6 phases
- [ ] Thinking content is properly formatted and captured
- [ ] Empty thinking scenarios tested and confirmed not logged

**Commit**: YES (groups with 5)
- Message: `feat(review): add phase-specific thinking capture to SecurityFSMAgent`
- Files: `iron_rook/review/agents/security.py` (updated), tests for thinking
- Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py -q`

### Wave 5: State Transition Logging (Tasks 9-10)

- [ ] 9. Add state transition logging to FSM

**What to do**:
  - Override or enhance LoopFSM transition logging in SecurityFSMAgent
  - Add explicit log at each phase transition: `[AGENT] FSM: old_state → new_state`
  - Log transition BEFORE state is changed (pre-transition hook)
  - Include phase name in transition log for clarity
  - Ensure transition logging happens even for valid transitions

**Must NOT do**:
  - Do NOT modify LoopFSM class itself - only add logging wrapper
  - Do NOT log transitions for internal FSM retries
  - Do NOT break FSM validation logic

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: State transition logging requires understanding of FSM lifecycle and logging hooks
  - **Skills**: None required
    - Reason: LoopFSM already has transition_to() method; wrapper approach is clean

  - **Skills Evaluated but Omitted**:
    - Other skills not applicable

  - **Parallelization**:
    - **Can Run In Parallel**: NO
    - **Parallel Group**: Sequential (part of Task 5)
    - **Blocks**: Task 6, 7, 8, 9, 10, 11
    - **Blocked By**: Tasks 4, 5

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/fsm/loop_fsm.py:transition_to()` - Base FSM transition method (lines 142-176)
  - `iron_rook/review/agents/security.py:_run_phase()` - Pattern for wrapping FSM execution
  - `iron_rook/review/security_phase_logger.py:log_transition()` - Method to call for logging

**API/Type References** (contracts to implement against):
  - `iron_rook.fsm.loop_state:LoopState` - State enum for transition logging

**Test References** (testing patterns to follow):
  - `tests/unit/fsm/test_loop_fsm.py` - Existing FSM transition tests for coverage
  - `tests/unit/review/agents/test_security_fsm.py` - SecurityFSMAgent tests from Task 5

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md:lines 26-28` - Shows FSM rules requirement

**WHY Each Reference Matters** (explain its relevance):
  - `loop_fsm.py:transition_to()` - Shows transition validation and Result pattern; wrapper should call log_transition()
  - `security_phase_logger.py:log_transition()` - Provides method for formatted transition logging
  - Existing FSM tests - Show how to test state transitions with assertions

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/agents/test_security_transitions.py
- [ ] Test covers: Valid transitions logged correctly
- [ ] Test covers: Invalid transitions raise errors
- [ ] Test covers: Phase name appears in transition logs
- [ ] Test covers: All 6 phase transitions logged in sequence
- [ ] Test covers: DONE state is terminal with no outgoing transitions
- [ ] pytest tests/unit/review/agents/test_security_transitions.py → PASS (8 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: FSM transitions logged with phase names and state changes
    Tool: Bash (log inspection)
    Preconditions: State transition logging implementation completed
    Steps:
      1. Run: iron-rook --agent security --output json -v 2>&1 | grep "FSM:"
      2. Assert: "[SecurityFSMAgent] FSM: IDLE → INTAKE" appears in logs
      3. Assert: "[SecurityFSMAgent] FSM: INTAKE → PLAN_TODOS" appears
      4. Assert: "[SecurityFSMAgent] FSM: PLAN_TODOS → DELEGATE" appears
      5. Assert: "[SecurityFSMAgent] FSM: DELEGATE → COLLECT" appears
      6. Assert: "[SecurityFSMAgent] FSM: COLLECT → CONSOLIDATE" appears
      7. Assert: "[SecurityFSMAgent] FSM: CONSOLIDATE → EVALUATE" appears
      8. Assert: "[SecurityFSMAgent] FSM: EVALUATE → DONE" appears
    Expected Result: All 6 phase transitions logged in sequence
    Evidence: Log output file
  \`\`\`

**Evidence to Capture**:
- [ ] Log output showing all 6 phase transitions
- [ ] Phase names and state changes clearly visible
- [ ] Transition format matches expected pattern

**Commit**: YES (groups with 7)
- Message: `feat(review): add state transition logging to SecurityFSMAgent`
- Files: `iron_rook/review/agents/security.py` (updated), tests for transitions
- Pre-commit: `pytest tests/unit/review/agents/test_security_transitions.py -q`

### Wave 6: Result Aggregation in COLLECT Phase (Tasks 10-11)

- [ ] 10. Implement result aggregation in COLLECT phase

**What to do**:
  - Create _run_collect() method to validate and aggregate subagent results
  - Mark TODO status (done, blocked, deferred) based on subagent results
  - Collect all findings from subagents into consolidated list
  - Validate that each subagent result has required fields (findings, evidence, error)
  - Store consolidated results in FSM context for CONSOLIDATE phase

**Must NOT do**:
  - Do NOT mark TODOs done without subagent validation
  - Do NOT merge results with missing required fields
  - Do NOT create findings from missing subagent results

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: Result aggregation requires careful validation and data structure handling
  - **Skills**: None required
    - Reason: Consolidation and collection patterns are documented in security_review_agent.md

  - **Skills Evaluated but Omitted**:
    - Other skills not applicable

  - **Parallelization**:
    - **Can Run In Parallel**: NO
    - **Parallel Group**: Sequential (part of Task 5)
    - **Blocks**: Task 6, 7, 8, 9, 10, 11
    - **Blocked By**: Task 5

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `iron_rook/review/security_review_agent.md:lines 197-232` - COLLECT phase specification for result validation
  - `iron_rook/review/agents/security.py:review()` - Shows ReviewOutput aggregation pattern in orchestrator
  - `iron_rook/fsm/todo.py:Todo` - Todo class for tracking status (done, blocked, deferred)

**API/Type References** (contracts to implement against):
  - `iron_rook.review.contracts:Todo` - Todo schema for subagent result tracking
  - `iron_rook.review.contracts:ReviewOutput` - For returning aggregated findings

**Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_fsm.py` - FSM tests from Task 5
  - `tests/unit/fsm/test_todo.py` - Todo class tests for status tracking

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md:lines 211-232` - Shows todo_status output format
  - `iron_rook/review/security_review_agent.md:lines 238-268` - Shows gates and missing_information format

**WHY Each Reference Matters** (explain its relevance):
  - `security_review_agent.md:COLLECT phase` - Defines exact output schema for todo_status and issues_with_results
  - `todo.py` - Shows status enum values for consistency
  - Existing security tests - Provide patterns for testing result aggregation

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/agents/test_security_collect.py
- [ ] Test covers: Valid subagent results marked as done
- [ ] Test covers: Blocked subagent results handled with issues logged
- [ ] Test covers: Missing subagent results handled with missing_information
- [ ] Test covers: Findings aggregated correctly from multiple subagents
- [ ] Test covers: Consolidated results passed to EVALUATE phase
- [ ] pytest tests/unit/review/agents/test_security_collect.py → PASS (6 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: COLLECT phase validates and aggregates results from multiple subagents
    Tool: Bash (python test execution)
    Preconditions: Collection implementation completed, subagents exist
    Steps:
      1. Run: python -m pytest tests/unit/review/agents/test_security_collect.py -v -k test_collect_aggregation
      2. Assert: Test passes (findings from multiple subagents aggregated)
      3. Mock SecurityFSMAgent with 3 subagent results
      4. Run COLLECT phase execution
      5. Assert: All subagent results marked as done in todo_status
      6. Assert: Findings list contains all subagent findings
      7. Assert: Next phase request is "consolidate" or "evaluate"
    Expected Result: COLLECT phase properly aggregates subagent results and marks TODOs
    Evidence: Test output
  \`\`\`

**Evidence to Capture**:
- [ ] Test output showing successful result aggregation
- [ ] TODO status updates visible in logs
- [ ] Findings from multiple subagents merged correctly

**Commit**: YES (groups with 8)
- Message: `feat(review): add result aggregation in COLLECT phase`
- Files: `iron_rook/review/agents/security.py` (updated), tests for collection
- Pre-commit: `pytest tests/unit/review/agents/test_security_collect.py -q`

### Wave 7-10: Comprehensive Test Suite (Tasks 11-14)

- [ ] 11. Write unit tests for subagents

- [ ] 12. Write unit tests for subagents

**What to do**:
  - Create test file `tests/unit/review/subagents/test_security_subagents.py`
  - Test AuthSecuritySubagent FSM execution (intake → plan → act → synthesize → done)
  - Test InjectionScannerSubagent FSM execution
  - Test SecretScannerSubagent FSM execution
  - Test DependencyAuditSubagent FSM execution
  - Test error handling and retry logic in all subagents
  - Test subagent returns proper ReviewOutput format

**Must NOT do**:
  - Do NOT test subagents without FSM implementation - FSM is core feature
  - Do NOT skip error scenarios - test both success and failure cases
  - Do NOT duplicate test code - use pytest fixtures for common setup

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: Subagent testing requires understanding of FSM patterns and error handling
  - **Skills**: None required
    - Reason: FSM testing patterns from loop_fsm.py tests provide sufficient guidance

  - **Skills Evaluated but Omitted**:
    - Other skills not applicable

  - **Parallelization**:
    - **Can Run In Parallel**: NO
    - **Parallel Group**: Sequential (part of Task 5)
    - **Blocks**: Task 9, 10, 11
    - **Blocked By**: Task 5

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `tests/unit/fsm/test_loop_fsm.py` - Existing LoopFSM tests for state transitions and retries
  - `tests/unit/review/agents/test_security.py` - Base class tests for inheritance patterns

**API/Type References** (contracts to implement against):
  - `iron_rook.fsm.loop_state:LoopState` - States for FSM testing
  - `iron_rook.review.contracts:ReviewOutput` - Return type for subagents

**Test References** (testing patterns to follow):
  - `tests/unit/review/agents/` - Directory structure for new test file placement
  - Existing test files in tests/unit/review/agents/ - Pattern for test organization

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md` - Subagent FSM execution pattern described
  - `iron_rook/review/README.md` - Testing conventions

**WHY Each Reference Matters** (explain its relevance):
  - `test_loop_fsm.py` - Shows how to test state transitions with pytest and assertions
  - `test_security.py` - Shows existing SecurityReviewer test patterns for consistency
  - Subagent FSM pattern - Each subagent should complete intake → plan → act → synthesize → done loop

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/unit/review/subagents/test_security_subagents.py
- [ ] Test covers: AuthSecuritySubagent completes FSM successfully
- [ ] Test covers: InjectionScannerSubagent completes FSM successfully
- [ ] Test covers: SecretScannerSubagent completes FSM successfully
- [ ] Test covers: DependencyAuditSubagent completes FSM successfully
- [ ] Test covers: Subagent returns findings in correct format
- [ ] Test covers: Subagent handles errors and retries correctly
- [ ] pytest tests/unit/review/subagents/test_security_subagents.py → PASS (8 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: All 4 subagent types execute FSM loops and produce findings
    Tool: Bash (pytest execution)
    Preconditions: All subagent implementations completed
    Steps:
      1. Run: python -m pytest tests/unit/review/subagents/test_security_subagents.py -v
      2. Assert: All 8 tests pass
      3. Inspect test coverage for all components
      4. Verify each subagent type is tested
    Expected Result: All subagents have comprehensive test coverage and pass tests
    Evidence: Pytest output
  \`\`\`

**Evidence to Capture**:
- [ ] Test output showing 8 tests passed
- [ ] Coverage of all 4 subagent types (AuthSecuritySubagent, InjectionScannerSubagent, SecretScannerSubagent, DependencyAuditSubagent)
- [ ] Error scenarios tested (timeout, invalid input, FSM errors)

**Commit**: YES (groups with 4)
- Message: `test(review): add comprehensive tests for security subagents`
- Files: `tests/unit/review/subagents/test_security_subagents.py`, tests for FSM transitions, tests for thinking, tests for collection
- Pre-commit: `pytest tests/unit/review/ -q`

### Wave 8-14: Integration Tests (Tasks 14-21)

- [ ] 14. Write integration tests for end-to-end security review flow

**What to do**:
  - Create integration test `tests/integration/test_security_fsm_integration.py`
  - Test complete security review flow with multiple subagents
  - Test INTAKE → PLAN_TODOS → DELEGATE → COLLECT → CONSOLIDATE → EVALUATE → DONE
  - Mock subagents to return controlled findings
  - Test result aggregation and final report generation
  - Test error handling with failed subagents
  - Verify final ReviewOutput matches SecurityReviewReport schema

**Must NOT do**:
  - Do NOT rely on real LLM for integration tests - mock LLM responses
  - Do NOT test without mocking subagents - need controlled test scenarios
  - Do NOT skip validation of final output schema

**Recommended Agent Profile**:
> Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-high`
    - Reason: End-to-end testing requires understanding of complete security review workflow
  - **Skills**: None required
    - Reason: Integration patterns from existing test structure provide sufficient guidance

  - **Skills Evaluated but Omitted**:
    - Other skills not applicable

  - **Parallelization**:
    - **Can Run In Parallel**: NO
    - **Parallel Group**: Sequential (final tasks only)
    - **Blocks**: None (final task - no subsequent work)
    - **Blocked By**: Tasks 1-14

**References** (CRITICAL - Be Exhaustive):

> The executor has NO context from your interview. References are their ONLY guide.
> Each reference must answer: "What should I look at and WHY?"

**Pattern References** (existing code to follow):
  - `tests/unit/review/agents/test_security.py` - Existing integration test for security reviewer
  - `tests/integration/` - Directory structure for integration tests
  - Mock patterns from existing test files (unittest.mock, pytest fixtures)

**API/Type References** (contracts to implement against):
  - `iron_rook.review.contracts:ReviewOutput` - Return type to validate
  - `iron_rook.review.contracts:SecurityReviewReport` - Final report schema to validate

**Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security.py` - Shows mock usage and async testing patterns
  - `tests/unit/fsm/test_loop_fsm.py` - Shows FSM testing patterns for coverage
  - Existing integration tests - Structure for complex workflow tests

**Documentation References** (specs and requirements):
  - `iron_rook/review/security_review_agent.md` - Complete workflow specification
  - `iron_rook/review/README.md` - Testing and integration guidance

**WHY Each Reference Matters** (explain its relevance):
  - `test_security.py` - Shows existing SecurityReviewer test patterns to maintain consistency
  - Integration test patterns - Show how to test multi-agent workflows with mocks
  - Security review agent spec - Defines expected end-to-end flow to validate

**Acceptance Criteria**:

> **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
> Every criterion MUST be verifiable by running a command or using a tool.
> REPLACE all placeholders with actual values from task context.

**If TDD (tests enabled):**
- [ ] Test file created: tests/integration/test_security_fsm_integration.py
- [ ] Test covers: Complete 6-phase FSM execution in order
- [ ] Test covers: Subagents dispatched and results collected
- [ ] Test covers: Result aggregation and consolidation
- [ ] Test covers: Final report generation with correct schema
- [ ] Test covers: Error handling with subagent failures
- [ ] Test covers: SecurityFSMAgent returns valid ReviewOutput to orchestrator
- [ ] pytest tests/integration/test_security_fsm_integration.py → PASS (6 tests, 0 failures)

**Agent-Executed QA Scenarios** (MANDATORY — per-scenario, ultra-detailed):

  \`\`\`
  Scenario: End-to-end security review with 6 phases, subagents, and aggregation produces valid findings
    Tool: Bash (pytest execution)
    Preconditions: All implementations completed
    Steps:
      1. Run: python -m pytest tests/integration/test_security_fsm_integration.py -v
      2. Assert: All 6 tests pass
      3. Inspect test coverage for all components
      4. Verify mock subagents returned controlled findings
      5. Check final report structure matches SecurityReviewReport
    Expected Result: Complete security review flow works end-to-end
    Evidence: Pytest output and coverage report
  \`\`\`

**Evidence to Capture**:
- [ ] Test file with 6 integration tests passed
- [ ] Coverage report demonstrating all components tested
- [ ] Example final report from integration test

**Commit**: YES (final commit)
- Message: `test(integration): add end-to-end integration tests for security FSM reviewer`
- Files: `tests/integration/test_security_fsm_integration.py`, all previous test files
- Pre-commit: `pytest tests/ -q && pytest tests/integration/test_security_fsm_integration.py -q`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1, 2 | `feat(logging): add phase-specific logging and colored output` | `security_phase_logger.py`, `cli.py` | pytest tests/unit/review -q |
| 3, 4 | `feat(review): add subagent infrastructure with FSM support` | `security_subagents.py` | pytest tests/unit/review/subagents -q |
| 5, 6 | `refactor(review): implement 6-phase FSM in SecurityReviewer with phase transitions` | `security.py` | pytest tests/unit/review/agents -q |
| 7, 8 | `feat(review): add thinking capture, transitions, and aggregation` | `security.py` | pytest tests/unit/review/agents -q |
| 9, 10 | `test(review): add comprehensive tests for FSM, subagents, thinking, transitions, collection` | Multiple test files | pytest tests/unit/review/ -q |
| 11, 14 | `test(integration): add end-to-end integration tests for security FSM reviewer` | `test_security_fsm_integration.py` | pytest tests/ -q |

---

## Success Criteria

### Verification Commands
```bash
# Verify phase logger works
python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; logger = SecurityPhaseLogger(); logger.log_thinking('TEST', 'test thinking'); print('Success')"

# Verify colored logging
iron-rook --agent security --output json -v 2>&1 | head -10

# Verify 6-phase FSM execution
python -m pytest tests/unit/review/agents/test_security_fsm.py -v

# Verify subagents work
python -m pytest tests/unit/review/subagents/test_security_subagents.py -v

# Verify end-to-end flow
python -m pytest tests/integration/test_security_fsm_integration.py -v
```

### Final Checklist
- [ ] SecurityReviewer uses 6-phase FSM (intake, plan_todos, delegate, collect, consolidate, evaluate, done)
- [ ] SecurityReviewer delegates to subagents (auth_security, injection_scanner, secret_scanner, dependency_audit)
- [ ] Per-phase thinking logged with phase prefix
- [ ] State transitions logged explicitly at each phase change
- [ ] Colored logging implemented via RichHandler in CLI
- [ ] All subagents run their own FSM loops (intake → plan → act → synthesize → done)
- [ ] COLLECT phase aggregates and validates subagent results
- [ ] CONSOLIDATE phase merges and deduplicates findings before EVALUATE
- [ ] All tests pass (unit + integration) with 90%+ coverage
- [ ] Running `iron-rook --agent security --output json -v` shows phase-by-phase execution with thinking
- [ ] Integration tests demonstrate complete end-to-end flow
