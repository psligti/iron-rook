# Security FSM Thinking Steps Integration

## TL;DR

> **Quick Summary**: Add structured "thinking steps" to the security FSM using Pydantic models (ThinkingStep, ThinkingFrame, RunLog), integrate with SecurityPhaseLogger for display, maintain backward compatibility with existing LLM thinking extraction, and implement using TDD approach.
>
> **Deliverables**:
> - 3 new Pydantic models in `iron_rook/review/contracts.py` (ThinkingStep, ThinkingFrame, RunLog)
> - Modified `SecurityReviewer` class with `_thinking_log` accumulator
> - Extended `SecurityPhaseLogger` with `log_thinking_frame()` method
> - Updated all 6 phase handlers to create and log ThinkingFrames
> - Comprehensive test suite using TDD pattern
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 2 waves (tests + models, then integration)
> **Critical Path**: Create models → Update phase handlers → Integration tests

---

## Context

### Original Request
Add structured "thinking steps" to the security FSM, similar to a user-provided example pattern. Each state handler should return:
1. Next state
2. DecisionTrace object ("simulated thinking")
3. Any artifacts produced (todos, subagent results, etc.)

The trace should be brief, evidence-linked, and never a long free-form monologue.

### Interview Summary
**Key Discussions**:
- **Model location**: User confirmed - add to `iron_rook/review/contracts.py` (not new file)
- **LLM thinking preservation**: User confirmed - keep both raw string AND structured steps (backward compatibility)
- **RunLog scope**: User confirmed - internal only, NOT in public ReviewOutput API
- **Test strategy**: User confirmed - TDD (RED-GREEN-REFACTOR pattern)

**Technical Decisions**:
- Use Pydantic v2 patterns (already in project: `pydantic>=2.0`)
- Integrate with existing SecurityPhaseLogger for colored display
- Preserve existing `_extract_thinking_from_response()` functionality
- Follow existing Pydantic patterns: `BaseModel`, `ConfigDict`, `Field(default_factory=list)`

### Research Findings
- **Pydantic is already used**: `iron_rook/review/contracts.py` contains multiple BaseModel classes (ReviewContext, Scope, Finding, ReviewOutput, etc.)
- **Existing patterns**:
  - `pd.BaseModel` with `model_config = pd.ConfigDict(extra="forbid"|"ignore")`
  - `Field(default_factory=list)` for list fields
  - Type hints with Literal for enums
- **SecurityPhaseLogger**: Has `log_thinking(phase, message)` for simple string logging, uses Rich for colored output
- **Current thinking extraction**: `_extract_thinking_from_response()` handles multiple formats (JSON "thinking" field, XML `<thinking>` tags, markdown-wrapped JSON)
- **Test patterns**: `test_security_thinking.py` verifies thinking extraction with mock LLM responses

### Metis Review
**Identified Gaps** (addressed in plan):
- **Error handling**: Added explicit strategy for malformed structured data (fallback to raw thinking string, log warning)
- **Field validation**: Defined required vs optional fields, enum values for `kind`
- **Test file placement**: Confirmed - add to existing `test_security_thinking.py`, no new file
- **Edge cases**: Addressed partially structured data, conflicting sources, empty thinking, invalid enums, Unicode

**Guardrails Applied** (from Metis review):
- **MUST NOT**: Modify `SecurityReviewer` public API - internal changes only
- **MUST NOT**: Expose `RunLog` or `_thinking_log` in public API
- **MUST**: Preserve existing `ReviewContext.thinking` string output unchanged
- **MUST**: All existing tests in `test_security_thinking.py` pass without modification
- **MUST NOT**: Add visualization UI, export/import, search/filter, or analytics features
- **MUST**: Follow existing Pydantic patterns exactly (`BaseModel`, `ConfigDict`, `Field`)

**Scope Boundaries** (explicitly locked):
- **INCLUDE**:
  - Create 3 Pydantic models (ThinkingStep, ThinkingFrame, RunLog)
  - Modify SecurityReviewer internal implementation
  - Extend SecurityPhaseLogger with `log_thinking_frame()`
  - Update all 6 phase handlers
  - Add comprehensive test suite
- **EXCLUDE**:
  - Changing FSM transitions (keep existing SECURITY_FSM_TRANSITIONS)
  - Modifying subagent behavior
  - Changing LLM prompts or response handling
  - Adding visualization UI or dashboards
  - Adding export/import functionality
  - Adding search/filter/query capabilities
  - Adding analytics or pattern analysis

---

## Work Objectives

### Core Objective
Add structured "thinking steps" to the security FSM to improve observability and debugging of phase execution, while maintaining full backward compatibility with existing behavior.

### Concrete Deliverables
- `iron_rook/review/contracts.py`: Added ThinkingStep, ThinkingFrame, RunLog models
- `iron_rook/review/agents/security.py`: Modified SecurityReviewer with `_thinking_log` accumulator and updated phase handlers
- `iron_rook/review/security_phase_logger.py`: Added `log_thinking_frame()` method
- `tests/unit/review/agents/test_security_thinking.py`: Extended with new tests for thinking frames

### Definition of Done
- [x] All 3 Pydantic models created and validated
- [x] All 6 phase handlers updated to create ThinkingFrames
- [x] SecurityPhaseLogger.log_thinking_frame() implemented
- [x] All tests pass (100% pass rate)
- [x] Existing tests unchanged and passing
- [ ] Code follows existing Pydantic patterns exactly
- [ ] Backward compatibility verified (no API changes)

### Must Have
- ThinkingStep model with kind, why, evidence, next, confidence fields
- ThinkingFrame model with state, ts, goals, checks, risks, steps, decision fields
- RunLog model with frames list and add() method
- SecurityReviewer._thinking_log accumulator (internal only)
- All 6 phase handlers create ThinkingFrames with appropriate goals/checks/risks/steps
- SecurityPhaseLogger.log_thinking_frame() displays structured frames with colored output
- TDD approach: write tests first, implement to pass, refactor if needed

### Must NOT Have (Guardrails)
- NO changes to SecurityReviewer public API
- NO exposure of RunLog or _thinking_log outside SecurityReviewer
- NO modification of existing test methods (only add new tests)
- NO changes to FSM transitions (SECURITY_FSM_TRANSITIONS)
- NO changes to ReviewContext structure
- NO breaking of existing _extract_thinking_from_response() behavior
- NO visualization UI, dashboards, or frontend components
- NO export/import functionality for thinking logs
- NO search/filter/query capabilities across thinking frames
- NO analytics or pattern analysis features

---

## Verification Strategy (MANDATORY)

> **UNIVERSAL RULE: ZERO HUMAN INTERVENTION**
>
> ALL tasks in this plan MUST be verifiable WITHOUT any human action.
> This is NOT conditional — it applies to EVERY task, regardless of test strategy.

### Test Decision
- **Infrastructure exists**: YES (pytest with asyncio)
- **Automated tests**: TDD (RED-GREEN-REFACTOR)
- **Framework**: pytest

### TDD Workflow

Each TODO follows RED-GREEN-REFACTOR:

