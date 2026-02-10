# Security FSM Reliability Learnings

## 2026-02-10

### Phase Prompt Parser Robustness

**Issue**: The `_load_phase_prompt()` method in `fsm_security_orchestrator.py` silently returned empty strings when a phase section was missing or empty.

**Fix Applied**:
- Added `MissingPhasePromptError` exception class
- Modified `_load_phase_prompt()` to explicitly check if section exists and is non-empty
- Raises descriptive error messages when phase sections are missing or empty

**Parser Expectations**:
- Section start marker: `### {PHASE_NAME}` (uppercase, no leading space)
- Section end marker: `---`
- Example: `### INTAKE` ... `---`

**Phase Sections Verified** (all 6 phases):
- INTAKE (line 43)
- PLAN_TODOS (line 73)
- DELEGATE (line 138)
- COLLECT (line 197)
- CONSOLIDATE (line 238)
- EVALUATE (line 274)

### Phase Prompt Format Consistency

**Issue Found**: PLAN_TODOS and DELEGATE sections had leading spaces before `###`, creating inconsistency.

**Fix Applied**: Removed leading spaces from lines 73 and 138 to match parser expectation of `### {PHASE}` format (no leading space).

**Why This Matters**:
- Parser uses `line.strip() == section_start` for matching, so leading spaces technically worked but created inconsistency
- Consistent formatting improves maintainability and reduces chance of future parsing bugs
- Makes the contract between prompt file and parser explicit

### JSON Envelope Contract

**Phase Output Schema** (from PhaseOutput contracts.py):
```json
{
  "phase": "intake" | "plan_todos" | "delegate" | "collect" | "consolidate" | "evaluate",
  "data": {
    // ALL phase-specific fields go here
  },
  "next_phase_request": "plan_todos" | "delegate" | "collect" | "consolidate" | "evaluate" | "done" | "stopped_budget" | "stopped_human"
}
```

**Critical Rules**:
- Only 6 valid `phase` values
- Only 7 valid `next_phase_request` values
- ALL fields except `phase` and `next_phase_request` MUST be inside `data` object
- Schema enforces `extra="forbid"` - extra fields will cause validation errors

# Learnings from Task 1: Build RED baseline for handoff/continuation regressions

## Test Harness Defects Fixed

1. Type hint mismatch: `TestFSMOrchestrator` was referenced but class name was `TestSecurityReviewOrchestrator`
2. Fixture invocation error: `sample_pr_input()` was called as function but it's a fixture (no function call needed)
3. Mock session manager not async: `mock_session_manager.get_session` was not async, but orchestrator expects async call
4. Missing required field in mock: `MockAgentResponse.content` was missing `data` field required by `PhaseOutput` schema
5. Non-existent prompt file: Tests used `prompt_path="test_prompt.md"` but file doesn't exist. Changed to `prompt_path=None` to use default.

## RED Tests Added

1. `test_invalid_transition_request_fails_deterministically`
   - Tests that invalid phase transitions fail deterministically with explicit error
   - Uses monkey-patching of `LLMClient.complete` to simulate invalid transitions

2. `test_missing_required_phase_fields_do_not_silently_continue`
   - Tests that missing required phase fields fail explicitly instead of silent continuation
   - Uses monkey-patching to simulate missing `phase` field

3. `test_malformed_json_returns_partial_report_or_explicit_error`
   - Tests that malformed JSON returns partial report or explicit error path
   - Uses monkey-patching to simulate JSON parse error

4. `test_non_continuation_paths_terminate_with_explicit_stop_reason`
   - Tests that non-continuation/stall paths terminate with explicit stop reason
   - Uses monkey-patching to simulate `next_phase_request: "stopped_budget"`

5. `test_transition_validation_actually_enforces_fsm_transitions`
   - Tests that `_validate_phase_transition` actually enforces FSM_TRANSITIONS
   - Direct call to validator with invalid transition

