# Issues, Blockers, and Gotchas

## [2026-02-13] Test Infrastructure Import Error

### Issue
Integration test `test_security_fsm_integration.py` fails with `ModuleNotFoundError: No module named 'dawn_kestrel'`

### Impact
- Cannot run integration tests to verify Phase 1 fix works
- Cannot verify end-to-end security review produces working subagent_requests
- Blocks progression on Task 3 (run integration tests)

### Root Cause
Test file imports from `iron_rook.review.orchestrator` which imports `dawn_kestrel.core.result`
The `dawn_kestrel` package is not installed or not in PYTHONPATH

### Resolution Needed
Fix test infrastructure import paths or install missing dependencies before tests can run

## [2026-02-12] Test Suite Execution Results - Task 9

### Critical Blocker: Python Version Incompatibility

**Issue**: Cannot run test suite due to Python version mismatch

**Details**:
- Project requires Python >= 3.11 (specified in `pyproject.toml:10`)
- `dawn-kestrel` dependency requires Python >= 3.11
- System has only Python 3.9.6 available
- Python 3.11 and 3.12 not found on system

**Impact**:
- ALL 10 test files fail during collection phase
- Cannot verify any security FSM refactoring changes
- Cannot run integration tests or unit tests
- Blocks all verification tasks (Tasks 3, 9, 10)

**Test Collection Errors** (10 total):
```
ERROR collecting tests/integration/test_security_fsm_integration.py
ERROR collecting tests/test_cli_rich_logging.py
ERROR collecting tests/test_loop_fsm.py
ERROR collecting tests/test_security_phase_logger.py
ERROR collecting tests/test_state_machine.py
ERROR collecting tests/unit/review/agents/test_security_fsm.py
ERROR collecting tests/unit/review/agents/test_security_thinking.py
ERROR collecting tests/unit/review/agents/test_security_transitions.py
ERROR collecting tests/unit/review/agents/test_subagent_fsm_execution.py
ERROR collecting tests/unit/review/subagents/test_security_subagents.py
```

**Root Cause**:
```
ModuleNotFoundError: No module named 'dawn_kestrel'
```

All test files fail because they import modules that depend on `dawn_kestrel`, which cannot be installed on Python 3.9.6.

### Type Checking Issues Found

**Mypy Errors Found**: 30 errors in 12 files

**Security-Specific Type Errors** (relevant to Phase 2 refactoring):
```
iron_rook/review/agents/security.py:1936: error: Argument "severity" to "Finding" has incompatible type "str"; expected "Literal['warning', 'critical', 'blocking']"  [arg-type]
iron_rook/review/agents/security.py:1937: error: Argument "confidence" to "Finding" has incompatible type "str"; expected "Literal['high', 'medium', 'low']"  [arg-type]
iron_rook/review/agents/security.py:1968: error: Argument "severity" to "Finding" has incompatible type "str"; expected "Literal['warning', 'critical', 'blocking']"  [arg-type]
iron_rook/review/agents/security.py:1969: error: Argument "confidence" to "Finding" has incompatible type "str"; expected "Literal['high', 'medium', 'low']"  [arg-type]
iron_rook/review/agents/security.py:2022: error: Argument "decision" to "ReviewOutput" has incompatible type "str"; expected "Literal['merge', 'warning', 'critical', 'blocking']"  [arg-type]
iron_rook/review/agents/security.py:2030: error: Argument "decision" to "MergeGate" has incompatible type "str"; expected "Literal['approve', 'needs_changes', 'block', 'approve_with_warnings']"  [arg-type]
```

**Additional Type Errors** (non-security):
- `iron_rook/fsm/loop_fsm.py`: 6 "Name 'err' already defined" errors (variable redefinition issues)
- `iron_rook/review/base.py`: Incompatible return value type for FSM transitions
- `iron_rook/review/pattern_learning.py`: Type annotation and assignment issues
- `iron_rook/review/logging_utils.py`: Type annotation issues
- `iron_rook/review/verifier.py`: Type annotation missing
- `iron_rook/review/utils/config.py`: Missing stubs for "yaml" library
- `iron_rook/review/utils/executor.py`: Type annotation issues
- `iron_rook/review/doc_gen.py`: Type annotation missing
- `iron_rook/review/subagents/security_subagents.py`: Type mismatch for verifier argument
- `iron_rook/review/subagents/security_subagent_dynamic.py`: Type mismatch for severity/confidence arguments

### Build/Typecheck Commands Executed

**Attempted Commands**:
1. `pytest tests/ -v` - Failed due to Python version mismatch
2. `python -m build` - Command not found
3. `python -m mypy .` - Failed due to invalid error code in config
4. `python -m mypy iron_rook/ --config-file=/dev/null --ignore-missing-imports` - Partially successful (30 errors found)

**Mypy Config Issue**:
The mypy configuration in `pyproject.toml:48` specifies `disable_error_code = "possibly-missing-attribute"`, which is not a valid mypy error code. This causes mypy to fail immediately before checking any files.

### Next Steps Required

**To Fix Test Suite Execution**:
1. Install Python 3.11 or 3.12 on the system
2. Reinstall project dependencies with correct Python version
3. Run `pytest tests/ -v` to verify all tests pass

**To Fix Type Errors**:
1. Fix invalid mypy configuration in `pyproject.toml`
2. Add type annotations for variables that need them
3. Fix literal type mismatches in `security.py` (use proper Literal types instead of str)
4. Install missing type stubs: `python -m pip install types-PyYAML`
5. Fix variable redefinition issues in `loop_fsm.py`

**Cannot Continue Until**:
- Python 3.11+ is installed and configured
- Dependencies are properly installed
- Tests can be collected and executed

### Regression Status

**Regressions Found**: UNKNOWN
**Reason**: Cannot determine regressions because test suite cannot run due to environment issues

**Tests That Cannot Be Verified**:
- All 10 test files in the test suite
- Integration tests for security FSM
- Unit tests for security agents
- FSM transition tests
- State machine tests

### Verification Status

**Task 9 Status**: BLOCKED - Cannot complete verification
**Root Cause**: Python version mismatch (3.9.6 vs required >=3.11)
**Estimated Fix Time**: Depends on Python installation and environment setup

### Evidence Captured

**Test Output Evidence**:
- Full pytest collection error output saved
- Mypy type checking output saved with 30 detailed errors

**Error Messages**:
```
ERROR collecting tests/integration/test_security_fsm_integration.py
...
ModuleNotFoundError: No module named 'dawn_kestrel'
```

**Type Check Errors**:
```
Found 30 errors in 12 files (checked 42 source files)
```