**Task Structure:**
1. **RED**: Write failing test first
   - Test file: `tests/unit/review/agents/test_security_thinking.py`
   - Test command: `pytest tests/unit/review/agents/test_security_thinking.py::test_name -xvs`
   - Expected: FAIL (test exists, implementation doesn't)
2. **GREEN**: Implement minimum code to pass
   - Command: `pytest tests/unit/review/agents/test_security_thinking.py::test_name -xvs`
   - Expected: PASS
3. **REFACTOR**: Clean up while keeping green
   - Command: `pytest tests/unit/review/agents/test_security_thinking.py -xvs`
   - Expected: PASS (still)

### Agent-Executed QA Scenarios (MANDATORY — ALL tasks)

> Whether TDD is enabled or not, EVERY task MUST include Agent-Executed QA Scenarios.
> - **With TDD**: QA scenarios complement unit tests at integration/E2E level
> - **Without TDD**: QA scenarios are the PRIMARY verification method
>
> These describe how the executing agent DIRECTLY verifies the deliverable
> by running it — importing modules, creating objects, verifying behavior.
> The agent performs what a developer would do, but automated via tools.

**Verification Tool by Deliverable Type:**

| Type | Tool | How Agent Verifies |
|------|------|-------------------|
| **Pydantic Models** | Bash (python REPL) | Import, validate, test edge cases |
| **Class Methods** | Bash (python REPL) | Create instances, call methods, assert behavior |
| **Integration** | Bash (python REPL) | Full workflow: create reviewer, run phases, verify frames |
| **Logging** | Bash (python REPL) | Call logger methods, capture output, assert formatting |

**Each Scenario MUST Follow This Format:**

```
Scenario: [Descriptive name — what component/flow is being verified]
  Tool: Bash (python REPL)
  Preconditions: [What must be true before this scenario runs]
  Steps:
    1. [Exact Python code/expression to execute]
    2. [Next code/expression with expected intermediate state]
    3. [Assertion with exact expected value]
  Expected Result: [Concrete, observable outcome]
  Failure Indicators: [What would indicate failure]
  Evidence: [Import success, validation results, captured output]
```

**Anti-patterns (NEVER write scenarios like this):**
- ❌ "Verify the Pydantic models work correctly"
- ❌ "Check that the thinking frames are created properly"
- ❌ "Test the logger displays frames"

**Write scenarios like this instead:**
- ✅ `from iron_rook.review.contracts import ThinkingStep; step = ThinkingStep(kind="transition", why="test") → assert step.kind == "transition"`
- ✅ `from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); assert hasattr(r, '_thinking_log')`
- ✅ `frame = ThinkingFrame(state="test"); logger.log_thinking_frame(frame) → assert "TEST" in output`

---

## Execution Strategy

### Parallel Execution Waves

> Maximize throughput by grouping independent tasks into parallel waves.
> Each wave completes before the next begins.

```
Wave 1 (Start Immediately):
├── Task 1: Add ThinkingStep Pydantic model
├── Task 2: Add ThinkingFrame Pydantic model
├── Task 3: Add RunLog Pydantic model
└── Task 4: Write tests for Pydantic models

Wave 2 (After Wave 1):
├── Task 5: Add log_thinking_frame() to SecurityPhaseLogger
├── Task 6: Add _thinking_log accumulator to SecurityReviewer
└── Task 7: Write tests for SecurityPhaseLogger extension

Wave 3 (After Wave 2):
├── Task 8: Update _run_intake() to create ThinkingFrame
├── Task 9: Update _run_plan_todos() to create ThinkingFrame
└── Task 10: Update _run_delegate() to create ThinkingFrame

Wave 4 (After Wave 3):
├── Task 11: Update _run_collect() to create ThinkingFrame
├── Task 12: Update _run_consolidate() to create ThinkingFrame
└── Task 13: Update _run_evaluate() to create ThinkingFrame

Wave 5 (After Wave 4):
└── Task 14: Integration tests for full workflow

Critical Path: Task 1 → Task 5 → Task 8 → Task 14
Parallel Speedup: ~50% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 5 | 2, 3 |
| 2 | None | 5 | 1, 3 |
| 3 | None | 6 | 1, 2 |
| 4 | 1, 2, 3 | None | None (after models) |
| 5 | 4 | 8, 9, 10 | 6, 7 |
| 6 | 3 | 8, 9, 10 | 5, 7 |
| 7 | 5 | None | None (after logger) |
| 8 | 5 | 14 | 9, 10, 11, 12, 13 |
| 9 | 5 | 14 | 8, 10, 11, 12, 13 |
| 10 | 5 | 14 | 8, 9, 11, 12, 13 |
| 11 | 5 | 14 | 8, 9, 10, 12, 13 |
| 12 | 5 | 14 | 8, 9, 10, 11, 13 |
| 13 | 5 | 14 | 8, 9, 10, 11, 12 |
| 14 | 8, 9, 10, 11, 12, 13 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2, 3, 4 | task(category="quick", load_skills=[], run_in_background=false) |
| 2 | 5, 6, 7 | task(category="quick", load_skills=[], run_in_background=false) |
| 3 | 8, 9, 10 | task(category="quick", load_skills=[], run_in_background=false) |
| 4 | 11, 12, 13 | task(category="quick", load_skills=[], run_in_background=false) |
| 5 | 14 | task(category="unspecified-low", load_skills=[], run_in_background=false) |

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info.

- [x] 1. Add ThinkingStep Pydantic model to contracts.py

  **What to do**:
  - Create ThinkingStep model in `iron_rook/review/contracts.py`
  - Fields: kind (Literal["transition", "tool", "delegate", "gate", "stop"]), why (str), evidence (List[str]), next (Optional[str]), confidence (Literal["low", "medium", "high"])
  - Follow existing Pydantic patterns: use pd.Field with default_factory=list for evidence, set default values
  - Use ConfigDict for model configuration (extra="ignore" or "forbid")

  **Must NOT do**:
  - Create custom validators (use Pydantic defaults only)
  - Add visualization or export methods
  - Change existing model patterns in contracts.py

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single file change, well-defined Pydantic model, straightforward
  - **Skills**: []
    - No specialized skills needed for Pydantic model definition
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: UI/UX not relevant for data model
    - `playwright`: No browser interaction needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3)
  - **Blocks**: Task 4 (tests for ThinkingStep)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/contracts.py:87-93` - Scope class (pd.BaseModel with Field and model_config pattern)
  - `iron_rook/review/contracts.py:95-100` - Check class (Field with default_factory for lists)
  - `iron_rook/review/contracts.py:102-140` - ReviewContext, Finding, ReviewOutput (BaseModel patterns)

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import as `from iron_rook.review.contracts import BaseModel, Field, ConfigDict`

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:17-33` - Test extraction patterns, mock setup
  - `tests/unit/review/agents/test_security_thinking.py:127-205` - Phase thinking logging tests

  **Documentation References** (specs and requirements):
  - User-provided example (in context): ThinkingStep model specification with kind, why, evidence, next, confidence

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel field definitions
  - Example: User's example code in context - ThinkingStep model structure

  **WHY Each Reference Matters** (explain the relevance):
  - `contracts.py:87-93`: Shows exact Field and ConfigDict patterns to follow (default_factory, extra handling)
  - `contracts.py:95-100`: Demonstrates list field with default_factory pattern needed for evidence list
  - `test_security_thinking.py:17-33`: Shows test pattern for model validation and edge cases

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: ThinkingStep model validates correctly with valid inputs
  - [ ] Test covers: ThinkingStep rejects invalid kind enum values
  - [ ] Test covers: ThinkingStep default values applied correctly
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::test_thinking_step_validation -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: ThinkingStep model creates with valid input
    Tool: Bash (python REPL)
    Preconditions: None
    Steps:
      1. python -c "from iron_rook.review.contracts import ThinkingStep; step = ThinkingStep(kind='transition', why='test', evidence=['e1'], next='done', confidence='high')"
      2. python -c "from iron_rook.review.contracts import ThinkingStep; step = ThinkingStep(kind='transition', why='test'); assert step.evidence == []"
      3. python -c "from iron_rook.review.contracts import ThinkingStep; step = ThinkingStep(kind='transition', why='test'); assert step.confidence == 'medium'"
    Expected Result: ThinkingStep created with all fields, defaults applied
    Evidence: Import successful, no exceptions
    Failure Indicators: ImportError, ValidationError

  Scenario: ThinkingStep rejects invalid kind enum
    Tool: Bash (python REPL)
    Preconditions: ThinkingStep model defined
    Steps:
      1. python -c "from iron_rook.review.contracts import ThinkingStep; from pydantic import ValidationError; exec('try:\n    step = ThinkingStep(kind=\"invalid\", why=\"test\")\nexcept ValidationError as e:\n    print(\"ValidationError\")')"
      2. Assert: ValidationError was raised (output contains "ValidationError")
    Expected Result: ValidationError raised for invalid enum value
    Evidence: ValidationError output captured
    Failure Indicators: No exception raised, invalid kind accepted

  Scenario: ThinkingStep evidence field uses default_factory list
    Tool: Bash (python REPL)
    Preconditions: ThinkingStep model defined
    Steps:
      1. python -c "from iron_rook.review.contracts import ThinkingStep; step = ThinkingStep(kind='transition', why='test'); assert isinstance(step.evidence, list)"
      2. python -c "from iron_rook.review.contracts import ThinkingStep; step = ThinkingStep(kind='transition', why='test'); assert step.evidence == []"
    Expected Result: Evidence field is empty list when not provided
    Evidence: Field value is list, defaults applied correctly
    Failure Indicators: evidence is None, wrong type, TypeError
  \`\`\`

  **Evidence to Capture:**
  - [ ] Python import success messages
  - [ ] Validation error messages (if any)
  - [ ] Test output showing pass/fail status

  **Commit**: YES
  - Message: `type(contracts): add ThinkingStep Pydantic model`
  - Files: `iron_rook/review/contracts.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::test_thinking_step_validation -xvs`

- [x] 2. Add ThinkingFrame Pydantic model to contracts.py

  **What to do**:
  - Create ThinkingFrame model in `iron_rook/review/contracts.py`
  - Fields: state (str), ts (str with default_factory for timestamp), goals (List[str]), checks (List[str]), risks (List[str]), steps (List[ThinkingStep]), decision (str)
  - Import ThinkingStep for steps field type
  - Use default_factory=list for all list fields
  - Use ConfigDict for model configuration

  **Must NOT do**:
  - Add methods beyond Pydantic model definition
  - Modify existing models in contracts.py

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single file change, well-defined Pydantic model, straightforward
  - **Skills**: []
    - No specialized skills needed for Pydantic model definition
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: UI/UX not relevant for data model
    - `playwright`: No browser interaction needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3)
  - **Blocks**: Task 4 (tests for ThinkingFrame)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/contracts.py:87-93` - Scope class (BaseModel with Field pattern)
  - `iron_rook/review/contracts.py:95-100` - Check class (list fields with default_factory)

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import as `from iron_rook.review.contracts import BaseModel, Field, ConfigDict, ThinkingStep`

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:17-33` - Test patterns for models

  **Documentation References** (specs and requirements):
  - User-provided example (in context): ThinkingFrame model specification with state, ts, goals, checks, risks, steps, decision

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel field definitions
  - Example: User's example code in context - ThinkingFrame model structure

  **WHY Each Reference Matters** (explain the relevance):
  - `contracts.py:87-93`: Shows exact BaseModel and ConfigDict patterns to follow
  - `contracts.py:95-100`: Demonstrates list field with default_factory needed for goals/checks/risks/steps

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: ThinkingFrame model validates correctly with valid inputs
  - [ ] Test covers: ThinkingFrame timestamp default_factory generates ISO format
  - [ ] Test covers: ThinkingFrame all list fields use default_factory
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::test_thinking_frame_validation -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: ThinkingFrame model creates with valid input
    Tool: Bash (python REPL)
    Preconditions: ThinkingStep model defined
    Steps:
      1. python -c "from iron_rook.review.contracts import ThinkingFrame; from datetime import datetime; frame = ThinkingFrame(state='test', ts=datetime.utcnow().isoformat() + 'Z', goals=['g1'], checks=['c1'], risks=['r1'], steps=[], decision='test')"
      2. python -c "from iron_rook.review.contracts import ThinkingFrame; frame = ThinkingFrame(state='test'); assert len(frame.goals) == 0"
      3. python -c "from iron_rook.review.contracts import ThinkingFrame; frame = ThinkingFrame(state='test'); assert 'Z' in frame.ts"
    Expected Result: ThinkingFrame created with all fields, timestamp has 'Z' suffix
    Evidence: Import successful, no exceptions
    Failure Indicators: ImportError, ValidationError

  Scenario: ThinkingFrame timestamp default_factory generates ISO format
    Tool: Bash (python REPL)
    Preconditions: ThinkingFrame model defined
    Steps:
      1. python -c "from iron_rook.review.contracts import ThinkingFrame; frame = ThinkingFrame(state='test'); assert isinstance(frame.ts, str)"
      2. python -c "from iron_rook.review.contracts import ThinkingFrame; frame = ThinkingFrame(state='test'); assert 'T' in frame.ts or 'Z' in frame.ts"
      3. python -c "from iron_rook.review.contracts import ThinkingFrame; frame = ThinkingFrame(state='test'); assert len(frame.ts.split('T')) == 2 or len(frame.ts.split('Z')) == 2"
    Expected Result: Timestamp is ISO 8601 format string
    Evidence: Field value is string with ISO format
    Failure Indicators: timestamp is None, wrong format, TypeError
  \`\`\`

  **Evidence to Capture:**
  - [ ] Python import success messages
  - [ ] Validation error messages (if any)
  - [ ] Test output showing pass/fail status

  **Commit**: YES
  - Message: `type(contracts): add ThinkingFrame Pydantic model`
  - Files: `iron_rook/review/contracts.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::test_thinking_frame_validation -xvs`

- [x] 3. Add RunLog Pydantic model to contracts.py

  **What to do**:
  - Create RunLog model in `iron_rook/review/contracts.py`
  - Fields: frames (List[ThinkingFrame])
  - Add add() method to append frames
  - Use default_factory=list for frames field
  - Use ConfigDict for model configuration

  **Must NOT do**:
  - Add persistence methods (save/load) - internal accumulator only
  - Modify ThinkingFrame or ThinkingStep models

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single file change, well-defined Pydantic model, straightforward
  - **Skills**: []
    - No specialized skills needed for Pydantic model definition
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: UI/UX not relevant for data model
    - `playwright`: No browser interaction needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2)
  - **Blocks**: Task 4 (tests for RunLog)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/contracts.py:87-100` - Scope, Check classes (BaseModel with Field pattern)

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import as `from iron_rook.review.contracts import BaseModel, Field, ConfigDict, ThinkingFrame`

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:17-33` - Test patterns for models

  **Documentation References** (specs and requirements):
  - User-provided example (in context): RunLog model specification with frames list and add() method

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel field definitions
  - Example: User's example code in context - RunLog model structure

  **WHY Each Reference Matters** (explain the relevance):
  - `contracts.py:87-100`: Shows exact BaseModel, Field, and default_factory patterns to follow

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: RunLog model validates correctly with valid inputs
  - [ ] Test covers: RunLog.frames uses default_factory=[]
  - [ ] Test covers: RunLog.add() method appends frame correctly
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::test_run_log_validation -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: RunLog model creates with valid input
    Tool: Bash (python REPL)
    Preconditions: ThinkingFrame model defined
    Steps:
      1. python -c "from iron_rook.review.contracts import RunLog, ThinkingFrame; log = RunLog(); assert len(log.frames) == 0"
      2. python -c "from iron_rook.review.contracts import RunLog, ThinkingFrame; log = RunLog(); frame = ThinkingFrame(state='test'); log.add(frame); assert len(log.frames) == 1"
      3. python -c "from iron_rook.review.contracts import RunLog, ThinkingFrame; log = RunLog(); frames = [ThinkingFrame(state='t1'), ThinkingFrame(state='t2')]; [log.add(f) for f in frames]; assert len(log.frames) == 2"
    Expected Result: RunLog created with empty frames, add() appends correctly
    Evidence: Import successful, no exceptions, frames list updated
    Failure Indicators: ImportError, AttributeError (no add method), list operations fail

  Scenario: RunLog.frames uses default_factory list
    Tool: Bash (python REPL)
    Preconditions: RunLog model defined
    Steps:
      1. python -c "from iron_rook.review.contracts import RunLog; log = RunLog(); assert isinstance(log.frames, list)"
      2. python -c "from iron_rook.review.contracts import RunLog; log = RunLog(); assert log.frames == []"
    Expected Result: Frames field is empty list when not provided
    Evidence: Field value is list, defaults applied correctly
    Failure Indicators: frames is None, wrong type, TypeError
  \`\`\`

  **Evidence to Capture:**
  - [ ] Python import success messages
  - [ ] Validation error messages (if any)
  - [ ] Test output showing pass/fail status

  **Commit**: YES
  - Message: `type(contracts): add RunLog Pydantic model`
  - Files: `iron_rook/review/contracts.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::test_run_log_validation -xvs`

- [x] 4. Write tests for Pydantic models (ThinkingStep, ThinkingFrame, RunLog)

  **What to do**:
  - Add tests to `tests/unit/review/agents/test_security_thinking.py`
  - Test ThinkingStep: valid input, invalid kind enum, default values, evidence field default_factory
  - Test ThinkingFrame: valid input, timestamp default_factory, list fields default_factory
  - Test RunLog: valid input, add() method, frames default_factory
  - Follow existing test patterns in test_security_thinking.py
  - Use pytest fixtures where appropriate

  **Must NOT do**:
  - Create new test file (add to existing test_security_thinking.py)
  - Modify existing test methods (only add new test classes/functions)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Test additions to existing file, straightforward validation tests
  - **Skills**: []
    - No specialized skills needed for pytest tests
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Tasks 1, 2, 3)
  - **Blocks**: None (final task in Wave 1)
  - **Blocked By**: Tasks 1, 2, 3 (models must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `tests/unit/review/agents/test_security_thinking.py:17-33` - Test structure (mock setup, assertions)
  - `tests/unit/review/agents/test_security_thinking.py:127-167` - Phase thinking test patterns

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import models to test

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Existing test structure and patterns

  **Documentation References** (specs and requirements):
  - Test requirements from interview: TDD approach, pytest framework

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pytest.org/en/stable/how-to/assert.html` - pytest assertion patterns
  - Example: `tests/unit/review/agents/test_security_thinking.py` - existing test file structure

  **WHY Each Reference Matters** (explain the relevance):
  - `test_security_thinking.py:17-33`: Shows test pattern with mock setup and assertions
  - `test_security_thinking.py:127-167`: Demonstrates test structure for phase-related tests

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: ThinkingStep validation (valid/invalid)
  - [ ] Test covers: ThinkingFrame validation (valid, timestamp, defaults)
  - [ ] Test covers: RunLog validation (valid, add method)
  - [ ] All tests initially FAIL (RED), then PASS after implementation (GREEN)
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: All ThinkingStep tests pass
    Tool: Bash (pytest)
    Preconditions: ThinkingStep model implemented
    Steps:
      1. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_thinking_step_valid_input -xvs
      2. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_thinking_step_invalid_kind -xvs
      3. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_thinking_step_default_values -xvs
    Expected Result: All ThinkingStep tests pass
    Evidence: Test output shows all tests passed
    Failure Indicators: Any test FAIL, pytest exit code non-zero

  Scenario: All ThinkingFrame tests pass
    Tool: Bash (pytest)
    Preconditions: ThinkingFrame model implemented
    Steps:
      1. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_thinking_frame_valid_input -xvs
      2. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_thinking_frame_timestamp -xvs
      3. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_thinking_frame_default_lists -xvs
    Expected Result: All ThinkingFrame tests pass
    Evidence: Test output shows all tests passed
    Failure Indicators: Any test FAIL, pytest exit code non-zero

  Scenario: All RunLog tests pass
    Tool: Bash (pytest)
    Preconditions: RunLog model implemented
    Steps:
      1. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_run_log_valid_input -xvs
      2. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_run_log_add_method -xvs
      3. pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels::test_run_log_default_frames -xvs
    Expected Result: All RunLog tests pass
    Evidence: Test output shows all tests passed
    Failure Indicators: Any test FAIL, pytest exit code non-zero
  \`\`\`

  **Evidence to Capture:**
  - [ ] Test run output (pytest summary)
  - [ ] Individual test results (passed/failed counts)
  - [ ] Coverage report (if available)

  **Commit**: YES
  - Message: `test(agents): add tests for thinking models (ThinkingStep, ThinkingFrame, RunLog)`
  - Files: `tests/unit/review/agents/test_security_thinking.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels -xvs`

- [x] 5. Add log_thinking_frame() method to SecurityPhaseLogger

  **What to do**:
  - Add `log_thinking_frame(frame: ThinkingFrame) -> None` method to `iron_rook/review/security_phase_logger.py`
  - Display state header with bold styling and phase color
  - Display goals list with dim styling (bullet format)
  - Display checks list with dim styling (bullet format)
  - Display risks list with red styling (bullet format)
  - Display each thinking step with kind, why, evidence, next, confidence
  - Display final decision with bold styling
  - Log to internal logger (existing pattern in log_thinking method)

  **Must NOT do**:
  - Modify existing `log_thinking(phase, message)` method
  - Modify existing `log_transition(from_state, to_state)` method
  - Add export/import functionality

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method addition to existing logger, well-defined behavior
  - **Skills**: []
    - No specialized skills needed for logger method
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components (only logging)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7)
  - **Blocks**: Task 8 (phase handlers depend on logger)
  - **Blocked By**: None (can start immediately)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/security_phase_logger.py:54-76` - log_thinking method (Rich styling, logging patterns)
  - `iron_rook/review/security_phase_logger.py:30-41` - PHASE_COLORS dict (color patterns)

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame type annotation
  - `iron_rook/review/security_phase_logger.py:54-76` - Follow existing Rich console patterns

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Test patterns for logger methods

  **Documentation References** (specs and requirements):
  - SecurityPhaseLogger existing methods (log_thinking, log_transition)
  - User requirement: Integrate with SecurityPhaseLogger for display

  **External References** (libraries and frameworks):
  - Official docs: `https://rich.readthedocs.io/en/stable/console.html#rich.console.Console.print` - Rich console.print API
  - Example: User's example code in context - log_thinking_frame display logic

  **WHY Each Reference Matters** (explain the relevance):
  - `security_phase_logger.py:54-76`: Shows exact Rich styling patterns to follow (Text objects, color styles)
  - `security_phase_logger.py:30-41`: Demonstrates PHASE_COLORS usage for consistent styling

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: log_thinking_frame() displays state header correctly
  - [ ] Test covers: log_thinking_frame() displays goals/checks/risks with bullets
  - [ ] Test covers: log_thinking_frame() displays thinking steps with all fields
  - [ ] Test covers: log_thinking_frame() logs to internal logger
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: log_thinking_frame() displays state header with styling
    Tool: Bash (python REPL)
    Preconditions: SecurityPhaseLogger imported, ThinkingFrame model defined
    Steps:
      1. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame; logger = SecurityPhaseLogger(); frame = ThinkingFrame(state='test'); print('State test passed')"
      2. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame; logger = SecurityPhaseLogger(); frame = ThinkingFrame(state='intake'); logger.log_thinking_frame(frame); print('Check output format')"
      3. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame; logger = SecurityPhaseLogger(); frame = ThinkingFrame(state='plan_todos'); logger.log_thinking_frame(frame); print('Check PLAN_TODOS color')"
    Expected Result: Frame state displayed with bold styling and phase-specific color
    Evidence: Console output shows "== STATE ==" with color, no exceptions
    Failure Indicators: Method not found, AttributeError, no color applied

  Scenario: log_thinking_frame() displays goals/checks/risks with bullets
    Tool: Bash (python REPL)
    Preconditions: SecurityPhaseLogger with log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame; logger = SecurityPhaseLogger(); frame = ThinkingFrame(state='test', goals=['g1', 'g2']); logger.log_thinking_frame(frame)"
      2. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame; logger = SecurityPhaseLogger(); frame = ThinkingFrame(state='test', checks=['c1', 'c2']); logger.log_thinking_frame(frame)"
      3. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame; logger = SecurityPhaseLogger(); frame = ThinkingFrame(state='test', risks=['r1']); logger.log_thinking_frame(frame)"
    Expected Result: Goals/checks/risks displayed as bullet list with dim styling
    Evidence: Console output shows bullet points with styling, no exceptions
    Failure Indicators: Missing bullets, wrong styling, TypeError

  Scenario: log_thinking_frame() displays thinking steps with all fields
    Tool: Bash (python REPL)
    Preconditions: SecurityPhaseLogger with log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame, ThinkingStep; logger = SecurityPhaseLogger(); step = ThinkingStep(kind='transition', why='test', evidence=['e1'], next='done', confidence='high'); frame = ThinkingFrame(state='test', steps=[step]); logger.log_thinking_frame(frame)"
      2. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame, ThinkingStep; logger = SecurityPhaseLogger(); step = ThinkingStep(kind='gate', why='test', next='collect', confidence='medium'); frame = ThinkingFrame(state='test', steps=[step]); logger.log_thinking_frame(frame)"
      3. python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; from iron_rook.review.contracts import ThinkingFrame, ThinkingStep; logger = SecurityPhaseLogger(); step = ThinkingStep(kind='stop', why='test', confidence='low'); frame = ThinkingFrame(state='test', steps=[step]); logger.log_thinking_frame(frame)"
    Expected Result: Each step displays kind, why, evidence, next, confidence with styling
    Evidence: Console output shows all step fields, formatted correctly, no exceptions
    Failure Indicators: Missing fields, wrong format, AttributeError
  \`\`\`

  **Evidence to Capture:**
  - [ ] Console output examples for each scenario
  - [ ] No exceptions raised
  - [ ] Rich styling applied (bold, dim, colors)

  **Commit**: YES
  - Message: `type(logger): add log_thinking_frame() method to SecurityPhaseLogger`
  - Files: `iron_rook/review/security_phase_logger.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame -xvs`

- [x] 6. Write tests for SecurityPhaseLogger.log_thinking_frame()

  **What to do**:
  - Add tests to `tests/unit/review/agents/test_security_thinking.py`
  - Test log_thinking_frame() displays state header correctly
  - Test log_thinking_frame() displays goals/checks/risks with bullets
  - Test log_thinking_frame() displays thinking steps with all fields
  - Test log_thinking_frame() logs to internal logger
  - Mock console output to verify formatting (or use caplog pytest fixture)
  - Follow existing test patterns in test_security_thinking.py

  **Must NOT do**:
  - Create new test file (add to existing test_security_thinking.py)
  - Modify existing test methods (only add new test classes/functions)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Test additions to existing file, mock-based logger tests
  - **Skills**: []
    - No specialized skills needed for pytest tests
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components (only logging tests)

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on Task 5)
  - **Blocks**: None (final task in Wave 2)
  - **Blocked By**: Task 5 (log_thinking_frame must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `tests/unit/review/agents/test_security_thinking.py:17-76` - Test patterns with mocks and assertions

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/security_phase_logger.py` - SecurityPhaseLogger class

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Existing test structure

  **Documentation References** (specs and requirements):
  - Test requirements from interview: TDD approach, pytest framework

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pytest.org/en/stable/how-to/assert.html` - pytest assertion patterns
  - Example: `tests/unit/review/agents/test_security_thinking.py` - existing test file structure

  **WHY Each Reference Matters** (explain the relevance):
  - `test_security_thinking.py:17-76`: Shows test pattern with mock setup and assertions to follow

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: log_thinking_frame() calls Rich console.print
  - [ ] Test covers: log_thinking_frame() logs to internal logger
  - [ ] Test covers: log_thinking_frame() applies correct styling (bold, dim, colors)
  - [ ] All tests initially FAIL (RED), then PASS after implementation (GREEN)
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame::test_log_thinking_frame_header -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: log_thinking_frame() header test passes
    Tool: Bash (pytest)
    Preconditions: SecurityPhaseLogger with log_thinking_frame implemented
    Steps:
      1. pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame::test_log_thinking_frame_header -xvs
      2. pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame::test_log_thinking_frame_goals -xvs
      3. pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame::test_log_thinking_frame_steps -xvs
    Expected Result: All log_thinking_frame tests pass
    Evidence: Test output shows all tests passed
    Failure Indicators: Any test FAIL, pytest exit code non-zero
  \`\`\`

  **Evidence to Capture:**
  - [ ] Test run output (pytest summary)
  - [ ] Individual test results (passed/failed counts)

  **Commit**: YES
  - Message: `test(agents): add tests for SecurityPhaseLogger.log_thinking_frame()`
  - Files: `tests/unit/review/agents/test_security_thinking.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame -xvs`

- [x] 7. Add _thinking_log accumulator to SecurityReviewer class

  **What to do**:
  - Add `self._thinking_log = RunLog()` to `SecurityReviewer.__init__()`
  - Import RunLog from contracts
  - Ensure _thinking_log is private (underscore prefix)
  - No public API changes (internal only)

  **Must NOT do**:
  - Expose _thinking_log in public API
  - Add get_thinking_log() method
  - Modify existing __init__ parameters

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single field addition to existing class, internal-only change
  - **Skills**: []
    - No specialized skills needed for field initialization
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 5, 7)
  - **Blocks**: Task 8 (phase handlers depend on _thinking_log)
  - **Blocked By**: Task 3 (RunLog must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:52-78` - SecurityReviewer.__init__() method pattern
  - `iron_rook/review/agents/security.py:76-78` - Private field initialization pattern (_phase_outputs, _current_security_phase)

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import RunLog type

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Test patterns for SecurityReviewer

  **Documentation References** (specs and requirements):
  - Interview requirement: RunLog internal only, NOT in public API

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.python.org/3/tutorial/classes.html` - Python class initialization patterns
  - Example: User's example code in context - _thinking_log accumulator pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:52-78`: Shows exact __init__ pattern to follow with private fields and underscore prefix

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: SecurityReviewer._thinking_log exists and is RunLog instance
  - [ ] Test covers: _thinking_log is private (not in dir(reviewer) without _)
  - [ ] Test covers: _thinking_log initialized with empty frames list
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestSecurityReviewerThinkingLog::test_thinking_log_initialized -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: SecurityReviewer._thinking_log is initialized correctly
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer imported, RunLog model defined
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); assert hasattr(r, '_thinking_log')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; from iron_rook.review.contracts import RunLog; r = SecurityReviewer(); assert isinstance(r._thinking_log, RunLog)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); assert len(r._thinking_log.frames) == 0"
    Expected Result: _thinking_log exists as RunLog instance with empty frames
    Evidence: Import successful, no exceptions, private attribute check
    Failure Indicators: AttributeError, _thinking_log not RunLog instance, frames not empty

  Scenario: _thinking_log is private (not in public API)
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log field
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); public_attrs = [a for a in dir(r) if not a.startswith('_')]; assert '_thinking_log' not in public_attrs"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); assert 'thinking_log' not in dir(r)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); assert '_thinking_log' in dir(r)"
    Expected Result: _thinking_log is private (only accessible with underscore)
    Evidence: Public attributes list excludes _thinking_log
    Failure Indicators: thinking_log in public API, no underscore prefix
  \`\`\`

  **Evidence to Capture:**
  - [ ] Python import success messages
  - [ ] Test output showing pass/fail status

  **Commit**: YES
  - Message: `type(agents): add _thinking_log accumulator to SecurityReviewer`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestSecurityReviewerThinkingLog -xvs`

