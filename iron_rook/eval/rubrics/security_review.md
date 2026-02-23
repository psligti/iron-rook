# Security Review Evaluation Rubric

Evaluates security review agent effectiveness in vulnerability detection and analysis.

## Metadata

- **Version**: 1.0.0
- **Category**: security_review
- **Description**: Judges security review quality for PR analysis

## Prompt Template

```
You are an expert evaluator judging the QUALITY of a security review agent's output.

Your task is to evaluate whether the agent effectively identified security vulnerabilities
and provided actionable recommendations.

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

1. **Vulnerability Detection** (weight: 0.30)
   - Did it detect actual vulnerabilities in the code?
   - Did it avoid false positives?
   - Did it identify both obvious and subtle issues?
   - Did it cover the OWASP Top 10 relevant categories?

2. **Severity Accuracy** (weight: 0.20)
   - Are severity ratings appropriate (warning/critical/blocking)?
   - Is blocking reserved for exploitable issues?
   - Are critical issues differentiated from warnings?

3. **Evidence Quality** (weight: 0.20)
   - Does each finding include concrete file:line references?
   - Is there code context showing the vulnerability?
   - Is the evidence sufficient to understand the issue?

4. **Recommendation Actionability** (weight: 0.20)
   - Are fix recommendations specific and implementable?
   - Do suggestions follow security best practices?
   - Are suggested patches syntactically correct?

5. **Delegation Effectiveness** (weight: 0.10)
   - Were appropriate subagents used (auth, injection, secrets, deps)?
   - Was TODO decomposition logical and complete?
   - Were tool calls appropriate (bandit, semgrep, pip-audit)?

## Output Format

You MUST respond with a valid JSON object matching this schema:

```json
{{
  "score": <float between 0.0 and 1.0>,
  "passed": <boolean>,
  "reasoning": "<brief explanation of the score>",
  "breakdown": {{
    "vulnerability_detection": <float 0.0-1.0>,
    "severity_accuracy": <float 0.0-1.0>,
    "evidence_quality": <float 0.0-1.0>,
    "recommendation_actionability": <float 0.0-1.0>,
    "delegation_effectiveness": <float 0.0-1.0>
  }},
  "issues": ["<list of specific issues found, if any>"],
  "strengths": ["<list of strengths in the response, if any>"]
}}
```

Respond with ONLY the JSON object, no additional text.
```
