# Learnings - security-fsm-thinking-steps

## 2026-02-11T21:35:12Z - Initial Session

### Pydantic Model Patterns (from contracts.py)
- All models use `pd.BaseModel` as base class
- Use `model_config = pd.ConfigDict(extra="ignore"|"forbid")` for model configuration
- List fields use `pd.Field(default_factory=list)` to ensure mutable defaults are handled correctly
- Import pydantic as `import pydantic as pd`
- Use `Literal` type hints for enum-like fields
- Optional fields use `Optional[T]` from typing

### SecurityReviewer Structure (from security.py)
- Has `_phase_logger` of type `SecurityPhaseLogger`
- Has `_phase_outputs: Dict[str, Any]` for phase results
- Has `_current_security_phase: str` for tracking current phase
- Uses `LoopFSM` for FSM infrastructure
- Phase methods are async: `_run_intake`, `_run_plan_todos`, etc.
- Phase outputs are stored in `_phase_outputs` dictionary

### SecurityPhaseLogger Patterns (from security_phase_logger.py)
- Uses Rich `Console` for colored output
- `PHASE_COLORS` dict maps phase names to color styles
- `log_thinking(phase, message)` method logs simple string messages
- `log_transition(from_state, to_state)` method logs FSM transitions
- Internal logger: `self._logger = logging.getLogger("security.thinking")`

### Test Patterns (from test_security_thinking.py)
- Uses `pytest` with `@pytest.mark.asyncio` for async tests
- Uses `unittest.mock.Mock` for mocking
- Test class naming: `Test<FeatureName>`
- Test method naming: `test_<specific_behavior>`
- Imports: `from iron_rook.review.agents.security import SecurityReviewer`
- Tests mock the `_execute_llm` method to control LLM responses
- For console output testing: mock `logger._console.print` and capture call arguments
- For logger testing: add `logging.StreamHandler` to capture log output to StringIO

### SecurityPhaseLogger.log_thinking_frame() Testing
- Method takes a `ThinkingFrame` object as input
- Displays state header with phase color (e.g., "== INTAKE ==")
- Displays goals, checks, and risks as bullet lists with labels
- Displays thinking steps with all fields: kind, why, evidence, next, confidence
- Displays decision field at the end
- Logs structured data to internal logger with counts and decision
- When color disabled, only logs to logger (no console output)

### ThinkingFrame Creation Pattern (from _run_plan_todos())
- Import ThinkingFrame and ThinkingStep from contracts
- Create ThinkingFrame after LLM response parsing
- Fields:
  - `state`: phase name as string (e.g., "plan_todos")
  - `goals`: list of phase-specific goals
  - `checks`: list of validation checks
  - `risks`: list of potential risks
  - `steps`: list of ThinkingStep objects extracted from thinking text
  - `decision`: next phase from output.get("next_phase_request")
- Call `self._phase_logger.log_thinking_frame(frame)` to log to console
- Call `self._thinking_log.add(frame)` to accumulate in RunLog
- Maintain backward compatibility with existing `_extract_thinking_from_response()`

### ThinkingStep Creation from LLM Thinking
- Create ThinkingStep only if thinking text is non-empty
- Use `kind="transition"` for general phase transitions
- Extract thinking text via `_extract_thinking_from_response(response_text)`
- Set `evidence=["LLM response analysis"]` for LLM-derived thinking
- Set `next` to target phase (e.g., "delegate")
- Use default `confidence="medium"`

### Integration Test Output
- ThinkingFrame is logged with Rich formatting (bold colors, bullets)
- Goals/Checks/Risks displayed with appropriate labels
- Decision shown at end
- Logs to internal logger with counts: "goals=N, checks=N, risks=N, steps=N, decision=X"

## 2026-02-11T21:55:44Z - Task: Update _run_collect() to create ThinkingFrame

### _run_collect() ThinkingFrame Pattern
- Similar structure to _run_delegate() and _run_plan_todos()
- Goals for COLLECT phase:
  - Validate subagent results and findings
  - Mark TODO statuses based on completion
  - Ensure findings quality and completeness
- Checks for COLLECT phase:
  - Verify all subagent responses are received and valid
  - Validate findings structure and required fields
  - Ensure TODO status updates are consistent
- Risks for COLLECT phase:
  - Malformed subagent responses
  - Incomplete or inconsistent findings
  - Missing status updates for TODOs
- Uses `kind="transition"` for ThinkingStep (same as plan_todos)
- Decision defaults to "consolidate" from FSM_TRANSITIONS

### ThinkingStep kind Literal Values
- Valid values: 'transition', 'tool', 'delegate', 'gate', 'stop'
- Use `kind="transition"` for phase transitions (plan_todos, collect)
- Use `kind="delegate"` for delegation phase
- Cannot use phase name as kind (e.g., "collect" is invalid)

### Verification
- All 30 tests in test_security_thinking.py pass
- Collect phase test: test_collect_phase_logs_thinking_from_response

## 2026-02-11T22:05:00Z - Task: Update _run_evaluate() to create ThinkingFrame

### _run_evaluate() ThinkingFrame Pattern
- Final phase in FSM (transitions to "done")
- Goals for EVALUATE phase:
  - Assess findings severity (critical/high/medium/low)
  - Generate comprehensive risk assessment
  - Provide clear recommendations for each finding
  - Determine overall risk level (critical/high/medium/low)
  - Specify required and suggested actions
- Checks for EVALUATE phase:
  - Verify findings are properly categorized by severity
  - Ensure evidence is provided for each finding
  - Check recommendations are actionable and specific
  - Validate risk assessment is consistent with findings
- Risks for EVALUATE phase:
  - Underestimating critical vulnerabilities
  - Missing high-impact security issues
  - Providing ambiguous or impractical recommendations
  - Inconsistent severity classification
- Uses `kind="transition"` for ThinkingStep
- Decision defaults to "done" (final phase)

### Parallel Task Execution
- Tasks run in parallel (e.g., _run_consolidate and _run_evaluate)
- File can be modified by other tasks between read and edit
- Solution: Re-read file before editing to avoid conflicts

### Verification
- All 30 tests in test_security_thinking.py pass
- Evaluate phase test: test_evaluate_phase_logs_thinking_from_response