- [ ] 8. Update _run_intake() to create ThinkingFrame

  **What to do**:
  - Create ThinkingFrame in `_run_intake()` before LLM call
  - Set goals: ["Understand change scope and threat surface"]
  - Set checks: ["Do we have changed file list and diff summary?"]
  - Set risks: ["Missing scope causes blind spots"]
  - Create ThinkingStep with kind="transition", why="We need a concrete checklist before delegating, so plan TODOs next.", evidence=[f"changed_files:{len(context.changed_files)}"], next="plan_todos", confidence="high"
  - Add step to frame.steps
  - Set frame.decision after phase completes
  - Call `self._thinking_log.add(frame)`
  - Call `self._phase_logger.log_thinking_frame(frame)`
  - Keep existing LLM thinking extraction and logging (backward compatibility)

  **Must NOT do**:
  - Change _run_intake() signature
  - Remove existing thinking extraction code
  - Modify FSM transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method update with well-defined thinking frame pattern
  - **Skills**: []
    - No specialized skills needed for phase handler update
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 9, 10)
  - **Blocks**: Task 14 (integration tests)
  - **Blocked By**: Tasks 5, 6 (log_thinking_frame and _thinking_log must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:185-220` - _run_intake() method (existing thinking logging pattern)
  - `iron_rook/review/agents/security.py:194-209` - LLM thinking extraction and logging pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame, ThinkingStep types
  - `iron_rook/review/base.py` - ReviewContext type for context

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:127-167` - Phase thinking test patterns

  **Documentation References** (specs and requirements):
  - User-provided example (in context): intake phase ThinkingFrame structure
  - Interview requirement: Preserve existing LLM thinking extraction

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.python.org/3/library/datetime.html` - datetime for timestamps
  - Example: User's example code in context - ThinkingFrame creation pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:185-220`: Shows exact pattern for phase execution, LLM calls, thinking extraction, logging to follow
  - `security.py:194-209`: Demonstrates _extract_thinking_from_response usage and _phase_logger.log_thinking pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: _run_intake() creates ThinkingFrame with correct fields
  - [ ] Test covers: _run_intake() adds ThinkingStep with evidence link
  - [ ] Test covers: _run_intake() calls _thinking_log.add()
  - [ ] Test covers: _run_intake() calls _phase_logger.log_thinking_frame()
  - [ ] Test covers: Existing LLM thinking extraction still works
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestIntakeThinkingFrame::test_run_intake_creates_frame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: _run_intake() creates ThinkingFrame with goals/checks/risks
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log, log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); print('Test 1: _thinking_log exists'); assert hasattr(r, '_thinking_log')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); print('Test 2: Check frame created after _run_intake'); import asyncio; ctx = type('obj', (object,), {'changed_files': ['f1'], 'diff': 'test', 'repo_root': '/repo', 'base_ref': 'main', 'head_ref': 'HEAD'}); asyncio.run(r._run_intake(ctx)); assert len(r._thinking_log.frames) > 0"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); print('Test 3: Check frame state'); import asyncio; ctx = type('obj', (object,), {'changed_files': ['f1'], 'diff': 'test', 'repo_root': '/repo', 'base_ref': 'main', 'head_ref': 'HEAD'}); asyncio.run(r._run_intake(ctx)); assert r._thinking_log.frames[-1].state == 'intake'"
    Expected Result: ThinkingFrame created with state='intake', goals/checks/risks populated
    Evidence: Frame exists in log, state is 'intake', no exceptions
    Failure Indicators: No frame added, wrong state, missing fields

  Scenario: _run_intake() adds ThinkingStep with evidence link
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _run_intake() implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); import asyncio; ctx = type('obj', (object,), {'changed_files': ['f1.py', 'f2.py'], 'diff': 'test diff', 'repo_root': '/repo', 'base_ref': 'main', 'head_ref': 'HEAD'}); asyncio.run(r._run_intake(ctx)); print('Frame created:', len(r._thinking_log.frames) > 0)"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); import asyncio; ctx = type('obj', (object,), {'changed_files': ['f1.py', 'f2.py'], 'diff': 'test diff', 'repo_root': '/repo', 'base_ref': 'main', 'head_ref': 'HEAD'}); asyncio.run(r._run_intake(ctx)); steps = r._thinking_log.frames[-1].steps; assert len(steps) > 0"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); import asyncio; ctx = type('obj', (object,), {'changed_files': ['f1.py', 'f2.py'], 'diff': 'test diff', 'repo_root': '/repo', 'base_ref': 'main', 'head_ref': 'HEAD'}); asyncio.run(r._run_intake(ctx)); step = r._thinking_log.frames[-1].steps[0]; assert 'changed_files' in step.evidence[0]"
    Expected Result: ThinkingStep added with evidence containing 'changed_files'
    Evidence: Step exists, evidence list populated with reference
    Failure Indicators: No step added, evidence missing, wrong format
  \`\`\`

  **Evidence to Capture:**
  - [ ] Frame creation success (no exceptions)
  - [ ] Step evidence content verification

  **Commit**: YES
  - Message: `type(agents): update _run_intake() to create ThinkingFrame`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestIntakeThinkingFrame -xvs`

