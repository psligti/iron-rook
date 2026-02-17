
## Task 2: Mock Phase Responses Helper (2026-02-16)

### Implementation
- Created `tests/conftest.py` with:
  - `_PHASE_TEMPLATES`: Dict containing default response structures for all 5 FSM phases
  - `create_mock_response(phase, overrides)`: Helper function that creates JSON responses with optional overrides
  - `mock_phase_responses`: Pytest fixture returning dict of phase → JSON string

### Key Patterns
- Phase structure: `{"phase": "...", "data": {...}, "next_phase_request": "..."}`
- Phases: intake → plan → act → synthesize → check → done
- Overrides support dot notation for nested keys (e.g., `"data.summary"`)

### Usage Examples
```python
# Basic usage
response = create_mock_response("intake")

# With overrides
response = create_mock_response("intake", {"data": {"summary": "Custom"}})

# Nested overrides
response = create_mock_response("check", {"data.findings.high": ["issue1"]})
```

### Notes
- LSP diagnostics clean on new file (pre-existing errors in other test files)
- Docstrings kept for public API (create_mock_response, mock_phase_responses fixture)
# Learnings - Review Agents Subagent Unification

## 2026-02-16

### Task 1: Shared Test Fixtures

**Created:** `tests/conftest.py` (extended existing file)

**Added Fixtures:**
1. `mock_review_context` - Standard ReviewContext with changed_files, diff, repo_root, base_ref, head_ref, pr_title, pr_description
2. `mock_simple_runner` - Fixture factory returning `AsyncMock` with configurable `run_with_retry` response
3. `assert_valid_review_output(output)` - Helper function validating ReviewOutput structure (agent, summary, severity, scope, merge_gate, findings, checks, skips)

**Test Patterns:**
- Pytest fixtures use `@pytest.fixture` decorator
- Factory fixtures return inner function that creates configured mocks
- Validation helpers raise AssertionError with descriptive messages
- Use `isinstance()` checks for type validation in assertion helpers

**Imports Used:**
```python
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput, Scope, MergeGate, Finding, Check, Skip, RunLog
)
from unittest.mock import AsyncMock
```
