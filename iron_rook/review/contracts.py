"""Pydantic contracts for review agent output."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Literal, Dict, Any, Optional
from dataclasses import dataclass, field
import pydantic as pd
import json
import re


class MergePolicy(ABC):
    """Interface for merge decision policies.

    A merge policy determines the final merge decision and fix lists
    based on review outputs from subagents.

    Implementations must preserve the contract: decision values must
    be one of: "approve", "needs_changes", "block", "approve_with_warnings"
    """

    @abstractmethod
    def compute_merge_decision(self, results: List["ReviewOutput"]) -> MergeGate:
        """Compute merge decision based on review outputs.

        Args:
            results: List of ReviewOutput from subagents

        Returns:
            MergeGate with decision and fix lists
        """
        pass


class PriorityMergePolicy(MergePolicy):
    """Default merge policy based on severity priority.

    Priority ordering: blocking > critical > warning > approve

    Decision logic:
    - Any blocking finding -> "block"
    - Any critical finding (no blocking) -> "needs_changes"
    - Any warning finding (no blocking/critical) -> "approve_with_warnings"
    - No findings -> "approve"
    """

    def compute_merge_decision(self, results: List["ReviewOutput"]) -> MergeGate:
        """Compute merge decision using priority policy.

        Args:
            results: List of ReviewOutput from subagents

        Returns:
            MergeGate with decision and fix lists
        """
        must_fix = []
        should_fix = []
        decision: Literal["approve", "needs_changes", "block", "approve_with_warnings"] = "approve"

        for result in results:
            must_fix.extend(result.merge_gate.must_fix)
            should_fix.extend(result.merge_gate.should_fix)

            for finding in result.findings:
                if finding.severity == "blocking":
                    must_fix.append(f"{finding.title}: {finding.recommendation}")
                elif finding.severity == "critical":
                    must_fix.append(f"{finding.title}: {finding.recommendation}")
                elif finding.severity == "warning":
                    should_fix.append(f"{finding.title}: {finding.recommendation}")

        if must_fix:
            has_blocking = any(
                f.severity == "blocking" for result in results for f in result.findings
            )
            decision = "block" if has_blocking else "needs_changes"
        elif should_fix:
            decision = "approve_with_warnings"
        else:
            decision = "approve"

        return MergeGate(
            decision=decision,
            must_fix=list(set(must_fix)),
            should_fix=list(set(should_fix)),
            notes_for_coding_agent=[f"Review completed by {len(results)} subagents"],
        )


class Scope(pd.BaseModel):
    relevant_files: List[str]
    ignored_files: List[str] = pd.Field(default_factory=list)
    reasoning: str

    model_config = pd.ConfigDict(extra="ignore")


class Check(pd.BaseModel):
    name: str
    required: bool
    commands: List[str]
    why: str
    expected_signal: str | None = None

    model_config = pd.ConfigDict(extra="ignore")


class Skip(pd.BaseModel):
    name: str
    why_safe: str
    when_to_run: str

    model_config = pd.ConfigDict(extra="ignore")


class Finding(pd.BaseModel):
    id: str
    title: str
    severity: Literal["warning", "critical", "blocking"]
    confidence: Literal["high", "medium", "low"]
    owner: Literal["dev", "docs", "devops", "security"]
    estimate: Literal["S", "M", "L"]
    evidence: str
    risk: str
    recommendation: str
    suggested_patch: str | None = None
    provenance: Dict[str, str] | None = pd.Field(
        default=None,
        description="Provenance metadata tracking origin (e.g., second-wave delegation)",
    )

    model_config = pd.ConfigDict(extra="forbid")


class MergeGate(pd.BaseModel):
    decision: Literal["approve", "needs_changes", "block", "approve_with_warnings"]
    must_fix: List[str] = pd.Field(default_factory=list)
    should_fix: List[str] = pd.Field(default_factory=list)
    notes_for_coding_agent: List[str] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="ignore")


class ReviewOutput(pd.BaseModel):
    agent: str
    summary: str
    severity: Literal["merge", "warning", "critical", "blocking"]
    scope: Scope
    checks: List[Check] = pd.Field(default_factory=list)
    skips: List[Skip] = pd.Field(default_factory=list)
    findings: List[Finding] = pd.Field(default_factory=list)
    merge_gate: MergeGate

    model_config = pd.ConfigDict(extra="ignore")


class ReviewInputs(pd.BaseModel):
    repo_root: str
    base_ref: str
    head_ref: str
    pr_title: str = ""
    pr_description: str = ""
    ticket_description: str = ""
    include_optional: bool = False
    timeout_seconds: int = 300

    model_config = pd.ConfigDict(extra="ignore")


class ToolPlan(pd.BaseModel):
    proposed_commands: List[str] = pd.Field(default_factory=list)
    auto_fix_available: bool = False
    execution_summary: str = ""

    model_config = pd.ConfigDict(extra="ignore")


class OrchestratorOutput(pd.BaseModel):
    merge_decision: MergeGate
    findings: List[Finding] = pd.Field(default_factory=list)
    tool_plan: ToolPlan
    subagent_results: List[ReviewOutput] = pd.Field(default_factory=list)
    summary: str = ""
    total_findings: int = 0

    model_config = pd.ConfigDict(extra="ignore")


def get_review_output_schema() -> str:
    """Return JSON schema for ReviewOutput as a string for inclusion in prompts.

    This schema must match exactly the ReviewOutput Pydantic model above.
    Any changes to the model must be reflected here.

    Returns:
        JSON schema string with explicit type information
    """

    return f"""You MUST output valid JSON matching this exact schema. The output is parsed directly by the ReviewOutput Pydantic model with no post-processing. Do NOT add any fields outside this schema:

