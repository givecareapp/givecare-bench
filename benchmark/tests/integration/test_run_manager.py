"""
Tests for RunManager (State Persistence & Run Tracking).

Following TDD methodology - these tests are written FIRST before implementation.
"""
from __future__ import annotations

import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from invisiblebench.evaluation.run_manager import RunManager


class TestRunKeyGeneration:
    """Test run key generation logic."""

    def test_generate_run_key_basic(self):
        """Run keys should combine timestamp prefix and sanitized model name."""
        manager = RunManager(runs_dir="/tmp/test_runs")

        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = 'abcd1234' * 4  # 32 chars
            run_key = manager.generate_run_key("anthropic/claude-3.7-sonnet")

        # Should be format: <8-char-uuid>_<sanitized-model>
        assert run_key.startswith("abcd1234_")
        assert "anthropic" in run_key
        assert "claude" in run_key

    def test_generate_run_key_sanitizes_special_chars(self):
        """Special characters in model names should be sanitized."""
        manager = RunManager(runs_dir="/tmp/test_runs")

        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = 'xyz789ab' * 4
            run_key = manager.generate_run_key("openai/gpt-4o@special!")

        # Should replace special chars with underscores
        assert run_key == "xyz789ab_openai_gpt-4o_special_"

    def test_generate_run_key_with_custom_prefix(self):
        """Should accept custom run_id prefix instead of generating UUID."""
        manager = RunManager(runs_dir="/tmp/test_runs")

        run_key = manager.generate_run_key(
            "anthropic/claude-3.7-sonnet",
            run_id="custom123"
        )

        assert run_key.startswith("custom123_")

    def test_generate_run_key_deterministic_with_prefix(self):
        """Same model + prefix should produce same run key."""
        manager = RunManager(runs_dir="/tmp/test_runs")

        key1 = manager.generate_run_key("model-a", run_id="test001")
        key2 = manager.generate_run_key("model-a", run_id="test001")

        assert key1 == key2


class TestSaveAndLoadRun:
    """Test saving and loading run state."""

    def test_save_run_creates_file(self, tmp_path):
        """save_run should create JSON file in runs directory."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        run_data = {
            "run_key": "abc123_model-a",
            "model_name": "model-a",
            "status": "running",
        }

        success = manager.save_run("abc123_model-a", run_data)

        assert success is True
        assert (runs_dir / "abc123_model-a.json").exists()

    def test_save_run_writes_valid_json(self, tmp_path):
        """Saved run data should be valid JSON."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        run_data = {
            "run_key": "xyz789_model-b",
            "model_name": "model-b",
            "start_time": "2025-01-15T10:00:00Z",
            "status": "initializing",
            "results": {"overall_score": 0.76},
        }

        manager.save_run("xyz789_model-b", run_data)

        # Load and verify JSON structure
        file_path = runs_dir / "xyz789_model-b.json"
        with open(file_path, 'r') as f:
            loaded_data = json.load(f)

        assert loaded_data["run_key"] == "xyz789_model-b"
        assert loaded_data["model_name"] == "model-b"
        assert loaded_data["results"]["overall_score"] == 0.76

    def test_load_run_returns_data(self, tmp_path):
        """load_run should return saved run data."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        run_data = {
            "run_key": "test001_model-c",
            "model_name": "model-c",
            "status": "completed",
        }

        manager.save_run("test001_model-c", run_data)
        loaded = manager.load_run("test001_model-c")

        assert loaded is not None
        assert loaded["run_key"] == "test001_model-c"
        assert loaded["status"] == "completed"

    def test_load_run_nonexistent_returns_none(self, tmp_path):
        """load_run should return None for nonexistent runs."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        loaded = manager.load_run("nonexistent_run")

        assert loaded is None

    def test_save_run_overwrites_existing(self, tmp_path):
        """save_run should overwrite existing run data."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save initial data
        manager.save_run("update_test", {"status": "initializing", "score": 0.0})

        # Update with new data
        manager.save_run("update_test", {"status": "completed", "score": 0.85})

        loaded = manager.load_run("update_test")
        assert loaded["status"] == "completed"
        assert loaded["score"] == 0.85

    def test_save_run_atomic_write(self, tmp_path):
        """save_run should use atomic writes to prevent partial corruption."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        run_data = {"run_key": "atomic_test", "large_data": "x" * 10000}

        # This should complete fully or not at all
        success = manager.save_run("atomic_test", run_data)

        assert success is True
        loaded = manager.load_run("atomic_test")
        assert len(loaded["large_data"]) == 10000


