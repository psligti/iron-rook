"""Checkpoint manager for recovery and resume support."""

import hashlib
import json
import tempfile
from pathlib import Path
from typing import List, Optional

from iron_rook.review.contracts import CheckpointData
from iron_rook.review.constants import get_checkpoints_dir


class CheckpointManager:
    """Manages checkpoint persistence for review recovery.

    Provides atomic write operations to ensure checkpoint data integrity
    during save operations. Uses temp file + rename pattern to prevent
    partial reads if a write is interrupted.
    """

    def __init__(self, repo_root: Path):
        """Initialize checkpoint manager.

        Args:
            repo_root: Root directory of the repository being reviewed
        """
        self.checkpoints_dir = get_checkpoints_dir(repo_root)

    def _get_checkpoint_path(self, inputs_hash: str) -> Path:
        """Get the file path for a checkpoint by its inputs hash.

        Args:
            inputs_hash: SHA256 hash (first 16 chars) of changed files + diff

        Returns:
            Path to the checkpoint JSON file
        """
        return self.checkpoints_dir / f"{inputs_hash}.json"

    def compute_inputs_hash(self, changed_files: List[str], diff: str) -> str:
        """Compute a hash of review inputs for cache validation.

        The hash is derived from sorted changed files list and the diff content.
        Only the first 16 characters of the SHA256 hash are used for brevity.

        Args:
            changed_files: List of file paths that changed in the PR
            diff: The git diff content

        Returns:
            First 16 characters of SHA256 hash
        """
        content = "\n".join(sorted(changed_files)) + "\n" + diff
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def save(self, checkpoint: CheckpointData) -> Path:
        """Save checkpoint data with atomic write.

        Uses temp file + rename pattern to ensure atomicity. If the write
        is interrupted, the existing checkpoint file (if any) remains intact.

        Args:
            checkpoint: CheckpointData to persist

        Returns:
            Path to the saved checkpoint file
        """
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        path = self._get_checkpoint_path(checkpoint.inputs_hash)
        # Atomic write: write to temp, then rename
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write(checkpoint.model_dump_json(indent=2))
            temp_path = Path(f.name)
        temp_path.replace(path)
        return path

    def load(self, inputs_hash: str) -> Optional[CheckpointData]:
        """Load checkpoint data by inputs hash.

        Args:
            inputs_hash: SHA256 hash (first 16 chars) to look up

        Returns:
            CheckpointData if found, None otherwise
        """
        path = self._get_checkpoint_path(inputs_hash)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return CheckpointData.model_validate(data)

    def exists(self, inputs_hash: str) -> bool:
        """Check if a checkpoint exists for the given inputs hash.

        Args:
            inputs_hash: SHA256 hash (first 16 chars) to check

        Returns:
            True if checkpoint exists, False otherwise
        """
        return self._get_checkpoint_path(inputs_hash).exists()

    def delete(self, inputs_hash: str) -> None:
        """Delete a checkpoint by inputs hash.

        Silently succeeds if the checkpoint does not exist.

        Args:
            inputs_hash: SHA256 hash (first 16 chars) to delete
        """
        path = self._get_checkpoint_path(inputs_hash)
        if path.exists():
            path.unlink()