- [x] 9. Update _run_plan_todos() to create ThinkingFrame

  **What to do**:
  - Create ThinkingFrame in `_run_plan_todos()` before LLM call
  - Set goals: ["Convert scope into targeted security checks (TODOs)"]
  - Set checks: ["Which areas are risky given changed files?"]
  - Set risks: ["Overchecking wastes time; underchecking misses issues"]
  - Create ThinkingStep with kind="transition", why="We now have a checklist; delegate each TODO to a focused subagent.", evidence=[f"todos:{len(todos)}"], next="delegate", confidence="high"
  - Add step to frame.steps
  - Set frame.decision after phase completes
  - Call `self._thinking_log.add(frame)`
  - Call `self._phase_logger.log_thinking_frame(frame)`
  - Keep existing LLM thinking extraction and logging

  **Must NOT do**:
  - Change _run_plan_todos() signature
  - Remove existing thinking extraction code
  - Modify FSM transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method update with well-defined thinking frame pattern
  - **Skills**: []
    - No specialized skills needed for phase handler update
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 10)
  - **Blocks**: Task 14 (integration tests)
  - **Blocked By**: Tasks 5, 6 (log_thinking_frame and _thinking_log must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:221-257` - _run_plan_todos() method (existing pattern)
  - `iron_rook/review/agents/security.py:244-252` - Existing thinking extraction and logging pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame, ThinkingStep types
  - `iron_rook/review/base.py` - ReviewContext type for context

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:207-250` - PlanTodos thinking test patterns

  **Documentation References** (specs and requirements):
  - User-provided example (in context): plan_todos phase ThinkingFrame structure
  - Interview requirement: Preserve existing LLM thinking extraction

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel patterns
  - Example: User's example code in context - ThinkingFrame creation pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:221-257`: Shows exact pattern for phase execution to follow
  - `security.py:244-252`: Demonstrates existing thinking extraction and logging pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: _run_plan_todos() creates ThinkingFrame with correct fields
  - [ ] Test covers: _run_plan_todos() adds ThinkingStep with evidence link
  - [ ] Test covers: _run_plan_todos() calls _thinking_log.add()
  - [ ] Test covers: _run_plan_todos() calls _phase_logger.log_thinking_frame()
  - [ ] Test covers: Existing LLM thinking extraction still works
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestPlanTodosThinkingFrame::test_run_plan_todos_creates_frame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: _run_plan_todos() creates ThinkingFrame with goals/checks/risks
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log, log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['intake'] = {'data': {'risk_hypotheses': ['h1', 'h2']}}; print('Test 1: _run_plan_todos creates frame')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['intake'] = {'data': {'risk_hypotheses': ['h1', 'h2']}}; asyncio.run(r._run_plan_todos(None)); print('Frame created:', len(r._thinking_log.frames) > 1)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['intake'] = {'data': {'risk_hypotheses': ['h1', 'h2']}}; asyncio.run(r._run_plan_todos(None)); assert r._thinking_log.frames[-1].state == 'plan_todos'"
    Expected Result: ThinkingFrame created with state='plan_todos', goals/checks/risks populated
    Evidence: Frame exists in log, state is 'plan_todos', no exceptions
    Failure Indicators: No frame added, wrong state, missing fields

  Scenario: _run_plan_todos() adds ThinkingStep with evidence link
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _run_plan_todos() implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['intake'] = {'data': {'risk_hypotheses': ['h1', 'h2', 'h3']}}; import asyncio; asyncio.run(r._run_plan_todos(None)); print('Step created:', len(r._thinking_log.frames[-1].steps) > 0)"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['intake'] = {'data': {'risk_hypotheses': ['h1', 'h2', 'h3']}}; import asyncio; asyncio.run(r._run_plan_todos(None)); step = r._thinking_log.frames[-1].steps[0]; assert 'todos' in step.evidence[0]"
    Expected Result: ThinkingStep added with evidence containing 'todos'
    Evidence: Step exists, evidence list populated with reference
    Failure Indicators: No step added, evidence missing, wrong format
  \`\`\`

  **Evidence to Capture:**
  - [ ] Frame creation success (no exceptions)
  - [ ] Step evidence content verification

  **Commit**: YES
  - Message: `type(agents): update _run_plan_todos() to create ThinkingFrame`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestPlanTodosThinkingFrame -xvs`

- [x] 10. Update _run_delegate() to create ThinkingFrame

  **What to do**:
  - Create ThinkingFrame in `_run_delegate()` before LLM call
  - Set goals: ["Fan out TODOs to narrow subagents"]
  - Set checks: ["Each TODO gets a scoped result + evidence pointers"]
  - Set risks: ["Subagents drift outside scope or return low-evidence claims"]
  - Create ThinkingStep with kind="delegate", why="Subagents completed scoped checks; collect results for consolidation.", evidence=[f"subagent_results:{len(results)}"], next="collect", confidence="medium"
  - Add step to frame.steps
  - Set frame.decision after phase completes
  - Call `self._thinking_log.add(frame)`
  - Call `self._phase_logger.log_thinking_frame(frame)`
  - Keep existing LLM thinking extraction and logging

  **Must NOT do**:
  - Change _run_delegate() signature
  - Remove existing thinking extraction code
  - Modify FSM transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method update with well-defined thinking frame pattern
  - **Skills**: []
    - No specialized skills needed for phase handler update
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with Tasks 8, 9)
  - **Blocks**: Task 14 (integration tests)
  - **Blocked By**: Tasks 5, 6 (log_thinking_frame and _thinking_log must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:258-291` - _run_delegate() method (existing pattern)
  - `iron_rook/review/agents/security.py:281-286` - Existing thinking extraction and logging pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame, ThinkingStep types
  - `iron_rook/review/base.py` - ReviewContext type for context

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:252-292` - Delegate thinking test patterns

  **Documentation References** (specs and requirements):
  - User-provided example (in context): delegate phase ThinkingFrame structure
  - Interview requirement: Preserve existing LLM thinking extraction

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel patterns
  - Example: User's example code in context - ThinkingFrame creation pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:258-291`: Shows exact pattern for phase execution to follow
  - `security.py:281-286`: Demonstrates existing thinking extraction and logging pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: _run_delegate() creates ThinkingFrame with correct fields
  - [ ] Test covers: _run_delegate() adds ThinkingStep with evidence link
  - [ ] Test covers: _run_delegate() calls _thinking_log.add()
  - [ ] Test covers: _run_delegate() calls _phase_logger.log_thinking_frame()
  - [ ] Test covers: Existing LLM thinking extraction still works
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestDelegateThinkingFrame::test_run_delegate_creates_frame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: _run_delegate() creates ThinkingFrame with goals/checks/risks
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log, log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}, {'id': 't2'}]}}; print('Test 1: _run_delegate creates frame')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}, {'id': 't2'}]}}; asyncio.run(r._run_delegate(None)); print('Frame created:', len(r._thinking_log.frames) > 2)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}, {'id': 't2'}]}}; asyncio.run(r._run_delegate(None)); assert r._thinking_log.frames[-1].state == 'delegate'"
    Expected Result: ThinkingFrame created with state='delegate', goals/checks/risks populated
    Evidence: Frame exists in log, state is 'delegate', no exceptions
    Failure Indicators: No frame added, wrong state, missing fields

  Scenario: _run_delegate() adds ThinkingStep with evidence link
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _run_delegate() implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}, {'id': 't2'}]}}; import asyncio; asyncio.run(r._run_delegate(None)); print('Step created:', len(r._thinking_log.frames[-1].steps) > 0)"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}, {'id': 't2'}]}}; import asyncio; asyncio.run(r._run_delegate(None)); step = r._thinking_log.frames[-1].steps[0]; assert 'subagent_results' in step.evidence[0]"
    Expected Result: ThinkingStep added with evidence containing 'subagent_results'
    Evidence: Step exists, evidence list populated with reference
    Failure Indicators: No step added, evidence missing, wrong format
  \`\`\`

  **Evidence to Capture:**
  - [ ] Frame creation success (no exceptions)
  - [ ] Step evidence content verification

  **Commit**: YES
  - Message: `type(agents): update _run_delegate() to create ThinkingFrame`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestDelegateThinkingFrame -xvs`

