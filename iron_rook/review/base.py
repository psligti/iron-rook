"""Base ReviewerAgent abstract class for all review subagents."""
from __future__ import annotations
from typing import List
from abc import ABC, abstractmethod
from pathlib import Path
import pydantic as pd

from iron_rook.review.contracts import ReviewOutput
from iron_rook.review.verifier import FindingsVerifier


def _match_glob_pattern(file_path: str, pattern: str) -> bool:
    """Match file path against glob pattern, handling ** correctly.

    Args:
        file_path: File path to check
        pattern: Glob pattern (supports *, **, ?)

    Returns:
        True if file path matches pattern
    """
    from fnmatch import fnmatch

    path = Path(file_path)
    path_parts = list(path.parts)

    if '**' in pattern:
        parts = pattern.split('**')
        if len(parts) == 2:
            prefix = parts[0].rstrip('/')
            suffix = parts[1].lstrip('/')

            if prefix:
                prefix_parts = prefix.split('/')
                if not path_parts[:len(prefix_parts)] == prefix_parts:
                    return False
                remaining = path_parts[len(prefix_parts):]
            else:
                remaining = path_parts

            if suffix:
                suffix_parts = suffix.split('/')
                if not suffix_parts:
                    return True

                if len(remaining) >= len(suffix_parts):
                    if remaining[-len(suffix_parts):] == suffix_parts:
                        return True

                if len(suffix_parts) == 1 and remaining:
                    if fnmatch(remaining[-1], suffix_parts[0]):
                        return True
                    if fnmatch('/'.join(remaining), suffix_parts[0]):
                        return True
                return False
            return True

    return fnmatch(str(path), pattern)


class ReviewContext(pd.BaseModel):
    """Context data passed to reviewer agents."""

    changed_files: List[str]
    diff: str
    repo_root: str
    base_ref: str | None = None
    head_ref: str | None = None
    pr_title: str | None = None
    pr_description: str | None = None

    model_config = pd.ConfigDict(extra="forbid")


