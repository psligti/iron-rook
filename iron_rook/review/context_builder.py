"""Context builder interface and default implementation for review agents.

This module provides seam for building ReviewContext objects, allowing
customization of context construction logic (e.g., filtering, discovery,
fallback behavior) while maintaining a consistent interface for the orchestrator.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List

from iron_rook.review.base import BaseReviewerAgent, ReviewContext
from iron_rook.review.contracts import (
    ReviewInputs,
    PullRequestChangeList,
    PullRequestMetadata,
    PRChange,
    PRMetadata,
    PRConstraints,
)
from iron_rook.review.discovery import EntryPointDiscovery

logger = logging.getLogger(__name__)


class ContextBuilder(ABC):
    """Abstract interface for building ReviewContext for review agents.

    Implementations can customize how ReviewContext is constructed, including:
    - Entry point discovery and filtering
    - Fallback behavior when discovery fails
    - Context enrichment strategies

    The default implementation (DefaultContextBuilder) mirrors the original
    orchestrator behavior to ensure backward compatibility.
    """

    @abstractmethod
    async def build(
        self,
        inputs: ReviewInputs,
        agent: BaseReviewerAgent,
    ) -> ReviewContext:
        """Build ReviewContext for a specific agent.

        Args:
            inputs: ReviewInputs with review parameters
            agent: BaseReviewerAgent to build context for

        Returns:
            ReviewContext populated with review data (filtered changed_files)
        """
        pass


class DefaultContextBuilder(ContextBuilder):
    """Default context builder implementation mirroring orchestrator behavior.

    This implementation preserves the original orchestrator context building logic:
    1. Discovers entry points relevant to the agent's patterns
    2. Filters changed_files to only those containing discovered entry points
    3. Falls back to is_relevant_to_changes() if discovery fails

    This ensures backward compatibility with existing behavior while providing
    an injectable seam for customization.
    """

    def __init__(self, discovery: EntryPointDiscovery | None = None) -> None:
        """Initialize default context builder.

        Args:
            discovery: EntryPointDiscovery instance for context filtering.
                        Defaults to None (creates new instance if needed).
        """
        self.discovery = discovery or EntryPointDiscovery()

    async def build(
        self,
        inputs: ReviewInputs,
        agent: BaseReviewerAgent,
    ) -> ReviewContext:
        """Build ReviewContext for a specific agent.

        This method performs intelligent context filtering using entry point discovery:
        1. Discovers entry points relevant to the agent's patterns
        2. Filters changed_files to only those containing discovered entry points
        3. Falls back to is_relevant_to_changes() if discovery fails

        Args:
            inputs: ReviewInputs with review parameters
            agent: BaseReviewerAgent to build context for

        Returns:
            ReviewContext populated with review data (filtered changed_files)
        """
        from iron_rook.review.utils.git import get_changed_files, get_diff

        agent_name = agent.__class__.__name__

        all_changed_files = await get_changed_files(
            inputs.repo_root, inputs.base_ref, inputs.head_ref
        )

        entry_points = await self.discovery.discover_entry_points(
            agent_name=agent_name,
            repo_root=inputs.repo_root,
            changed_files=all_changed_files,
        )

        if entry_points is not None:
            ep_file_set = {ep.file_path for ep in entry_points}
            filtered_files = [f for f in all_changed_files if f in ep_file_set]
            logger.info(
                f"[{agent_name}] Entry point discovery found {len(entry_points)} entry points, "
                f"filtered to {len(filtered_files)}/{len(all_changed_files)} files"
            )
            changed_files = filtered_files
        else:
            logger.info(
                f"[{agent_name}] Entry point discovery returned None, "
                f"using is_relevant_to_changes() fallback"
            )
            if agent.is_relevant_to_changes(all_changed_files):
                changed_files = all_changed_files
            else:
                changed_files = []
                logger.info(f"[{agent_name}] Agent not relevant to changes, skipping review")

        diff = await get_diff(inputs.repo_root, inputs.base_ref, inputs.head_ref)

        return ReviewContext(
            changed_files=changed_files,
            diff=diff,
            repo_root=inputs.repo_root,
            base_ref=inputs.base_ref,
            head_ref=inputs.head_ref,
            pr_title=inputs.pr_title,
            pr_description=inputs.pr_description,
        )


async def build_review_context(
    repo_root: str,
    base_ref: str,
    head_ref: str,
    pr_title: str = "",
    pr_description: str = "",
    ticket_description: str = "",
) -> PullRequestChangeList:
    """Build PullRequestChangeList from git context for security review.

    Args:
        repo_root: Path to the Git repository
        base_ref: Base git reference (e.g., 'main', 'origin/main')
        head_ref: Head git reference (e.g., 'feature-branch', 'HEAD')
        pr_title: Pull request title
        pr_description: Pull request description
        ticket_description: Associated ticket description

    Returns:
        PullRequestChangeList populated with PR metadata and changes

    Raises:
        RepositoryNotFoundError: If repository is not found
        InvalidRefError: If an invalid reference is provided
    """
    from git import Repo as GitRepo
    from git.exc import InvalidGitRepositoryError, NoSuchPathError

    from iron_rook.review.utils.git import RepositoryNotFoundError, InvalidRefError

    try:
        repo = GitRepo(repo_root)
    except InvalidGitRepositoryError as e:
        raise RepositoryNotFoundError(f"Not a git repository: {repo_root}") from e
    except NoSuchPathError as e:
        raise RepositoryNotFoundError(f"Path does not exist: {repo_root}") from e

    try:
        base_commit = repo.commit(base_ref)
        head_commit = repo.commit(head_ref)
    except ValueError as e:
        raise InvalidRefError(f"Invalid Git reference: {e}") from e

    author = str(head_commit.author)
    created_at = datetime.fromtimestamp(head_commit.committed_date).isoformat()
    commit_range = f"{base_commit.hexsha[:8]}..{head_commit.hexsha[:8]}"

    pr_metadata = PullRequestMetadata(
        id=f"pr-{head_commit.hexsha[:8]}",
        title=pr_title or f"Changes from {base_ref} to {head_ref}",
        base_branch=base_ref,
        head_branch=head_ref,
        author=author,
        url=None,
    )

    repo_name = Path(repo_root).name

    metadata = PRMetadata(
        repo=repo_name,
        commit_range=commit_range,
        created_at=created_at,
    )

    changes: List[PRChange] = []
    for diff_item in base_commit.diff(head_commit, create_patch=True):
        file_path = diff_item.b_path or diff_item.a_path

        if not file_path:
            continue

        if _is_binary_file(file_path):
            continue

        if diff_item.new_file:
            change_type = "added"
        elif diff_item.deleted_file:
            change_type = "deleted"
        elif diff_item.renamed_file:
            change_type = "renamed"
        else:
            change_type = "modified"

        diff_raw = diff_item.diff if diff_item.diff else b""
        diff_text = (
            diff_raw.decode("utf-8", errors="ignore")
            if isinstance(diff_raw, bytes)
            else str(diff_raw)
        )
        diff_summary = _summarize_diff(diff_text)

        changes.append(
            PRChange(
                path=file_path,
                change_type=change_type,
                diff_summary=diff_summary,
                risk_hints=_extract_risk_hints(file_path, diff_text),
            )
        )

    return PullRequestChangeList(
        pr=pr_metadata,
        changes=changes,
        metadata=metadata,
        constraints=PRConstraints(),
    )


def _is_binary_file(file_path: str) -> bool:
    """Check if a file is likely a binary file based on extension."""
    binary_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".pkl",
        ".parquet",
        ".xls",
        ".xlsx",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".mp3",
        ".mp4",
        ".wav",
        ".avi",
        ".mov",
        ".mkv",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        ".svg",
        ".webp",
    }
    ext = Path(file_path).suffix.lower()
    return ext in binary_extensions


def _summarize_diff(diff_text: str) -> str:
    """Generate a human-readable summary of the diff."""
    if not diff_text:
        return "No changes"

    lines_added = diff_text.count("\n+")
    lines_removed = diff_text.count("\n-")
    lines_added -= diff_text.count("\n+++")
    lines_removed -= diff_text.count("\n---")

    parts = []
    if lines_added > 0:
        parts.append(f"+{lines_added}")
    if lines_removed > 0:
        parts.append(f"-{lines_removed}")

    if parts:
        return f"{', '.join(parts)} lines"
    return "No content changes"


def _extract_risk_hints(file_path: str, diff_text: str) -> List[str]:
    """Extract potential risk hints from file path and diff content."""
    hints = []
    path_lower = file_path.lower()

    risk_keywords = {
        "password": "credentials",
        "secret": "secrets",
        "token": "auth tokens",
        "key": "api keys",
        "sql": "sql queries",
        "query": "database queries",
        "exec": "command execution",
        "eval": "code evaluation",
        "shell": "shell commands",
        "crypto": "cryptography",
        "hash": "hashing",
        "encrypt": "encryption",
        "decrypt": "decryption",
        "auth": "authentication",
        "login": "authentication",
        "user": "user data",
        "session": "session management",
        "cookie": "cookies",
        "jwt": "jwt tokens",
        "oauth": "oauth",
    }

    if "auth" in path_lower or "login" in path_lower:
        hints.append("auth")
    if "config" in path_lower:
        hints.append("config")
    if "security" in path_lower:
        hints.append("security")

    diff_lower = diff_text.lower()
    for keyword, hint in risk_keywords.items():
        if keyword in diff_lower and hint not in hints:
            hints.append(hint)

    return hints[:5]