## Orchestrator Bugs Discovered

1. **Missing pydantic import**: The orchestrator uses `pd.ValidationError` but doesn't import `pydantic as pd`. This causes `NameError` when trying to catch validation errors.

2. **AgentRuntime path not implemented**: The orchestrator accepts `agent_runtime` parameter but only has the direct LLM path (`if self.agent_runtime is None`). There's no `else` branch that uses `agent_runtime.execute_agent()`.

3. **Transition validation not enforced**: The `_validate_phase_transition` method exists and is defined correctly, but the orchestrator doesn't call it during phase transitions. Invalid transitions may be silently accepted.

## Patterns That Work

- Using monkey-patching of `LLMClient.complete` to simulate different LLM responses is effective for testing edge cases
- Using `agent_runtime=None` forces the orchestrator to use the direct LLM path, which makes mocking easier
- Async mock functions for `session_manager.get_session` work correctly with pytest-asyncio

## Patterns That Don't Work

- Trying to mock `agent_runtime.execute_agent` when the orchestrator doesn't actually call that method
- Passing `mock_agent_runtime` to orchestrator when the AgentRuntime path isn't implemented


### Task 2: Align prompt-phase contract and parser robustness

**Files Modified**:
- iron_rook/review/fsm_security_orchestrator.py: Added `MissingPhasePromptError` exception class and hardened `_load_phase_prompt()` with explicit error handling
- iron_rook/review/security_review_agent.md: Fixed phase section header formatting (removed leading spaces from PLAN_TODOS and DELEGATE)
- tests/test_fsm_orchestrator.py: Added `TestPhasePromptLoading` and `TestJSONEnvelopeCompliance` test classes
- tests/test_phase_prompt_envelope.py: Created standalone test file (6 tests pass)

**Error Handling Improvements**:
- `_load_phase_prompt()` now checks if phase section marker exists before attempting extraction
- Raises `MissingPhasePromptError` with descriptive messages including expected format
- Error messages explain: what phase was expected, that it wasn't found, and the expected format (e.g., `### INTAKE`)
- Prevents silent empty prompt usage that would lead to unpredictable LLM behavior

**Phase Section Contract**:
- All phase headers now use consistent format: `### {PHASE_NAME}` (uppercase, no leading space)
- Section delimiters: `---`
- Verified all 6 phases: INTAKE, PLAN_TODOS, DELEGATE, COLLECT, CONSOLIDATE, EVALUATE

**Test Coverage Added**:
- `test_load_phase_prompt_valid_phase`: Tests loading valid phase prompts returns expected content
- `test_load_phase_prompt_missing_phase_raises_error`: Tests missing phase raises descriptive error
- `test_load_phase_prompt_all_phases_from_security_review_agent`: Tests all 6 phases can be loaded from security_review_agent.md
- `test_phase_output_extra_fields_forbidden`: Tests PhaseOutput schema rejects extra fields at top level (extra="forbid")
- `test_phase_output_valid_intake_output`: Tests valid INTAKE phase output passes validation
- `test_phase_output_valid_evaluate_output`: Tests valid EVALUATE phase output passes validation

**Tests Results**:
- All 6 tests in test_phase_prompt_envelope.py pass
- All 3 tests in test_fsm_orchestrator.py::TestPhasePromptLoading pass
- All 3 tests in test_fsm_orchestrator.py::TestJSONEnvelopeCompliance pass

**What Was NOT Changed** (per task requirements):
- Did NOT alter semantic content of phase prompts (only formatting)
- Did NOT change phase sequence or FSM semantics
- Did NOT modify schema contracts in contracts.py (PhaseOutput, FSMState, SecurityReviewReport preserved)

**PhaseOutput Schema Notes**:
- `data` field has `default_factory=dict`, so it won't fail validation when missing
- `next_phase_request` has `default=None`, so it won't fail validation when missing
- `extra="forbid"` is enforced, so extra fields at top level fail validation