class BaseReviewerAgent(ABC):
    """Abstract base class for all review subagents.

    All specialized reviewers must inherit from this class and implement
    the required abstract methods. This ensures consistent interface across
    all review agents.
    """

    def __init__(self, verifier: FindingsVerifier | None = None):
        """Initialize base reviewer with optional verifier strategy.

        Args:
            verifier: FindingsVerifier strategy instance. If None, uses
                GrepFindingsVerifier by default.
        """
        from iron_rook.review.verifier import GrepFindingsVerifier

        self._verifier = verifier or GrepFindingsVerifier()

    @abstractmethod
    async def review(self, context: ReviewContext) -> ReviewOutput:
        """Perform review on given context.

        Args:
            context: ReviewContext containing changed files, diff, and metadata

        Returns:
            ReviewOutput with findings, severity, and merge gate decision
        """
        pass

    @abstractmethod
    def get_agent_name(self) -> str:
        """Get agent identifier."""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get system prompt for this reviewer agent.

        Returns:
            System prompt string for LLM
        """
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this reviewer agent.

        Returns:
            System prompt string for LLM
        """
        pass

    @abstractmethod
    def get_relevant_file_patterns(self) -> List[str]:
        """Get file patterns this reviewer is relevant to.

        Returns:
            List of glob patterns (e.g., ["*.py", "src/**/*.py"])
        """
        pass

    @abstractmethod
    def get_allowed_tools(self) -> List[str]:
        """Get allowed tool/command prefixes for this reviewer.

        Returns:
            List of command/tool prefixes this reviewer may propose in checks
        """
        pass

    def is_relevant_to_changes(self, changed_files: List[str]) -> bool:
        """Check if this reviewer is relevant to the given changed files.

        Args:
            changed_files: List of changed file paths

        Returns:
            True if any changed file matches the relevant patterns
        """
        patterns = self.get_relevant_file_patterns()
        if not patterns:
            return False

        for file_path in changed_files:
            for pattern in patterns:
                try:
                    if _match_glob_pattern(file_path, pattern):
                        return True
                except ValueError:
                    continue
        return False

    def format_inputs_for_prompt(self, context: ReviewContext) -> str:
        """Format review context for inclusion in LLM prompt.

        Args:
            context: ReviewContext to format

        Returns:
            Formatted string suitable for inclusion in prompt
        """
        import logging
        logger = logging.getLogger(__name__)

        agent_name = self.__class__.__name__
        logger.info(f"[{agent_name}] Building prompt context:")
        logger.info(f"[{agent_name}]   Repo root: {context.repo_root}")
        logger.info(f"[{agent_name}]   Changed files: {len(context.changed_files)}")
        logger.info(f"[{agent_name}]   Diff size: {len(context.diff)} chars")

        parts = [
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

        return "\n".join(parts)

    def verify_findings(
        self,
        findings: List,
        changed_files: List[str],
        repo_root: str
    ) -> List[dict]:
        """Verify findings by delegating to the verifier strategy.

        This method delegates to the configured FindingsVerifier strategy,
        allowing different verification implementations (grep, LSP, etc.)

        Args:
            findings: List of Finding objects from ReviewOutput
            changed_files: List of changed file paths
            repo_root: Repository root path

        Returns:
            List of verification entries from the verifier strategy

        Note:
            Graceful degradation: Delegates to strategy, which handles
            failures gracefully by returning empty list and logging warnings.
        """
        return self._verifier.verify(findings, changed_files, repo_root)

    async def _execute_review_with_runner(
        self,
        context: ReviewContext,
        *,
        early_return_on_no_relevance: bool = False,
        no_relevance_summary: str | None = None,
    ) -> ReviewOutput:
        """Shared execution flow for review agents using SimpleReviewAgentRunner.

        This template method centralizes the common pattern used by all review agents:
        1. Filter relevant files (optional early return)
        2. Build system prompt and formatted context
        3. Create SimpleReviewAgentRunner instance
        4. Execute LLM call with retry
        5. Parse JSON response with validation fallback
        6. Handle errors appropriately

        Args:
            context: ReviewContext containing changed files, diff, and metadata
            early_return_on_no_relevance: If True, return merge-severity ReviewOutput
                when no relevant files are found. If False, proceed regardless.
            no_relevance_summary: Custom summary message for no-relevance case.
                If None, uses default message.

        Returns:
            ReviewOutput with findings, severity, and merge gate decision

        Raises:
            ValueError: If API key is missing or invalid
            TimeoutError: If LLM request times out
            Exception: For other API-related errors

        Example:
            >>> class MyReviewer(BaseReviewerAgent):
            ...     async def review(self, context: ReviewContext) -> ReviewOutput:
            ...         return await self._execute_review_with_runner(
            ...             context,
            ...             early_return_on_no_relevance=True,
            ...             no_relevance_summary="No MyReviewer-relevant files changed"
            ...         )
        """
        import logging
        from dawn_kestrel.core.harness import SimpleReviewAgentRunner
        from iron_rook.review.contracts import Scope, MergeGate

        logger = logging.getLogger(__name__)
        class_name = self.__class__.__name__

        relevant_files = [
            file_path
            for file_path in context.changed_files
            if self.is_relevant_to_changes([file_path])
        ]

        logger.info(f"[{class_name}] Filtering relevant files: {len(relevant_files)}/{len(context.changed_files)} matched")

        if early_return_on_no_relevance and not relevant_files:
            logger.info(f"[{class_name}] No relevant files found, returning early with 'merge' severity")
            return ReviewOutput(
                agent=self.get_agent_name(),
                summary=no_relevance_summary or f"No {self.get_agent_name()}-relevant files changed. Review not applicable.",
                severity="merge",
                scope=Scope(
                    relevant_files=[],
                    reasoning="No files matched relevance patterns",
                ),
                findings=[],
                merge_gate=MergeGate(
                    decision="approve",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[no_relevance_summary or f"No {self.get_agent_name()}-relevant files were changed."],
                ),
            )

        system_prompt = self.get_system_prompt()
        formatted_context = self.format_inputs_for_prompt(context)

        user_message = f"""{system_prompt}

{formatted_context}

Please analyze the above changes and provide your review in the specified JSON format."""

        logger.info(f"[{class_name}] Prompt construction complete:")
        logger.info(f"[{class_name}]   System prompt: {len(system_prompt)} chars")
        logger.info(f"[{class_name}]   Formatted context: {len(formatted_context)} chars")
        logger.info(f"[{class_name}]   Full user_message: {len(user_message)} chars")
        logger.info(f"[{class_name}]   Relevant files: {len(relevant_files)}")

        runner = SimpleReviewAgentRunner(
            agent_name=self.get_agent_name(),
            allowed_tools=self.get_allowed_tools(),
        )

        try:
            response_text = await runner.run_with_retry(system_prompt, formatted_context)
            logger.info(f"[{class_name}] Got response: {len(response_text)} chars")

            output = ReviewOutput.model_validate_json(response_text)
            logger.info(f"[{class_name}] JSON validation successful!")
            logger.info(f"[{class_name}]   agent: {output.agent}")
            logger.info(f"[{class_name}]   severity: {output.severity}")
            logger.info(f"[{class_name}]   findings: {len(output.findings)}")

            return output

        except pd.ValidationError as e:
            logger.error(f"[{class_name}] JSON validation error: {e}")
            logger.error(f"[{class_name}]   Error count: {len(e.errors())}")
            for error in e.errors()[:5]:
                logger.error(f"[{class_name}]     - {error['loc']}: {error['msg']}")
            logger.error(f"[{class_name}]   Original response (first 500 chars): {response_text[:500]}...")

            return ReviewOutput(
                agent=self.get_agent_name(),
                summary=f"Error parsing LLM response: {str(e)}",
                severity="critical",
                scope=Scope(
                    relevant_files=relevant_files,
                    ignored_files=[],
                    reasoning="Failed to parse LLM JSON response due to validation error."
                ),
                findings=[],
                merge_gate=MergeGate(
                    decision="needs_changes",
                    must_fix=[],
                    should_fix=[],
                    notes_for_coding_agent=[
                        "Review LLM response format and ensure it matches expected schema."
                    ]
                )
            )
        except (TimeoutError, ValueError):
            raise
        except Exception as e:
            raise Exception(f"LLM API error: {str(e)}") from e

    def learn_entry_point_pattern(self, pattern: dict) -> bool:
        """Learn a new entry point pattern from PR review.

        This method allows reviewers to discover and learn new patterns during
        review. Patterns are staged for manual approval before integration.

        Args:
            pattern: Pattern dictionary with keys:
                - type: "ast", "file_path", or "content"
                - pattern: The pattern string
                - weight: Relevance weight (0.0-1.0)
                - language: Optional language field (required for ast/content)
                - source: Optional source description (e.g., "PR #123")

        Returns:
            True if pattern was staged successfully, False otherwise

        Example:
            During review, discover a new security pattern:
            >>> pattern = {
            ...     'type': 'content',
            ...     'pattern': r'AWS_ACCESS_KEY\\s*[=:]',
            ...     'language': 'python',
            ...     'weight': 0.95,
            ...     'source': 'PR #123 - AWS key found in code'
            ... }
            >>> self.learn_entry_point_pattern(pattern)
            True

        Note:
            This is an optional method. Default implementation does nothing.
            Reviewers can override this to enable pattern learning.
        """
        import logging

        logger = logging.getLogger(__name__)

        logger.debug(
            f"[{self.__class__.__name__}] learn_entry_point_pattern called "
            f"but not implemented (pattern: {pattern.get('type', 'unknown')})"
        )
        return False
