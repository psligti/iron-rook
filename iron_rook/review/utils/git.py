"""Git utility functions for review agents."""

from __future__ import annotations

from typing import List
from pathlib import Path
from git import Repo as GitRepo
from git.exc import InvalidGitRepositoryError, NoSuchPathError


class GitError(Exception):
    """Base exception for Git-related errors."""


class InvalidRefError(GitError):
    """Raised when an invalid Git reference is provided."""


class RepositoryNotFoundError(GitError):
    """Raised when a Git repository is not found at the specified path."""


async def get_changed_files(repo_root: str, base_ref: str, head_ref: str) -> List[str]:
    """
    Get list of changed files between two refs.

    Args:
        repo_root: Path to the Git repository
        base_ref: Base git reference (e.g., 'main', 'origin/main')
        head_ref: Head git reference (e.g., 'feature-branch', 'HEAD')

    Returns:
        List of changed file paths

    Raises:
        RepositoryNotFoundError: If the repository is not found
        InvalidRefError: If an invalid reference is provided
    """
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

    changed_files = []
    for diff_item in base_commit.diff(head_commit):
        file_path = diff_item.b_path or diff_item.a_path

        if not file_path:
            continue

        if _is_binary_file(file_path):
            continue

        changed_files.append(file_path)

    return changed_files


async def get_diff(repo_root: str, base_ref: str, head_ref: str) -> str:
    """
    Get unified diff between two refs.

    Args:
        repo_root: Path to the Git repository
        base_ref: Base git reference (e.g., 'main', 'origin/main')
        head_ref: Head git reference (e.g., 'feature-branch', 'HEAD')

    Returns:
        Unified diff as string

    Raises:
        RepositoryNotFoundError: If the repository is not found
        InvalidRefError: If an invalid reference is provided
    """
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

    diff_text = []
    for diff_item in base_commit.diff(head_commit, create_patch=True):
        if diff_item.diff:
            diff_text.append(diff_item.diff.decode("utf-8", errors="ignore"))

    return "".join(diff_text)


async def get_repo_tree(repo_root: str) -> str:
    """
    Get repository tree structure.

    Args:
        repo_root: Path to the Git repository

    Returns:
        Repository tree as string

    Raises:
        RepositoryNotFoundError: If the repository is not found
    """
    try:
        repo = GitRepo(repo_root)
    except InvalidGitRepositoryError as e:
        raise RepositoryNotFoundError(f"Not a git repository: {repo_root}") from e
    except NoSuchPathError as e:
        raise RepositoryNotFoundError(f"Path does not exist: {repo_root}") from e

    tree = repo.tree()
    tree_lines = []

    for item in tree.traverse():
        if item.type == "blob":
            tree_lines.append(item.path)

    return "\n".join(tree_lines)


def _is_binary_file(file_path: str) -> bool:
    """
    Check if a file is likely a binary file based on extension.

    Args:
        file_path: Path to the file

    Returns:
        True if file is likely binary, False otherwise
    """
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
