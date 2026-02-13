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
from typing import Any, Dict, List, Optional


def _git_sha() -> str:
    """Return current HEAD commit hash, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    """Return True if there are uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip()) if result.returncode == 0 else False
    except Exception:
        return False


def _file_hash(path: Path) -> str:
    """SHA256 hex digest of a file's contents."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _scenario_hash(scenarios_dir: Path) -> str:
    """Deterministic SHA256 over sorted scenario file paths and their content hashes."""
    h = hashlib.sha256()
    scenario_files = sorted(scenarios_dir.rglob("*.json"))
    for f in scenario_files:
        # Use relative path for portability
        rel = f.relative_to(scenarios_dir)
        h.update(str(rel).encode("utf-8"))
        h.update(_file_hash(f).encode("utf-8"))
    return h.hexdigest()


def _scoring_config_hash(config_path: Path) -> str:
    """SHA256 of scoring.yaml content."""
    if config_path.exists():
        return _file_hash(config_path)
    return "missing"


def _read_contract_version(config_path: Path) -> str:
    """Read contract_version from scoring.yaml."""
    if not config_path.exists():
        return "unknown"
    try:
        import yaml

        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return str(cfg.get("contract_version", "unknown"))
    except Exception:
        return "unknown"


def _read_benchmark_version(project_root: Path) -> str:
    """Read version from pyproject.toml."""
    toml_path = project_root / "pyproject.toml"
    if not toml_path.exists():
        return "unknown"
    try:
        text = toml_path.read_text()
        for line in text.splitlines():
            if line.strip().startswith("version"):
                # Parse: version = "1.2.0"
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"


def generate_manifest(
    project_root: Path,
    model_ids: List[str],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a reproducibility manifest for a benchmark run.

    Args:
        project_root: Path to project root (where pyproject.toml lives).
        model_ids: List of model IDs being evaluated.
        run_id: Optional UUID4 string. Generated if not provided.

    Returns:
        Dict with all manifest fields.
    """
    if run_id is None:
        run_id = str(uuid.uuid4())

    scenarios_dir = project_root / "benchmark" / "scenarios"
    config_path = project_root / "benchmark" / "configs" / "scoring.yaml"

    return {
        "run_id": run_id,
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "scenario_hash": _scenario_hash(scenarios_dir),
        "scoring_config_hash": _scoring_config_hash(config_path),
        "scorer_prompt_hashes": {},
        "model_ids": model_ids,
        "run_date": datetime.now(timezone.utc).isoformat(),
        "contract_version": _read_contract_version(config_path),
        "python_version": sys.version,
        "benchmark_version": _read_benchmark_version(project_root),
    }


def write_manifest(manifest: Dict[str, Any], output_dir: Path) -> Path:
    """Write manifest to run_manifest.json in the output directory.

    Returns the path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return path
