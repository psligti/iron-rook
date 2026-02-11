# Draft: Security Agent FSM Implementation

## Requirements (confirmed)
- Implement 6-phase FSM: intake → plan_todos → delegate → collect → consolidate → evaluate → done
- Add subagent delegation for specialized security checkers
- Add per-phase LLM thinking/output logging with phase-specific logger
- Add colored logging for all log messages
- Add explicit state transition logging

## Technical Decisions
- Use existing LoopFSM as foundation for state management
- Map security phases to LoopFSM states
- Create subagent types: auth_security, injection_scanner, secret_scanner, dependency_audit
- Use RichHandler for colored log output
- Create special logger: `security_thinking` for phase-specific output
- Load phase prompts from `security_review_agent.md`

## Research Findings
- LoopFSM exists in `iron_rook/fsm/loop_fsm.py` with states: INTAKE, PLAN, ACT, SYNTHESIZE, DONE, FAILED, STOPPED
- SecurityReviewer currently uses simple 3-state FSM: IDLE → INITIALIZING → RUNNING → COMPLETED
- `security_review_agent.md` contains detailed phase specifications and output schemas
- Current logging uses standard Python logging without colors
- Rich console is only used for terminal progress, not log messages
- No subagent delegation exists; SecurityReviewer is a leaf agent

## Scope Boundaries
- INCLUDE:
  - Implement 6-phase FSM in SecurityReviewer class
  - Create subagent base classes for specialized security checkers
  - Add per-phase thinking logging with phase prefix
  - Implement colored logging via RichHandler
  - Add state transition logging in FSM
  - Implement result aggregation in COLLECT phase

- EXCLUDE:
  - Creating new subagent types beyond documented ones (auth_security, injection_scanner, secret_scanner, dependency_audit)
  - Modifying PRReviewOrchestrator (this is about SecurityReviewer only)
  - Changing phase schemas in `security_review_agent.md`
