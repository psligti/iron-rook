"""Pattern learning mechanism for PR review agents.

This module provides functionality for reviewers to learn new entry point patterns
from PR reviews and stage them for manual approval before integration.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


class PatternLearning:
    """Manages pattern learning and staging for reviewer agents.

    Patterns are learned during PR reviews and staged for manual approval.
    This provides safety by preventing automatic pattern application.

    Staging workflow:
    1. Reviewer calls add_learned_pattern() during review
    2. Patterns are stored in agent-specific staged file
    3. Developer reviews staged patterns manually
    4. Developer calls commit_learned_patterns() to merge into main doc
    """

    def __init__(self, docs_dir: Optional[Path] = None):
        """Initialize PatternLearning.

        Args:
            docs_dir: Path to reviewers docs directory. If None, uses default.
        """
        if docs_dir is None:
            docs_dir = Path(__file__).parents[4] / "docs" / "reviewers"
        self.docs_dir = Path(docs_dir)

    def add_learned_pattern(
        self,
        agent_name: str,
        pattern: Dict[str, Any]
    ) -> bool:
        """Add a learned pattern to the staged list for an agent.

        Args:
            agent_name: Name of the agent (e.g., "security")
            pattern: Pattern dictionary with keys:
                - type: "ast", "file_path", or "content"
                - pattern: The pattern string
                - weight: Relevance weight (0.0-1.0)
                - language: Optional language field (required for ast/content)
                - source: Optional source description (e.g., "PR #123")

        Returns:
            True if pattern was added successfully, False otherwise

        Example:
            >>> pattern = {
            ...     'type': 'content',
            ...     'pattern': r'API_KEY\\s*[=:]',
            ...     'language': 'python',
            ...     'weight': 0.95,
            ...     'source': 'PR #123 - Hardcoded secret found'
            ... }
            >>> learning.add_learned_pattern('security', pattern)
            True
        """
        try:
            # Validate pattern structure
            if not self._validate_pattern(pattern):
                logger.warning(f"Invalid pattern structure for {agent_name}: {pattern}")
                return False

            # Get staged patterns file path
            staged_file = self._get_staged_file_path(agent_name)

            # Load existing staged patterns
            staged_patterns = self._load_staged_patterns(agent_name)

            # Check for duplicates (same type + pattern)
            for existing in staged_patterns:
                if (existing.get('type') == pattern.get('type') and
                    existing.get('pattern') == pattern.get('pattern')):
                    logger.info(f"Pattern already staged for {agent_name}: {pattern['pattern']}")
                    return False

            # Add new pattern
            staged_patterns.append(pattern)

            # Save to staged file
            self._save_staged_patterns(agent_name, staged_patterns)

            logger.info(f"Added learned pattern for {agent_name}: {pattern['pattern']}")
            return True

        except Exception as e:
            logger.error(f"Failed to add learned pattern for {agent_name}: {e}")
            return False

    def get_staged_patterns(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get all staged patterns for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            List of staged pattern dictionaries
        """
        return self._load_staged_patterns(agent_name)

    def commit_learned_patterns(self, agent_name: str) -> tuple[bool, str]:
        """Commit staged patterns to agent's main documentation.

        This merges staged patterns from {agent_name}_staged_patterns.yaml
        into the main {agent_name}_reviewer.md file.

        Args:
            agent_name: Name of the agent

        Returns:
            Tuple of (success, message)

        Example:
            >>> success, msg = learning.commit_learned_patterns('security')
            >>> if success:
            ...     print(f"Committed {msg}")
        """
        try:
            # Load staged patterns
            staged_patterns = self._load_staged_patterns(agent_name)

            if not staged_patterns:
                return False, f"No staged patterns found for {agent_name}"

            # Get main doc path
            main_doc_path = self.docs_dir / f"{agent_name}_reviewer.md"

            if not main_doc_path.exists():
                return False, f"Main documentation not found: {main_doc_path}"

            # Load main doc content
            content = main_doc_path.read_text(encoding='utf-8')

            # Extract existing patterns from YAML frontmatter
            existing_patterns = self.load_patterns_from_doc(agent_name, main_doc_path)

            # Merge patterns (prioritize existing, add new ones)
            merged_patterns = self._merge_patterns(existing_patterns, staged_patterns)

            # Update YAML frontmatter with merged patterns
            updated_content = self._update_yaml_frontmatter(content, merged_patterns)

            # Save updated main doc
            main_doc_path.write_text(updated_content, encoding='utf-8')

            # Clear staged patterns file
            staged_file = self._get_staged_file_path(agent_name)
            if staged_file.exists():
                staged_file.unlink()

            committed_count = len(staged_patterns)
            logger.info(f"Committed {committed_count} patterns for {agent_name}")

            return True, f"Committed {committed_count} patterns to {agent_name}_reviewer.md"

        except Exception as e:
            logger.error(f"Failed to commit patterns for {agent_name}: {e}")
            return False, f"Error committing patterns for {agent_name}: {str(e)}"

    def load_patterns_from_doc(
        self,
        agent_name: str,
        doc_path: Path
    ) -> List[Dict[str, Any]]:
        """Load patterns from agent documentation YAML frontmatter.

        Args:
            agent_name: Name of the agent
            doc_path: Path to the agent documentation file

        Returns:
            List of pattern dictionaries from the documentation

        Example:
            >>> patterns = learning.load_patterns_from_doc(
            ...     'security',
            ...     Path('docs/reviewers/security_reviewer.md')
            ... )
            >>> print(f"Found {len(patterns)} patterns")
        """
        try:
            if not doc_path.exists():
                logger.warning(f"Documentation file not found: {doc_path}")
                return []

            content = doc_path.read_text(encoding='utf-8')

            # Extract YAML frontmatter
            frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not frontmatter_match:
                logger.warning(f"No YAML frontmatter found in {doc_path}")
                return []

            frontmatter_text = frontmatter_match.group(1)

            # Parse patterns array
            patterns = []
            in_patterns_section = False
            current_pattern = {}

            for line in frontmatter_text.split('\n'):
                stripped = line.strip()

                if stripped.startswith('patterns:'):
                    in_patterns_section = True
                    continue

                if in_patterns_section:
                    if stripped.startswith('- type:'):
                        # Save previous pattern if exists
                        if current_pattern:
                            patterns.append(current_pattern)
                        # Start new pattern
                        current_pattern = {'type': stripped.split('type:')[1].strip()}
                    elif current_pattern and stripped.startswith('pattern:'):
                        # Extract pattern string (handle quotes)
                        pattern_value = stripped.split('pattern:')[1].strip().strip('"\'')
                        current_pattern['pattern'] = pattern_value
                    elif current_pattern and stripped.startswith('language:'):
                        current_pattern['language'] = stripped.split('language:')[1].strip()
                    elif current_pattern and stripped.startswith('weight:'):
                        weight_str = stripped.split('weight:')[1].strip()
                        current_pattern['weight'] = float(weight_str)
                    elif not stripped or stripped.startswith('heuristics:'):
                        # End of patterns section or empty line
                        if current_pattern:
                            patterns.append(current_pattern)
                            current_pattern = {}
                        if stripped.startswith('heuristics:'):
                            in_patterns_section = False

            # Add last pattern if exists
            if current_pattern:
                patterns.append(current_pattern)

            logger.info(f"Loaded {len(patterns)} patterns from {doc_path}")
            return patterns

        except Exception as e:
            logger.error(f"Failed to load patterns from {doc_path}: {e}")
            return []

    def _get_staged_file_path(self, agent_name: str) -> Path:
        """Get the path to the staged patterns file for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            Path to staged patterns YAML file
        """
        return self.docs_dir / f"{agent_name}_staged_patterns.yaml"

    def _load_staged_patterns(self, agent_name: str) -> List[Dict[str, Any]]:
        """Load staged patterns from YAML file.

        Args:
            agent_name: Name of the agent

        Returns:
            List of staged pattern dictionaries
        """
        staged_file = self._get_staged_file_path(agent_name)

        if not staged_file.exists():
            return []

        try:
            content = staged_file.read_text(encoding='utf-8')

            # Parse simple YAML structure
            patterns = []
            current_pattern = {}

            for line in content.split('\n'):
                stripped = line.strip()

                if stripped.startswith('- type:'):
                    if current_pattern:
                        patterns.append(current_pattern)
                    current_pattern = {'type': stripped.split('type:')[1].strip()}
                elif current_pattern and stripped.startswith('pattern:'):
                    pattern_value = stripped.split('pattern:')[1].strip().strip('"\'')
                    current_pattern['pattern'] = pattern_value
                elif current_pattern and stripped.startswith('language:'):
                    current_pattern['language'] = stripped.split('language:')[1].strip()
                elif current_pattern and stripped.startswith('weight:'):
                    weight_str = stripped.split('weight:')[1].strip()
                    current_pattern['weight'] = float(weight_str)
                elif current_pattern and stripped.startswith('source:'):
                    source_value = stripped.split('source:')[1].strip().strip('"\'')
                    current_pattern['source'] = source_value
                elif not stripped and current_pattern:
                    patterns.append(current_pattern)
                    current_pattern = {}

            if current_pattern:
                patterns.append(current_pattern)

            return patterns

        except Exception as e:
            logger.error(f"Failed to load staged patterns for {agent_name}: {e}")
            return []

    def _save_staged_patterns(
        self,
        agent_name: str,
        patterns: List[Dict[str, Any]]
    ) -> None:
        """Save staged patterns to YAML file.

        Args:
            agent_name: Name of the agent
            patterns: List of pattern dictionaries to save
        """
        staged_file = self._get_staged_file_path(agent_name)

        # Build YAML content
        lines = [
            f'# Staged patterns for {agent_name} reviewer',
            '# These patterns await manual approval before integration',
            '# To commit: python -m dawn_kestrel.agents.review.pattern_learning commit {agent_name}',
            '',
            'learned_patterns:'
        ]

        for pattern in patterns:
            lines.append(f'  - type: {pattern["type"]}')
            lines.append(f'    pattern: "{pattern["pattern"]}"')
            if 'language' in pattern:
                lines.append(f'    language: {pattern["language"]}')
            if 'weight' in pattern:
                lines.append(f'    weight: {pattern["weight"]}')
            if 'source' in pattern:
                lines.append(f'    source: "{pattern["source"]}"')

        content = '\n'.join(lines)

        # Ensure parent directory exists
        staged_file.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        staged_file.write_text(content, encoding='utf-8')

        logger.debug(f"Saved {len(patterns)} staged patterns to {staged_file}")

    def _validate_pattern(self, pattern: Dict[str, Any]) -> bool:
        """Validate pattern structure.

        Args:
            pattern: Pattern dictionary to validate

        Returns:
            True if pattern is valid, False otherwise
        """
        required_fields = ['type', 'pattern', 'weight']

        # Check required fields
        for field in required_fields:
            if field not in pattern:
                return False

        # Validate type
        if pattern['type'] not in ['ast', 'file_path', 'content']:
            return False

        # Validate weight range
        try:
            weight = float(pattern['weight'])
            if not (0.0 <= weight <= 1.0):
                return False
        except (ValueError, TypeError):
            return False

        # Validate pattern string is not empty
        if not pattern['pattern'] or not isinstance(pattern['pattern'], str):
            return False

        # For ast and content types, language is required
        if pattern['type'] in ['ast', 'content'] and 'language' not in pattern:
            return False

        return True

    def _merge_patterns(
        self,
        existing: List[Dict[str, Any]],
        new: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge existing patterns with new patterns.

        Args:
            existing: List of existing patterns from main doc
            new: List of new patterns from staged file

        Returns:
            Merged list of patterns (existing + unique new patterns)
        """
        merged = list(existing)

        # Track unique patterns by type + pattern combination
        seen = {(p['type'], p['pattern']) for p in existing}

        # Add new patterns that aren't duplicates
        for pattern in new:
            key = (pattern['type'], pattern['pattern'])
            if key not in seen:
                merged.append(pattern)
                seen.add(key)

        # Sort by weight (descending)
        merged.sort(key=lambda p: p.get('weight', 0.5), reverse=True)

        return merged

    def _update_yaml_frontmatter(
        self,
        content: str,
        new_patterns: List[Dict[str, Any]]
    ) -> str:
        """Update YAML frontmatter with new patterns.

        Args:
            content: Full documentation content
            new_patterns: New patterns to write to frontmatter

        Returns:
            Updated documentation content
        """
        # Extract YAML frontmatter
        frontmatter_match = re.search(r'^(---\n.*?\n---)', content, re.DOTALL)
        if not frontmatter_match:
            logger.warning("No YAML frontmatter found, returning original content")
            return content

        old_frontmatter = frontmatter_match.group(1)

        # Find patterns section in frontmatter
        patterns_start = old_frontmatter.find('\npatterns:')
        if patterns_start == -1:
            logger.warning("No patterns section found, returning original content")
            return content

        heuristics_start = old_frontmatter.find('\nheuristics:', patterns_start)
        if heuristics_start == -1:
            # No heuristics section, patterns goes to end
            patterns_end = len(old_frontmatter)
        else:
            patterns_end = heuristics_start

        # Build new patterns section
        new_patterns_lines = ['patterns:']
        for pattern in new_patterns:
            new_patterns_lines.append(f'  - type: {pattern["type"]}')
            new_patterns_lines.append(f'    pattern: "{pattern["pattern"]}"')
            if 'language' in pattern:
                new_patterns_lines.append(f'    language: {pattern["language"]}')
            new_patterns_lines.append(f'    weight: {pattern["weight"]}')

        new_patterns_section = '\n'.join(new_patterns_lines)

        # Rebuild frontmatter
        before_patterns = old_frontmatter[:patterns_start]
        after_patterns = old_frontmatter[patterns_end:]

        new_frontmatter = before_patterns + '\n' + new_patterns_section + after_patterns

        # Replace in full content
        updated_content = content.replace(old_frontmatter, new_frontmatter)

        return updated_content
