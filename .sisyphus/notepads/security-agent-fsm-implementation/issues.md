# Bug Fix - COLLECT Phase Prompt

## Issue
The security FSM was failing with error:
```
ERROR: Phase collect failed: Invalid transition: collect -> execute. Valid transitions: ['consolidate']
```

## Root Cause
The LLM was returning `"next_phase_request": "execute"` instead of `"consolidate"` in the COLLECT phase response, causing an invalid transition attempt.

## Analysis
- The COLLECT phase prompt had the correct example showing `"next_phase_request": "consolidate"`
- However, the LLM was hallucinating and returning "execute" instead
- The word "execute" appears only in the method name `_execute_llm`, which might have influenced the LLM

## Fix
Added explicit instructions to the COLLECT phase prompt:
- Added "CRITICAL" section emphasizing that the next phase MUST be "consolidate"
- Added "REMEMBER" section reinforcing that "consolidate" is the only valid transition from COLLECT
- This should prevent the LLM from hallucinating "execute" as the next phase

## Files Changed
- `iron_rook/review/agents/security.py` - Updated COLLECT phase prompt (lines 483-506)

## Testing
Run the security agent again to verify the fix:
```bash
iron-rook --agent security --output json -v
```

## Notes
- The FSM transitions are correct: collect → consolidate → evaluate → done
- The prompt was technically correct but needed stronger emphasis to prevent LLM hallucination
- Consider adding more examples or negative examples in future if this persists
