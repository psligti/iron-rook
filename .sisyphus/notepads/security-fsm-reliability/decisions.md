# Security FSM Reliability Decisions

## 2026-02-10

### Decision 1: Explicit Error for Missing Phase Prompts

**Context**: The parser was silently returning empty strings when phase sections were missing.

**Decision**: Add explicit `MissingPhasePromptError` exception that:
- Checks if phase section marker exists in prompt file
- Checks if phase section content is non-empty
- Provides descriptive error messages explaining expected format

**Rationale**:
- Silent failures lead to unpredictable LLM behavior (no phase-specific instructions)
- Explicit errors make debugging easier
- Contract violation should fail fast rather than produce incorrect results

### Decision 2: Standardize Phase Header Format

**Context**: PLAN_TODOS and DELEGATE sections had leading spaces before `###`.

**Decision**: Standardize all phase headers to `### {PHASE}` format (no leading space).

**Rationale**:
- Parser uses `line.strip()` for matching, so leading spaces technically worked
- Inconsistent format increases maintenance burden
- Makes contract between prompt file and parser more explicit
- Reduces chance of future bugs if parser changes

**Not Done**:
- Did NOT change semantic content of phase prompts (only formatting)
- Did NOT change phase sequence or FSM semantics
- Did NOT modify schema contracts in contracts.py

### Decision 3: Phase Prompt Extraction Logic

**Context**: Parser extracts phase-specific prompts for each FSM phase execution.

**Decision**: Keep existing extraction logic but add validation:
- Line-by-line scan for section start/end markers
- Track `in_section` state
- Collect lines between markers
- Validate section exists before returning
- Validate section is non-empty before returning

**Rationale**:
- Simple, reliable parsing approach
- Explicit validation prevents silent failures
- Maintains backward compatibility with properly formatted prompts

### Decision 4: Test Coverage Strategy

**Context**: Need to verify missing phase section handling and JSON envelope compliance.

**Decision**: Add tests that:
1. Test `MissingPhasePromptError` is raised for missing phase sections
2. Test `MissingPhasePromptError` is raised for empty phase sections
3. Test error messages are descriptive and include expected format
4. Test valid phase prompts are loaded correctly
5. (Future) Test JSON envelope compliance in integration tests

**Rationale**:
- Explicit error handling needs corresponding tests
- Error messages should be actionable
- Valid path should continue to work correctly

## Task 2 Decision Summary

### Decision 1: Explicit Error vs Silent Empty Prompt

**Context**: `_load_phase_prompt()` returned empty strings for missing/empty phase sections, leading to unpredictable LLM behavior.

**Decision**: Raise `MissingPhasePromptError` with:
- Check if phase section marker exists before extraction
- Check if extracted prompt is non-empty after extraction
- Descriptive error messages including expected format

**Rationale**:
- Silent failures lead to incorrect LLM outputs
- Explicit errors enable fast debugging
- Clear error messages help fix prompt files quickly

### Decision 2: Consistent Phase Header Formatting

**Context**: PLAN_TODOS and DELEGATE had leading spaces before `###`.

**Decision**: Standardize all phase headers to `### {PHASE}` format (no leading space).

**Rationale**:
- Parser uses `line.strip()` so spaces technically worked
- Inconsistent format increases maintenance burden
- Clear contract between prompt file and parser

### Decision 3: Test Coverage Strategy

**Context**: Need to verify missing phase section handling and JSON envelope compliance.

**Decision**: Add two test classes:
- `TestPhasePromptLoading`: Tests for _load_phase_prompt() robustness
- `TestJSONEnvelopeCompliance`: Tests for PhaseOutput schema enforcement

**Rationale**:
- Explicit error handling needs corresponding tests
- Error messages should be actionable and tested
- Valid paths should continue to work
