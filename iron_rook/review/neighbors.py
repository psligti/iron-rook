"""Neighbor discovery for import graph and config/env references."""

from __future__ import annotations

import ast
import re
from pathlib import Path, PurePosixPath

import pydantic as pd


_ENV_PATTERNS = [
    re.compile(r"os\.getenv\(\s*['\"]([A-Z0-9_]+)['\"]"),
    re.compile(r"os\.environ\[\s*['\"]([A-Z0-9_]+)['\"]\s*\]"),
    re.compile(r"process\.env\.([A-Z0-9_]+)"),
]

_CONFIG_PATH_PATTERN = re.compile(r"['\"]([^'\"]+\.(?:yaml|yml|json|toml|ini|env))['\"]")


class NeighborsResult(pd.BaseModel):
    """Deterministic set of discovered neighbors and references."""

    import_neighbors: list[str] = pd.Field(default_factory=list)
    config_references: list[str] = pd.Field(default_factory=list)
    env_keys: list[str] = pd.Field(default_factory=list)

    model_config = pd.ConfigDict(extra="forbid")


def _normalize(path: str) -> str:
    return PurePosixPath(path).as_posix().lstrip("/")


def _resolve_repo_path(current_file: str, candidate: str, repo_files: set[str]) -> str | None:
    normalized_candidate = _normalize(candidate)
    if normalized_candidate in repo_files:
        return normalized_candidate

    current_parent = PurePosixPath(current_file).parent
    relative_candidate = _normalize((current_parent / normalized_candidate).as_posix())
    if relative_candidate in repo_files:
        return relative_candidate

    return None


def _extract_relative_import_neighbors(
    file_path: str, source: str, repo_files: set[str]
) -> set[str]:
    neighbors: set[str] = set()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return neighbors

    current_parts = list(PurePosixPath(file_path).parent.parts)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level < 1:
            continue

        up_levels = max(node.level - 1, 0)
        if up_levels > len(current_parts):
            continue

        base_parts = current_parts[: len(current_parts) - up_levels]
        module_parts = node.module.split(".") if node.module else []

        import_candidates: list[str] = []
        if module_parts:
            import_candidates.append("/".join([*base_parts, *module_parts]) + ".py")
        else:
            import_candidates.extend(
                "/".join([*base_parts, alias.name]) + ".py" for alias in node.names
            )

        for candidate in import_candidates:
            normalized = _normalize(candidate)
            if normalized in repo_files:
                neighbors.add(normalized)

    return neighbors


def _extract_env_keys(source: str) -> set[str]:
    keys: set[str] = set()
    for pattern in _ENV_PATTERNS:
        keys.update(pattern.findall(source))
    return keys


def _extract_config_paths(current_file: str, source: str, repo_files: set[str]) -> set[str]:
    paths: set[str] = set()
    for literal_path in _CONFIG_PATH_PATTERN.findall(source):
        resolved = _resolve_repo_path(current_file, literal_path, repo_files)
        if resolved:
            paths.add(resolved)
    return paths


def find_neighbors(
    repo_root: str, changed_files: list[str], repo_map: dict[str, list[str]]
) -> NeighborsResult:
    """Find deterministic import/config/env neighbors for changed files."""

    repo_files = {_normalize(path) for path in repo_map.get("files", [])}
    import_neighbors: set[str] = set()
    config_references: set[str] = set()
    env_keys: set[str] = set()

    repo_root_path = Path(repo_root)
    for changed_file in changed_files:
        normalized_changed = _normalize(changed_file)
        absolute_file = repo_root_path / normalized_changed

        try:
            source = absolute_file.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            continue

        if normalized_changed.endswith(".py"):
            import_neighbors.update(
                _extract_relative_import_neighbors(normalized_changed, source, repo_files)
            )

        config_references.update(_extract_config_paths(normalized_changed, source, repo_files))
        env_keys.update(_extract_env_keys(source))

    return NeighborsResult(
        import_neighbors=sorted(import_neighbors),
        config_references=sorted(config_references),
        env_keys=sorted(env_keys),
    )
