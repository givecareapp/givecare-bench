"""Run reproducibility manifest for benchmark runs.

Captures environment metadata at run start to detect setup drift
when comparing runs.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from invisiblebench.utils.benchmark_inventory import (
    collect_confidential_scenario_paths,
    get_benchmark_version,
    get_code_version,
)

RUN_DIRECTORY_TIME_FORMAT = "%Y-%m-%d_%H-%M-%SZ"


def run_timestamp(run_path: Path, manifests: list[dict[str, Any]]) -> datetime | None:
    """Read a run's UTC timestamp; custom directory names use source dates."""
    try:
        return datetime.strptime(run_path.name, RUN_DIRECTORY_TIME_FORMAT)
    except ValueError:
        dates = []
        for manifest in manifests:
            try:
                date = datetime.fromisoformat(manifest["run_date"])
                dates.append(date.replace(tzinfo=date.tzinfo or UTC).astimezone(UTC).replace(tzinfo=None))
            except (KeyError, TypeError, ValueError):
                continue
        return min(dates) if dates else None


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _git_dirty() -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip()) if result.returncode == 0 else False
    except (OSError, subprocess.SubprocessError):
        return False


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _scenario_hash(scenarios_dir: Path, extra_files: list[Path] | None = None) -> str:
    """Sorted-path SHA256 so hash is stable across filesystem orderings."""
    h = hashlib.sha256()
    scenario_files = sorted(scenarios_dir.rglob("*.json"))
    if extra_files:
        scenario_files.extend(sorted(extra_files))
    for f in scenario_files:
        try:
            rel = f.relative_to(scenarios_dir)
        except ValueError:
            rel = Path("private_confidential") / f.name
        h.update(str(rel).encode("utf-8"))
        h.update(_file_hash(f).encode("utf-8"))
    return h.hexdigest()


def scenario_corpus_hash(project_root: Path) -> str:
    """Hash the complete public scenario corpus for scan comparability."""
    return _scenario_hash(project_root / "benchmark" / "scenarios")


def generate_manifest(
    project_root: Path,
    model_ids: list[str],
    scenario_ids: list[str] | None = None,
    transcript_policy: dict[str, Any] | None = None,
    run_id: str | None = None,
    harness: str | None = None,
    mode: str | None = None,
    include_confidential: bool = False,
) -> dict[str, Any]:
    """Snapshot environment metadata at run start to detect setup drift across comparisons."""
    if run_id is None:
        run_id = str(uuid.uuid4())

    scenarios_dir = project_root / "benchmark" / "scenarios"

    extra_scenario_files = collect_confidential_scenario_paths(project_root) if include_confidential else []

    manifest = {
        "schema": "invisiblebench-run-manifest/v3",
        "run_id": run_id,
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "scenario_hash": _scenario_hash(scenarios_dir, extra_files=extra_scenario_files),
        "scenario_ids": sorted(set(scenario_ids or [])),
        "model_ids": model_ids,
        "run_date": datetime.now(UTC).isoformat(),
        "python_version": sys.version,
        "benchmark_version": get_benchmark_version(project_root),
        "code_version": get_code_version(project_root),
    }
    if transcript_policy is not None:
        manifest["transcript_policy"] = transcript_policy
    if harness is not None:
        manifest["harness"] = harness
    if mode is not None:
        manifest["mode"] = mode
    return manifest


def write_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:
    """Write manifest to run_manifest.json; returns the written path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    with open(path, "x") as f:
        json.dump(manifest, f, indent=2)
    return path