{ReviewOutput.model_json_schema()}

 CRITICAL RULES:
 - Include ALL required fields: agent, summary, severity, scope, merge_gate
 - NEVER include extra fields not in this schema (will cause validation errors)
 - For findings: NEVER include fields like 'type', 'message' - only use the fields listed above
 - severity in findings is NOT the same as severity in the root object
 - findings severity options: 'warning', 'critical', 'blocking' (NOT 'merge')
 - root severity options: 'merge', 'warning', 'critical', 'blocking'
 - All fields are MANDATORY unless marked as optional with "or null"
 - Empty arrays are allowed: [], null values are allowed only where specified
 - Return ONLY the JSON object, no other text, no markdown code blocks
 - Output must be valid JSON that passes ReviewOutput Pydantic validation as-is
 - Do NOT include planning, analysis, or commentary text outside the JSON object

EXAMPLE VALID OUTPUT:
{{
  "agent": "security",
  "summary": "No security issues found",
  "severity": "merge",
  "scope": {{
    "relevant_files": ["file1.py", "file2.py"],
    "ignored_files": [],
    "reasoning": "Reviewed all changed files for security vulnerabilities"
  }},
  "checks": [],
  "skips": [],
  "findings": [],
  "merge_gate": {{
    "decision": "approve",
    "must_fix": [],
    "should_fix": [],
    "notes_for_coding_agent": ["Review complete"]
  }}
}}

EXAMPLE WITH FINDING:
{{
  "agent": "security",
  "summary": "Found potential secret in code",
  "severity": "blocking",
  "scope": {{
    "relevant_files": ["config.py"],
    "ignored_files": [],
    "reasoning": "Found hardcoded API key"
  }},
  "checks": [],
  "skips": [],
  "findings": [
    {{
      "id": "SEC-001",
      "title": "Hardcoded API key",
      "severity": "blocking",
      "confidence": "high",
      "owner": "security",
      "estimate": "S",
      "evidence": "Line 45 contains API_KEY='sk-12345'",
      "risk": "Secret exposed in source code",
      "recommendation": "Remove the key and load it from secure config"
    }}
  ],
  "merge_gate": {{
    "decision": "block",
    "must_fix": ["Hardcoded API key in config.py"],
    "should_fix": [],
    "notes_for_coding_agent": ["Rotate API key immediately"]
  }}
}}

