"""Adapter for integrating iron-rook reviewer agents with dawn-kestrel SDK.

This module provides the bridge between iron-rook's BaseReviewerAgent
and dawn-kestrel's OpenCodeAsyncClient, enabling execution of
review subagents through the SDK's agent registry.
"""

from __future__ import annotations

import logging
from typing import Any

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import ReviewOutput, Scope, MergeGate
from dawn_kestrel.agents.builtin import Agent


logger = logging.getLogger(__name__)


def create_reviewer_agent_from_base(
    base_agent: BaseReviewerAgent,
) -> Agent:
    """Create a dawn-kestrel Agent from iron-rook BaseReviewerAgent.

    This adapter enables iron-rook reviewer agents to be registered
    and executed via dawn-kestrel's AgentRuntime.

    Args:
        base_agent: BaseReviewerAgent instance to wrap

    Returns:
        Agent dataclass compatible with dawn-kestrel's AgentRegistry
    """
    agent_name = base_agent.get_agent_name()

    # Map reviewer's allowed tools to permission rules
    allowed_tools = base_agent.get_allowed_tools()
    permissions = []

    # Allow grep, glob, read for all reviewers (they need to analyze code)
    permissions.extend(
        [
            {"permission": "grep", "pattern": "*", "action": "allow"},
            {"permission": "glob", "pattern": "*", "action": "allow"},
            {"permission": "read", "pattern": "*", "action": "allow"},
        ]
    )

    # Add tool-specific permissions based on reviewer's allowed_tools
    for tool in allowed_tools:
        if tool == "bash":
            permissions.append({"permission": "bash", "pattern": "*", "action": "allow"})
        elif tool == "python":
            permissions.append({"permission": "bash", "pattern": "python *", "action": "allow"})

    # Deny editing tools (reviewers are read-only)
    permissions.extend(
        [
            {"permission": "edit", "pattern": "*", "action": "deny"},
            {"permission": "write", "pattern": "*", "action": "deny"},
        ]
    )

    system_prompt = base_agent.get_system_prompt()

    return Agent(
        name=agent_name,
        description=f"PR Review Agent: {agent_name}",
        mode="subagent",
        permission=permissions,
        native=True,
        hidden=False,
        prompt=system_prompt,
        options={
            "iron_rook_reviewer": True,  # Marker for custom handling
            "allowed_tools": allowed_tools,
        },
    )


def review_context_to_user_message(
    context: ReviewContext,
    system_prompt: str,
) -> str:
    """Convert ReviewContext to user_message format for OpenCodeAsyncClient.

    Formats the review context into a structured user message that includes
    the system prompt and context information.

    Args:
        context: ReviewContext containing changed files, diff, and metadata
        system_prompt: System prompt for the reviewer

    Returns:
        Formatted user message string
    """
    parts = [
        system_prompt,
        "",
        "## Review Context",
        "",
        f"**Repository Root**: {context.repo_root}",
        "",
        "### Changed Files",
    ]

    for file_path in context.changed_files:
        parts.append(f"- {file_path}")

    if context.base_ref and context.head_ref:
        parts.append("")
        parts.append("### Git Diff")
        parts.append(f"**Base Ref**: {context.base_ref}")
        parts.append(f"**Head Ref**: {context.head_ref}")

    parts.append("")
    parts.append("### Diff Content")
    parts.append("```diff")
    parts.append(context.diff)
    parts.append("```")

    if context.pr_title:
        parts.append("")
        parts.append("### Pull Request")
        parts.append(f"**Title**: {context.pr_title}")
        if context.pr_description:
            parts.append(f"**Description**:\n{context.pr_description}")

    parts.append("")
    parts.append(
        "Please analyze the above changes and provide your review in the specified JSON format."
    )

    return "\n".join(parts)


def _extract_json_from_response(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    start = text.find("{")
    if start == -1:
        return text

    brace_count = 0
    end = start
    for i, char in enumerate(text[start:], start):
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break

    return text[start:end] if end > start else text


def agent_result_to_review_output(
    agent_name: str,
    agent_result: Any,
    context: ReviewContext,
) -> ReviewOutput:
    """Convert AgentResult from SDK to ReviewOutput.

    Parses the SDK's AgentResult.response and converts it to
    iron-rook's ReviewOutput format.

    Args:
        agent_name: Name of the reviewer agent
        agent_result: AgentResult from dawn-kestrel SDK
        context: Original ReviewContext for fallback

    Returns:
        ReviewOutput with findings, severity, and merge gate decision

    Raises:
        ValueError: If response cannot be parsed as valid ReviewOutput JSON
    """
    response_text = agent_result.response
    clean_json = _extract_json_from_response(response_text)
    parts_count = len(agent_result.parts or [])
    logger.debug(f"[{agent_name}] Parts count: {parts_count}")

    if not clean_json.startswith("{"):
        for i, part in enumerate(agent_result.parts or []):
            part_text = getattr(part, "text", None)
            if part_text:
                logger.debug(f"[{agent_name}] Part {i} text (first 200 chars): {part_text[:200]}")
                if "{" in part_text:
                    extracted = _extract_json_from_response(part_text)
                    if extracted.startswith("{"):
                        clean_json = extracted
                        logger.debug(f"[{agent_name}] Found JSON in part {i}")
                        break

    try:
        output = ReviewOutput.model_validate_json(clean_json)
        logger.info(f"[{agent_name}] Successfully parsed ReviewOutput from SDK response")
        return output

    except Exception as e:
        logger.error(f"[{agent_name}] Failed to parse SDK response as ReviewOutput: {e}")
        logger.debug(f"[{agent_name}] Raw response (first 1000 chars): {response_text[:1000]}")
        logger.debug(f"[{agent_name}] Cleaned JSON (first 1000 chars): {clean_json[:1000]}")

        # Fallback: create error ReviewOutput
        return ReviewOutput(
            agent=agent_name,
            summary=f"Failed to parse review output: {str(e)}",
            severity="critical",
            scope=Scope(
                relevant_files=context.changed_files,
                ignored_files=[],
                reasoning="SDK response could not be parsed as valid ReviewOutput JSON",
            ),
            findings=[],
            checks=[],
            skips=[],
            merge_gate=MergeGate(
                decision="needs_changes",
                must_fix=[f"Review output parsing failed: {str(e)}"],
                should_fix=[],
                notes_for_coding_agent=[
                    "Review LLM response format and ensure it matches expected schema."
                ],
            ),
        )


def create_error_review_output(
    agent_name: str,
    error_message: str,
    context: ReviewContext,
) -> ReviewOutput:
    """Create error ReviewOutput for failed agent execution.

    Args:
        agent_name: Name of the reviewer agent
        error_message: Error message from failed execution
        context: Original ReviewContext

    Returns:
        ReviewOutput with blocking severity and error information
    """
    return ReviewOutput(
        agent=agent_name,
        summary=f"Agent error: {error_message}",
        severity="blocking",
        scope=Scope(
            relevant_files=context.changed_files,
            ignored_files=[],
            reasoning=f"Agent encountered error: {error_message}",
        ),
        findings=[],
        checks=[],
        skips=[],
        merge_gate=MergeGate(
            decision="block",
            must_fix=[f"Agent {agent_name} failed: {error_message}"],
            should_fix=[],
            notes_for_coding_agent=[],
        ),
    )