- [x] 11. Update _run_collect() to create ThinkingFrame

  **What to do**:
  - Create ThinkingFrame in `_run_collect()` before LLM call
  - Set goals: ["Normalize subagent outputs into a single structure"]
  - Set checks: ["Do we have results for every TODO?"]
  - Set risks: ["Missing results leads to false confidence"]
  - Create ThinkingStep with kind="transition", why="All TODO results present; consolidate into a risk view.", evidence=[f"todos:{len(todos)}, results:{len(results)}"], next="consolidate", confidence="high"
  - Add step to frame.steps
  - Set frame.decision after phase completes
  - Call `self._thinking_log.add(frame)`
  - Call `self._phase_logger.log_thinking_frame(frame)`
  - Keep existing LLM thinking extraction and logging

  **Must NOT do**:
  - Change _run_collect() signature
  - Remove existing thinking extraction code
  - Modify FSM transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method update with well-defined thinking frame pattern
  - **Skills**: []
    - No specialized skills needed for phase handler update
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 12, 13)
  - **Blocks**: Task 14 (integration tests)
  - **Blocked By**: Tasks 5, 6 (log_thinking_frame and _thinking_log must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:292-323` - _run_collect() method (existing pattern)
  - `iron_rook/review/agents/security.py:313-318` - Existing thinking extraction and logging pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame, ThinkingStep types
  - `iron_rook/review/base.py` - ReviewContext type for context

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:294-336` - Collect thinking test patterns

  **Documentation References** (specs and requirements):
  - User-provided example (in context): collect phase ThinkingFrame structure
  - Interview requirement: Preserve existing LLM thinking extraction

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel patterns
  - Example: User's example code in context - ThinkingFrame creation pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:292-323`: Shows exact pattern for phase execution to follow
  - `security.py:313-318`: Demonstrates existing thinking extraction and logging pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: _run_collect() creates ThinkingFrame with correct fields
  - [ ] Test covers: _run_collect() adds ThinkingStep with evidence link
  - [ ] Test covers: _run_collect() calls _thinking_log.add()
  - [ ] Test covers: _run_collect() calls _phase_logger.log_thinking_frame()
  - [ ] Test covers: Existing LLM thinking extraction still works
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestCollectThinkingFrame::test_run_collect_creates_frame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: _run_collect() creates ThinkingFrame with goals/checks/risks
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log, log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['delegate'] = {'data': {'subagent_requests': []}}; print('Test 1: _run_collect creates frame')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['delegate'] = {'data': {'subagent_requests': []}}; asyncio.run(r._run_collect(None)); print('Frame created:', len(r._thinking_log.frames) > 3)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['delegate'] = {'data': {'subagent_requests': []}}; asyncio.run(r._run_collect(None)); assert r._thinking_log.frames[-1].state == 'collect'"
    Expected Result: ThinkingFrame created with state='collect', goals/checks/risks populated
    Evidence: Frame exists in log, state is 'collect', no exceptions
    Failure Indicators: No frame added, wrong state, missing fields

  Scenario: _run_collect() adds ThinkingStep with evidence link
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _run_collect() implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}]}}; r._phase_outputs['delegate'] = {'data': {'subagent_results': {'t1': 'done'}}}; import asyncio; asyncio.run(r._run_collect(None)); print('Step created:', len(r._thinking_log.frames[-1].steps) > 0)"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['plan_todos'] = {'data': {'todos': [{'id': 't1'}]}}; r._phase_outputs['delegate'] = {'data': {'subagent_results': {'t1': 'done'}}}; import asyncio; asyncio.run(r._run_collect(None)); step = r._thinking_log.frames[-1].steps[0]; assert 'todos' in step.evidence[0] or 'results' in step.evidence[0]"
    Expected Result: ThinkingStep added with evidence containing 'todos' or 'results'
    Evidence: Step exists, evidence list populated with reference
    Failure Indicators: No step added, evidence missing, wrong format
  \`\`\`

  **Evidence to Capture:**
  - [ ] Frame creation success (no exceptions)
  - [ ] Step evidence content verification

  **Commit**: YES
  - Message: `type(agents): update _run_collect() to create ThinkingFrame`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestCollectThinkingFrame -xvs`