class TestListRuns:
    """Test listing runs with optional filtering."""

    def test_list_runs_empty_directory(self, tmp_path):
        """list_runs should return empty list for empty directory."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        runs = manager.list_runs()

        assert runs == []

    def test_list_runs_returns_all_runs(self, tmp_path):
        """list_runs should return all saved runs."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save multiple runs
        manager.save_run("run1_model-a", {"model_name": "model-a"})
        manager.save_run("run2_model-b", {"model_name": "model-b"})
        manager.save_run("run3_model-c", {"model_name": "model-c"})

        runs = manager.list_runs()

        assert len(runs) == 3
        run_keys = [r["run_key"] for r in runs]
        assert "run1_model-a" in run_keys
        assert "run2_model-b" in run_keys
        assert "run3_model-c" in run_keys

    def test_list_runs_filters_by_model_name(self, tmp_path):
        """list_runs should filter by model_name when provided."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save runs with different models
        manager.save_run("run1_claude", {"model_name": "anthropic/claude-3.7-sonnet"})
        manager.save_run("run2_gpt", {"model_name": "openai/gpt-4o"})
        manager.save_run("run3_claude", {"model_name": "anthropic/claude-3.7-sonnet"})

        claude_runs = manager.list_runs(model_name="anthropic/claude-3.7-sonnet")

        assert len(claude_runs) == 2
        for run in claude_runs:
            assert run["model_name"] == "anthropic/claude-3.7-sonnet"

    def test_list_runs_ignores_non_json_files(self, tmp_path):
        """list_runs should only process .json files."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True)
        manager = RunManager(runs_dir=str(runs_dir))

        # Create a valid run
        manager.save_run("valid_run", {"model_name": "model-a"})

        # Create non-JSON files
        (runs_dir / "readme.txt").write_text("Not a run file")
        (runs_dir / ".DS_Store").write_text("System file")

        runs = manager.list_runs()

        assert len(runs) == 1
        assert runs[0]["run_key"] == "valid_run"

    def test_list_runs_handles_corrupted_json(self, tmp_path):
        """list_runs should skip corrupted JSON files gracefully."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True)
        manager = RunManager(runs_dir=str(runs_dir))

        # Create valid run
        manager.save_run("valid_run", {"model_name": "model-a"})

        # Create corrupted JSON file
        (runs_dir / "corrupted_run.json").write_text("{invalid json")

        runs = manager.list_runs()

        # Should return only valid run
        assert len(runs) == 1
        assert runs[0]["run_key"] == "valid_run"


class TestDetectDuplicate:
    """Test duplicate run detection."""

    def test_detect_duplicate_no_existing_runs(self, tmp_path):
        """detect_duplicate should return False when no runs exist."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        is_duplicate = manager.detect_duplicate(
            model_name="model-a",
            scenario_id="scenario-001"
        )

        assert is_duplicate is False

    def test_detect_duplicate_different_model(self, tmp_path):
        """detect_duplicate should return False for different model."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save run for model-a
        manager.save_run("run1_model-a", {
            "model_name": "model-a",
            "scenario_id": "scenario-001",
            "status": "completed"
        })

        # Check for model-b with same scenario
        is_duplicate = manager.detect_duplicate(
            model_name="model-b",
            scenario_id="scenario-001"
        )

        assert is_duplicate is False

    def test_detect_duplicate_different_scenario(self, tmp_path):
        """detect_duplicate should return False for different scenario."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save run for scenario-001
        manager.save_run("run1_model-a", {
            "model_name": "model-a",
            "scenario_id": "scenario-001",
            "status": "completed"
        })

        # Check same model but different scenario
        is_duplicate = manager.detect_duplicate(
            model_name="model-a",
            scenario_id="scenario-002"
        )

        assert is_duplicate is False

    def test_detect_duplicate_exact_match(self, tmp_path):
        """detect_duplicate should return True for exact model+scenario match."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save completed run
        manager.save_run("run1_model-a", {
            "model_name": "model-a",
            "scenario_id": "scenario-001",
            "status": "completed"
        })

        # Check for duplicate
        is_duplicate = manager.detect_duplicate(
            model_name="model-a",
            scenario_id="scenario-001"
        )

        assert is_duplicate is True

    def test_detect_duplicate_ignores_in_progress_runs(self, tmp_path):
        """detect_duplicate should ignore runs that are still in progress."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Save in-progress run
        manager.save_run("run1_model-a", {
            "model_name": "model-a",
            "scenario_id": "scenario-001",
            "status": "running"
        })

        # Should not be considered duplicate (can resume)
        is_duplicate = manager.detect_duplicate(
            model_name="model-a",
            scenario_id="scenario-001"
        )

        assert is_duplicate is False


