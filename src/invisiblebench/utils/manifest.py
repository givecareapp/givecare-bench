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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from invisiblebench.evaluation.check_registry import check_prompt_hashes
from invisiblebench.utils.benchmark_inventory import (
    collect_confidential_scenario_paths,
    get_benchmark_version,
    get_code_version,
)


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


def _scoring_config_hash(config_path: Path) -> str:
    if config_path.exists():
        return _file_hash(config_path)
    return "missing"


def _read_contract_version(config_path: Path) -> str:
    if not config_path.exists():
        return "unknown"
    try:
        import yaml

        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return str(cfg.get("contract_version", "unknown"))
    except (ImportError, OSError, yaml.YAMLError):
        return "unknown"


def generate_manifest(
    project_root: Path,
    model_ids: list[str],
    run_id: str | None = None,
    harness: str | None = None,
    mode: str | None = None,
    include_confidential: bool = False,
) -> dict[str, Any]:
    """Snapshot environment metadata at run start to detect setup drift across comparisons."""
    if run_id is None:
        run_id = str(uuid.uuid4())

    scenarios_dir = project_root / "benchmark" / "scenarios"
    config_path = project_root / "benchmark" / "configs" / "scoring.yaml"

    extra_scenario_files = collect_confidential_scenario_paths(project_root) if include_confidential else []

    manifest = {
        "run_id": run_id,
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "scenario_hash": _scenario_hash(scenarios_dir, extra_files=extra_scenario_files),
        "scoring_config_hash": _scoring_config_hash(config_path),
        "scorer_prompt_hashes": check_prompt_hashes(project_root / "checks"),
        "model_ids": model_ids,
        "run_date": datetime.now(timezone.utc).isoformat(),
        "contract_version": _read_contract_version(config_path),
        "python_version": sys.version,
        "benchmark_version": get_benchmark_version(project_root),
        "code_version": get_code_version(project_root),
    }
    if harness is not None:
        manifest["harness"] = harness
    if mode is not None:
        manifest["mode"] = mode
    return manifest


def write_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:
    """Write manifest to run_manifest.json; returns the written path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path
