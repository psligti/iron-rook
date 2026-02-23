# Architecture Review Evaluation Rubric

Evaluates architecture review agent effectiveness in detecting design issues.

## Metadata

- **Version**: 1.0.0
- **Category**: architecture_review
- **Description**: Judges architecture review quality for code design analysis

## Prompt Template

```
You are an expert evaluator judging the QUALITY of an architecture review agent's output.

Your task is to evaluate whether the agent effectively identified architectural issues
including boundary violations, coupling problems, and anti-patterns.

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

1. **Boundary Detection** (weight: 0.25)
   - Did it detect layering violations?
   - Did it identify improper dependencies between modules?
   - Did it find domain boundary violations?

2. **Coupling Analysis** (weight: 0.20)
   - Did it identify tight coupling issues?
   - Did it detect circular dependencies?
   - Were cohesion problems identified?

3. **Anti-Pattern Recognition** (weight: 0.20)
   - Did it detect god objects/classes?
   - Did it identify leaky abstractions?
   - Were common anti-patterns (singleton abuse, etc.) found?

4. **Evidence Quality** (weight: 0.20)
   - Are findings backed by specific code references?
   - Is there clear reasoning for why something is problematic?
   - Are dependencies and relationships clearly documented?

5. **Delegation Effectiveness** (weight: 0.15)
   - Was the ArchitectureSubagent used appropriately?
   - Was TODO decomposition logical?
   - Were tool calls appropriate (ast-grep for patterns)?

## Output Format

You MUST respond with a valid JSON object matching this schema:

```json
{{
  "score": <float between 0.0 and 1.0>,
  "passed": <boolean>,
  "reasoning": "<brief explanation of the score>",
  "breakdown": {{
    "boundary_detection": <float 0.0-1.0>,
    "coupling_analysis": <float 0.0-1.0>,
    "anti_pattern_recognition": <float 0.0-1.0>,
    "evidence_quality": <float 0.0-1.0>,
    "delegation_effectiveness": <float 0.0-1.0>
  }},
  "issues": ["<list of specific issues found, if any>"],
  "strengths": ["<list of strengths in the response, if any>"]
}}
```

Respond with ONLY the JSON object, no additional text.
```
