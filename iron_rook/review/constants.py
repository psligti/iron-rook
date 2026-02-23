"""Constants for .iron-rook directory structure."""

from pathlib import Path

IRON_ROOK_DIR = ".iron-rook"
CHECKPOINTS_DIR = "checkpoints"
REPORTS_DIR = "reports"
LOGS_DIR = "logs"


def get_iron_rook_dir(repo_root: Path) -> Path:
    """Get the .iron-rook directory path."""
    return repo_root / IRON_ROOK_DIR


def get_checkpoints_dir(repo_root: Path) -> Path:
    """Get the checkpoints directory path."""
    return get_iron_rook_dir(repo_root) / CHECKPOINTS_DIR


def get_reports_dir(repo_root: Path) -> Path:
    """Get the reports directory path."""
    return get_iron_rook_dir(repo_root) / REPORTS_DIR


def get_logs_dir(repo_root: Path) -> Path:
    """Get the logs directory path."""
    return get_iron_rook_dir(repo_root) / LOGS_DIR
