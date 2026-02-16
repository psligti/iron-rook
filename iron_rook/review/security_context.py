"""Security context loader for reducing false positives in security reviews.

This module provides utilities to load and inject architectural context
into security review prompts, helping reviewers understand where security
is enforced and what NOT to flag.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)


class SecurityContextLoader:
    """Loads and generates security context for reviewers.

    Combines:
    1. Static context from SECURITY_CONTEXT.md (human-maintained)
    2. Auto-detected context from codebase analysis
    3. Negative rules (things NOT to flag)
    """

    # Default context file name
    CONTEXT_FILE = "SECURITY_CONTEXT.md"

    # Common patterns indicating where security is enforced
    AUTH_PATTERNS = [
        "@require_auth",
        "@auth_required",
        "@login_required",
        "AuthMiddleware",
        "AuthenticationMiddleware",
        "def authenticate",
        "def authorize",
    ]

    RATE_LIMIT_PATTERNS = [
        "@limiter",
        "@ratelimit",
        "RateLimiter",
        "rate_limit",
        "throttle",
    ]

    SESSION_PATTERNS = [
        "SessionMiddleware",
        "session.get(",
        "session_manager",
        "create_session",
    ]

    def __init__(self, repo_root: str):
        """Initialize context loader.

        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = repo_root
        self._static_context: Optional[str] = None
        self._auto_context: Optional[str] = None

    def load_context(self) -> str:
        """Load and combine all context sources."""
        parts = []

        static = self._load_static_context()
        if static:
            parts.append("## ARCHITECTURE CONTEXT (from SECURITY_CONTEXT.md)\n")
            parts.append(static)

        auto = self._detect_context()
        if auto:
            parts.append("\n## AUTO-DETECTED CONTEXT\n")
            parts.append(auto)

        parts.append("\n## DO NOT FLAG (Common False Positives)\n")
        parts.append(self._get_negative_rules())

        return "\n".join(parts)

    def _load_static_context(self) -> str:
        if self._static_context is not None:
            return self._static_context

        context_path = os.path.join(self.repo_root, self.CONTEXT_FILE)
        if not os.path.exists(context_path):
            logger.debug(f"No SECURITY_CONTEXT.md found at {context_path}")
            self._static_context = ""
            return ""

        try:
            with open(context_path, "r") as f:
                self._static_context = f.read()
            logger.info(f"Loaded security context from {context_path}")
        except Exception as e:
            logger.warning(f"Failed to load security context: {e}")
            self._static_context = ""
        return self._static_context

    def _detect_context(self) -> str:
        if self._auto_context is not None:
            return self._auto_context

        findings = []
        auth_location = self._find_patterns_location(self.AUTH_PATTERNS)
        if auth_location:
            findings.append(f"- Authentication enforced at: {', '.join(auth_location[:3])}")

        rate_location = self._find_patterns_location(self.RATE_LIMIT_PATTERNS)
        if rate_location:
            findings.append(f"- Rate limiting enforced at: {', '.join(rate_location[:3])}")

        session_location = self._find_patterns_location(self.SESSION_PATTERNS)
        if session_location:
            findings.append(f"- Session management at: {', '.join(session_location[:3])}")

        self._auto_context = "\n".join(findings) if findings else ""
        return self._auto_context

    def _find_patterns_location(self, patterns: List[str]) -> List[str]:
        locations = []
        for pattern in patterns[:3]:
            try:
                cmd = [
                    "rg",
                    "-l",
                    "-g",
                    "*.py",
                    "-g",
                    "!*test*",
                    "--max-count=1",
                    pattern,
                    self.repo_root,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.returncode == 0 and proc.stdout.strip():
                    for line in proc.stdout.strip().split("\n")[:1]:
                        locations.append(os.path.relpath(line, self.repo_root))
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            except Exception as e:
                logger.debug(f"Pattern search failed for {pattern}: {e}")
        return list(set(locations))

    def _get_negative_rules(self) -> str:
        return """
1. **"No authentication on service function"** - Auth is at router level, not service layer
2. **"No rate limiting on internal function"** - Rate limiting is at gateway/middleware
3. **"Unused parameter"** - May be intentional for interface compliance or future use
4. **"Uses html.parser"** - This is the SECURE parser choice (not a vulnerability)
5. **"No input validation in service"** - Validation often at Pydantic/router level
6. **"Missing CSRF token"** - Check if this is a stateless API (doesn't need CSRF)
7. **"No HTTPS in code"** - HTTPS is server/infrastructure configuration
8. **"Generic exception handling"** - Often intentional for error logging/wrapping
9. **"Missing size validation"** - Only flag if it's a new vulnerability, not hardening
10. **"BeautifulSoup parsing"** - Only flag if using lxml/html5lib (vulnerable parsers)

## POSITIVE FINDINGS (Mark as INFO, NOT vulnerability)

If you find code that correctly implements security:
- Set severity to "info"
- Set category to "positive"
- DO NOT add to must_fix or should_fix lists

Examples of POSITIVE findings:
- "Correctly uses html.parser (secure BeautifulSoup parser)"
- "Input validated via Pydantic model at router"
- "Rate limiting configured at middleware level"
"""


def load_security_context(repo_root: str) -> str:
    """Load combined security context for a repository."""
    return SecurityContextLoader(repo_root).load_context()


def classify_finding_severity(title: str, description: str) -> tuple[str, str]:
    """Classify finding severity with smart rules for false positive reduction."""
    title_lower = title.lower()
    desc_lower = description.lower()
    combined = f"{title_lower} {desc_lower}"

    positive_indicators = [
        "is secure",
        "is correct",
        "properly configured",
        "uses secure",
        "correctly implements",
        "follows best practice",
        "has validation",
        "has authentication",
        "has rate limiting",
        "secure parser",
    ]
    for indicator in positive_indicators:
        if indicator in combined:
            return ("info", "positive")

    out_of_scope_patterns = [
        ("no authentication", ["function", "service", "endpoint", "module"]),
        ("no rate limiting", ["function", "service", "endpoint", "module"]),
        ("no session", ["function", "service", "module"]),
        ("unused parameter", []),
        ("no csrf", ["api", "stateless"]),
    ]

    for pattern, context_words in out_of_scope_patterns:
        if pattern in combined:
            if not context_words:
                return ("info", "out_of_scope")
            for word in context_words:
                if word in combined:
                    return ("info", "out_of_scope")

    if any(w in combined for w in ["critical", "sql injection", "xss", "rce", "auth bypass"]):
        return ("critical", "vulnerability")
    if any(w in combined for w in ["high", "exposed secret", "credential", "bypass"]):
        return ("high", "vulnerability")
    if any(w in combined for w in ["medium", "missing", "hardening", "validation"]):
        return ("medium", "hardening")
    return ("low", "best_practice")
