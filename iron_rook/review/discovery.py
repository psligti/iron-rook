"""Entry point discovery module for PR review agents.

This module provides intelligent discovery of code entry points using multiple strategies:
- AST pattern matching (via ast-grep)
- LSP symbol discovery
- Content pattern search (grep)
- File path pattern matching (glob)

Discovery supports timeout protection and graceful fallback behavior.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast
from dataclasses import dataclass
import time

from dawn_kestrel.tools.framework import ToolRegistry, ToolContext, ToolResult


logger = logging.getLogger(__name__)


@dataclass
class EntryPoint:
    """Represents a discovered entry point.

    Attributes:
        file_path: Path to file containing the entry point
        line_number: Line number (if applicable)
        description: Human-readable description of the entry point
        weight: Relevance score (0.0-1.0), higher is more relevant
        pattern_type: Type of pattern that discovered this (ast, content, file_path)
        evidence: Raw evidence from discovery tool
    """

    file_path: str
    line_number: Optional[int]
    description: str
    weight: float
    pattern_type: str
    evidence: str


class EntryPointDiscovery:
    """Discover entry points for PR review agents using multi-strategy approach.

    This class implements a multi-strategy discovery system:
    1. Load agent-specific entry point documentation (YAML frontmatter)
    2. Apply AST patterns using ast_grep_search
    3. Apply LSP symbol discovery using lsp_symbols
    4. Apply content patterns using grep
    5. Apply file path patterns using glob
    6. Rank results by weight and return top N

    Features:
    - Timeout protection (30s per discovery)
    - Graceful error handling
    - Fallback behavior (return None on empty discovery)
    - Detailed logging for debugging

    Example:
        >>> discovery = EntryPointDiscovery(timeout_seconds=30)
        >>> entry_points = await discovery.discover_entry_points(
        ...     agent_name="security",
        ...     repo_root="/path/to/repo",
        ...     changed_files=["src/auth.py", "src/api.py"]
        ... )
        >>> if entry_points is None:
        ...     # Fallback to is_relevant_to_changes()
        ...     pass
        >>> else:
        ...     # Use discovered entry points
        ...     for ep in entry_points:
        ...         print(f"{ep.file_path}:{ep.line_number} - {ep.description}")
    """

    DISCOVERY_TIMEOUT = 30
    MAX_ENTRY_POINTS = 50
    LANGUAGE_EXTENSIONS: Dict[str, str] = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "tsx": ".tsx",
        "jsx": ".jsx",
        "go": ".go",
        "rust": ".rs",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
        "csharp": ".cs",
        "ruby": ".rb",
        "php": ".php",
    }

    def __init__(
        self, timeout_seconds: int = DISCOVERY_TIMEOUT, tool_registry: Optional[ToolRegistry] = None
    ) -> None:
        """Initialize entry point discovery.

        Args:
            timeout_seconds: Timeout for discovery operations (default: 30s)
            tool_registry: ToolRegistry for executing tools (optional, creates builtin if not provided)
        """
        self.timeout_seconds = timeout_seconds
        self.tool_registry = tool_registry or ToolRegistry()

    async def discover_entry_points(
        self,
        agent_name: str,
        repo_root: str,
        changed_files: List[str],
    ) -> Optional[List[EntryPoint]]:
        """Discover entry points for a given agent.

        This is the main entry point for discovery. It loads the agent's
        entry point documentation and applies all discovery strategies.

        Args:
            agent_name: Name of the agent (e.g., "security", "architecture")
            repo_root: Path to repository root
            changed_files: List of changed file paths

        Returns:
            List of EntryPoint objects sorted by weight (descending), or None
            if discovery should be skipped (empty results or error).

        Behavior:
            - Returns None on empty discovery (triggers fallback to is_relevant_to_changes())
            - Returns None on timeout (logs warning, triggers fallback)
            - Returns None on error (logs error, triggers fallback)
            - Returns empty list if agent has no entry point doc
        """
        start_time = time.time()

        try:
            entry_points = await asyncio.wait_for(
                self._discover_impl(agent_name, repo_root, changed_files),
                timeout=self.timeout_seconds,
            )

            elapsed = time.time() - start_time
            logger.info(
                f"[{agent_name}] Discovery completed in {elapsed:.2f}s, "
                f"found {len(entry_points) if entry_points else 0} entry points"
            )

            if not entry_points:
                logger.info(
                    f"[{agent_name}] No entry points discovered, "
                    f"falling back to is_relevant_to_changes()"
                )
                return None

            if len(entry_points) > self.MAX_ENTRY_POINTS:
                logger.info(
                    f"[{agent_name}] Found {len(entry_points)} entry points, "
                    f"limiting to top {self.MAX_ENTRY_POINTS}"
                )
                entry_points = entry_points[: self.MAX_ENTRY_POINTS]

            return entry_points

        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            logger.warning(
                f"[{agent_name}] Discovery timed out after {elapsed:.2f}s, "
                f"falling back to is_relevant_to_changes()"
            )
            return None

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[{agent_name}] Discovery failed after {elapsed:.2f}s: {e}",
                exc_info=True,
            )
            return None

    async def _discover_impl(
        self,
        agent_name: str,
        repo_root: str,
        changed_files: List[str],
    ) -> List[EntryPoint]:
        """Implementation of entry point discovery.

        This method:
        1. Loads entry point documentation for the agent
        2. Parses YAML frontmatter to extract patterns
        3. Applies each discovery strategy (AST, LSP, grep, glob)
        4. Merges and ranks results by weight

        Args:
            agent_name: Name of the agent
            repo_root: Path to repository root
            changed_files: List of changed file paths

        Returns:
            List of EntryPoint objects sorted by weight (descending)
        """
        patterns = await self._load_agent_patterns(agent_name)

        if not patterns:
            logger.info(f"[{agent_name}] No entry point documentation found")
            return []

        all_entry_points: List[EntryPoint] = []

        ast_patterns = patterns.get("ast", [])
        if ast_patterns:
            logger.info(
                f"[{agent_name}] Running AST pattern discovery ({len(ast_patterns)} patterns)"
            )
            ast_results = await self._discover_ast_patterns(ast_patterns, repo_root, changed_files)
            all_entry_points.extend(ast_results)

        content_patterns = patterns.get("content", [])
        if content_patterns:
            logger.info(
                f"[{agent_name}] Running content pattern discovery ({len(content_patterns)} patterns)"
            )
            content_results = await self._discover_content_patterns(
                content_patterns, repo_root, changed_files
            )
            all_entry_points.extend(content_results)

        file_path_patterns = patterns.get("file_path", [])
        if file_path_patterns:
            logger.info(
                f"[{agent_name}] Running file path discovery ({len(file_path_patterns)} patterns)"
            )
            file_path_results = await self._discover_file_path_patterns(
                file_path_patterns, changed_files
            )
            all_entry_points.extend(file_path_results)

        all_entry_points.sort(key=lambda ep: (-ep.weight, ep.file_path, ep.line_number or 0))

        logger.info(
            f"[{agent_name}] Discovery complete: {len(all_entry_points)} entry points "
            f"(AST: {len([ep for ep in all_entry_points if ep.pattern_type == 'ast'])}, "
            f"Content: {len([ep for ep in all_entry_points if ep.pattern_type == 'content'])}, "
            f"File Path: {len([ep for ep in all_entry_points if ep.pattern_type == 'file_path'])})"
        )

        return all_entry_points

    async def _load_agent_patterns(self, agent_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """Load and parse entry point patterns for an agent.

        This method:
        1. Looks for docs/reviewers/{agent_name}_reviewer.md
        2. Parses YAML frontmatter
        3. Extracts patterns grouped by type

        Args:
            agent_name: Name of the agent (e.g., "security")

        Returns:
            Dictionary with pattern groups: {"ast": [...], "content": [...], "file_path": [...]}
        """
        doc_path = Path("docs/reviewers") / f"{agent_name}_reviewer.md"

        if not doc_path.exists():
            logger.debug(f"[{agent_name}] Entry point doc not found: {doc_path}")
            return {}

        content = doc_path.read_text()
        yaml_content, frontmatter = self._parse_frontmatter(content)

        if not frontmatter:
            logger.debug(f"[{agent_name}] No frontmatter found in {doc_path}")
            return {}

        patterns_dict: Dict[str, List[Dict[str, Any]]] = {
            "ast": [],
            "content": [],
            "file_path": [],
        }

        patterns_yaml = frontmatter.get("patterns", [])
        if not patterns_yaml:
            logger.debug(f"[{agent_name}] No patterns found in frontmatter")
            return {}

        for pattern_yaml in patterns_yaml:
            pattern = {}
            for line in pattern_yaml.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    pattern[key.strip()] = value.strip()

            pattern_type = pattern.get("type")
            if pattern_type in patterns_dict:
                if "weight" in pattern:
                    try:
                        pattern["weight"] = float(pattern["weight"])
                    except ValueError:
                        pattern["weight"] = 0.5
                else:
                    pattern["weight"] = 0.5

                patterns_dict[pattern_type].append(pattern)

        return patterns_dict

    def _parse_frontmatter(self, content: str) -> Tuple[str, Dict[str, Any]]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: File content as string

        Returns:
            Tuple of (frontmatter_yaml, frontmatter_dict)

        Raises:
            ValueError: If frontmatter is missing or invalid
        """
        frontmatter_pattern = r"^---\n(.*?)\n---"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            raise ValueError("Missing YAML frontmatter (must start with ---)")

        yaml_content = match.group(1)

        frontmatter = {}
        lines = yaml_content.split("\n")
        current_key = None
        in_array = False
        current_item_lines = []

        for line in lines:
            if not line.strip() or line.strip().startswith("#"):
                continue

            if in_array and re.match(r"^\s+-\s+", line):
                if current_item_lines:
                    array_values.append("\n".join(current_item_lines))
                item_line = re.sub(r"^-\s+", "", line.lstrip())
                current_item_lines = [item_line]
                continue
            elif in_array and line.startswith(" "):
                if current_item_lines:
                    current_item_lines.append(line.lstrip())
                continue
            elif in_array:
                if current_item_lines:
                    array_values.append("\n".join(current_item_lines))
                    current_item_lines = []
                frontmatter[current_key] = array_values
                in_array = False

            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                if value == "":
                    current_key = key
                    in_array = True
                    array_values = []
                else:
                    value = value.strip("\"'")
                    frontmatter[key] = value

        if in_array:
            if current_item_lines:
                array_values.append("\n".join(current_item_lines))
            frontmatter[current_key] = array_values

        return yaml_content, frontmatter

    async def _discover_ast_patterns(
        self, patterns: List[dict], repo_root: str, changed_files: List[str]
    ) -> List[EntryPoint]:
        """Discover entry points using AST patterns via ast-grep.

        Args:
            patterns: List of pattern dicts with 'pattern', 'language', 'weight'
            repo_root: Path to repository root
            changed_files: List of changed file paths

        Returns:
            List of EntryPoint objects from AST matches
        """
        entry_points: List[EntryPoint] = []

        for pattern_def in patterns:
            pattern = pattern_def.get("pattern")
            language = pattern_def.get("language", "python")
            weight = pattern_def.get("weight", 0.5)

            if not pattern:
                continue

            try:
                lang_files = self._get_changed_files_for_language(changed_files, language)

                if not lang_files:
                    continue

                full_paths = [str(Path(repo_root) / f) for f in lang_files]

                # Use ToolRegistry to execute ast_grep_search tool
                tool = self.tool_registry.get("ast_grep_search")
                if not tool:
                    logger.warning(
                        "ast_grep_search tool not found in registry, skipping AST pattern discovery"
                    )
                    break

                # Create minimal ToolContext for tool execution
                ctx = self._build_tool_context()

                result = await self._execute_tool(
                    tool=tool,
                    args={
                        "pattern": pattern,
                        "language": language,
                        "paths": full_paths,
                    },
                    ctx=ctx,
                )

                # Parse tool output
                if result.output:
                    for line in result.output.split("\n"):
                        if not line.strip():
                            continue

                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            file_path = parts[0]
                            try:
                                rel_path = str(Path(file_path).relative_to(repo_root))
                            except ValueError:
                                rel_path = file_path

                            line_number = None
                            try:
                                line_number = int(parts[1].split(":")[0])
                            except (ValueError, IndexError):
                                pass

                            code_snippet = parts[2] if len(parts) >= 3 else ""

                            entry_point = EntryPoint(
                                file_path=rel_path,
                                line_number=line_number,
                                description=f"AST pattern: {pattern}",
                                weight=weight,
                                pattern_type="ast",
                                evidence=code_snippet,
                            )
                            entry_points.append(entry_point)

            except Exception as e:
                logger.warning(f"AST pattern search failed: {pattern} - {e}")

        return entry_points

    async def _discover_content_patterns(
        self, patterns: List[dict], repo_root: str, changed_files: List[str]
    ) -> List[EntryPoint]:
        """Discover entry points using content patterns via ripgrep.

        Args:
            patterns: List of pattern dicts with 'pattern', 'language', 'weight'
            repo_root: Path to repository root
            changed_files: List of changed file paths

        Returns:
            List of EntryPoint objects from content pattern matches
        """
        entry_points: List[EntryPoint] = []

        for pattern_def in patterns:
            pattern = pattern_def.get("pattern")
            language = pattern_def.get("language", "python")
            weight = pattern_def.get("weight", 0.5)

            if not pattern:
                continue

            try:
                lang_files = self._get_changed_files_for_language(changed_files, language)

                if not lang_files:
                    continue

                full_paths = [str(Path(repo_root) / f) for f in lang_files]

                # Use ToolRegistry to execute grep tool
                tool = self.tool_registry.get("grep")
                if not tool:
                    logger.warning(
                        "grep tool not found in registry, skipping content pattern discovery"
                    )
                    break

                # Create minimal ToolContext for tool execution
                ctx = self._build_tool_context()

                # Build file pattern from full paths
                file_pattern = " ".join(full_paths)

                result = await self._execute_tool(
                    tool=tool,
                    args={
                        "pattern": pattern,
                        "include": file_pattern,
                        "max_results": 1000,  # High limit to get all matches
                    },
                    ctx=ctx,
                )

                # Parse tool output
                if result.output:
                    for line in result.output.split("\n"):
                        if not line.strip():
                            continue

                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            file_path = parts[0]
                            try:
                                rel_path = str(Path(file_path).relative_to(repo_root))
                            except ValueError:
                                rel_path = file_path

                            line_number = None
                            try:
                                line_number = int(parts[1])
                            except ValueError:
                                pass

                            content_snippet = parts[2] if len(parts) >= 3 else ""

                            entry_point = EntryPoint(
                                file_path=rel_path,
                                line_number=line_number,
                                description=f"Content pattern: {pattern}",
                                weight=weight,
                                pattern_type="content",
                                evidence=content_snippet,
                            )
                            entry_points.append(entry_point)

            except Exception as e:
                logger.warning(f"Content pattern search failed: {pattern} - {e}")

        return entry_points

    async def _discover_file_path_patterns(
        self,
        patterns: List[Dict[str, Any]],
        changed_files: List[str],
    ) -> List[EntryPoint]:
        """Discover entry points using file path pattern matching.

        Uses glob patterns to match file paths.

        Args:
            patterns: List of file path patterns with weight
            changed_files: List of changed file paths

        Returns:
            List of EntryPoint objects from file path matches
        """

        entry_points: List[EntryPoint] = []

        for pattern_def in patterns:
            pattern = pattern_def.get("pattern")
            weight = pattern_def.get("weight", 0.5)

            if not pattern:
                continue

            try:
                for file_path in changed_files:
                    if self._match_glob_pattern(file_path, pattern):
                        entry_point = EntryPoint(
                            file_path=file_path,
                            line_number=None,
                            description=f"File path pattern: {pattern}",
                            weight=weight,
                            pattern_type="file_path",
                            evidence=file_path,
                        )
                        entry_points.append(entry_point)

            except Exception as e:
                logger.warning(f"File path pattern search failed: {pattern} - {e}")

        return entry_points

    def _match_glob_pattern(self, file_path: str, pattern: str) -> bool:
        """Match file path against glob pattern.

        Uses base module's _match_glob_pattern for consistency.

        Args:
            file_path: File path to check
            pattern: Glob pattern (supports *, **, ?)

        Returns:
            True if file path matches pattern
        """
        from iron_rook.review.base import _match_glob_pattern

        return _match_glob_pattern(file_path, pattern)

    def _get_changed_files_for_language(self, changed_files: List[str], language: str) -> List[str]:
        """Filter changed files by language extension."""
        extension = self.LANGUAGE_EXTENSIONS.get(language, f".{language}")
        return [file_path for file_path in changed_files if file_path.endswith(extension)]

    def _build_tool_context(self) -> ToolContext:
        """Build a minimal tool context used by discovery tools."""
        return ToolContext(
            session_id="discovery",
            message_id="discovery",
            agent="discovery",
            abort=asyncio.Event(),
            messages=[],
        )

    async def _execute_tool(
        self, tool: object, args: Dict[str, Any], ctx: ToolContext
    ) -> ToolResult:
        """Execute a tool supporting both object.execute(...) and callable mocks."""
        result: Any
        execute = getattr(tool, "execute", None)

        if callable(execute):
            result = await execute(args=args, ctx=ctx)
        elif callable(tool):
            result = await tool(args=args, ctx=ctx)  # type: ignore[call-top-callable]
        else:
            raise TypeError("Tool is not executable")

        if asyncio.iscoroutine(result):
            result = await result

        if not isinstance(result, ToolResult) and callable(tool):
            fallback = await tool(args=args, ctx=ctx)  # type: ignore[call-top-callable]
            if asyncio.iscoroutine(fallback):
                fallback = await fallback
            result = fallback

        return cast(ToolResult, result)