class TestDeleteRun:
    """Test run deletion."""

    def test_delete_run_removes_file(self, tmp_path):
        """delete_run should remove the run file."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Create run
        manager.save_run("test_run", {"model_name": "model-a"})
        assert (runs_dir / "test_run.json").exists()

        # Delete run
        success = manager.delete_run("test_run")

        assert success is True
        assert not (runs_dir / "test_run.json").exists()

    def test_delete_run_nonexistent_returns_false(self, tmp_path):
        """delete_run should return False for nonexistent run."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        success = manager.delete_run("nonexistent_run")

        assert success is False

    def test_delete_run_by_model_name(self, tmp_path):
        """delete_run should support deleting all runs for a model."""
        runs_dir = tmp_path / "runs"
        manager = RunManager(runs_dir=str(runs_dir))

        # Create multiple runs for same model
        manager.save_run("run1_model-a", {"model_name": "model-a"})
        manager.save_run("run2_model-a", {"model_name": "model-a"})
        manager.save_run("run3_model-b", {"model_name": "model-b"})

        # Delete all runs for model-a
        deleted_count = manager.delete_runs_by_model("model-a")

        assert deleted_count == 2
        assert not (runs_dir / "run1_model-a.json").exists()
        assert not (runs_dir / "run2_model-a.json").exists()
        assert (runs_dir / "run3_model-b.json").exists()


class TestRunManagerInitialization:
    """Test RunManager initialization and directory creation."""

    def test_init_creates_runs_directory(self, tmp_path):
        """RunManager should create runs directory if it doesn't exist."""
        runs_dir = tmp_path / "new_runs"
        assert not runs_dir.exists()

        manager = RunManager(runs_dir=str(runs_dir))

        assert runs_dir.exists()
        assert runs_dir.is_dir()

    def test_init_uses_existing_directory(self, tmp_path):
        """RunManager should work with existing runs directory."""
        runs_dir = tmp_path / "existing_runs"
        runs_dir.mkdir()

        # Create a test file to verify directory isn't recreated
        test_file = runs_dir / "test.txt"
        test_file.write_text("existing")

        manager = RunManager(runs_dir=str(runs_dir))

        assert test_file.exists()
        assert test_file.read_text() == "existing"


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_save_run_handles_permission_error(self, tmp_path):
        """save_run should handle permission errors gracefully."""
        runs_dir = tmp_path / "runs"

        # RunManager.__init__ creates the directory, so we call it first
        manager = RunManager(runs_dir=str(runs_dir))

        # Now make directory read-only
        runs_dir.chmod(0o444)

        try:
            success = manager.save_run("test_run", {"data": "test"})
            # Should return False on permission error
            assert success is False
        finally:
            # Restore permissions for cleanup
            runs_dir.chmod(0o755)

    def test_load_run_handles_malformed_json(self, tmp_path):
        """load_run should return None for malformed JSON."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True)
        manager = RunManager(runs_dir=str(runs_dir))

        # Create malformed JSON file
        (runs_dir / "bad_run.json").write_text("{incomplete")

        loaded = manager.load_run("bad_run")

        assert loaded is None
