# Dependencies on "delegate" and "collect" Phases

## Task: Search for backwards compatibility dependencies

### Search Scope
- Target directories: `iron_rook/review/`, `iron_rook/review/subagents/`
- Search patterns: `_phase_outputs["delegate"]`, `_phase_outputs["collect"]`, string literals `"delegate"`, `"collect"`

---

## Findings Summary

### 1. Direct Phase Output Storage (WRITE operations)

**File:** `iron_rook/review/agents/security.py`

| Line | Phase | Operation | Context |
|------|-------|-----------|---------|
| 148 | "delegate" | `self._phase_outputs["delegate"] = output` | Stores delegate phase output after successful phase execution |
| 156 | "collect" | `self._phase_outputs["collect"] = output` | Stores collect phase output after successful phase execution |

**Impact:** These are WRITE operations that will be removed. No external code reads these outputs directly at this point.

---

### 2. Direct Phase Output Access (READ operations)

**File:** `iron_rook/review/agents/security.py`

| Line | Phase | Usage | Purpose |
|------|-------|-------|---------|
| 1028 | "delegate" | `delegate_output = self._phase_outputs.get("delegate", {}).get("data", {})` | Used in `_build_collect_message()` to provide DELEGATE output as context to COLLECT phase |
| 1187 | "delegate" | `delegate_output = self._phase_outputs.get("delegate", {})` | Used in `_build_review_output_from_evaluate()` to extract subagent_results from delegate phase for final report |

**Impact:** CRITICAL - These READ operations will break when delegate phase is removed:
1. **Line 1028**: COLLECT phase expects DELEGATE output as context. When COLLECT runs after PLAN_TODOS (skipping DELEGATE), this will fail or return empty context.
2. **Line 1187**: Final report generation expects to find delegate output with subagent_results. This will be empty after refactor.

---

### 3. String Literal References (Phase Names in Code)

**File:** `iron_rook/review/agents/security.py`

| Line | Context | Reference | Impact |
|------|---------|-----------|--------|
| 32-34 | FSM_TRANSITIONS | `"delegate": ["collect", "consolidate", "evaluate", "done"]` | Defines valid transitions FROM delegate |
| 33 | FSM_TRANSITIONS | `"collect": ["consolidate"]` | Defines valid transitions FROM collect |
| 85 | LoopState mapping | `"delegate": LoopState.ACT` | Maps phase to ACT loop state |
| 86 | LoopState mapping | `"collect": LoopState.SYNTHESIZE` | Maps phase to SYNTHESIZE loop state |
| 141, 358 | Default next phase | `"delegate"` | Used as default next_phase_request value |
| 144 | Phase check | `self._current_security_phase == "delegate"` | Conditional logic for delegate phase |
| 149, 494, 499 | Default next phase | `"collect"` | Used as default next_phase_request value |
| 152 | Phase check | `self._current_security_phase == "collect"` | Conditional logic for collect phase |
| 352, 502 | State transition | `next="delegate"`, `state="delegate"` | Transition states for FSM |
| 398, 530 | Prompt retrieval | `"delegate"`, `"collect"` | Phase-specific prompt lookup |
| 417, 549 | Response parsing | `"delegate"`, `"collect"` | Phase-specific output parsing |
| 491, 582 | Transition kinds | `kind="delegate"`, `state="collect"` | Transition state definitions |
| 852, 885 | Default values | `"next_phase_request": "delegate"`, `"collect"` | Mock/test default values |

**Impact:** All of these references will need to be removed when the phases are removed:
- FSM_TRANSITIONS entries
- LoopState mappings
- Phase checks
- Prompt retrieval logic
- Response parsing logic
- Transition state logic

---

### 4. Documentation References

**File:** `iron_rook/review/README.md`

| Line | Context | Reference |
|------|---------|-----------|
| 617, 619 | Mermaid diagram | Transitions: Plan_Todos --> Delegate, Delegate --> Collect |
| 763, 764 | Mermaid diagram | State: PhaseContext --> ValidateDelegate/ValidateCollect |
| 837-839 | FSM transitions | `"delegate": ["collect", ...], "collect": ["consolidate"]` |
| 900-902 | FSM transitions | `"delegate": ["collect", ...], "collect": ["consolidate"]` |

**Impact:** Documentation will need updating to reflect new phase transitions.

---

**File:** `iron_rook/review/security_review_agent.md`

| Line | Context | Reference |
|------|---------|-----------|
| 10 | Phase schema | `"phase": "intake" | "plan_todos" | "delegate" | "collect" | ...` |
| 14 | Next phase schema | `"next_phase_request": ... | "delegate" | "collect" | ...` |
| 89, 149 | Validation rules | Valid next_phase_request values include "delegate", "collect" |
| 131, 155 | Example outputs | `"next_phase_request": "delegate"`, `"phase": "delegate"` |
| 189, 214 | Example outputs | `"next_phase_request": "collect"`, `"phase": "collect"` |

**Impact:** Documentation examples and schemas will need updating.

---

### 5. Type Definitions

**File:** `iron_rook/review/contracts.py`

