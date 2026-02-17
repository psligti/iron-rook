# Decisions - Security Agent FSM Migration

## 2026-02-16 Session Start

### Decision: Use dawn_kestrel.core.fsm.FSMBuilder (not dawn_kestrel.workflow.fsm)

The plan references `WorkflowFSMBuilder` from `dawn_kestrel.core.fsm:824-893`, but the actual class in dawn_kestrel is `FSMBuilder` (lines 467-739).

**Rationale:**
- `dawn_kestrel.core.fsm.FSMBuilder` is the generic builder with fluent API
- `dawn_kestrel.workflow.fsm.FSM` is a specific workflow implementation
- The plan intends to use the generic builder pattern

**Decision:** Create `WorkflowFSMAdapter` that wraps `FSMBuilder` from `dawn_kestrel.core.fsm`

### Decision: Preserve Custom Phase Transitions

Security agent has custom transitions in `SECURITY_FSM_TRANSITIONS` that differ from both:
- Default `LoopFSM` transitions
- `WORKFLOW_FSM_TRANSITIONS` in dawn_kestrel

**Approach:** The adapter should:
1. Map security phase names to workflow state names internally
2. Preserve the security-specific transition logic
3. Allow early-exit paths through minimal synthesize/check phases