- [x] 12. Update _run_consolidate() to create ThinkingFrame

  **What to do**:
  - Create ThinkingFrame in `_run_consolidate()` before LLM call
  - Set goals: ["Merge findings into a single risk assessment"]
  - Set checks: ["Are there any high-risk signals? any evidence?"]
  - Set risks: ["Conflicting subagent results; weak evidence"]
  - Create ThinkingStep with kind="transition", why="We have a consolidated view; evaluate against merge gates.", evidence=["consolidated:1"], next="evaluate", confidence="high"
  - Add step to frame.steps
  - Set frame.decision after phase completes
  - Call `self._thinking_log.add(frame)`
  - Call `self._phase_logger.log_thinking_frame(frame)`
  - Keep existing LLM thinking extraction and logging

  **Must NOT do**:
  - Change _run_consolidate() signature
  - Remove existing thinking extraction code
  - Modify FSM transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method update with well-defined thinking frame pattern
  - **Skills**: []
    - No specialized skills needed for phase handler update
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 11, 13)
  - **Blocks**: Task 14 (integration tests)
  - **Blocked By**: Tasks 5, 6 (log_thinking_frame and _thinking_log must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:324-359` - _run_consolidate() method (existing pattern)
  - `iron_rook/review/agents/security.py:345-350` - Existing thinking extraction and logging pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame, ThinkingStep types
  - `iron_rook/review/base.py` - ReviewContext type for context

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:338-380` - Consolidate thinking test patterns

  **Documentation References** (specs and requirements):
  - User-provided example (in context): consolidate phase ThinkingFrame structure
  - Interview requirement: Preserve existing LLM thinking extraction

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel patterns
  - Example: User's example code in context - ThinkingFrame creation pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:324-359`: Shows exact pattern for phase execution to follow
  - `security.py:345-350`: Demonstrates existing thinking extraction and logging pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: _run_consolidate() creates ThinkingFrame with correct fields
  - [ ] Test covers: _run_consolidate() adds ThinkingStep with evidence link
  - [ ] Test covers: _run_consolidate() calls _thinking_log.add()
  - [ ] Test covers: _run_consolidate() calls _phase_logger.log_thinking_frame()
  - [ ] Test covers: Existing LLM thinking extraction still works
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestConsolidateThinkingFrame::test_run_consolidate_creates_frame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: _run_consolidate() creates ThinkingFrame with goals/checks/risks
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log, log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['collect'] = {'data': {'todo_status': []}}; print('Test 1: _run_consolidate creates frame')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['collect'] = {'data': {'todo_status': []}}; asyncio.run(r._run_consolidate(None)); print('Frame created:', len(r._thinking_log.frames) > 4)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['collect'] = {'data': {'todo_status': []}}; asyncio.run(r._run_consolidate(None)); assert r._thinking_log.frames[-1].state == 'consolidate'"
    Expected Result: ThinkingFrame created with state='consolidate', goals/checks/risks populated
    Evidence: Frame exists in log, state is 'consolidate', no exceptions
    Failure Indicators: No frame added, wrong state, missing fields

  Scenario: _run_consolidate() adds ThinkingStep with evidence link
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _run_consolidate() implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['collect'] = {'data': {'todo_status': []}}; import asyncio; asyncio.run(r._run_consolidate(None)); print('Step created:', len(r._thinking_log.frames[-1].steps) > 0)"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['collect'] = {'data': {'todo_status': []}}; import asyncio; asyncio.run(r._run_consolidate(None)); step = r._thinking_log.frames[-1].steps[0]; assert 'consolidated' in step.evidence[0]"
    Expected Result: ThinkingStep added with evidence containing 'consolidated'
    Evidence: Step exists, evidence list populated with reference
    Failure Indicators: No step added, evidence missing, wrong format
  \`\`\`

  **Evidence to Capture:**
  - [ ] Frame creation success (no exceptions)
  - [ ] Step evidence content verification

  **Commit**: YES
  - Message: `type(agents): update _run_consolidate() to create ThinkingFrame`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestConsolidateThinkingFrame -xvs`

- [x] 13. Update _run_evaluate() to create ThinkingFrame

  **What to do**:
  - Create ThinkingFrame in `_run_evaluate()` before LLM call
  - Set goals: ["Make final decision: safe to merge?"]
  - Set checks: ["Any secrets? auth regressions? injection? missing evidence?"]
  - Set risks: ["Passing with unknowns"]
  - Create ThinkingStep with kind="stop", why="All gates satisfied for this run; finalize.", evidence=["evaluation:approve"], next="done", confidence="medium"
  - Add step to frame.steps
  - Set frame.decision after phase completes
  - Call `self._thinking_log.add(frame)`
  - Call `self._phase_logger.log_thinking_frame(frame)`
  - Keep existing LLM thinking extraction and logging

  **Must NOT do**:
  - Change _run_evaluate() signature
  - Remove existing thinking extraction code
  - Modify FSM transitions

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `quick`
    - Reason: Single method update with well-defined thinking frame pattern
  - **Skills**: []
    - No specialized skills needed for phase handler update
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 11, 12)
  - **Blocks**: Task 14 (integration tests)
  - **Blocked By**: Tasks 5, 6 (log_thinking_frame and _thinking_log must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `iron_rook/review/agents/security.py:360-393` - _run_evaluate() method (existing pattern)
  - `iron_rook/review/agents/security.py:381-386` - Existing thinking extraction and logging pattern

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/contracts.py` - Import ThinkingFrame, ThinkingStep types
  - `iron_rook/review/base.py` - ReviewContext type for context

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py:382-423` - Evaluate thinking test patterns

  **Documentation References** (specs and requirements):
  - User-provided example (in context): evaluate phase ThinkingFrame structure
  - Interview requirement: Preserve existing LLM thinking extraction

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pydantic.dev/latest/concepts/models/` - Pydantic BaseModel patterns
  - Example: User's example code in context - ThinkingFrame creation pattern

  **WHY Each Reference Matters** (explain the relevance):
  - `security.py:360-393`: Shows exact pattern for phase execution to follow
  - `security.py:381-386`: Demonstrates existing thinking extraction and logging pattern

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: _run_evaluate() creates ThinkingFrame with correct fields
  - [ ] Test covers: _run_evaluate() adds ThinkingStep with evidence link
  - [ ] Test covers: _run_evaluate() calls _thinking_log.add()
  - [ ] Test covers: _run_evaluate() calls _phase_logger.log_thinking_frame()
  - [ ] Test covers: Existing LLM thinking extraction still works
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestEvaluateThinkingFrame::test_run_evaluate_creates_frame -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: _run_evaluate() creates ThinkingFrame with goals/checks/risks
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _thinking_log, log_thinking_frame implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['consolidate'] = {'data': {}}; print('Test 1: _run_evaluate creates frame')"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['consolidate'] = {'data': {}}; asyncio.run(r._run_evaluate(None)); print('Frame created:', len(r._thinking_log.frames) > 5)"
      3. python -c "from iron_rook.review.agents.security import SecurityReviewer; import asyncio; r = SecurityReviewer(); r._phase_outputs['consolidate'] = {'data': {}}; asyncio.run(r._run_evaluate(None)); assert r._thinking_log.frames[-1].state == 'evaluate'"
    Expected Result: ThinkingFrame created with state='evaluate', goals/checks/risks populated
    Evidence: Frame exists in log, state is 'evaluate', no exceptions
    Failure Indicators: No frame added, wrong state, missing fields

  Scenario: _run_evaluate() adds ThinkingStep with kind='stop'
    Tool: Bash (python REPL)
    Preconditions: SecurityReviewer with _run_evaluate() implemented
    Steps:
      1. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['consolidate'] = {'data': {}}; import asyncio; asyncio.run(r._run_evaluate(None)); print('Step created:', len(r._thinking_log.frames[-1].steps) > 0)"
      2. python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); r._phase_outputs['consolidate'] = {'data': {}}; import asyncio; asyncio.run(r._run_evaluate(None)); step = r._thinking_log.frames[-1].steps[0]; assert step.kind == 'stop'"
    Expected Result: ThinkingStep added with kind='stop' and next='done'
    Evidence: Step exists, kind is 'stop', next is 'done'
    Failure Indicators: No step added, wrong kind, wrong next
  \`\`\`

  **Evidence to Capture:**
  - [ ] Frame creation success (no exceptions)
  - [ ] Step content verification (kind='stop', next='done')

  **Commit**: YES
  - Message: `type(agents): update _run_evaluate() to create ThinkingFrame`
  - Files: `iron_rook/review/agents/security.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestEvaluateThinkingFrame -xvs`

- [x] 14. Integration tests for full workflow

  **What to do**:
  - Add integration tests to `tests/unit/review/agents/test_security_thinking.py`
  - Test full workflow: create SecurityReviewer → run phases → verify ThinkingFrames in log
  - Verify all 6 phases create frames correctly
  - Verify backward compatibility: existing thinking extraction still works
  - Verify SecurityPhaseLogger.log_thinking_frame() called correctly
  - Follow existing test patterns

  **Must NOT do**:
  - Create new test file (add to existing test_security_thinking.py)
  - Modify existing test methods (only add new test classes/functions)

  **Recommended Agent Profile**:
  > Select category + skills based on task domain. Justify each choice.
  - **Category**: `unspecified-low`
    - Reason: Full workflow integration test, requires multiple components working together
  - **Skills**: []
    - No specialized skills needed for integration tests
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser interaction needed
    - `frontend-ui-ux`: No UI components

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Sequential (depends on all phase handlers)
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 8, 9, 10, 11, 12, 13 (all phase handlers must exist first)

  **References** (CRITICAL - Be Exhaustive):

  > The executor has NO context from your interview. References are their ONLY guide.
  > Each reference must answer: "What should I look at and WHY?"

  **Pattern References** (existing code to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Existing integration test patterns
  - `tests/integration/test_security_fsm_integration.py` - Integration test examples

  **API/Type References** (contracts to implement against):
  - `iron_rook/review/agents/security.py` - SecurityReviewer class
  - `iron_rook/review/contracts.py` - ThinkingFrame, ThinkingStep, RunLog models

  **Test References** (testing patterns to follow):
  - `tests/unit/review/agents/test_security_thinking.py` - Existing test structure and patterns

  **Documentation References** (specs and requirements):
  - Interview requirements: Backward compatibility, all phases create frames

  **External References** (libraries and frameworks):
  - Official docs: `https://docs.pytest.org/en/stable/how-to/assert.html` - pytest assertion patterns
  - Example: `tests/integration/test_security_fsm_integration.py` - Integration test examples

  **WHY Each Reference Matters** (explain the relevance):
  - `test_security_fsm_integration.py`: Shows full workflow integration test patterns to follow

  **Acceptance Criteria**:

  > **AGENT-EXECUTABLE VERIFICATION ONLY** — No human action permitted.
  > Every criterion MUST be verifiable by running a command or using a tool.

  **TDD (tests enabled):**
  - [ ] Test file: tests/unit/review/agents/test_security_thinking.py
  - [ ] Test covers: Full workflow creates frames for all 6 phases
  - [ ] Test covers: Backward compatibility verified (existing tests still pass)
  - [ ] Test covers: SecurityPhaseLogger called correctly for all frames
  - [ ] pytest tests/unit/review/agents/test_security_thinking.py::TestIntegrationWorkflow -xvs → PASS

  **Agent-Executed QA Scenarios (MANDATORY — per-scenario, ultra-detailed):**

  \`\`\`
  Scenario: Full workflow creates ThinkingFrames for all phases
    Tool: Bash (pytest)
    Preconditions: All phase handlers implemented
    Steps:
      1. pytest tests/unit/review/agents/test_security_thinking.py::TestIntegrationWorkflow::test_full_workflow_creates_frames -xvs
      2. pytest tests/unit/review/agents/test_security_thinking.py::TestIntegrationWorkflow::test_backward_compatibility -xvs
      3. pytest tests/unit/review/agents/test_security_thinking.py::TestIntegrationWorkflow::test_all_phases_logged -xvs
    Expected Result: All integration tests pass
    Evidence: Test output shows all tests passed
    Failure Indicators: Any test FAIL, pytest exit code non-zero

  Scenario: Backward compatibility verified (existing tests still pass)
    Tool: Bash (pytest)
    Preconditions: All phase handlers implemented
    Steps:
      1. pytest tests/unit/review/agents/test_security_thinking.py::TestExtractThinkingFromResponse -xvs
      2. pytest tests/unit/review/agents/test_security_thinking.py::TestIntakePhaseThinking -xvs
      3. pytest tests/unit/review/agents/test_security_thinking.py::TestPlanTodosPhaseThinking -xvs
    Expected Result: All existing thinking extraction tests still pass
    Evidence: Test output shows existing tests passed
    Failure Indicators: Any existing test FAIL, backward compatibility broken
  \`\`\`

  **Evidence to Capture:**
  - [ ] Test run output (pytest summary)
  - [ ] Individual test results (passed/failed counts)
  - [ ] Backward compatibility verification output

  **Commit**: YES
  - Message: `test(agents): add integration tests for full workflow`
  - Files: `tests/unit/review/agents/test_security_thinking.py`
  - Pre-commit: `pytest tests/unit/review/agents/test_security_thinking.py::TestIntegrationWorkflow -xvs`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `type(contracts): add ThinkingStep Pydantic model` | `iron_rook/review/contracts.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels -xvs` |
| 2 | `type(contracts): add ThinkingFrame Pydantic model` | `iron_rook/review/contracts.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels -xvs` |
| 3 | `type(contracts): add RunLog Pydantic model` | `iron_rook/review/contracts.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels -xvs` |
| 4 | `test(agents): add tests for thinking models` | `tests/unit/review/agents/test_security_thinking.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestThinkingModels -xvs` |
| 5 | `type(logger): add log_thinking_frame() method to SecurityPhaseLogger` | `iron_rook/review/security_phase_logger.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame -xvs` |
| 6 | `test(agents): add tests for SecurityPhaseLogger.log_thinking_frame()` | `tests/unit/review/agents/test_security_thinking.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestPhaseLoggerFrame -xvs` |
| 7 | `type(agents): add _thinking_log accumulator to SecurityReviewer` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestSecurityReviewerThinkingLog -xvs` |
| 8 | `type(agents): update _run_intake() to create ThinkingFrame` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestIntakeThinkingFrame -xvs` |
| 9 | `type(agents): update _run_plan_todos() to create ThinkingFrame` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestPlanTodosThinkingFrame -xvs` |
| 10 | `type(agents): update _run_delegate() to create ThinkingFrame` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestDelegateThinkingFrame -xvs` |
| 11 | `type(agents): update _run_collect() to create ThinkingFrame` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestCollectThinkingFrame -xvs` |
| 12 | `type(agents): update _run_consolidate() to create ThinkingFrame` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestConsolidateThinkingFrame -xvs` |
| 13 | `type(agents): update _run_evaluate() to create ThinkingFrame` | `iron_rook/review/agents/security.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestEvaluateThinkingFrame -xvs` |
| 14 | `test(agents): add integration tests for full workflow` | `tests/unit/review/agents/test_security_thinking.py` | `pytest tests/unit/review/agents/test_security_thinking.py::TestIntegrationWorkflow -xvs` |

---

## Success Criteria

### Verification Commands
```bash
# Run all new tests
pytest tests/unit/review/agents/test_security_thinking.py -xvs

# Verify backward compatibility (existing tests still pass)
pytest tests/unit/review/agents/test_security_thinking.py::TestExtractThinkingFromResponse -xvs
pytest tests/unit/review/agents/test_security_thinking.py::TestIntakePhaseThinking -xvs
pytest tests/unit/review/agents/test_security_thinking.py::TestPlanTodosPhaseThinking -xvs
pytest tests/unit/review/agents/test_security_thinking.py::TestDelegatePhaseThinking -xvs
pytest tests/unit/review/agents/test_security_thinking.py::TestCollectPhaseThinking -xvs
pytest tests/unit/review/agents/test_security_thinking.py::TestConsolidatePhaseThinking -xvs
pytest tests/unit/review/agents/test_security_thinking.py::TestEvaluatePhaseThinking -xvs

# Verify models can be imported
python -c "from iron_rook.review.contracts import ThinkingStep, ThinkingFrame, RunLog; print('Models imported successfully')"

# Verify SecurityPhaseLogger has log_thinking_frame
python -c "from iron_rook.review.security_phase_logger import SecurityPhaseLogger; logger = SecurityPhaseLogger(); assert hasattr(logger, 'log_thinking_frame')"

# Verify SecurityReviewer has _thinking_log
python -c "from iron_rook.review.agents.security import SecurityReviewer; r = SecurityReviewer(); assert hasattr(r, '_thinking_log'); assert len(r._thinking_log.frames) == 0"
```

### Final Checklist
- [ ] All 3 Pydantic models created (ThinkingStep, ThinkingFrame, RunLog)
- [ ] All 3 models follow existing Pydantic patterns (BaseModel, ConfigDict, Field)
- [ ] SecurityPhaseLogger.log_thinking_frame() method added
- [ ] SecurityReviewer._thinking_log accumulator added (internal only)
- [ ] All 6 phase handlers updated to create ThinkingFrames
- [ ] All tests pass (100% pass rate)
- [ ] Backward compatibility verified (existing tests unchanged and passing)
- [ ] Code follows existing patterns exactly
- [ ] No public API changes (SecurityReviewer API unchanged)
- [ ] RunLog NOT exposed in public API
- [ ] Must NOT Have items excluded (no UI, no export, no analytics)
- [ ] Scope locked down (all tasks completed, no extras)
