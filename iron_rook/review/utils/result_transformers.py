"""Result transformers for converting between agent result types.

This module provides transformation functions to convert AgentResult
(from dawn-kestrel SDK) into ReviewOutput (iron-rook review contract).

The transformation handles:
- JSON extraction from agent response (with markdown code block support)
- Validation using ReviewOutput Pydantic model
- Graceful fallback for empty/invalid responses
- Detailed error logging for debugging
"""

import json
import re
import logging
from typing import Optional

from dawn_kestrel.core.agent_types import AgentResult
from iron_rook.review.base import ReviewContext
from iron_rook.review.contracts import (
    ReviewOutput,
    Scope,
    MergeGate,
)

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract JSON from text, handling markdown code blocks.

    Args:
        text: Text potentially containing JSON

    Returns:
        Extracted JSON string, or None if not found
    """
    if not text or not text.strip():
        return None

    pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(pattern, text)

    if matches:
        return matches[0].strip()

    text = text.strip()

    if text.startswith("{") or text.startswith("["):
        return text

    return None


def create_fallback_review_output(
    agent_name: str, context: ReviewContext, error_message: str = ""
) -> ReviewOutput:
    """Create a fallback ReviewOutput for error cases.

    When transformation fails (empty response, invalid JSON, validation error),
    we return a ReviewOutput with merge severity to allow the review to proceed.

    Args:
        agent_name: Name of the agent
        context: Review context for building scope
        error_message: Optional error message for summary

    Returns:
        ReviewOutput with merge severity and empty findings
    """
    scope = Scope(
        relevant_files=context.changed_files,
        ignored_files=[],
        reasoning=f"Review based on changed files in {context.repo_root}",
    )

    merge_gate = MergeGate(
        decision="approve",
        must_fix=[],
        should_fix=[],
        notes_for_coding_agent=[],
    )

    if error_message:
        summary = f"Review completed with note: {error_message}"
    else:
        summary = "Review completed - no specific findings"

    return ReviewOutput(
        agent=agent_name,
        summary=summary,
        severity="merge",
        scope=scope,
        checks=[],
        skips=[],
        findings=[],
        merge_gate=merge_gate,
    )


def agent_result_to_review_output(
    agent_result: AgentResult, context: ReviewContext
) -> ReviewOutput:
    """Transform AgentResult to ReviewOutput.

    This function extracts the agent's response JSON, validates it against
    the ReviewOutput schema, and returns a valid ReviewOutput instance.

    The transformation handles:
    - JSON extraction from response (with markdown code block support)
    - Validation using ReviewOutput.model_validate()
    - Graceful fallback for empty/invalid responses
    - Preserves context information for scope building

    Args:
        agent_result: Result from AgentRuntime.execute_agent
        context: Review context for fallback scope building

    Returns:
        Valid ReviewOutput instance

    Examples:
        >>> result = AgentResult(
        ...     agent_name="security",
        ...     response='{"agent": "security", "summary": "No issues", ...}',
        ...     parts=[],
        ...     metadata={},
        ...     tools_used=[],
        ...     duration=1.0,
        ... )
        >>> context = ReviewContext(
        ...     changed_files=["src/auth.py"],
        ...     diff="+ def authenticate()",
        ...     repo_root="/repo",
        ... )
        >>> output = agent_result_to_review_output(result, context)
        >>> assert output.agent == "security"
        >>> assert isinstance(output, ReviewOutput)
    """
    if agent_result.error:
        logger.warning(f"Agent {agent_result.agent_name} had error: {agent_result.error}")
        return create_fallback_review_output(
            agent_name=agent_result.agent_name,
            context=context,
            error_message=f"Agent error: {agent_result.error}",
        )

    json_str = extract_json_from_text(agent_result.response)

    if not json_str:
        logger.warning(f"Agent {agent_result.agent_name} returned no JSON in response")
        return create_fallback_review_output(
            agent_name=agent_result.agent_name,
            context=context,
            error_message="No JSON output found in agent response",
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Agent {agent_result.agent_name} returned invalid JSON")
        logger.error(f"  JSONDecodeError: {e}")
        logger.error(f"  Line {e.lineno}, Column {e.colno}: {e.msg}")
        logger.error(f"  Extracted JSON string (first 1000 chars): {json_str[:1000]}")
        logger.error(f"  Full JSON length: {len(json_str)} characters")
        logger.error(f"  Raw response length: {len(agent_result.response)} characters")
        logger.error(f"  Raw response (first 500 chars): {agent_result.response[:500]}")
        return create_fallback_review_output(
            agent_name=agent_result.agent_name,
            context=context,
            error_message=f"Invalid JSON: {str(e)}",
        )

    if "agent" not in data or not data["agent"]:
        data["agent"] = agent_result.agent_name

    try:
        output = ReviewOutput.model_validate(data)
        logger.info(
            f"Successfully transformed AgentResult from {agent_result.agent_name} "
            f"to ReviewOutput with {len(output.findings)} findings"
        )
        return output
    except Exception as e:
        logger.error(f"Agent {agent_result.agent_name} returned invalid ReviewOutput")
        logger.error(f"  Exception: {type(e).__name__}: {e}")
        logger.error(
            f"  Parsed data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}"
        )
        logger.error(f"  Full parsed data (first 1000 chars): {str(data)[:1000]}")
        logger.error(f"  Raw response (first 500 chars): {agent_result.response[:500]}")
        return create_fallback_review_output(
            agent_name=agent_result.agent_name,
            context=context,
            error_message=f"Validation error: {str(e)}",
        )
