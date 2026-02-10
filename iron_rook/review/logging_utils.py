"""Centralized logging utilities for iron_rook with package filtering and context support."""

from __future__ import annotations

import logging
import sys
from typing import Optional, List


class PackageFilter(logging.Filter):
    """Filter to only allow logs from specified packages.

    This ensures only dawn_kestrel and iron_rook logs are displayed.
    """

    def __init__(self, packages: List[str]) -> None:
        self.packages = packages

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records to only allow specified packages.

        Args:
            record: LogRecord to filter

        Returns:
            True if record should be logged, False otherwise
        """
        return any(record.name.startswith(pkg) for pkg in self.packages)


class ReviewLogger:
    """Centralized logger with package filtering and context support.

    Provides a singleton instance for consistent logging configuration across
    the iron_rook package, with automatic filtering to only show
    dawn_kestrel and iron_rook logs.
    """

    _instance: Optional["ReviewLogger"] = None

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose
        self._context = None

        self.logger = logging.getLogger("iron_rook")
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        self.logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        handler.addFilter(PackageFilter(["iron_rook", "dawn_kestrel"]))

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)
        self.logger.propagate = False

    @classmethod
    def get(cls, verbose: bool = False) -> "ReviewLogger":
        """Get or create the singleton ReviewLogger instance.

        Args:
            verbose: Whether to enable DEBUG level logging

        Returns:
            The singleton ReviewLogger instance
        """
        if cls._instance is None or cls._instance._verbose != verbose:
            cls._instance = ReviewLogger(verbose)
        return cls._instance

    def set_context(self, context: Optional[object]) -> None:
        """Set review context for log messages.

        Args:
            context: ReviewContext object or similar with review metadata
        """
        self._context = context
        if context:
            try:
                repo_root = getattr(context, "repo_root", "unknown")
                base_ref = getattr(context, "base_ref", "unknown")
                head_ref = getattr(context, "head_ref", "unknown")
                changed_files_count = len(getattr(context, "changed_files", []))

                self.logger.info(
                    f"Review Context: repo_root={repo_root}, "
                    f"base_ref={base_ref}, head_ref={head_ref}, "
                    f"files={changed_files_count}"
                )
            except Exception:
                pass

    def log_with_context(self, level: int, msg: str, **kwargs) -> None:
        extra = {}
        if self._context is not None:
            try:
                extra["context"] = {
                    "repo_root": getattr(self._context, "repo_root", "unknown"),
                    "base_ref": getattr(self._context, "base_ref", None),
                    "head_ref": getattr(self._context, "head_ref", None),
                }
            except Exception:
                pass

        self.logger.log(level, msg, extra=extra)

    def verbose_logging_enabled(self) -> bool:
        """Check if verbose logging is enabled.

        Returns:
            True if DEBUG level logging is enabled
        """
        return self._verbose
