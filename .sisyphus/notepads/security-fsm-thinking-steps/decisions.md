# Decisions - security-fsm-thinking-steps

## 2026-02-11T21:35:12Z - Initial Session

### Model Location
- Decision: Add ThinkingStep, ThinkingFrame, RunLog models to `iron_rook/review/contracts.py`
- Reasoning: User confirmed this location, consistent with other Pydantic models in the file
- Follows existing patterns in contracts.py (Scope, Check, Finding, MergeGate, etc.)

### Backward Compatibility
- Decision: Preserve existing `_extract_thinking_from_response()` functionality
- Reasoning: User confirmed - keep both raw string AND structured steps
- New structured models complement, don't replace, existing thinking extraction

### RunLog Scope
- Decision: RunLog is internal-only, NOT exposed in public API
- Reasoning: User confirmed - internal accumulator only, not in ReviewOutput
- Stored as `_thinking_log` in SecurityReviewer (private field)

### Logger Extension
- Decision: Add `log_thinking_frame()` method to SecurityPhaseLogger
- Reasoning: Integrate with existing logging infrastructure for consistent colored display
- Don't modify existing `log_thinking()` or `log_transition()` methods

### Test Strategy
- Decision: Use TDD (RED-GREEN-REFACTOR) pattern
- Reasoning: User confirmed TDD approach for this feature
- Tests first (RED), then implementation (GREEN), then refactor if needed

### Timestamp Format
- Decision: Use ISO 8601 format with 'Z' suffix for ThinkingFrame.ts
- Reasoning: Standard datetime format, matches existing patterns
- Example: `2026-02-11T21:35:12.922Z`

## 2026-02-11T21:36:59Z - Task 3 Complete: RunLog Model

### Status
- Task 3 (Add RunLog Pydantic model) completed successfully
- Model already existed in commit ebb68ba (added with ThinkingStep and ThinkingFrame)
- No new commit needed - model already committed

### RunLog Implementation
- Location: `iron_rook/review/contracts.py` (lines 128-151)
- Fields: `frames: List[ThinkingFrame]` with `default_factory=list`
- Method: `add(frame: ThinkingFrame) -> None` appends to `self.frames`
- Configuration: `model_config = pd.ConfigDict(extra="ignore")`
- Docstrings: Class docstring and method docstring (public API documentation)

### Verification
All QA scenarios passed:
1. ✓ RunLog creates with empty frames list (`len(log.frames) == 0`)
2. ✓ RunLog.add() appends frames correctly
3. ✓ RunLog.add() handles multiple frames
4. ✓ RunLog.frames is a list type
5. ✓ RunLog.frames defaults to empty list

### Design Compliance
- ✓ Follows existing patterns in contracts.py (Scope, Check classes)
- ✓ Uses `pd.BaseModel` as base class
- ✓ Uses `pd.Field(default_factory=list)` for list field
- ✓ Has no persistence methods (save/load) - internal accumulator only
- ✓ Does not modify existing models
- ✓ Imports ThinkingFrame for type annotation (no forward reference needed since defined in same file)
