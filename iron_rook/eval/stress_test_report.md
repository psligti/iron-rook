# Stress Test Report

Generated: 2026-02-24T15:26:59.586802+00:00

## Summary

- Total tests: 9
- Passed: 0
- Failed: 9
- Timeouts: 0

## Test Results

### stress-empty-file

- Status: FAIL
- Duration: 0.15s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-massive-file

- Status: FAIL
- Duration: 0.10s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-deep-nesting

- Status: FAIL
- Duration: 0.12s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-unicode

- Status: FAIL
- Duration: 0.11s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-false-positives

- Status: FAIL
- Duration: 0.11s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-subtle-issues

- Status: FAIL
- Duration: 0.11s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-mixed-languages

- Status: FAIL
- Duration: 0.10s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-resource-exhaustion

- Status: FAIL
- Duration: 0.10s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

### stress-ambiguous

- Status: FAIL
- Duration: 0.11s
- Error: `BadName: Ref 'Invalid revision spec 'HEAD~1^0' - not enough parent commits to reach '~1'' did not resolve to an object`

## Gap Analysis

### Agent Gaps

- Subtle issue detection weak: stress-subtle-issues

### Skill Gaps


### Tool Gaps

- Unicode handling issue in stress-unicode

### Harness Gaps


## Recommendations

1. Enhance prompts for subtle issue detection
2. Add robust unicode handling