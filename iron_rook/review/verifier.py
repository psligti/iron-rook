"""FindingsVerifier strategy interface and implementations."""
from __future__ import annotations
from typing import List
from abc import ABC, abstractmethod


class FindingsVerifier(ABC):
    """Abstract strategy for verifying review findings.

    Implementations can use different verification approaches:
    - Grep-based pattern matching (GrepFindingsVerifier)
    - LSP-based code analysis (future: LSPFindingsVerifier)
    - Static analysis tools (future: StaticAnalysisFindingsVerifier)
    """

    @abstractmethod
    def verify(
        self,
        findings: List,
        changed_files: List[str],
        repo_root: str
    ) -> List[dict]:
        """Verify findings by cross-checking with code analysis tools.

        Args:
            findings: List of Finding objects from ReviewOutput
            changed_files: List of changed file paths
            repo_root: Repository root path

        Returns:
            List of verification entries, each containing:
                - tool_type: str (e.g., "grep", "lsp")
                - search_pattern: str (pattern searched for)
                - matches: List[str] (matching lines/content)
                - line_numbers: List[int] (line numbers where matches found)
                - file_path: str (file where matches found)

        Note:
            Graceful degradation: If verification fails, implementations
            should return empty list and log warning without blocking
            review completion.
        """
        pass


class GrepFindingsVerifier(FindingsVerifier):
    """Grep-based findings verification using pattern matching.

    This implementation:
    1. Extracts search patterns from finding evidence
    2. Uses grep to search for patterns in changed files
    3. Collects verification evidence (matches, line numbers)
    4. Returns structured verification data

    Graceful degradation: If verification fails, returns empty list
    and logs warning without blocking review completion.
    """

    def verify(
        self,
        findings: List,
        changed_files: List[str],
        repo_root: str
    ) -> List[dict]:
        """Verify findings by cross-checking with grep-based code analysis.

        Args:
            findings: List of Finding objects from ReviewOutput
            changed_files: List of changed file paths
            repo_root: Repository root path

        Returns:
            List of verification entries with grep match results
        """
        import logging

        logger = logging.getLogger(__name__)

        verification_evidence = []

        if not findings:
            logger.debug("[GrepFindingsVerifier] No findings to verify")
            return verification_evidence

        logger.info(f"[GrepFindingsVerifier] Verifying {len(findings)} findings")

        for finding in findings:
            try:
                # Extract search pattern from finding evidence
                evidence_text = finding.evidence if hasattr(finding, 'evidence') else ""
                title_text = finding.title if hasattr(finding, 'title') else ""

                # Try to extract meaningful search terms from evidence
                search_terms = self._extract_search_terms(evidence_text, title_text)

                for search_term in search_terms:
                    # Use grep to search for the term in changed files
                    grep_results = self._grep_files(search_term, changed_files, repo_root)

                    if grep_results:
                        verification_entry = {
                            "tool_type": "grep",
                            "search_pattern": search_term,
                            "matches": grep_results.get("matches", []),
                            "line_numbers": grep_results.get("line_numbers", []),
                            "file_path": grep_results.get("file_path", "")
                        }
                        verification_evidence.append(verification_entry)
                        logger.debug(
                            f"[GrepFindingsVerifier] Verified finding '{title_text}': "
                            f"{len(grep_results.get('matches', []))} grep matches"
                        )

            except Exception as e:
                # Graceful degradation: log warning and continue
                logger.warning(
                    f"[GrepFindingsVerifier] Verification failed for finding "
                    f"'{getattr(finding, 'title', 'unknown')}': {e}"
                )
                continue

        logger.info(f"[GrepFindingsVerifier] Verification complete: {len(verification_evidence)} evidence entries")
        return verification_evidence

    def _extract_search_terms(self, evidence_text: str, title_text: str) -> List[str]:
        """Extract meaningful search terms from evidence and title.

        Args:
            evidence_text: Evidence text from finding
            title_text: Title of the finding

        Returns:
            List of search terms extracted from the text
        """
        import re

        search_terms = []

        # Extract quoted strings (e.g., "API_KEY", 'password')
        quoted_pattern = r'["\']([^"\']{3,})["\']'
        for match in re.finditer(quoted_pattern, evidence_text):
            term = match.group(1).strip()
            if term and term not in search_terms:
                search_terms.append(term)

        # Extract code identifiers (e.g., eval, subprocess.run)
        # Match words that look like function calls or variable names
        code_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\s*(?:\(|=|\.)'
        for match in re.finditer(code_pattern, evidence_text):
            term = match.group(1)
            # Filter out common words
            if term.lower() not in ['the', 'and', 'for', 'are', 'line', 'file']:
                if term not in search_terms:
                    search_terms.append(term)

        # Extract key terms from title
        title_words = re.findall(r'\b([A-Z_]{2,})\b|[a-z_]{3,}', title_text)
        for word in title_words:
            if word and word.upper() == word:  # All caps - likely code identifier
                if word not in search_terms:
                    search_terms.append(word)

        # Limit search terms to avoid excessive grep calls and filter empty strings
        return [term for term in search_terms[:5] if term]

    def _grep_files(
        self,
        pattern: str,
        file_paths: List[str],
        repo_root: str
    ) -> dict:
        """Search for pattern in files using grep.

        Args:
            pattern: Search pattern (string literal, not regex)
            file_paths: List of file paths to search
            repo_root: Repository root path

        Returns:
            Dict with keys:
                - matches: List[str] (matching lines)
                - line_numbers: List[int] (line numbers)
                - file_path: str (first file where matches found)

        Note:
            Graceful degradation: Returns empty dict on failure
        """
        import logging
        import subprocess
        import shlex
        from pathlib import Path

        logger = logging.getLogger(__name__)

        matches = []
        line_numbers = []
        first_match_file = ""

        # Escape the pattern for safe shell use
        escaped_pattern = shlex.quote(pattern)

        for file_path in file_paths:
            try:
                full_path = Path(repo_root) / file_path
                if not full_path.exists():
                    continue

                # Use grep with line numbers (-n) and fixed string matching (-F)
                result = subprocess.run(
                    ['grep', '-n', '-F', escaped_pattern, str(full_path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if ':' in line:
                            line_num_str, content = line.split(':', 1)
                            try:
                                line_num = int(line_num_str)
                                line_numbers.append(line_num)
                                matches.append(content.strip())
                                if not first_match_file:
                                    first_match_file = file_path
                            except ValueError:
                                continue

            except subprocess.TimeoutExpired:
                logger.debug(f"Grep timeout for pattern '{pattern}' in {file_path}")
                continue
            except Exception as e:
                logger.debug(f"Grep failed for pattern '{pattern}' in {file_path}: {e}")
                continue

        return {
            "matches": matches,
            "line_numbers": line_numbers,
            "file_path": first_match_file
        }
