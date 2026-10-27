"""Run reproducibility manifest for benchmark runs.

Captures environment metadata at run start to detect setup drift
when comparing runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from invisiblebench.utils.benchmark_inventory import (
    collect_confidential_scenario_paths,
    get_benchmark_version,
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


def is_git_commit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(char in "0123456789abcdef" for char in value)
    )


def _git_state(project_root: Path) -> tuple[str | None, bool | None]:
    """Unknown provenance is not a clean tree; inspect the owning checkout."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        sha = commit.stdout.strip()
        if commit.returncode or status.returncode or not is_git_commit(sha):
            return None, None
        return sha, bool(status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None, None


def scenario_hash(project_root: Path, include_confidential: bool = False) -> str:
    """Sorted-path SHA256 of the scenario corpus, stable across filesystem orderings."""
    scenarios_dir = project_root / "benchmark" / "scenarios"
    files = sorted(scenarios_dir.rglob("*.json"))
    if include_confidential:
        files += sorted(collect_confidential_scenario_paths(project_root))
    digest = hashlib.sha256()
    for path in files:
        try:
            rel = path.relative_to(scenarios_dir)
        except ValueError:
            rel = Path("private_confidential") / path.name
        digest.update(str(rel).encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("utf-8"))
    return digest.hexdigest()


def scenario_corpus_hash(project_root: Path) -> str:
    """Hash the public scenario corpus for scan comparability."""
    return scenario_hash(project_root)


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

    git_sha, git_dirty = _git_state(project_root)
    manifest = {
        "schema": "invisiblebench-run-manifest/v3",
        "run_id": run_id,
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "scenario_hash": scenario_hash(project_root, include_confidential),
        "scenario_ids": sorted(set(scenario_ids or [])),
        "model_ids": model_ids,
        "run_date": datetime.now(UTC).isoformat(),
        "benchmark_version": get_benchmark_version(project_root),
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
        f.flush()
        os.fsync(f.fileno())
    return path
