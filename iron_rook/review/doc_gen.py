"""Documentation generator for PR review agents.

This module provides functionality to automatically generate entry point documentation
for review agents by extracting patterns from their system prompts.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
import re
import logging
from datetime import datetime, timezone

from iron_rook.review.base import BaseReviewerAgent

logger = logging.getLogger(__name__)


class DocGenAgent:
    """Agent for generating entry point documentation from reviewer system prompts.

    This agent analyzes system prompts and extracts:
    - AST patterns (code structure patterns)
    - File path patterns (glob patterns)
    - Content patterns (regex patterns for content search)
    - Heuristics (high-level review guidance)
    """

    def __init__(self, agents_dir: Optional[Path] = None) -> None:
        """Initialize DocGenAgent.

        Args:
            agents_dir: Path to reviewer agent implementations. If None, uses default.
        """
        if agents_dir is None:
            agents_dir = Path(__file__).parent.parent / "agents"
        self.agents_dir = Path(agents_dir)
        self.output_dir = Path(__file__).parents[4] / "docs" / "reviewers"

    def generate_for_agent(
        self, agent: BaseReviewerAgent, force: bool = False, output_path: Optional[Path] = None
    ) -> tuple[bool, str]:
        """Generate documentation for a specific review agent.

        Args:
            agent: The reviewer agent instance
            force: If True, overwrite existing documentation even if hash matches
            output_path: Custom output path (default: docs/reviewers/{agent}_reviewer.md)

        Returns:
            Tuple of (success, message)
        """
        try:
            agent_name = self._get_agent_name(agent)
            logger.info(f"Generating documentation for agent: {agent_name}")

            # Get system prompt
            system_prompt = agent.get_system_prompt()

            # Calculate hash of system prompt
            prompt_hash = self._calculate_hash(system_prompt)

            # Check if documentation exists and hash matches
            if output_path is None:
                output_path = self.output_dir / f"{agent_name}_reviewer.md"

            if output_path.exists() and not force:
                existing_hash = self._extract_existing_hash(output_path)
                if existing_hash == prompt_hash:
                    return True, f"Documentation up-to-date for {agent_name} (hash matches)"

            # Extract patterns from system prompt
            patterns = self._extract_patterns_from_prompt(system_prompt, agent)

            # Extract heuristics from system prompt
            heuristics = self._extract_heuristics_from_prompt(system_prompt, agent_name)

            # If no heuristics extracted, add default based on agent name
            if not heuristics:
                default_heuristics = {
                    "security": [
                        "Check for insecure imports (pickle, eval, exec, marshal, shelve)",
                        "Verify proper authentication and authorization checks",
                        "Look for SQL injection vulnerabilities in database queries",
                    ],
                    "architecture": [
                        "Check for circular dependencies between modules",
                        "Look for god objects with too many responsibilities",
                        "Verify dependency injection patterns are consistent",
                    ],
                    "documentation": [
                        "Check for missing docstrings on public functions/classes",
                        "Verify README reflects current behavior and features",
                        "Look for changes that require configuration documentation updates",
                    ],
                    "linting": [
                        "Check for mutable default arguments (= [], = {})",
                        "Look for type hints coverage on public APIs",
                        "Verify import ordering and grouping",
                    ],
                    "telemetry": [
                        "Check for secrets/PII being logged in error messages",
                        "Look for critical paths with no error logging or metrics",
                        "Verify retry loops have limits and logging for visibility",
                    ],
                    "unit_tests": [
                        "Check for tests with time dependencies (need mocking)",
                        "Look for tests using random (need seeding for determinism)",
                        "Verify assertions are specific (not just assert True)",
                    ],
                    "diff_scoper": [
                        "Classify diff risk based on lines changed (>500 lines = high risk)",
                        "Look for deletions of classes/functions (breaking changes)",
                        "Check for changes to critical paths (auth, payments, core logic)",
                    ],
                    "requirements": [
                        "Compare implementation to PR description/ticket requirements",
                        "Check for acceptance criteria coverage",
                        "Look for incomplete implementations (NotImplementedError, pass)",
                    ],
                    "performance": [
                        "Look for nested loops (O(n^2) complexity)",
                        "Check for N+1 query patterns (queries inside loops)",
                        "Verify retry logic has exponential backoff and max attempts",
                    ],
                    "dependencies": [
                        "Check for new dependencies added without justification",
                        "Verify license compatibility (avoid GPL/AGPL if proprietary)",
                        "Look for loosened version pins (reproducibility risk)",
                    ],
                    "changelog": [
                        "Check for breaking changes without migration notes",
                        "Verify version bump matches change scope (major/minor/patch)",
                        "Look for user-visible behavior changes without changelog entry",
                    ],
                }
                heuristics = default_heuristics.get(
                    agent_name, ["Review code changes for relevant patterns"]
                )

            # Determine agent type
            agent_type = self._determine_agent_type(agent)

            # Generate YAML frontmatter
            frontmatter = self._generate_yaml_frontmatter(
                agent_name=agent_name,
                agent_type=agent_type,
                patterns=patterns,
                heuristics=heuristics,
                prompt_hash=prompt_hash,
            )

            # Generate full documentation content
            content = self._generate_full_documentation(
                agent_name=agent_name,
                frontmatter=frontmatter,
                system_prompt=system_prompt,
                patterns=patterns,
                heuristics=heuristics,
            )

            # Save documentation
            self._save_doc(output_path, content)

            return True, f"Generated documentation for {agent_name}"

        except Exception as e:
            logger.error(f"Failed to generate documentation for {agent_name}: {e}")
            return False, f"Error generating documentation for {agent_name}: {str(e)}"

    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content.

        Args:
            content: Content to hash

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]

    def _get_agent_name(self, agent: BaseReviewerAgent) -> str:
        """Extract agent name from agent instance.

        Args:
            agent: The agent instance

        Returns:
            Agent name string
        """
        get_name_method = getattr(agent, "get_agent_name", None)
        if get_name_method and callable(get_name_method):
            return get_name_method()
        return agent.__class__.__name__.lower().replace("reviewer", "")

    def _extract_existing_hash(self, doc_path: Path) -> Optional[str]:
        """Extract prompt_hash from existing documentation.

        Args:
            doc_path: Path to existing documentation file

        Returns:
            Existing hash if found, None otherwise
        """
        try:
            content = doc_path.read_text()
            match = re.search(r"^prompt_hash:\s*(\S+)", content, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def _extract_patterns_from_prompt(
        self, system_prompt: str, agent: BaseReviewerAgent
    ) -> List[Dict[str, Any]]:
        """Extract patterns from system prompt.

        Extracts AST patterns, file path patterns, and content patterns
        from system prompt text.

        Args:
            system_prompt: The agent's system prompt
            agent: The agent instance for additional context

        Returns:
            List of pattern dictionaries with type, pattern, weight, and language fields
        """
        patterns = []

        # Extract AST patterns (look for AST-related keywords)
        ast_patterns = self._extract_ast_patterns(system_prompt)
        patterns.extend(ast_patterns)

        # Extract file path patterns (look for glob patterns in prompts)
        file_path_patterns = self._extract_file_path_patterns(system_prompt, agent)
        patterns.extend(file_path_patterns)

        # Extract content patterns (look for keywords/regex patterns)
        content_patterns = self._extract_content_patterns(system_prompt)
        patterns.extend(content_patterns)

        # Ensure minimum pattern counts
        ast_count = len([p for p in patterns if p["type"] == "ast"])
        file_path_count = len([p for p in patterns if p["type"] == "file_path"])
        content_count = len([p for p in patterns if p["type"] == "content"])

        if ast_count < 3:
            patterns.append(
                {
                    "type": "ast",
                    "pattern": "FunctionDef with decorator",
                    "language": "python",
                    "weight": 0.7,
                }
            )

        if file_path_count < 2:
            relevant_patterns = agent.get_relevant_file_patterns()
            for pattern_str in relevant_patterns[:5]:
                patterns.append({"type": "file_path", "pattern": pattern_str, "weight": 0.7})

        if content_count < 2:
            patterns.append(
                {
                    "type": "content",
                    "pattern": "import\\s+\\w+|from\\s+\\w+",
                    "language": "python",
                    "weight": 0.7,
                }
            )

        # Sort patterns by weight (descending)
        patterns.sort(key=lambda x: x["weight"], reverse=True)

        return patterns

    def _extract_ast_patterns(self, system_prompt: str) -> List[Dict[str, Any]]:
        """Extract AST patterns from system prompt.

        Looks for patterns like:
        - "FunctionDef with decorator"
        - "ClassDef with"
        - "Call with function"
        - "Import with"
        - "For with nested"

        Args:
            system_prompt: The agent's system prompt

        Returns:
            List of AST pattern dictionaries
        """
        patterns = []

        # AST pattern indicators
        ast_keywords = [
            (r'FunctionDef with decorator ["\']@(\w+)["\']', 0.85, "FunctionDef with decorator"),
            (r"FunctionDef without docstring", 0.7, "FunctionDef without docstring"),
            (r'ClassDef with decorator ["\']@(\w+)["\']', 0.8, "ClassDef with decorator"),
            (r"ClassDef without docstring", 0.7, "ClassDef without docstring"),
            (r'ClassDef with (?:name|base) ["\'](\w+)["\']', 0.75, "ClassDef with name/base"),
            (r"ClassDef with more than (\d+) methods", 0.8, "ClassDef with many methods"),
            (
                r'FunctionDef with (?:parameter|arg)s? ["\']([^"\']+)["\']',
                0.75,
                "FunctionDef with specific parameter",
            ),
            (
                r"FunctionDef with more than (\d+) (?:parameter|arg)s?",
                0.7,
                "FunctionDef with many parameters",
            ),
            (r"FunctionDef with depth > (\d+)", 0.8, "FunctionDef with deep nesting"),
            (r"AsyncFunctionDef", 0.65, "AsyncFunctionDef"),
            (
                r'AsyncFunctionDef with more than (\d+) [\'"]?await[\'"]?',
                0.75,
                "AsyncFunctionDef with multiple awaits",
            ),
            (r'Call with function (?:name )?["\'](\w+)["\']', 0.75, "Call with function name"),
            (r'Call with function ["\'](\w+\.\w+)["\']', 0.8, "Call with function"),
            (
                r'Call with function ["\'](\w+\.\w+)["\'] and keyword argument ["\'](\w+)["\']',
                0.85,
                "Call with function and argument",
            ),
            (r'Import with (?:module )?["\']([^"\']+)["\']', 0.7, "Import with module"),
            (r'Import matching ["\']([^"\']+)["\']', 0.7, "Import matching pattern"),
            (r"For with nested For", 0.85, "For with nested For"),
            (r"While with nested While", 0.9, "While with nested While"),
            (r"AsyncFor with nested AsyncFor", 0.85, "AsyncFor with nested AsyncFor"),
            (r"Try with more than one ExceptHandler", 0.8, "Try with multiple exceptions"),
            (r'Try with bare ["\']except:?[\'"]?', 0.85, "Try with bare except"),
            (
                r'FunctionDef with name (?:containing|starting with) ["\'](\w+)["\']',
                0.75,
                "FunctionDef with specific name",
            ),
            (r'ClassDef with name ending in ["\'](\w+)["\']', 0.8, "ClassDef with name ending in"),
            (r'FunctionDef with decorator ["\']@(\w+)["\']', 0.85, "FunctionDef with decorator"),
            (
                r'FunctionDef with body containing only ["\'](\w+)["\']',
                0.75,
                "FunctionDef with simple body",
            ),
            (
                r'FunctionDef with parameter default ["\'](\S+)["\']',
                0.9,
                "FunctionDef with mutable default",
            ),
            (r'Import with alias ["\'](\w+ import \w+ as \w+)["\']', 0.65, "Import with alias"),
            (r'Import matching ["\']import \*["\']', 0.9, "Import star"),
            (
                r"FunctionDef with (?:no return|without return) annotations",
                0.75,
                "FunctionDef without return annotations",
            ),
        ]

        for pattern, weight, desc in ast_keywords:
            # Check if pattern appears in system prompt
            if re.search(pattern, system_prompt, re.IGNORECASE):
                patterns.append(
                    {"type": "ast", "pattern": desc, "language": "python", "weight": weight}
                )

        return patterns

    def _extract_file_path_patterns(
        self, system_prompt: str, agent: BaseReviewerAgent
    ) -> List[Dict[str, Any]]:
        """Extract file path patterns from system prompt.

        Looks for glob patterns like:
        - "**/*.py"
        - "auth/**"
        - "README*"
        - "**/tests/**/*.py"

        Args:
            system_prompt: The agent's system prompt
            agent: The agent instance

        Returns:
            List of file path pattern dictionaries
        """
        patterns = []

        # Look for glob patterns in system prompt
        glob_pattern = re.compile(r'["\']([\w\*/_\-\.]+)["\']')

        # Find all glob-like patterns
        for match in glob_pattern.finditer(system_prompt):
            pattern_str = match.group(1)

            # Only include if it looks like a glob pattern
            if "*" in pattern_str or "/" in pattern_str:
                # Determine weight based on pattern
                weight = 0.7
                if "**" in pattern_str:
                    weight = 0.8
                if pattern_str.startswith("**/"):
                    weight = 0.75

                # Avoid duplicates
                if not any(p["pattern"] == pattern_str for p in patterns):
                    patterns.append({"type": "file_path", "pattern": pattern_str, "weight": weight})

        return patterns

    def _extract_content_patterns(self, system_prompt: str) -> List[Dict[str, Any]]:
        """Extract content patterns from system prompt.

        Looks for:
        - Keywords like "secrets", "password", "token"
        - Regex patterns mentioned in prompt
        - Specific strings to search for

        Args:
            system_prompt: The agent's system prompt

        Returns:
            List of content pattern dictionaries
        """
        patterns = []

        # Look for specific content patterns
        content_indicators = [
            (
                r"(?:password|secret|token|api_key)\s*[=:]",
                0.95,
                r"password\\s*[=:]|secret\\s*[=:]|token\\s*[=:]|api_key\\s*[=:]",
            ),
            (r"AWS_[A-Z_]+|PRIVATE_KEY", 0.95, r"AWS_[A-Z_]+|PRIVATE_KEY"),
            (r"eval\s*\(", 0.95, r"eval\s*\("),
            (r"exec\s*\(", 0.95, r"exec\s*\("),
            (r"pickle\.loads\s*\(", 0.9, r"pickle\.loads\s*\("),
            (r"yaml\.load\s*\(", 0.9, r"yaml\.load\s*\("),
            (
                r"subprocess\.\w+\([^)]*shell\s*=\s*True",
                0.95,
                r"subprocess\.\w+\([^)]*shell\s*=\s*True",
            ),
            (
                r"subprocess\.\w+\([^)]*shell\s*=\s*True",
                0.95,
                r"subprocess\.\w+\([^)]*shell\s*=\s*True",
            ),
            (r"os\.system\s*\(", 0.95, r"os\.system\s*\("),
            (r"cursor\.execute\s*\([^)]*%[^)]*\)", 0.9, r"cursor\.execute\s*\([^)]*%"),
            (r"cursor\.execute\s*\([^)]*\.format", 0.9, r"cursor\.execute\s*\([^)]*\.format"),
            (r"except\s*:\s*pass", 0.85, r"except\s*:\s*pass"),
            (
                r"import\s+pickle|from\s+pickle\s+import",
                0.8,
                r"import\s+pickle|from\s+pickle\s+import",
            ),
            (r"NotImplementedError", 0.85, r"NotImplementedError"),
            (r"TODO|FIXME|XXX", 0.6, r"TODO|FIXME|XXX"),
            (r"\.\s*pass\s*$", 0.75, r"\.\s*pass\s*$"),
            (r"def\s+\w+\([^)]*\):\s*return\s+None", 0.7, r"def\s+\w+\([^)]*\):\s*return\s+None"),
            (
                r'version\s*=\s*["\'][\d\.]+\.\d+\.\\d+["\']',
                0.9,
                r'version\s*=\s*["\'][\d\.]+\.\d+\.\\d+["\']',
            ),
            (
                r"for\s+\w+\s+in\s+[^:]+:\s*for\s+\w+\s+in\s+",
                0.9,
                r"for\s+\w+\s+in\s+[^:]+:\s*for\s+\w+\s+in\s+",
            ),
            (r"while\s+\w+:\s*while\s+\w+:", 0.9, r"while\s+\w+:\s*while\s+\w+:"),
            (r"@\w+|@tenacity", 0.85, r"@retry|@tenacity"),
            (r"@deprecated", 0.9, r"@deprecated"),
            (r"warnings\.warn", 0.8, r"warnings\.warn"),
            (r"BREAKING|breaking", 0.85, r"BREAKING|breaking"),
            (r"deprecated|DEPRECATED", 0.85, r"deprecated|DEPRECATED"),
            (r'\*\s+["\']', 0.9, r'\*\s+["\']'),
            (r".{120,}", 0.7, r".{120,}"),
        ]

        for pattern, weight, regex in content_indicators:
            # Check if pattern appears in system prompt
            if re.search(pattern, system_prompt, re.IGNORECASE):
                patterns.append(
                    {"type": "content", "pattern": regex, "language": "python", "weight": weight}
                )

        return patterns

    def _extract_heuristics_from_prompt(self, system_prompt: str, agent_name: str) -> List[str]:
        """Extract heuristic rules from system prompt.

        Looks for:
        - Sentences starting with "Look for"
        - Sentences starting with "Check for"
        - Sentences starting with "Verify"
        - Sentences containing "should"
        - Sentences containing "recommend"
        - Sentences containing "consider"
        - Bullet points after "Blocking conditions:"
        - Questions under "must answer:"

        Args:
            system_prompt: The agent's system prompt
            agent_name: Name of the agent for fallback heuristics

        Returns:
            List of heuristic rule strings
        """
        heuristics = []

        # Clean system prompt by removing JSON schema sections that contain false positive keywords
        # like "should", "include", "title" which appear in schema definitions
        prompt_without_schema = system_prompt
        json_schema_removal_patterns = [
            r'\{[^}]*"title"[^}]*\}',
            r'"title":\s*"[^"]*",\s*"type"',
            r"CRITICAL RULES:.*?EXAMPLE VALID OUTPUT:",
        ]
        for pattern in json_schema_removal_patterns:
            prompt_without_schema = re.sub(pattern, "", prompt_without_schema, flags=re.DOTALL)

        # Extract bullet points under specific sections
        # Matches: "Blocking conditions:\n- plaintext secrets..."
        section_bullets_patterns = [
            (r"Blocking conditions:(.*?)(?=\n[A-Z]|\n---|\Z)", 0),
            (r"You specialize in:(.*?)(?=\n[A-Z]|\n---|\Z)", 0),
            (r"Checks you may request:(.*?)(?=\n[A-Z]|\n---|\Z)", 0),
            (r"High-signal file patterns:(.*?)(?=\n[A-Z]|\n---|\Z)", 0),
        ]

        for section_pattern, _ in section_bullets_patterns:
            for match in re.finditer(
                section_pattern, prompt_without_schema, re.IGNORECASE | re.DOTALL
            ):
                section_content = match.group(1)
                bullet_points = re.findall(r"^-\s+(.+)$", section_content, re.MULTILINE)
                for point in bullet_points:
                    point_clean = point.strip()
                    if point_clean and len(point_clean) > 10:
                        heuristics.append(point_clean)

        # Extract questions from "must answer:" sections
        must_answer_pattern = r"must answer:(.*?)(?=\n[A-Z]|\n---|\Z)"
        for match in re.finditer(
            must_answer_pattern, prompt_without_schema, re.IGNORECASE | re.DOTALL
        ):
            section_content = match.group(1)
            numbered_questions = re.findall(r"^\d+\)\s+(.+)$", section_content, re.MULTILINE)
            for question in numbered_questions:
                question_clean = question.strip()
                if question_clean and len(question_clean) > 10:
                    heuristics.append(question_clean)

        # Heuristic indicators
        heuristic_patterns = [
            r"Look for\s+([^.!?]+)",
            r"Check for\s+([^.!?]+)",
            r"Verify\s+([^.!?]+)",
        ]

        for pattern in heuristic_patterns:
            for match in re.finditer(pattern, prompt_without_schema, re.IGNORECASE):
                heuristic = match.group(1).strip()
                if heuristic and len(heuristic) > 10 and len(heuristic) < 200:
                    heuristics.append(heuristic)

        # Look for "should"/"recommend"/"consider" patterns
        should_recommend_consider_patterns = [
            r"\bshould\s+([^.!?]+)",
            r"\brecommend(?:s|ed|ing)?\s+([^.!?]+)",
            r"\bconsider\s+([^.!?]+)",
        ]

        for pattern in should_recommend_consider_patterns:
            for match in re.finditer(pattern, prompt_without_schema, re.IGNORECASE):
                heuristic = match.group(1).strip()
                if heuristic and len(heuristic) > 10 and len(heuristic) < 200:
                    # Add appropriate prefix
                    if "should" in match.group(0).lower():
                        heuristics.append(f"Should {heuristic}")
                    elif "recommend" in match.group(0).lower():
                        heuristics.append(f"Consider {heuristic}")
                    else:
                        heuristics.append(heuristic)

        # Remove duplicates while preserving order
        seen = set()
        unique_heuristics = []
        for h in heuristics:
            h_lower = h.lower()
            if h_lower not in seen:
                seen.add(h_lower)
                unique_heuristics.append(h)

        # Ensure at least one heuristic is returned
        if not unique_heuristics:
            # Get agent name for fallback
            default_heuristics = {
                "security": [
                    "Check for insecure imports (pickle, eval, exec, marshal, shelve)",
                    "Verify proper authentication and authorization checks",
                    "Look for SQL injection vulnerabilities in database queries",
                ],
                "architecture": [
                    "Check for circular dependencies between modules",
                    "Look for god objects with too many responsibilities",
                    "Verify dependency injection patterns are consistent",
                ],
                "documentation": [
                    "Check for missing docstrings on public functions/classes",
                    "Verify README reflects current behavior and features",
                    "Look for changes that require configuration documentation updates",
                ],
                "linting": [
                    "Check for mutable default arguments (= [], = {})",
                    "Look for type hints coverage on public APIs",
                    "Verify import ordering and grouping",
                ],
                "telemetry": [
                    "Check for secrets/PII being logged in error messages",
                    "Look for critical paths with no error logging or metrics",
                    "Verify retry loops have limits and logging for visibility",
                ],
                "unit_tests": [
                    "Check for tests with time dependencies (need mocking)",
                    "Look for tests using random (need seeding for determinism)",
                    "Verify assertions are specific (not just assert True)",
                ],
                "diff_scoper": [
                    "Classify diff risk based on lines changed (>500 lines = high risk)",
                    "Look for deletions of classes/functions (breaking changes)",
                    "Check for changes to critical paths (auth, payments, core logic)",
                ],
                "requirements": [
                    "Compare implementation to PR description/ticket requirements",
                    "Check for acceptance criteria coverage",
                    "Look for incomplete implementations (NotImplementedError, pass)",
                ],
                "performance": [
                    "Look for nested loops (O(n^2) complexity)",
                    "Check for N+1 query patterns (queries inside loops)",
                    "Verify retry logic has exponential backoff and max attempts",
                ],
                "dependencies": [
                    "Check for new dependencies added without justification",
                    "Verify license compatibility (avoid GPL/AGPL if proprietary)",
                    "Look for loosened version pins (reproducibility risk)",
                ],
                "changelog": [
                    "Check for breaking changes without migration notes",
                    "Verify version bump matches change scope (major/minor/patch)",
                    "Look for user-visible behavior changes without changelog entry",
                ],
            }
            unique_heuristics = default_heuristics.get(
                agent_name, ["Review code changes for relevant patterns"]
            )

        return unique_heuristics[:15]  # Limit to 15 heuristics

    def _determine_agent_type(self, agent: BaseReviewerAgent) -> str:
        """Determine if agent is required or optional.

        Args:
            agent: The agent instance

        Returns:
            'required' or 'optional'
        """
        agent_name = self._get_agent_name(agent)

        # Required agents (core reviewers)
        required_agents = {
            "architecture",
            "security",
            "linting",
            "diff_scoper",
            "requirements",
        }

        return "required" if agent_name in required_agents else "optional"

    def _generate_yaml_frontmatter(
        self,
        agent_name: str,
        agent_type: str,
        patterns: List[Dict[str, Any]],
        heuristics: List[str],
        prompt_hash: str,
    ) -> str:
        """Generate YAML frontmatter for documentation.

        Args:
            agent_name: Name of agent
            agent_type: 'required' or 'optional'
            patterns: List of pattern dictionaries
            heuristics: List of heuristic strings
            prompt_hash: Hash of system prompt

        Returns:
            YAML frontmatter string
        """
        lines = ["---", f"agent: {agent_name}", f"agent_type: {agent_type}", "version: 1.0.0"]

        # Generated timestamp
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f"generated_at: {generated_at}")
        lines.append(f"prompt_hash: {prompt_hash}")
        lines.append("patterns:")

        # Add patterns
        for pattern in patterns:
            lines.append(f"  - type: {pattern['type']}")
            lines.append(f'    pattern: "{pattern["pattern"]}"')
            if "language" in pattern:
                lines.append(f"    language: {pattern['language']}")
            lines.append(f"    weight: {pattern['weight']}")

        lines.append("heuristics:")

        # Add heuristics
        for heuristic in heuristics:
            lines.append(f'  - "{heuristic}"')

        lines.append("---")

        return "\\n".join(lines)

    def _generate_full_documentation(
        self,
        agent_name: str,
        frontmatter: str,
        system_prompt: str,
        patterns: List[Dict[str, Any]],
        heuristics: List[str],
    ) -> str:
        """Generate full documentation content.

        Args:
            agent_name: Name of agent
            frontmatter: YAML frontmatter string
            system_prompt: The agent's system prompt
            patterns: List of pattern dictionaries
            heuristics: List of heuristic strings

        Returns:
            Full documentation content
        """
        lines = [frontmatter, ""]

        # Add overview section
        title = f"# {agent_name.replace('_', ' ').title()} Reviewer Entry Points"
        lines.append(title)
        lines.append("")
        lines.append(
            "This document defines entry points for {} reviewer agent to use when determining which code to analyze in PR reviews.".format(
                agent_name.replace("_", " ")
            )
        )
        lines.append("")

        # Add overview
        lines.append("## Overview")
        lines.append("")

        # Extract specialization from system prompt
        specialize_match = re.search(r"You specialize in:\s*\n\s*([^\n]+)", system_prompt)
        if specialize_match:
            lines.append(f"The {agent_name.replace('_', ' ')} reviewer specializes in:")
            lines.append("")
            specialization = specialize_match.group(1).strip()
            lines.append(f"- {specialization}")
            lines.append("")

        # Group patterns by type
        ast_patterns = [p for p in patterns if p["type"] == "ast"]
        file_path_patterns = [p for p in patterns if p["type"] == "file_path"]
        content_patterns = [p for p in patterns if p["type"] == "content"]

        # Add AST patterns section
        if ast_patterns:
            lines.append("### AST Patterns (High Weight: 0.7-0.95)")
            lines.append("")
            lines.append("AST patterns match against abstract syntax tree of Python code.")
            lines.append("")

            high_weight = [p for p in ast_patterns if p["weight"] >= 0.9]
            medium_high = [p for p in ast_patterns if 0.8 <= p["weight"] < 0.9]
            medium = [p for p in ast_patterns if p["weight"] < 0.8]

            if high_weight:
                lines.append("**High-weight patterns (0.9+):**")
                for p in high_weight:
                    lines.append(f"- {p['pattern']}")
                lines.append("")

            if medium_high:
                lines.append("**Medium-high patterns (0.8-0.9):**")
                for p in medium_high:
                    lines.append(f"- {p['pattern']}")
                lines.append("")

            if medium:
                lines.append("**Medium patterns (0.7-0.8):**")
                for p in medium:
                    lines.append(f"- {p['pattern']}")
                lines.append("")

        # Add file path patterns section
        if file_path_patterns:
            lines.append("### File Path Patterns (Weight: 0.7-0.8)")
            lines.append("")
            lines.append("File path patterns match against changed file paths using glob patterns.")
            lines.append("")

            for p in file_path_patterns[:10]:
                lines.append(f"- `{p['pattern']}` (weight: {p['weight']})")
            lines.append("")

        # Add content patterns section
        if content_patterns:
            lines.append("### Content Patterns (Weight: 0.7-0.95)")
            lines.append("")
            lines.append(
                "Content patterns use regex to search for specific strings in file contents."
            )
            lines.append("")

            high_weight = [p for p in content_patterns if p["weight"] >= 0.9]
            medium = [p for p in content_patterns if p["weight"] < 0.9]

            if high_weight:
                lines.append("**High-weight patterns (0.9+):**")
                for p in high_weight:
                    lines.append(f"- `{p['pattern']}`")
                lines.append("")

            if medium:
                lines.append("**Medium patterns (0.7-0.9):**")
                for p in medium:
                    lines.append(f"- `{p['pattern']}`")
                lines.append("")

        # Add usage section
        lines.append("## Usage During Review")
        lines.append("")
        lines.append(
            "1. When a PR is received, {} reviewer loads this document".format(
                agent_name.replace("_", " ")
            )
        )
        lines.append("2. For each pattern, reviewer searches changed files")
        lines.append("3. Matches are collected and weighted by relevance")
        lines.append("4. Top matches are included in the LLM context for analysis")
        lines.append(
            '5. Verification evidence is attached to `ReviewOutput.extra_data["verification"]`'
        )
        lines.append("")

        # Add heuristics section
        if heuristics:
            lines.append("## Heuristics for LLM")
            lines.append("")
            lines.append(
                "The heuristics list provides guidance to the LLM when analyzing discovered entry points."
            )
            lines.append("")

            for heuristic in heuristics:
                lines.append(f"- {heuristic}")
            lines.append("")

        # Add maintenance section
        lines.append("## Maintenance")
        lines.append("")
        lines.append(
            "This document should be regenerated when {} reviewer's system prompt changes to keep entry points in sync with the agent's focus.".format(
                agent_name.replace("_", " ")
            )
        )
        lines.append("")
        lines.append("```bash")
        lines.append(f"opencode review generate-docs --agent {agent_name}")
        lines.append("```")
        lines.append("")

        return "\\n".join(lines)

    def _save_doc(self, output_path: Path, content: str) -> None:
        """Save documentation to file.

        Args:
            output_path: Path where to save documentation
            content: Documentation content to save
        """
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        output_path.write_text(content, encoding="utf-8")

        logger.info(f"Saved documentation to {output_path}")
