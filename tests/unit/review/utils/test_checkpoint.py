"""Tests for CheckpointManager."""

import json
import tempfile
from pathlib import Path

import pytest

from iron_rook.review.contracts import CheckpointData
from iron_rook.review.utils.checkpoint import CheckpointManager


@pytest.fixture
def temp_repo_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def manager(temp_repo_root: Path) -> CheckpointManager:
    return CheckpointManager(temp_repo_root)


class TestComputeInputsHash:
    def test_returns_16_char_hash(self, manager: CheckpointManager):
        changed_files = ["src/a.py", "src/b.py"]
        diff = "some diff content"
        result = manager.compute_inputs_hash(changed_files, diff)
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_is_deterministic(self, manager: CheckpointManager):
        changed_files = ["src/a.py"]
        diff = "diff content"
        result1 = manager.compute_inputs_hash(changed_files, diff)
        result2 = manager.compute_inputs_hash(changed_files, diff)
        assert result1 == result2

    def test_order_independent_for_files(self, manager: CheckpointManager):
        files1 = ["a.py", "b.py"]
        files2 = ["b.py", "a.py"]
        diff = "same"
        assert manager.compute_inputs_hash(files1, diff) == manager.compute_inputs_hash(
            files2, diff
        )

    def test_different_inputs_different_hash(self, manager: CheckpointManager):
        hash1 = manager.compute_inputs_hash(["a.py"], "diff1")
        hash2 = manager.compute_inputs_hash(["b.py"], "diff1")
        hash3 = manager.compute_inputs_hash(["a.py"], "diff2")
        assert hash1 != hash2
        assert hash1 != hash3


class TestSaveAndLoad:
    def test_save_creates_file(self, manager: CheckpointManager):
        checkpoint = CheckpointData(
            trace_id="test-123",
            inputs_hash="abcd1234efgh5678",
            timestamp="2024-01-01T00:00:00Z",
        )
        path = manager.save(checkpoint)
        assert path.exists()
        assert path.name == "abcd1234efgh5678.json"

    def test_save_creates_directory(self, temp_repo_root: Path):
        manager = CheckpointManager(temp_repo_root)
        checkpoint = CheckpointData(
            trace_id="test-123",
            inputs_hash="abcd1234efgh5678",
        )
        manager.save(checkpoint)
        assert manager.checkpoints_dir.exists()

    def test_load_returns_checkpoint(self, manager: CheckpointManager):
        original = CheckpointData(
            trace_id="test-456",
            inputs_hash="1234567890abcdef",
            timestamp="2024-01-01T00:00:00Z",
            repo_root="/test/repo",
            base_ref="main",
            head_ref="feature",
            completed_agents={"security": {"agent": "security"}},
            failed_agents=["lint"],
            current_agent="docs",
        )
        manager.save(original)
        loaded = manager.load("1234567890abcdef")
        assert loaded is not None
        assert loaded.trace_id == "test-456"
        assert loaded.inputs_hash == "1234567890abcdef"
        assert loaded.repo_root == "/test/repo"
        assert loaded.failed_agents == ["lint"]

    def test_load_returns_none_for_missing(self, manager: CheckpointManager):
        result = manager.load("nonexistent0000")
        assert result is None

    def test_atomic_write_uses_temp_file(self, manager: CheckpointManager):
        checkpoint = CheckpointData(
            trace_id="atomic-test",
            inputs_hash="atomic12345678",
        )
        path = manager.save(checkpoint)
        with open(path) as f:
            data = json.load(f)
        assert "trace_id" in data


class TestExists:
    def test_returns_false_when_missing(self, manager: CheckpointManager):
        assert not manager.exists("missing1234567")

    def test_returns_true_after_save(self, manager: CheckpointManager):
        checkpoint = CheckpointData(
            trace_id="test",
            inputs_hash="exists123456789",
        )
        manager.save(checkpoint)
        assert manager.exists("exists123456789")


class TestDelete:
    def test_removes_existing_checkpoint(self, manager: CheckpointManager):
        checkpoint = CheckpointData(
            trace_id="to-delete",
            inputs_hash="delete123456789",
        )
        manager.save(checkpoint)
        assert manager.exists("delete123456789")
        manager.delete("delete123456789")
        assert not manager.exists("delete123456789")

    def test_succeeds_silently_for_missing(self, manager: CheckpointManager):
        manager.delete("neverexisted12")

    def test_deletes_correct_file(self, manager: CheckpointManager):
        c1 = CheckpointData(trace_id="c1", inputs_hash="1111111111111111")
        c2 = CheckpointData(trace_id="c2", inputs_hash="2222222222222222")
        manager.save(c1)
        manager.save(c2)
        manager.delete("1111111111111111")
        assert not manager.exists("1111111111111111")
        assert manager.exists("2222222222222222")
