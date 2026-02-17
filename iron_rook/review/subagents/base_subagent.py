"""Base class for dynamic ReAct-style subagents with FSM loop.

This module provides BaseDynamicSubagent, an abstract base class for subagents
that execute a 5-phase ReAct-style FSM loop:
- INTAKE: Capture intent, acceptance criteria, evidence requirements
- PLAN: Select tools and analysis approach
- ACT: Execute tools and collect evidence
- SYNTHESIZE: Analyze results, check against intent, decide next step
- DONE: Return findings with evidence

The FSM loops: INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)

Stop conditions:
- Max iterations reached (MAX_ITERATIONS = 10)
- Goal met (SYNTHESIZE confirms intent satisfied)
- Stagnation (no new findings for STAGNATION_THRESHOLD iterations)
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Dict, List
import logging

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import ReviewOutput

logger = logging.getLogger(__name__)


# FSM transition map for ReAct-style subagent loop
REACT_FSM_TRANSITIONS: Dict[str, List[str]] = {
    "intake": ["plan"],
    "plan": ["act"],
    "act": ["synthesize"],
    "synthesize": ["plan", "done"],
    "done": [],
}

# Stop condition constants
MAX_ITERATIONS = 10
STAGNATION_THRESHOLD = 2


class BaseDynamicSubagent(BaseReviewerAgent):
    """Abstract base class for dynamic ReAct-style subagents with FSM loop.

    Provides the infrastructure for subagents that execute a multi-phase
    FSM loop with tool execution, evidence collection, and convergence
    detection.

    Subclasses must implement:
    - get_domain_tools(): Return list of tool names this subagent can use
    - get_domain_prompt(): Return domain-specific prompt instructions

    The FSM loop is:
        INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)

    Stop conditions:
    - MAX_ITERATIONS (10) reached
    - Goal achieved (detected in SYNTHESIZE phase)
    - Stagnation (no new findings for STAGNATION_THRESHOLD iterations)

    Key patterns from SecuritySubagent:
    - Evidence and findings accumulate across iterations
    - Stagnation detection: all(count == 0) or >= 3 iterations with findings
    - BIAS TOWARD DONE prevents infinite loops
    """

    # FSM transition map - subclasses can override if needed
    FSM_TRANSITIONS: Dict[str, List[str]] = REACT_FSM_TRANSITIONS

    def __init__(
        self,
        task: Dict[str, Any],
        verifier=None,
        max_retries: int = 3,
        agent_runtime=None,
        repo_root: str = "",
    ) -> None:
        """Initialize the dynamic subagent.

        Args:
            task: Task definition dict with keys:
                - todo_id: Unique task identifier
                - title: Task title/description
                - scope: Scope dict with paths, file patterns
                - acceptance_criteria: List of criteria for task completion
                - evidence_required: List of evidence types needed
            verifier: FindingsVerifier strategy instance
            max_retries: Maximum retry attempts for failed operations
            agent_runtime: Optional AgentRuntime for tool execution
            repo_root: Repository root path
        """
        super().__init__(verifier=verifier, max_retries=max_retries, agent_runtime=agent_runtime)

        self._task = task
        self._current_phase = "intake"
        self._phase_outputs: Dict[str, Any] = {}
        self._thinking_log: List[Any] = []

        # Iteration tracking
        self._iteration_count = 0

        # Accumulated results across iterations
        self._accumulated_evidence: List[Dict[str, Any]] = []
        self._accumulated_findings: List[Dict[str, Any]] = []
        self._findings_per_iteration: List[int] = []

        # Original intent from INTAKE phase (for goal checking)
        self._original_intent: Dict[str, Any] = {}

        # Context data for phase execution
        self._context_data: Dict[str, Any] = {}

        # Repository root for file operations
        self._repo_root = repo_root

    # ========================================================================
    # Abstract Methods - Subclasses MUST implement
    # ========================================================================

    @abstractmethod
    def get_domain_tools(self) -> List[str]:
        """Get list of domain-specific tools this subagent can use.

        Returns:
            List of tool names (e.g., ["grep", "bandit", "semgrep"])

        Example:
            >>> class SecuritySubagent(BaseDynamicSubagent):
            ...     def get_domain_tools(self) -> List[str]:
            ...         return ["grep", "bandit", "semgrep", "read"]
        """
        pass

    @abstractmethod
    def get_domain_prompt(self) -> str:
        """Get domain-specific prompt instructions.

        Returns:
            Domain-specific prompt section to include in system prompt

        Example:
            >>> class SecuritySubagent(BaseDynamicSubagent):
            ...     def get_domain_prompt(self) -> str:
            ...         return "Focus on finding evidence-based security findings..."
        """
        pass

    # ========================================================================
    # Abstract Methods from BaseReviewerAgent
    # ========================================================================

    def get_agent_name(self) -> str:
        """Get agent identifier based on task ID."""
        return f"dynamic_subagent_{self._task.get('todo_id', 'unknown')}"

    def get_allowed_tools(self) -> List[str]:
        """Get allowed tools - delegates to get_domain_tools()."""
        return self.get_domain_tools()

    def get_relevant_file_patterns(self) -> List[str]:
        """Get relevant file patterns from task scope."""
        scope = self._task.get("scope") or {}
        paths = scope.get("paths", []) if isinstance(scope, dict) else scope
        return paths if isinstance(paths, list) else [paths] if paths else ["**/*"]

    # ========================================================================
    # FSM Loop Infrastructure
    # ========================================================================

    async def _run_subagent_fsm(self, context: ReviewContext) -> ReviewOutput:
        """Execute the 5-phase ReAct-style FSM loop.

        This is the main FSM loop that drives the subagent through phases:
        INTAKE → PLAN → ACT → SYNTHESIZE → (PLAN or DONE)

        The loop continues until:
        - Reaches DONE phase
        - Max iterations exceeded
        - Stagnation detected

        Args:
            context: ReviewContext with repository info and changes

        Returns:
            ReviewOutput with findings, evidence, and merge decision

        Raises:
            ValueError: If invalid phase transition attempted
        """
        # Reset state for fresh run
        self._phase_outputs = {}
        self._current_phase = "intake"
        self._iteration_count = 0
        self._accumulated_evidence = []
        self._accumulated_findings = []
        self._findings_per_iteration = []
        self._original_intent = {}
        self._context_data = {"repo_root": context.repo_root}

        task_title = self._task.get("title", "unknown")
        logger.info(f"[{self.get_agent_name()}] Starting task: {task_title}")

        try:
            while self._current_phase != "done":
                # INTAKE phase - only runs once at start
                if self._current_phase == "intake":
                    logger.info(f"[{self.get_agent_name()}] === Starting INTAKE phase ===")
                    output = await self._run_intake_phase(context)
                    self._phase_outputs["intake"] = output
                    self._original_intent = output.get("data", {})
                    next_phase = output.get("next_phase_request", "plan")
                    logger.info(
                        f"[{self.get_agent_name()}] INTAKE completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                # PLAN phase - runs at start of each iteration
                elif self._current_phase == "plan":
                    self._iteration_count += 1
                    logger.info(
                        f"[{self.get_agent_name()}] === Starting PLAN phase "
                        f"(iteration {self._iteration_count}/{MAX_ITERATIONS}) ==="
                    )

                    # Check max iterations BEFORE running phase
                    if self._iteration_count > MAX_ITERATIONS:
                        logger.warning(
                            f"[{self.get_agent_name()}] Max iterations ({MAX_ITERATIONS}) "
                            "reached, forcing done"
                        )
                        self._current_phase = "done"
                        break

                    output = await self._run_plan_phase(context)
                    self._phase_outputs["plan"] = output
                    next_phase = output.get("next_phase_request", "act")
                    logger.info(
                        f"[{self.get_agent_name()}] PLAN completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                # ACT phase - executes tools and collects evidence
                elif self._current_phase == "act":
                    logger.info(
                        f"[{self.get_agent_name()}] === Starting ACT phase "
                        f"(iteration {self._iteration_count}) ==="
                    )
                    output = await self._run_act_phase(context)
                    self._phase_outputs["act"] = output

                    # Accumulate evidence and findings
                    new_evidence = output.get("data", {}).get("evidence_collected", [])
                    new_findings = output.get("data", {}).get("findings", [])
                    self._accumulated_evidence.extend(new_evidence)
                    self._accumulated_findings.extend(new_findings)
                    self._findings_per_iteration.append(len(new_findings))

                    # Store tool results in context
                    self._context_data["tool_results"] = output.get("data", {}).get(
                        "tool_results", {}
                    )

                    next_phase = output.get("next_phase_request", "synthesize")
                    logger.info(
                        f"[{self.get_agent_name()}] ACT completed, transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                # SYNTHESIZE phase - analyzes results and decides next step
                elif self._current_phase == "synthesize":
                    logger.info(
                        f"[{self.get_agent_name()}] === Starting SYNTHESIZE phase "
                        f"(iteration {self._iteration_count}) ==="
                    )
                    output = await self._run_synthesize_phase(context)
                    self._phase_outputs["synthesize"] = output
                    next_phase = output.get("next_phase_request", "done")

                    # Apply stop conditions - only override if LLM hasn't explicitly chosen
                    if next_phase in ("done", "plan") and self._should_stop():
                        next_phase = "done"

                    logger.info(
                        f"[{self.get_agent_name()}] SYNTHESIZE completed, "
                        f"transitioning to {next_phase}"
                    )
                    self._transition_to_phase(next_phase)

                else:
                    raise ValueError(f"Unknown phase: {self._current_phase}")

            logger.info(
                f"[{self.get_agent_name()}] === Task completed in "
                f"{self._iteration_count} iterations ==="
            )
            return self._build_review_output(context)

        except Exception as e:
            logger.error(
                f"[{self.get_agent_name()}] === Task FAILED after "
                f"{self._iteration_count} iterations ==="
            )
            logger.error(
                f"[{self.get_agent_name()}] Error: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return self._build_error_output(context, str(e))

    def _transition_to_phase(self, next_phase: str) -> None:
        """Validate and execute phase transition.

        Args:
            next_phase: Target phase to transition to

        Raises:
            ValueError: If transition is invalid per FSM_TRANSITIONS
        """
        valid_transitions = self.FSM_TRANSITIONS.get(self._current_phase, [])
        if next_phase not in valid_transitions:
            raise ValueError(
                f"Invalid transition: {self._current_phase} -> {next_phase}. "
                f"Valid: {valid_transitions}"
            )
        logger.info(f"[{self.get_agent_name()}] Transition: {self._current_phase} -> {next_phase}")
        self._current_phase = next_phase

    # ========================================================================
    # Stop Conditions
    # ========================================================================

    def _should_stop(self) -> bool:
        """Check if subagent should stop iterating.

        Returns:
            True if any stop condition is met
        """
        if self._iteration_count >= MAX_ITERATIONS:
            logger.info(f"[{self.get_agent_name()}] Stop: max iterations reached")
            return True

        if self._check_stagnation():
            logger.info(f"[{self.get_agent_name()}] Stop: stagnation detected")
            return True

        return False

    def _check_stagnation(self) -> bool:
        """Detect when subagent is making no progress.

        Stagnation is detected when:
        1. Zero findings for STAGNATION_THRESHOLD consecutive iterations
        2. After 3+ iterations with any findings (diminishing returns)

        Returns:
            True if stagnation detected
        """
        if len(self._findings_per_iteration) < STAGNATION_THRESHOLD:
            return False

        recent = self._findings_per_iteration[-STAGNATION_THRESHOLD:]
        all_zero = all(count == 0 for count in recent)
        has_findings = sum(recent) > 0
        enough_iterations = len(self._findings_per_iteration) >= 3

        # Stagnation type 1: Zero findings for multiple iterations
        if all_zero:
            logger.info(
                f"[{self.get_agent_name()}] Stagnation: zero findings for "
                f"{STAGNATION_THRESHOLD} iterations"
            )
            return True

        # Stagnation type 2: After 3+ iterations with findings, force done
        # (diminishing returns - more iterations rarely help for search/verification tasks)
        if enough_iterations and has_findings:
            logger.info(
                f"[{self.get_agent_name()}] Stagnation: 3+ iterations with findings, forcing done"
            )
            return True

        return False

    # ========================================================================
    # Phase Methods - Subclasses override these
    # ========================================================================

    async def _run_intake_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run INTAKE phase - capture intent and acceptance criteria.

        Args:
            context: ReviewContext with repository info

        Returns:
            Dict with phase output including:
            - data: Intent, acceptance criteria, evidence requirements
            - next_phase_request: "plan"
        """
        raise NotImplementedError("Subclasses must implement _run_intake_phase")

    async def _run_plan_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run PLAN phase - select tools and analysis approach.

        Args:
            context: ReviewContext with repository info

        Returns:
            Dict with phase output including:
            - data: Tools to use, analysis plan
            - next_phase_request: "act"
        """
        raise NotImplementedError("Subclasses must implement _run_plan_phase")

    async def _run_act_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run ACT phase - execute tools and collect evidence.

        Args:
            context: ReviewContext with repository info

        Returns:
            Dict with phase output including:
            - data: Tool results, evidence collected, findings
            - next_phase_request: "synthesize"
        """
        raise NotImplementedError("Subclasses must implement _run_act_phase")

    async def _run_synthesize_phase(self, context: ReviewContext) -> Dict[str, Any]:
        """Run SYNTHESIZE phase - analyze results and decide next step.

        Args:
            context: ReviewContext with repository info

        Returns:
            Dict with phase output including:
            - data: Analysis results, goal_achieved flag
            - next_phase_request: "plan" or "done"
        """
        raise NotImplementedError("Subclasses must implement _run_synthesize_phase")

    # ========================================================================
    # Output Building
    # ========================================================================

    def _build_review_output(self, context: ReviewContext) -> ReviewOutput:
        """Build final ReviewOutput from accumulated results.

        Args:
            context: ReviewContext with repository info

        Returns:
            ReviewOutput with findings, severity, and merge decision
        """
        raise NotImplementedError("Subclasses must implement _build_review_output")

    def _build_error_output(self, context: ReviewContext, error_message: str) -> ReviewOutput:
        """Build ReviewOutput for error case.

        Args:
            context: ReviewContext with repository info
            error_message: Error description

        Returns:
            ReviewOutput with error information
        """
        raise NotImplementedError("Subclasses must implement _build_error_output")
