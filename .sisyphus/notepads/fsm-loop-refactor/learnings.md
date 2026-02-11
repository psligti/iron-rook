# Learnings - FSM Loop Refactor

## Task: Implement sub-loop logic (PLAN → ACT → SYNTHESIZE)

### Implementation Summary

Added `run_loop(context)` method to LoopFSM class that orchestrates the PLAN → ACT → SYNTHESIZE cycle with proper state transitions and iteration management.

### Key Components

1. **MAX_ITERATIONS Class Constant** (default=10)
   - Added to `LoopFSM` class as a class variable
   - Prevents infinite loops by throwing RuntimeError when exceeded
   - Located at line 54 in `loop_fsm.py`

2. **check_goal_achievement() Placeholder Method**
   - Added placeholder method to be implemented in Task 6
   - Currently raises NotImplementedError
   - Will be used to determine if loop should continue or transition to DONE

3. **run_loop(context) Method**
   - Main loop orchestration method
   - Takes context dict as input, stores across iterations
   - Implements PLAN → ACT → SYNTHESIZE cycle
   - Increments iteration_count on each full cycle
   - Throws RuntimeError if iteration_count > MAX_ITERATIONS
   - After SYNTHESIZE: currently always transitions to DONE (Task 6 will add goal checking)

### State Transition Pattern

```
INTAKE → PLAN
PLAN → ACT → SYNTHESIZE → DONE (or PLAN for next iteration)
```

### Result Type Handling

Learned proper pattern for handling `Result` type from dawn_kestrel:
```python
result = self.transition_to(target_state)
if result.is_err():
    err: Err[LoopState] = result  # type: ignore[assignment]
    raise RuntimeError(f"Failed to transition: {err.error}")
```

This pattern matches the usage in `BaseReviewerAgent._transition_to()` method.

### Context Storage

Added `_context` attribute to store context data across loop iterations:
- Initialized in `__init__()` as empty dict
- Stored in `run_loop()` from input parameter
- Exposed via read-only `context` property
- Cleared in `reset()` method

### Next Steps (Future Tasks)

- Task 6: Implement actual `check_goal_achievement()` logic
- Task 7: Add tool execution and retry logic
- Add phase-specific behavior for PLAN, ACT, SYNTHESIZE states

## 2026-02-10: Fixed State Transition Error in BaseReviewerAgent

**Problem:**
- The `_execute_review_with_runner()` method had an invalid state transition sequence
- Original code: `INITIALIZING` -> `READY` -> `RUNNING`
- This maps to LoopFSM: `PLAN` -> `SYNTHESIZE` -> `ACT`
- LoopFSM only allows: `PLAN` -> `ACT`, not `PLAN` -> `SYNTHESIZE`
- Additionally, after execution, code tried `RUNNING` -> `COMPLETED` which maps to `ACT` -> `DONE`
- LoopFSM only allowed `ACT` -> `SYNTHESIZE`, not `ACT` -> `DONE` directly

**Solution:**
1. Updated state transition sequence in `iron_rook/review/base.py` (lines 411-414):
   - Changed comment from "IDLE -> INITIALIZING -> READY -> RUNNING" to "IDLE -> INITIALIZING -> RUNNING -> COMPLETED"
   - Removed invalid `READY` (SYNTHESIZE) transition
   - Kept only `INITIALIZING` -> `RUNNING` transitions

2. Updated LoopFSM transition map in `iron_rook/fsm/loop_fsm.py`:
   - Added `LoopState.DONE` to `LoopState.ACT` transitions
   - Now ACT can go to either `SYNTHESIZE` (for looping) or `DONE` (for single-pass)
   - This allows single-pass reviews (like security) to skip the SYNTHESIZE phase

**Files Modified:**
- `iron_rook/review/base.py`: Updated transition sequence and comment
- `iron_rook/fsm/loop_fsm.py`: Added ACT -> DONE transition option

**Verification:**
- Command `uv run iron-rook --agent security --output json -v` runs without state transition errors
- No more "Invalid transition: act -> done" errors
