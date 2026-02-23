# Generic Review Agent Evaluation Rubric

Evaluates any review agent on common quality dimensions.

## Metadata

- **Version**: 1.0.0
- **Category**: review_quality
- **Description**: Judges generic review agent quality applicable to all reviewers

## Prompt Template

```
You are an expert evaluator judging the QUALITY of a PR review agent's output.

Your task is to evaluate whether the agent performed an effective review
following the expected patterns and output contracts.

## Task Input
{task_input}

## Expected Output (if provided)
{expected_output}

## Agent's Response
{agent_response}

## Full Transcript Context
{transcript_context}

## Evaluation Criteria

Evaluate the response on these dimensions:

1. **Finding Quality** (weight: 0.25)
   - Does each finding have a clear id, title, and severity?
   - Is there concrete evidence with file:line references?
   - Are confidence levels appropriate (high/medium/low)?
   - Is the owner assignment correct (dev/docs/devops/security)?

2. **Merge Gate Decision** (weight: 0.20)
   - Is the decision appropriate for the findings (approve/needs_changes/block)?
   - Are must_fix and should_fix lists populated correctly?
   - Does severity mapping match the decision logic?

3. **Scope Accuracy** (weight: 0.15)
   - Are relevant_files correctly identified?
   - Is the reasoning for scope clear?
   - Were irrelevant files correctly ignored?

4. **Tool Usage** (weight: 0.20)
   - Were appropriate tools used for the domain?
   - Were tool calls efficient (no redundant calls)?
   - Did tools produce useful evidence?

5. **Delegation Effectiveness** (weight: 0.20)
   - Was TODO decomposition logical and complete?
   - Were subagents dispatched to appropriate tasks?
   - Were subagent results properly aggregated?

## Output Format

You MUST respond with a valid JSON object matching this schema:

```json
{{
  "score": <float between 0.0 and 1.0>,
  "passed": <boolean>,
  "reasoning": "<brief explanation of the score>",
  "breakdown": {{
    "finding_quality": <float 0.0-1.0>,
    "merge_gate_decision": <float 0.0-1.0>,
    "scope_accuracy": <float 0.0-1.0>,
    "tool_usage": <float 0.0-1.0>,
    "delegation_effectiveness": <float 0.0-1.0>
  }},
  "issues": ["<list of specific issues found, if any>"],
  "strengths": ["<list of strengths in the response, if any>"]
}}
```

Respond with ONLY the JSON object, no additional text.
```
