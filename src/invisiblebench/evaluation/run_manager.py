"""Run state persistence and tracking."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class RunManager:
    """Benchmark run state: generate keys, save/load, detect duplicates."""

    def __init__(self, runs_dir: str = "runs"):

        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def generate_run_key(self, model_name: str, run_id: Optional[str] = None) -> str:
        """Format: <8-char-id>_<sanitized-model-name>."""
        # Sanitize model name for filesystem
        sanitized = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_name)

        # SECURITY: Sanitize run_id to prevent path traversal attacks
        if run_id:
            prefix = re.sub(r"[^a-zA-Z0-9_.-]+", "_", run_id)
        else:
            prefix = uuid.uuid4().hex[:8]

        return f"{prefix}_{sanitized}"

    def save_run(self, run_key: str, data: Dict[str, Any]) -> bool:
        """Atomic write to JSON file. Returns True on success."""
        file_path = self.runs_dir / f"{run_key}.json"
        temp_path = file_path.with_suffix(".json.tmp")

        try:
            save_data = dict(data)
            if "run_key" not in save_data:
                save_data["run_key"] = run_key

            # Write to temp file first
            with open(temp_path, "w") as f:
                json.dump(save_data, f, indent=2, sort_keys=True)

            # Atomic rename
            temp_path.rename(file_path)
            return True

        except (OSError, IOError, PermissionError):
            # Clean up temp file if it exists
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
            return False

    def load_run(self, run_key: str) -> Optional[Dict[str, Any]]:

        file_path = self.runs_dir / f"{run_key}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                data: Dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, IOError, OSError):
            return None

    def list_runs(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:

        runs = []

        # Find all JSON files in runs directory
        try:
            json_files = list(self.runs_dir.glob("*.json"))
        except OSError:
            return []

        for file_path in json_files:
            # Skip temp files
            if file_path.suffix == ".tmp":
                continue

            try:
                with open(file_path, "r") as f:
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

    def detect_duplicate(self, model_name: str, scenario_id: str) -> bool:
        """True if a completed run exists for this model+scenario."""
        runs = self.list_runs(model_name=model_name)

        for run in runs:
            # Only consider completed runs as duplicates
            if run.get("status") != "completed":
                continue

            if run.get("scenario_id") == scenario_id:
                return True

        return False

    def delete_run(self, run_key: str) -> bool:

        file_path = self.runs_dir / f"{run_key}.json"

        if not file_path.exists():
            return False

        try:
            file_path.unlink()
            return True
        except (OSError, IOError, PermissionError):
            return False

    def delete_runs_by_model(self, model_name: str) -> int:

        runs = self.list_runs(model_name=model_name)
        deleted_count = 0

        for run in runs:
            run_key = run.get("run_key")
            if run_key and self.delete_run(run_key):
                deleted_count += 1

        return deleted_count
