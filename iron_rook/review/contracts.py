"""Pydantic contracts for review agent output."""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Literal, Dict, Optional, Any
import pydantic as pd


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
            if not result:
                continue
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
                f.severity == "blocking" for result in results if result for f in result.findings
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


class ThinkingStep(pd.BaseModel):
    kind: Literal["transition", "tool", "delegate", "gate", "stop"]
    why: str
    evidence: List[str] = pd.Field(default_factory=list)
    next: Optional[str] = None
    confidence: Literal["low", "medium", "high"] = "medium"

    model_config = pd.ConfigDict(extra="ignore")


class ThinkingFrame(pd.BaseModel):
    state: str
    ts: str = pd.Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    goals: List[str] = pd.Field(default_factory=list)
    checks: List[str] = pd.Field(default_factory=list)
    risks: List[str] = pd.Field(default_factory=list)
    steps: List[ThinkingStep] = pd.Field(default_factory=list)
    decision: str

    model_config = pd.ConfigDict(extra="ignore")


class RunLog(pd.BaseModel):
    """Accumulator for thinking frames during FSM execution.

    Internal accumulator that collects ThinkingFrame objects to track
    the agent's reasoning process through FSM phases.

    Methods:
        add: Append a ThinkingFrame to the frames list
    """

    frames: List[ThinkingFrame] = pd.Field(
        default_factory=list,
        description="List of thinking frames collected during FSM execution",
    )

    def add(self, frame: ThinkingFrame) -> None:
        """Append a thinking frame to the frames list.

        Args:
            frame: ThinkingFrame to add to the log
        """
        self.frames.append(frame)

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
    thinking_log: Optional[RunLog] = None

    model_config = pd.ConfigDict(extra="ignore")


class ReviewInputs(pd.BaseModel):
    repo_root: str
    base_ref: str
    head_ref: str
    pr_title: str = ""
    pr_description: str = ""
    ticket_description: str = ""
    include_optional: bool = False

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


# ============================================================================
# Security FSM Phase Output Models
# ============================================================================


class IntakePhaseOutput(pd.BaseModel):
    phase: Literal["intake"]
    data: "IntakePhaseData"
    next_phase_request: Literal["plan"]


class IntakePhaseData(pd.BaseModel):
    summary: str
    risk_hypotheses: List[str] = pd.Field(default_factory=list)
    questions: List[str] = pd.Field(default_factory=list)


class PlanPhaseOutput(pd.BaseModel):
    phase: Literal["plan"]
    data: "PlanPhaseData"
    next_phase_request: Literal["act"]


class SecurityTodo(pd.BaseModel):
    id: str
    description: str
    priority: Literal["high", "medium", "low"]
    risk_category: str
    acceptance_criteria: str
    evidence_required: List[str] = pd.Field(default_factory=list)


class PlanPhaseData(pd.BaseModel):
    todos: List[SecurityTodo] = pd.Field(default_factory=list)
    delegation_plan: Dict[str, str] = pd.Field(default_factory=dict)
    tools_considered: List[str] = pd.Field(default_factory=list)
    tools_chosen: List[str] = pd.Field(default_factory=list)
    why: str


PlanTodosPhaseOutput = PlanPhaseOutput
PlanTodosPhaseData = PlanPhaseData


class ActPhaseOutput(pd.BaseModel):
    """Output model for ACT phase."""

    phase: Literal["act"]
    data: "ActPhaseData"
    next_phase_request: Literal["synthesize"]


class ActPhaseData(pd.BaseModel):
    """Data model for ACT phase."""

    tool_results: Dict[str, str] = pd.Field(default_factory=dict)
    findings_summary: List[str] = pd.Field(default_factory=list)
    why: str


class SynthesizePhaseOutput(pd.BaseModel):
    """Output model for SYNTHESIZE phase."""

    phase: Literal["synthesize"]
    data: "SynthesizePhaseData"
    next_phase_request: Literal["check"]


class SynthesizePhaseData(pd.BaseModel):
    """Data model for SYNTHESIZE phase."""

    findings: List[Dict[str, str]] = pd.Field(default_factory=list)
    evidence_index: List[str] = pd.Field(default_factory=list)
    why: str


class CheckPhaseOutput(pd.BaseModel):
    """Output model for CHECK phase."""

    phase: Literal["check"]
    data: "CheckPhaseData"
    next_phase_request: Literal["done"]


class CheckPhaseData(pd.BaseModel):
    gates: Dict[str, bool] = pd.Field(default_factory=dict)
    confidence: float = pd.Field(ge=0.0, le=1.0)
    why: str


class EvaluatePhaseOutput(pd.BaseModel):
    phase: Literal["evaluate"]
    data: "EvaluatePhaseData"
    next_phase_request: Literal["done"]


class EvaluateFinding(pd.BaseModel):
    """Finding in evaluation phase."""

    severity: Literal["critical", "high", "medium", "low"]
    title: str
    description: str
    evidence: List[dict] = pd.Field(default_factory=list)
    recommendations: List[str] = pd.Field(default_factory=list)


class RiskAssessment(pd.BaseModel):
    """Risk assessment model."""

    overall: Literal["critical", "high", "medium", "low"]
    rationale: str
    areas_touched: List[str] = pd.Field(default_factory=list)


class EvaluatePhaseData(pd.BaseModel):
    """Data model for EVALUATE phase."""

    findings: Dict[str, List[EvaluateFinding]] = pd.Field(default_factory=dict)
    risk_assessment: RiskAssessment
    evidence_index: List[dict] = pd.Field(default_factory=list)
    actions: Dict[str, List[str]] = pd.Field(default_factory=dict)
    confidence: float = pd.Field(ge=0.0, le=1.0)
    missing_information: List[str] = pd.Field(default_factory=list)


def get_phase_output_schema(phase: str) -> str:
    """Return JSON schema for the specified phase output as a string for inclusion in prompts.

    Args:
        phase: Phase name (e.g., "intake", "plan_todos", "act", "synthesize", "check")

    Returns:
        JSON schema string with explicit type information

    Raises:
        ValueError: If phase name is not recognized
    """
    phase_schemas = {
        "intake": IntakePhaseOutput,
        "plan": PlanPhaseOutput,
        "act": ActPhaseOutput,
        "synthesize": SynthesizePhaseOutput,
        "check": CheckPhaseOutput,
        "evaluate": EvaluatePhaseOutput,
    }

    if phase not in phase_schemas:
        raise ValueError(f"Unknown phase: {phase}. Valid phases: {list(phase_schemas.keys())}")

    model = phase_schemas[phase]
    return f"""You MUST output valid JSON matching this exact schema. The output is parsed directly by a Pydantic model with no post-processing:

{model.model_json_schema()}

CRITICAL RULES:
- Include ALL required fields
- NEVER include extra fields not in this schema (will cause validation errors)
- Empty arrays are allowed: [], null values are allowed only where specified
- Return ONLY a JSON object, no other text, no markdown code blocks
- Output must be valid JSON that passes Pydantic validation as-is

EXAMPLE VALID OUTPUT:
{model.model_json_schema()}
"""


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
