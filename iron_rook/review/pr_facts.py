"""Deterministic PR facts models for security review.

This module provides Pydantic models and constants for building a deterministic
set of candidate files for security review. It enforces hard bounds to prevent
prompt overflow and includes anchor files that are always included.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final
from typing import List

import pydantic as pd


# Hard bounds - configurable constants with clear documentation

# Maximum number of candidate files to include in deep review
MAX_CANDIDATE_FILES: Final[int] = 200

# Maximum total file bytes (sum of all candidate files) for deep review
MAX_TOTAL_FILE_BYTES_FOR_DEEP_REVIEW: Final[int] = 200_000

# Maximum diff characters to include for triage
MAX_DIFF_CHARS_FOR_TRIAGE: Final[int] = 120_000

# Maximum number of hunks per file to include in diff summary
MAX_HUNKS_PER_FILE: Final[int] = 20

# Maximum filename length for sanitization
MAX_FILENAME_LENGTH: Final[int] = 255


# Deterministic anchor patterns - files always included in candidate set
ANCHOR_PATTERNS: Final[List[str]] = [
    # Dependency manifests
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "poetry.lock",
    "uv.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    # CI/CD
    ".github/workflows",
    ".gitlab-ci.yml",
    # Container/Infra
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".terraform",
    ".tf",
    # Security/Config
    ".env",
    ".env.example",
    "config",
]


def is_anchor_file(file_path: str) -> bool:
    """
    Check if a file matches anchor patterns.

    Args:
        file_path: The file path to check

    Returns:
        True if the file is an anchor file, False otherwise
    """
    file_lower = file_path.lower()

    for pattern in ANCHOR_PATTERNS:
        pattern_lower = pattern.lower()

        if pattern_lower.endswith("/"):
            # Directory pattern
            if file_lower.startswith(pattern_lower):
                return True
        elif pattern_lower.startswith("."):
            # Hidden file pattern - check if file starts with pattern
            # (e.g., .env matches .env, .env.example, .env.local)
            if file_lower.startswith(pattern_lower):
                return True
        elif "*" in pattern_lower:
            # Wildcard pattern (simplified - just substring match)
            if pattern_lower.replace("*", "") in file_lower:
                return True
        else:
            # Exact or suffix match
            if file_lower == pattern_lower or file_lower.endswith(pattern_lower):
                return True

    return False


class BoundsExceededError(Exception):
    """Raised when content exceeds configured bounds."""

    def __init__(
        self,
        message: str,
        limit: int | None = None,
        actual: int | None = None,
        metric: str | None = None,
    ):
        self.message = message
        self.limit = limit
        self.actual = actual
        self.metric = metric
        super().__init__(self.message)


class ChangedFiles(pd.BaseModel):
    """Full set of files changed in the PR."""

    files: List[str] = pd.Field(default_factory=list)
    base_ref: str
    head_ref: str

    model_config = pd.ConfigDict(extra="forbid")


class DiffHunk(pd.BaseModel):
    """A single hunk from a diff."""

    file_path: str
    line_start: int
    line_end: int
    content: str

    model_config = pd.ConfigDict(extra="forbid")


class DiffSummary(pd.BaseModel):
    """Bounded diff summary with selected hunks."""

    total_chars: int
    hunks: List[DiffHunk] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="forbid")

    @pd.model_validator(mode="after")
    def enforce_hunk_limit_per_file(self):
        """
        Enforce MAX_HUNKS_PER_FILE per file.

        Hunks beyond the limit for each file are dropped.
        """
        hunks_by_file = defaultdict(list)
        for hunk in self.hunks:
            hunks_by_file[hunk.file_path].append(hunk)

        result_hunks = []
        for file_path, file_hunks in hunks_by_file.items():
            result_hunks.extend(file_hunks[:MAX_HUNKS_PER_FILE])

        self.hunks = result_hunks
        return self


class RepoMapSummary(pd.BaseModel):
    """Bounded repository map summary."""

    total_files: int
    truncated_files: int
    sample_paths: List[str] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="forbid")


class AdjacencySignals(pd.BaseModel):
    """Placeholder for adjacency signals (neighbors, config refs, env keys)."""

    import_neighbors: List[str] = pd.Field(default_factory=list)
    config_references: List[str] = pd.Field(default_factory=list)
    env_key_references: List[str] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="forbid")


class CandidateFiles(pd.BaseModel):
    """Bounded set of candidate files for review."""

    files: List[str] = pd.Field(default_factory=list)
    total_bytes: int
    includes_anchors: bool

    model_config = pd.ConfigDict(extra="forbid")

    @pd.model_validator(mode="after")
    def enforce_file_count_limit(self):
        """
        Enforce MAX_CANDIDATE_FILES.

        Files beyond the limit are dropped.
        """
        if len(self.files) > MAX_CANDIDATE_FILES:
            self.files = self.files[:MAX_CANDIDATE_FILES]
        return self


class PRFacts(pd.BaseModel):
    """Collection of deterministic PR facts for security review."""

    changed_files: ChangedFiles
    diff_summary: DiffSummary
    repo_map: RepoMapSummary
    adjacency: AdjacencySignals
    candidates: CandidateFiles

    model_config = pd.ConfigDict(extra="forbid")