EXAMPLE WITH WARNINGS:
{{
  "agent": "style",
  "summary": "Minor style issues found",
  "severity": "warning",
  "scope": {{
    "relevant_files": ["src/utils.py"],
    "ignored_files": [],
    "reasoning": "Code style review only"
  }},
  "checks": [],
  "skips": [],
  "findings": [
    {{
      "id": "STYLE-001",
      "title": "Line too long",
      "severity": "warning",
      "confidence": "medium",
      "owner": "style",
      "estimate": "S",
      "evidence": "Line 45 exceeds 100 characters",
      "risk": "Code readability may suffer",
      "recommendation": "Split line across multiple lines"
    }}
  ],
   "merge_gate": {{
     "decision": "approve_with_warnings",
     "must_fix": [],
     "should_fix": ["STYLE-001"],
     "notes_for_coding_agent": ["Style review complete"]
   }}
 }}"""


class DelegationRequest(pd.BaseModel):
    """Structured delegation request from a review agent.

    Represents a request to delegate additional analysis to another agent.
    Agents can include these in their output's merge_gate.notes_for_coding_agent
    to request follow-up analysis from specialized subagents.
    """

    agent: str = pd.Field(
        ...,
        description="Name of the agent to delegate to (must be in allowlist)",
    )
    reason: str = pd.Field(
        ...,
        description="Why this delegation is needed",
    )
    priority: Literal["high", "medium", "low"] = pd.Field(
        default="medium",
        description="Priority of this delegation request",
    )
    constraints: Dict[str, Any] = pd.Field(
        default_factory=dict,
        description="Constraints for the delegated agent (e.g., file patterns, scope)",
    )
    expected_outputs: List[str] = pd.Field(
        default_factory=list,
        description="List of expected outputs from the delegated agent",
    )

    model_config = pd.ConfigDict(extra="forbid")


class DelegationResult(pd.BaseModel):
    """Result of parsing delegation requests from review outputs.

    Contains the list of valid delegation requests and any validation errors.
    """

    valid: bool = pd.Field(
        ...,
        description="True if all delegation requests are valid",
    )
    requests: List[DelegationRequest] = pd.Field(
        default_factory=list,
        description="List of parsed and validated delegation requests",
    )
    skip_reason: Optional[str] = pd.Field(
        default=None,
        description="Reason why delegation was skipped (if invalid)",
    )

    model_config = pd.ConfigDict(extra="forbid")


# Allowlist of agents that can be delegated to
# This prevents arbitrary agent execution and provides safety
ALLOWLISTED_DELEGATION_AGENTS = {
    "security",
    "architecture",
    "performance",
    "testing",
    "documentation",
    "dependency",
}


@dataclass
class BudgetConfig:
    """Configuration for delegation and execution budgets.

    Enforces hard caps on follow-up count and fan-out to prevent
    unbounded delegation loops and resource exhaustion.
    """

    max_delegated_actions: int = 30
    max_concurrency: int = 4
    timeout_seconds: int = 300


@dataclass
class BudgetTracker:
    """Tracks budget usage for delegation and execution.

    Prevents unbounded delegation and enforces concurrency limits.
    """

    config: BudgetConfig
    delegated_action_count: int = 0
    active_commands: int = 0

    def can_delegate_action(self) -> bool:
        """Check if another delegated action can be scheduled."""
        return self.delegated_action_count < self.config.max_delegated_actions

    def record_delegated_action(self) -> None:
        """Record that a delegated action was scheduled."""
        self.delegated_action_count += 1

    def can_execute_command(self) -> bool:
        """Check if another command can be executed within concurrency limit."""
        return self.active_commands < self.config.max_concurrency

    def add_active_command(self) -> None:
        """Track that a command has started execution."""
        self.active_commands += 1

    def remove_active_command(self) -> None:
        """Mark a command as complete."""
        self.active_commands = max(0, self.active_commands - 1)


def parse_delegation_requests(
    review_outputs: List[ReviewOutput],
    allowed_agents: Optional[set[str]] = None,
) -> DelegationResult:
    """Extract and validate delegation requests from review outputs.

    Parses delegation requests from merge_gate.notes_for_coding_agent in ReviewOutput.
    Delegation requests are expected to be JSON-encoded strings with the format:
    "delegate: <json>"

    Args:
        review_outputs: List of ReviewOutput objects to parse
        allowed_agents: Set of allowed agent names (defaults to ALLOWLISTED_DELEGATION_AGENTS)

    Returns:
        DelegationResult with valid status, list of requests, and skip reason if invalid

    Examples:
        >>> notes = ["delegate: {\"agent\": \"security\", \"reason\": \"Found potential vulnerability\"}"]
        >>> output = ReviewOutput(..., merge_gate=MergeGate(..., notes_for_coding_agent=notes))
        >>> result = parse_delegation_requests([output])
        >>> assert result.valid is True
        >>> assert len(result.requests) == 1
    """
    if allowed_agents is None:
        allowed_agents = ALLOWLISTED_DELEGATION_AGENTS

    all_requests: List[DelegationRequest] = []

    for output in review_outputs:
        notes = output.merge_gate.notes_for_coding_agent

        for note in notes:
            # Look for delegation requests in notes
            # Pattern: "delegate: {json}" or "delegation: {json}"
            match = re.match(r"^(?:delegate|delegation):\s*(.+)$", note.strip(), re.IGNORECASE)

            if not match:
                continue

            json_str = match.group(1)

            try:
                # Parse JSON
                data = json.loads(json_str)

                # Validate required fields
                if "agent" not in data:
                    return DelegationResult(
                        valid=False,
                        requests=[],
                        skip_reason=f"Delegation request missing 'agent' field: {json_str}",
                    )

                if "reason" not in data:
                    return DelegationResult(
                        valid=False,
                        requests=[],
                        skip_reason=f"Delegation request missing 'reason' field: {json_str}",
                    )

                # Check agent allowlist
                agent_name = data["agent"]
                if agent_name not in allowed_agents:
                    return DelegationResult(
                        valid=False,
                        requests=[],
                        skip_reason=f"Delegation to unknown/forbidden agent '{agent_name}'. Allowed agents: {sorted(allowed_agents)}",
                    )

                # Create DelegationRequest with validation
                request = DelegationRequest(**data)
                all_requests.append(request)

            except json.JSONDecodeError as e:
                return DelegationResult(
                    valid=False,
                    requests=[],
                    skip_reason=f"Invalid JSON in delegation request: {e}. Input: {json_str}",
                )
            except pd.ValidationError as e:
                return DelegationResult(
                    valid=False,
                    requests=[],
                    skip_reason=f"Validation error in delegation request: {e}. Input: {json_str}",
                )
            except Exception as e:
                return DelegationResult(
                    valid=False,
                    requests=[],
                    skip_reason=f"Unexpected error parsing delegation request: {e}. Input: {json_str}",
                )

    # Sort requests by priority (high -> medium -> low) for deterministic ordering
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_requests.sort(key=lambda r: priority_order.get(r.priority, 1))

    return DelegationResult(
        valid=True,
        requests=all_requests,
        skip_reason=None,
    )
