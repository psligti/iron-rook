"""Pydantic contracts for review agent output."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Literal, Dict, Any, Optional
from dataclasses import dataclass
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
    expected_signal: Optional[str] = None

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
    suggested_patch: Optional[str] = None
    provenance: Optional[Dict[str, str]] = pd.Field(
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


# ============================================================================


class PullRequestMetadata(pd.BaseModel):
    """Metadata about the pull request being reviewed."""

    id: str
    title: str
    base_branch: str
    head_branch: str
    author: str
    url: Optional[str] = None

    model_config = pd.ConfigDict(extra="forbid")


class PRChange(pd.BaseModel):
    """Represents a single file change in the PR."""

    path: str = pd.Field(
        ...,
        description="Path to the changed file relative to repo root",
    )
    change_type: Literal["added", "modified", "deleted", "renamed"] = pd.Field(
        ...,
        description="Type of change made to the file",
    )
    diff_summary: str = pd.Field(
        ...,
        description="Human-readable summary of what changed in the file",
    )
    risk_hints: List[str] = pd.Field(
        default_factory=list,
        description="Optional hints about risk categories (e.g., 'auth', 'tokens', 'sql')",
    )

    model_config = pd.ConfigDict(extra="forbid")


class PRMetadata(pd.BaseModel):
    """Additional metadata about the PR and repository."""

    repo: str
    commit_range: str
    created_at: str

    model_config = pd.ConfigDict(extra="forbid")


class PRConstraints(pd.BaseModel):
    """Constraints and limits for the security review."""

    tool_budget: int = pd.Field(
        default=25,
        description="Maximum number of tool calls allowed",
    )
    max_subagents: int = pd.Field(
        default=5,
        description="Maximum number of subagents that can be dispatched",
    )
    max_iterations: int = pd.Field(
        default=4,
        description="Maximum number of FSM iterations (phases)",
    )

    model_config = pd.ConfigDict(extra="forbid")


class PullRequestChangeList(pd.BaseModel):
    """Input contract for PR Security Review Agent - represents a PR change list.

    This is the primary input to the Security Review Agent FSM.
    Contains PR metadata, changed files, and constraints for execution.
    """

    pr: PullRequestMetadata
    changes: List[PRChange]
    metadata: PRMetadata
    constraints: PRConstraints = pd.Field(default_factory=PRConstraints)

    model_config = pd.ConfigDict(extra="forbid")


class SecurityTodoScope(pd.BaseModel):
    """Scope definition for a security TODO item."""

    paths: List[str] = pd.Field(
        ...,
        description="List of file paths to analyze for this TODO",
    )
    symbols: List[str] = pd.Field(
        default_factory=list,
        description="Specific function/class/symbol names to investigate",
    )
    related_paths: List[str] = pd.Field(
        default_factory=list,
        description="Additional paths to check for related context",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SecurityTodoDelegation(pd.BaseModel):
    """Delegation specification for a security TODO."""

    subagent_type: str = pd.Field(
        ...,
        description="Type of subagent to delegate to (e.g., 'auth_security', 'injection_security')",
    )
    goal: str = pd.Field(
        ...,
        description="Clear goal statement for the delegated subagent",
    )
    expected_artifacts: List[str] = pd.Field(
        default_factory=list,
        description="Expected output artifacts from the subagent",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SecurityTodo(pd.BaseModel):
    """A structured TODO item for security analysis.

    Represents a specific security check to be performed, with scope,
    priority, acceptance criteria, and optional delegation to specialized subagent.
    """

    todo_id: str = pd.Field(
        ...,
        description="Unique identifier for this TODO (e.g., 'SEC-001')",
    )
    title: str = pd.Field(
        ...,
        description="Human-readable title of the security check",
    )
    scope: SecurityTodoScope = pd.Field(
        ...,
        description="Files and symbols to analyze for this TODO",
    )
    priority: Literal["high", "medium", "low"] = pd.Field(
        ...,
        description="Priority level for this security check",
    )
    risk_category: str = pd.Field(
        ...,
        description="Risk category (e.g., 'authn_authz', 'injection', 'crypto', 'data_exposure')",
    )
    acceptance_criteria: List[str] = pd.Field(
        ...,
        description="List of criteria that must be satisfied for this TODO to be 'done'",
    )
    evidence_required: List[str] = pd.Field(
        default_factory=list,
        description="Types of evidence required (e.g., 'file_refs', 'config_refs', 'tests_or_reasoning')",
    )
    delegation: Optional[SecurityTodoDelegation] = pd.Field(
        default=None,
        description="If set, delegates this TODO to a specialized subagent",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SubagentRequest(pd.BaseModel):
    """Request object for dispatching a subagent."""

    todo_id: str = pd.Field(
        ...,
        description="ID of the TODO this request is for",
    )
    subagent_type: str = pd.Field(
        ...,
        description="Type of subagent to execute",
    )
    goal: str = pd.Field(
        ...,
        description="Goal for the subagent execution",
    )
    scope: SecurityTodoScope = pd.Field(
        ...,
        description="Scope of analysis for the subagent",
    )
    evidence_required: List[str] = pd.Field(
        default_factory=list,
        description="Evidence types the subagent must provide",
    )
    limits: Dict[str, Any] = pd.Field(
        default_factory=dict,
        description="Budget/iteration limits for this subagent",
    )

    model_config = pd.ConfigDict(extra="forbid")


class EvidenceRef(pd.BaseModel):
    """A reference to evidence (file, diff, etc.)."""

    type: Literal["file_ref", "diff_ref", "config_ref", "tool_output", "test_result"] = pd.Field(
        ...,
        description="Type of evidence reference",
    )
    path: str = pd.Field(
        ...,
        description="File path or identifier for the evidence",
    )
    lines: Optional[str] = pd.Field(
        default=None,
        description="Line numbers or range (e.g., '88-121')",
    )
    excerpt: Optional[str] = pd.Field(
        default=None,
        description="Brief excerpt from the evidence",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SecurityFinding(pd.BaseModel):
    """A security vulnerability or issue discovered during review."""

    severity: Literal["critical", "high", "medium", "low", "info"] = pd.Field(
        ...,
        description="Severity level of this finding",
    )
    title: str = pd.Field(
        ...,
        description="Concise title of the finding",
    )
    description: str = pd.Field(
        ...,
        description="Detailed description of the security issue",
    )
    evidence: List[EvidenceRef] = pd.Field(
        ...,
        description="Evidence supporting this finding",
    )
    recommendations: List[str] = pd.Field(
        default_factory=list,
        description="Recommended actions to address the finding",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SubagentFSMState(pd.BaseModel):
    """FSM state tracking for a subagent execution."""

    phase: Literal[
        "intake", "evidence_gather", "analyze", "recommend", "report", "done", "blocked"
    ] = pd.Field(..., description="Current phase in the subagent FSM")
    iterations: int = pd.Field(
        default=0,
        description="Number of iterations performed",
    )
    stop_reason: Optional[str] = pd.Field(
        default=None,
        description="Reason FSM stopped (e.g., 'done', 'blocked', 'budget')",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SubagentResult(pd.BaseModel):
    """Result from a delegated subagent execution.

    Contains findings, evidence, FSM state, and confidence level.
    """

    todo_id: str = pd.Field(
        ...,
        description="ID of the TODO this result is for",
    )
    subagent_type: str = pd.Field(
        ...,
        description="Type of subagent that produced this result",
    )
    fsm: SubagentFSMState = pd.Field(
        ...,
        description="FSM state tracking for the subagent execution",
    )
    summary: str = pd.Field(
        ...,
        description="Brief summary of the subagent's analysis",
    )
    findings: List[SecurityFinding] = pd.Field(
        default_factory=list,
        description="Security findings discovered by the subagent",
    )
    evidence: List[EvidenceRef] = pd.Field(
        default_factory=list,
        description="Evidence collected by the subagent",
    )
    recommendations: List[str] = pd.Field(
        default_factory=list,
        description="Recommendations from the subagent",
    )
    confidence: float = pd.Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence level (0.0 to 1.0)",
    )
    needs_more: List[str] = pd.Field(
        default_factory=list,
        description="If blocked, list of what's needed to continue",
    )

    model_config = pd.ConfigDict(extra="forbid")


class TodoStatus(pd.BaseModel):
    """Status tracking for a TODO item."""

    todo_id: str = pd.Field(..., description="ID of the TODO")
    status: Literal["pending", "in_progress", "done", "blocked", "deferred"] = pd.Field(
        ...,
        description="Current status of the TODO",
    )
    subagent_type: Optional[str] = pd.Field(
        default=None,
        description="If delegated, type of subagent handling it",
    )

    model_config = pd.ConfigDict(extra="forbid")


class FSMState(pd.BaseModel):
    """FSM state tracking for the Security Agent."""

    phase: str = pd.Field(..., description="Current FSM phase")
    iterations: int = pd.Field(
        default=0,
        description="Number of iterations through the FSM",
    )
    stop_reason: Optional[str] = pd.Field(
        default=None,
        description="Reason FSM stopped (if not 'done')",
    )
    tool_calls_used: int = pd.Field(
        default=0,
        description="Total tool calls used in this session",
    )
    subagents_used: int = pd.Field(
        default=0,
        description="Total subagents dispatched in this session",
    )

    model_config = pd.ConfigDict(extra="forbid")


class RiskAssessment(pd.BaseModel):
    """Overall risk assessment for the PR."""

    overall: Literal["critical", "high", "medium", "low"] = pd.Field(
        ...,
        description="Overall risk level for the PR",
    )
    rationale: str = pd.Field(
        ...,
        description="Explanation of the overall risk assessment",
    )
    areas_touched: List[str] = pd.Field(
        default_factory=list,
        description="Security areas touched by changes",
    )

    model_config = pd.ConfigDict(extra="forbid")


class Action(pd.BaseModel):
    """An action to take based on review findings."""

    type: Literal["code_change", "telemetry", "config_change", "test_addition", "documentation"] = (
        pd.Field(..., description="Type of action required")
    )
    description: str = pd.Field(
        ...,
        description="Description of the action",
    )

    model_config = pd.ConfigDict(extra="forbid")


class SecurityReviewReport(pd.BaseModel):
    """Final consolidated security review report.

    This is the complete output from the FSM Security Agent,
    containing all findings, risk assessment, and actions.
    """

    agent: Dict[str, str] = pd.Field(
        ...,
        description="Agent metadata (name, version)",
    )
    pr: Dict[str, str] = pd.Field(
        ...,
        description="PR metadata (id, title)",
    )
    fsm: FSMState = pd.Field(
        ...,
        description="FSM state and execution metadata",
    )
    todos: List[TodoStatus] = pd.Field(
        ...,
        description="Status of all TODOs created during the review",
    )
    findings: Dict[str, List[SecurityFinding]] = pd.Field(
        ...,
        description="Findings grouped by severity (critical, high, medium, low, info)",
    )
    risk_assessment: RiskAssessment = pd.Field(
        ...,
        description="Overall risk assessment for the PR",
    )
    evidence_index: List[EvidenceRef] = pd.Field(
        ...,
        description="Index of all evidence collected during review",
    )
    actions: Dict[str, List[Action]] = pd.Field(
        ...,
        description="Required and suggested actions grouped by category",
    )
    confidence: float = pd.Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the review (0.0 to 1.0)",
    )
    missing_information: List[str] = pd.Field(
        default_factory=list,
        description="Any missing information that prevented complete analysis",
    )

    model_config = pd.ConfigDict(extra="forbid")


class PhaseOutput(pd.BaseModel):
    """Output from a single FSM phase.

    Used to track progress and validate phase transitions.
    """

    phase: Literal["intake", "plan_todos", "delegate", "collect", "consolidate", "evaluate"] = (
        pd.Field(..., description="Which phase this output is from")
    )
    data: Dict[str, Any] = pd.Field(
        default_factory=dict,
        description="Phase-specific data (e.g., todos list, subagent requests)",
    )
    next_phase_request: Optional[
        Literal[
            "plan_todos",
            "delegate",
            "collect",
            "consolidate",
            "evaluate",
            "done",
            "stopped_budget",
            "stopped_human",
            "stopped_retry_exhausted",
        ]
    ] = pd.Field(
        default=None,
        description="Suggested next phase",
    )

    model_config = pd.ConfigDict(extra="forbid")
