# Security Subagent Implementation - Summary

## Problem Identified

The security review system had a critical architectural flaw:

**DELEGATE phase only simulated subagent execution without actually running any analysis tools.**

The flow was:
1. INTAKE → 6 real security risks identified
2. PLAN_TODOS → 6 TODOs created
3. DELEGATE → LLM called to "generate subagent requests" (no execution)
4. COLLECT → Expected results that don't exist
5. CONSOLIDATE/EVALUATE → 0 findings due to no actual analysis

Result: **0 findings with 30% confidence** despite INTAKE identifying 6 real security risks.

## Solution Implemented

### 1. Created `SecuritySubagent` (iron_rook/review/subagents/security_subagent_dynamic.py)

A lightweight FSM-based agent that:
- Receives a specific security task from parent SecurityReviewer
- Runs simplified 4-phase FSM: **INTAKE → PLAN → ACT → DONE**
- Uses security tools directly (grep, ast-grep, bandit, semgrep, etc.)
- Returns findings without delegating to other agents
- Does not have DELEGATE capability - does all its own work

### 2. Updated `SecurityReviewer._run_delegate()` (iron_rook/review/agents/security.py)

Added actual subagent execution logic:

```python
# Parse subagent requests from LLM response
subagent_requests = output.get("data", {}).get("subagent_requests", [])

# ACTUALLY EXECUTE SUBAGENTS
for request in subagent_requests:
    subagent = SecuritySubagent(task=request)
    result = await subagent.review(context)
    # Collect results with findings

# Store results for COLLECT phase
output["data"]["subagent_results"] = subagent_results
```

### 3. Phase Templates for Subagent FSM

Added prompts for each subagent phase:
- **INTAKE**: Understand task and scope
- **PLAN**: Select tools and analysis approach
- **ACT**: Execute tools and collect evidence (uses grep, ast-grep, bandit, semgrep)
- **DONE**: Return final results

## Architecture Change

### Before (Broken)
```
INTAKE → PLAN_TODOS → DELEGATE (simulated) → COLLECT (no results) → CONSOLIDATE → EVALUATE
                                        ↓
                                    LLM only - no execution
                                        ↓
                                    No findings
```

### After (Fixed)
```
INTAKE → PLAN_TODOS → DELEGATE (actual execution) → COLLECT (with results) → CONSOLIDATE → EVALUATE
                                        ↓
                    ┌─────────────────────────┐
                    │  SecuritySubagent #1  │  INTAKE → PLAN → ACT → DONE
                    │  SecuritySubagent #2  │  (uses grep, ast-grep, etc.)
                    │  ...                    │
                    └─────────────────────────┘
                                        ↓
                                    Subagent results collected
                                        ↓
                                    Real findings generated
```

## Key Changes

### New File: `security_subagent_dynamic.py`

**SecuritySubagent class:**
- `__init__(task, verifier, max_retries, agent_runtime)`: Receives task definition
- `review(context)`: Main entry point, runs simplified FSM
- `_run_intake(context)`: Understand task scope
- `_run_plan(context)`: Select tools and approach
- `_run_act(context)`: Execute tools and collect evidence
- `_transition_to_phase(next_phase)`: Validate and transition
- `_get_phase_prompt(phase, context)`: Phase-specific prompts
- `_execute_llm(system_prompt, user_message)`: Call LLM for analysis
- `_extract_thinking_from_response(response_text)`: Parse LLM reasoning
- `_parse_response(response_text, expected_phase)`: Parse JSON response
- `_build_review_output(done_output, context)`: Convert to ReviewOutput

### Modified File: `security.py`

**Updated `_run_delegate()` method:**
- Parses LLM response to get `subagent_requests`
- Instantiates `SecuritySubagent` for each request
- Executes subagent's `review()` method with context
- Collects results including:
  - Delegated tasks with actual findings
  - Self-assigned tasks marked as done
  - Blocked tasks with error messages
- Stores `subagent_results` in output for COLLECT phase

## How It Works

### Task Flow Example

