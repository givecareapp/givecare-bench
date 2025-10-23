"""
State persistence and run tracking for LongitudinalBench.

This module provides RunManager for saving/loading benchmark run state,
enabling resumption and preventing duplicate evaluations.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class RunManager:
    """
    Manages benchmark run state persistence.

    Handles:
    - Generating unique run keys
    - Saving/loading run state to JSON files
    - Listing and filtering runs
    - Detecting duplicate evaluations
    - Deleting runs
    """

    def __init__(self, runs_dir: str = "runs"):
        """
        Initialize RunManager.

        Args:
            runs_dir: Directory to store run JSON files (default: "runs")
        """
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def generate_run_key(
        self,
        model_name: str,
        run_id: Optional[str] = None
    ) -> str:
        """
        Generate unique run key for a model evaluation.

        Run key format: <8-char-id>_<sanitized-model-name>

        Args:
            model_name: Model identifier (e.g., "anthropic/claude-3.7-sonnet")
            run_id: Optional custom prefix (default: generates UUID)

        Returns:
            Unique run key string

        Examples:
            >>> manager.generate_run_key("anthropic/claude-3.7-sonnet")
            "a1b2c3d4_anthropic_claude-3.7-sonnet"
            >>> manager.generate_run_key("openai/gpt-4o", run_id="test001")
            "test001_openai_gpt-4o"
        """
        # Sanitize model name for filesystem
        sanitized = re.sub(r'[^a-zA-Z0-9_.-]+', '_', model_name)

        # Generate or use provided run_id prefix
        prefix = run_id if run_id else uuid.uuid4().hex[:8]

        return f"{prefix}_{sanitized}"

    def save_run(self, run_key: str, data: Dict[str, Any]) -> bool:
        """
        Save run data to JSON file atomically.

        Uses atomic write pattern (write to temp, then rename) to prevent
        partial writes from corrupting run state.

        Args:
            run_key: Unique run identifier
            data: Run data dictionary

        Returns:
            True if save succeeded, False otherwise
        """
        file_path = self.runs_dir / f"{run_key}.json"
        temp_path = file_path.with_suffix('.json.tmp')

        try:
            # Ensure run_key is in the data
            save_data = dict(data)
            if "run_key" not in save_data:
                save_data["run_key"] = run_key

            # Write to temp file first
            with open(temp_path, 'w') as f:
                json.dump(save_data, f, indent=2, sort_keys=True)

            # Atomic rename
            temp_path.rename(file_path)
            return True

        except (OSError, IOError, PermissionError) as e:
            # Clean up temp file if it exists
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            return False

    def load_run(self, run_key: str) -> Optional[Dict[str, Any]]:
        """
        Load run data from JSON file.

        Args:
            run_key: Unique run identifier

        Returns:
            Run data dictionary, or None if not found/invalid
        """
        file_path = self.runs_dir / f"{run_key}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            return None

    def list_runs(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all runs, optionally filtered by model name.

        Args:
            model_name: Optional model name to filter by

        Returns:
            List of run data dictionaries
        """
        runs = []

        # Find all JSON files in runs directory
        try:
            json_files = list(self.runs_dir.glob("*.json"))
        except OSError:
            return []

        for file_path in json_files:
            # Skip temp files
            if file_path.suffix == '.tmp':
                continue

            try:
                with open(file_path, 'r') as f:
                    run_data = json.load(f)

                # Apply model name filter if provided
                if model_name:
                    run_model = run_data.get("model_name", "")
                    if run_model != model_name:
                        continue

                runs.append(run_data)

            except (json.JSONDecodeError, IOError, OSError):
                # Skip corrupted files
                continue

        return runs

    def detect_duplicate(
        self,
        model_name: str,
        scenario_id: str
    ) -> bool:
        """
        Check if a completed run exists for this model+scenario combination.

        Only considers runs with status="completed". In-progress runs can be
        resumed and are not considered duplicates.

        Args:
            model_name: Model identifier
            scenario_id: Scenario identifier

        Returns:
            True if duplicate exists, False otherwise
        """
        runs = self.list_runs(model_name=model_name)

        for run in runs:
            # Only consider completed runs as duplicates
            if run.get("status") != "completed":
                continue

            # Check if scenario matches
            if run.get("scenario_id") == scenario_id:
                return True

        return False

    def delete_run(self, run_key: str) -> bool:
        """
        Delete a specific run by key.

        Args:
            run_key: Unique run identifier

        Returns:
            True if deletion succeeded, False if run not found
        """
        file_path = self.runs_dir / f"{run_key}.json"

        if not file_path.exists():
            return False

        try:
            file_path.unlink()
            return True
        except (OSError, IOError, PermissionError):
            return False

    def delete_runs_by_model(self, model_name: str) -> int:
        """
        Delete all runs for a specific model.

        Args:
            model_name: Model identifier

        Returns:
            Number of runs deleted
        """
        runs = self.list_runs(model_name=model_name)
        deleted_count = 0

        for run in runs:
            run_key = run.get("run_key")
            if run_key and self.delete_run(run_key):
                deleted_count += 1

        return deleted_count
