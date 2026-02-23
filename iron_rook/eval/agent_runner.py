"""Custom agent runner for iron-rook reviewer agents.

This module provides a custom runner that can invoke iron-rook reviewer agents
and integrate with ash-hawk's evaluation harness.

Usage in suite YAML:
    agent:
      class: iron_rook.eval.agent_runner:IronRookRunner
      kwargs:
        reviewer: security
"""

from __future__ import annotations

import time
from typing import Any

from ash_hawk.types import (
    EvalTask,
    EvalTranscript,
    EvalOutcome,
    EvalStatus,
    FailureMode,
    TokenUsage,
)
from ash_hawk.policy import PolicyEnforcer


class IronRookRunner:
    """Runner that invokes iron-rook reviewer agents.

    This runner adapts iron-rook's reviewer agents to ash-hawk's agent runner protocol.

    Args:
        reviewer: Name of the iron-rook reviewer to use (e.g., "security", "architecture")
        provider: LLM provider for the reviewer
        model: LLM model for the reviewer
    """

    def __init__(
        self,
        reviewer: str = "security",
        provider: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> None:
        self._reviewer_name = reviewer
        self._provider = provider
        self._model = model

    def _get_provider_config(self) -> tuple[str, str]:
        """Get provider and model from dawn-kestrel settings if not specified."""
        if self._provider and self._model:
            return self._provider, self._model

        from dawn_kestrel.core.settings import get_settings

        settings = get_settings()
        account = settings.get_default_account()

        if account:
            provider = self._provider or account.provider_id.value
            model = self._model or account.model
            return provider, model

        provider = self._provider or settings.provider_default
        model = self._model or settings.model_default
        return provider, model

    async def run(
        self,
        task: EvalTask,
        policy_enforcer: PolicyEnforcer,
        config: dict[str, object],
    ) -> tuple[EvalTranscript, EvalOutcome]:
        """Run the iron-rook reviewer on the evaluation task.

        Args:
            task: The evaluation task containing the review input
            policy_enforcer: Policy enforcer for tool access control
            config: Agent configuration from the suite

        Returns:
            Tuple of (transcript, outcome)
        """
        from iron_rook.review.registry import ReviewerRegistry
        from iron_rook.review.base import ReviewContext

        start_time = time.time()

        try:
            task_input = task.input
            if not isinstance(task_input, dict):
                return (
                    EvalTranscript(
                        error_trace="Task input must be a dict",
                        duration_seconds=time.time() - start_time,
                    ),
                    EvalOutcome(
                        status=EvalStatus.ERROR,
                        failure_mode=FailureMode.VALIDATION_ERROR,
                        error_message="Task input must be a dict",
                    ),
                )

            # Handle inline code vs repo-based evaluation
            reviewer_name = task_input.get("agent", self._reviewer_name)

            if "code" in task_input:
                # Inline code mode - create temp file structure
                import tempfile
                import os

                code = task_input["code"]
                with tempfile.TemporaryDirectory() as tmpdir:
                    code_file = os.path.join(tmpdir, "code.py")
                    with open(code_file, "w") as f:
                        f.write(code)

                    diff = f"--- /dev/null\n+++ b/code.py\n@@ -0,0 +1,{len(code.splitlines())} @@\n"
                    for i, line in enumerate(code.splitlines(), 1):
                        diff += f"+{line}\n"

                    context = ReviewContext(
                        changed_files=["code.py"],
                        diff=diff,
                        repo_root=tmpdir,
                        base_ref="main",
                        head_ref="HEAD",
                    )

                    result = await self._run_reviewer(reviewer_name, context)
            else:
                # Repo-based mode
                repo_root = task_input.get("repo_root", ".")
                base_ref = task_input.get("base_ref", "main")
                head_ref = task_input.get("head_ref", "HEAD")

                import subprocess

                try:
                    diff_result = subprocess.run(
                        ["git", "-C", repo_root, "diff", f"{base_ref}...{head_ref}"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    diff = diff_result.stdout
                except subprocess.CalledProcessError as e:
                    diff = f"Error getting diff: {e.stderr}"

                try:
                    files_result = subprocess.run(
                        ["git", "-C", repo_root, "diff", "--name-only", f"{base_ref}...{head_ref}"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    changed_files = [f for f in files_result.stdout.strip().split("\n") if f]
                except subprocess.CalledProcessError:
                    changed_files = []

                context = ReviewContext(
                    changed_files=changed_files,
                    diff=diff,
                    repo_root=str(repo_root),
                    base_ref=base_ref,
                    head_ref=head_ref,
                    pr_title=task_input.get("pr_title"),
                    pr_description=task_input.get("pr_description"),
                )

                result = await self._run_reviewer(reviewer_name, context)

            duration = time.time() - start_time

            transcript = EvalTranscript(
                messages=[{"role": "user", "content": str(task_input)}],
                tool_calls=[],
                token_usage=TokenUsage(),
                cost_usd=0.0,
                duration_seconds=duration,
                agent_response=result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else str(result),
            )

            return transcript, EvalOutcome(status=EvalStatus.COMPLETED)

        except Exception as e:
            import traceback

            duration = time.time() - start_time
            return (
                EvalTranscript(
                    error_trace="".join(traceback.format_exception(type(e), e, e.__traceback__)),
                    duration_seconds=duration,
                ),
                EvalOutcome(
                    status=EvalStatus.ERROR,
                    failure_mode=FailureMode.AGENT_ERROR,
                    error_message=str(e),
                ),
            )

    async def _run_reviewer(self, reviewer_name: str, context: Any) -> Any:
        """Run the reviewer with the given context."""
        from iron_rook.review.registry import ReviewerRegistry

        reviewer_class = ReviewerRegistry.get_reviewer(reviewer_name)
        if reviewer_class is None:
            raise ValueError(f"Unknown reviewer: {reviewer_name}")

        reviewer = reviewer_class()
        return await reviewer.review(context)