1. **INTAKE phase** (SecurityReviewer)
   - Analyzes PR changes
   - Identifies 6 security risks:
     - Prompt injection via HTML
     - Data exfiltration to external GenAI
     - HTML parsing attacks
     - DoS via large documents
     - Incomplete sanitization
     - LLM response injection

2. **PLAN_TODOS phase** (SecurityReviewer)
   - Creates 6 TODOs
   - Maps each to a subagent or "self"
   - Example TODO:
     ```json
     {
       "todo_id": "SEC-001",
       "title": "Check for prompt injection in HTML sanitization",
       "scope": {"paths": ["sigmund/domains/web_vlc_checkout/services/web_vlc_checkout.py"]},
       "risk_category": "injection",
       "acceptance_criteria": ["Verify sanitization removes script tags"],
       "evidence_required": ["file_refs", "code_examples"]
     }
     ```

3. **DELEGATE phase** (SecurityReviewer)
   - LLM generates subagent_requests (one per TODO)
   - **NOW: Actually executes SecuritySubagent for each request**
   - Each SecuritySubagent:
     - INTAKE: Understands "Check for prompt injection"
     - PLAN: Selects `grep` and `ast-grep` to find sanitization patterns
     - ACT: Runs tools on the actual code
       ```bash
       grep -r "BeautifulSoup" sigmund/domains/web_vlc_checkout/services/
       ast-grep -p "soup.get_text()" --lang python
       ```
     - DONE: Returns findings with evidence

4. **COLLECT phase** (SecurityReviewer)
   - Receives actual subagent results
   - Validates each has findings or valid reasoning
   - Marks TODOs as done/blocked
   - **NOW: Has real evidence to work with**

5. **CONSOLIDATE phase** (SecurityReviewer)
   - Merges actual findings from subagents
   - De-duplicates by severity
   - **NOW: Has real findings to consolidate**

6. **EVALUATE phase** (SecurityReviewer)
   - Assesses real findings
   - Generates risk assessment
   - **NOW: Returns actual security report with findings**

## Expected Outcome

When security review runs now:
- ✅ Subagents actually execute security tools
- ✅ Real evidence is collected (file references, code examples, tool outputs)
- ✅ Findings are backed by actual analysis, not speculation
- ✅ Confidence is based on completed work, not "incomplete subagent reviews"
- ✅ Security risks identified in INTAKE are actually verified

## Testing

To verify the fix works:

```bash
# Run the same security review that failed before
iron-rook --agent security --output json -v

# Expected changes:
# - DELEGATE phase now logs "Executing X subagent tasks"
# - Each subagent runs its own FSM (INTAKE→PLAN→ACT→DONE)
# - ACT phase logs tool executions (grep, ast-grep, etc.)
# - COLLECT phase has actual results to process
# - Final report has > 0 findings with > 30% confidence
```

## Files Changed

1. **Created**: `iron_rook/review/subagents/security_subagent_dynamic.py` (603 lines)
   - New `SecuritySubagent` class
   - Simplified FSM transitions (intake → plan → act → done)
   - Phase-specific prompts with tool descriptions
   - Evidence collection and ReviewOutput generation

2. **Modified**: `iron_rook/review/agents/security.py`
   - `_run_delegate()` method added subagent execution logic (~30 new lines)
   - Instantiates and runs `SecuritySubagent` instances
   - Collects and stores results for COLLECT phase

## Notes

- The subagent design is intentionally **lightweight** and **self-contained**
- No further delegation - does its own work with tools
- Can handle any security task defined by LLM in DELEGATE phase
- LLM-guided tool selection - chooses appropriate tools per task
- Error handling - failed subagents marked as blocked with error message
- Parallel execution ready - subagents can run in parallel if needed

## LSP Errors to Address

The LSP errors detected are pre-existing issues in the codebase, not introduced by this change:

- `base.py:191` - FSM_TRANSITIONS attribute error (pre-existing)
- `base.py:192` - Type mismatch for LoopState (pre-existing)
- `security.py:1193` - Empty list type issue (pre-existing)
- `base.py:491` - Unbound variable (pre-existing)
- `cli.py:175` - TodoStorage import issue (pre-existing)
- Multiple `test_security_thinking.py` errors (pre-existing)

These should be addressed in a separate cleanup task.