| Line | Context | Reference |
|------|---------|-----------|
| 109 | Transition kinds | `Literal["transition", "tool", "delegate", "gate", "stop"]` |
| 263, 299 | Phase literals | `Literal["delegate"]`, `phase: Literal["collect"]` |
| 301 | Next phase literals | `Literal["collect", "consolidate", "evaluate", "done"]` |
| 313 | Phase literals | `phase: Literal["collect"]` |
| 398 | Documentation comment | `phase: Phase name (e.g., "intake", "plan_todos", "delegate", "collect", ...)` |
| 409-410 | Phase schemas | `"delegate": DelegatePhaseOutput, "collect": CollectPhaseOutput` |

**Impact:** Type definitions will need updating to remove these literals and phase output schemas.

---

**File:** `iron_rook/review/security_phase_logger.py`

| Line | Context | Reference |
|------|---------|-----------|
| 85 | Documentation | `to_state: The target state (e.g., "plan_todos", "delegate").` |

**Impact:** Documentation comment will need updating.

---

## Critical Dependencies (Will Break on Removal)

### High Priority - WILL BREAK CODE:

1. **`_build_collect_message()` (line 1026-1039)**
   - Depends on: `delegate_output = self._phase_outputs.get("delegate", {}).get("data", {})`
   - Impact: COLLECT phase will lose DELEGATE output context
   - Fix Required: Update to use PLAN_TODOS output instead (or skip DELEGATE context entirely)

2. **`_build_review_output_from_evaluate()` (line 1187)**
   - Depends on: `delegate_output = self._phase_outputs.get("delegate", {})`
   - Impact: Final report generation will not find subagent_results
   - Fix Required: Subagent delegation will be removed, so this extraction logic is no longer needed

### Medium Priority - Will Need Updates:

3. **FSM_TRANSITIONS dictionary**
   - Lines 32-34: `"delegate": ["collect", "consolidate", "evaluate", "done"]`
   - Line 34: `"collect": ["consolidate"]`
   - Impact: FSM validation will reject transitions
   - Fix Required: Remove these transition entries

4. **LoopState mappings**
   - Lines 85-86: `"delegate": LoopState.ACT`, `"collect": LoopState.SYNTHESIZE`
   - Impact: Phase state mapping errors
   - Fix Required: Remove these mappings

5. **Phase execution logic**
   - Lines 144, 152: Phase checks for `self._current_security_phase == "delegate"/"collect"`
   - Impact: Phase-specific logic will not execute
   - Fix Required: Remove phase-specific blocks

6. **Prompt and response parsing**
   - Lines 398, 417, 530, 549: Phase-specific prompt retrieval and response parsing
   - Impact: Will try to load non-existent prompts
   - Fix Required: Remove phase-specific handlers

7. **Type definitions**
   - `contracts.py`: Literal types for "delegate", "collect" and phase output schemas
   - Impact: Type validation will fail
   - Fix Required: Remove these literals and schemas

---

## External API Dependencies

### No External APIs Found

- No files in `iron_rook/review/subagents/` reference "delegate" or "collect" phases
  - The subagent file (`security_subagent_dynamic.py`) uses different phases: "intake", "plan", "act", "synthesize"
- No test files reference these phase names
- No public API exports depend on these phases

---

## Recommended Refactor Strategy

### Phase 1: Update Data Flow (Read Operations)

1. **Fix `_build_collect_message()`**:
   - Replace DELEGATE output context with PLAN_TODOS output
   - Or remove DELEGATE context entirely if not needed

2. **Fix `_build_review_output_from_evaluate()`**:
   - Remove subagent_results extraction from DELEGATE phase
   - Subagent delegation will be removed entirely

### Phase 2: Remove Phase Logic (Write Operations + Execution)

3. **Remove phase execution blocks**:
   - Remove "delegate" phase handling (lines ~144-148)
   - Remove "collect" phase handling (lines ~152-156)

4. **Remove FSM transition definitions**:
   - Remove `"delegate": [...]` from FSM_TRANSITIONS
   - Remove `"collect": [...]` from FSM_TRANSITIONS
   - Update `"plan_todos"` transitions to point to valid phases

5. **Remove LoopState mappings**:
   - Remove `"delegate": LoopState.ACT`
   - Remove `"collect": LoopState.SYNTHESIZE`

### Phase 3: Update Type System

6. **Update `contracts.py`**:
   - Remove "delegate", "collect" from Literal type definitions
   - Remove `DelegatePhaseOutput` and `CollectPhaseOutput` schemas
   - Update documentation comments

### Phase 4: Update Documentation

7. **Update README and markdown files**:
   - Remove delegate/collect from Mermaid diagrams
   - Update example outputs
   - Update phase transition documentation

---

## Verification Checklist

- [ ] All `_phase_outputs["delegate"]` writes removed
- [ ] All `_phase_outputs["collect"]` writes removed
- [ ] `_build_collect_message()` updated to not depend on delegate output
- [ ] `_build_review_output_from_evaluate()` updated to not extract subagent_results from delegate
- [ ] FSM_TRANSITIONS updated (delegate/collect entries removed)
- [ ] LoopState mappings updated (delegate/collect removed)
- [ ] Phase-specific prompt handlers removed
- [ ] Phase-specific response parsers removed
- [ ] Type definitions updated (contracts.py)
- [ ] Documentation updated (README, markdown files)
- [ ] Build passes with no errors
- [ ] LSP diagnostics clean on modified files
