"""Benchmark inventory and public-scope helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Optional

PUBLIC_CATEGORIES = ("safety", "empathy", "context", "continuity")
PRIVATE_CONFIDENTIAL_ENV = "INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR"


def get_project_root(start: Optional[Path] = None) -> Path:
    """Find the project root (where pyproject.toml lives)."""
    current = (start or Path(__file__)).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def inventory_path(project_root: Optional[Path] = None) -> Path:
    root = project_root or get_project_root()
    return root / "benchmark" / "benchmark_inventory.json"


def load_inventory(project_root: Optional[Path] = None) -> dict[str, Any]:
    path = inventory_path(project_root)
    return json.loads(path.read_text())


def get_benchmark_version(project_root: Optional[Path] = None) -> str:
    return str(load_inventory(project_root).get("benchmark_version", "unknown"))


def get_code_version(project_root: Optional[Path] = None) -> str:
    root = project_root or get_project_root()
    toml_path = root / "pyproject.toml"
    if not toml_path.exists():
        return "unknown"

    for line in toml_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("version"):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def get_private_confidential_dir(project_root: Optional[Path] = None) -> Optional[Path]:
    raw = os.environ.get(PRIVATE_CONFIDENTIAL_ENV)
    if not raw:
        return None

    root = project_root or get_project_root()
    path = Path(raw)
    if not path.is_absolute():
        path = (root / path).resolve()
    return path


def require_private_confidential_dir(project_root: Optional[Path] = None) -> Path:
    path = get_private_confidential_dir(project_root)
    if path is None:
        raise RuntimeError(
            "Confidential scenarios are not shipped in the public repo. "
            f"Set {PRIVATE_CONFIDENTIAL_ENV} to a private scenario directory."
        )
    if not path.exists():
        raise RuntimeError(
            f"Confidential scenario directory not found: {path} "
            f"(from {PRIVATE_CONFIDENTIAL_ENV})"
        )
    return path


def _iter_json_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for base in paths:
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("*.json")))
    return sorted(files)


def collect_public_scenario_paths(
    project_root: Optional[Path] = None,
    *,
    category_filter: Optional[list[str]] = None,
) -> list[Path]:
    root = project_root or get_project_root()
    scenarios_dir = root / "benchmark" / "scenarios"
    categories = [
        category for category in PUBLIC_CATEGORIES if not category_filter or category in category_filter
    ]
    return _iter_json_files([scenarios_dir / category for category in categories])


def collect_confidential_scenario_paths(project_root: Optional[Path] = None) -> list[Path]:
    confidential_dir = require_private_confidential_dir(project_root)
    return _iter_json_files([confidential_dir])


def collect_scenario_paths(
    project_root: Optional[Path] = None,
    *,
    category_filter: Optional[list[str]] = None,
    include_confidential: bool = False,
) -> list[Path]:
    public_paths = collect_public_scenario_paths(
        project_root,
        category_filter=[c for c in (category_filter or []) if c != "confidential"] or None,
    )
    if not include_confidential:
        return public_paths

    if category_filter and "confidential" not in category_filter:
        return public_paths

    return sorted(public_paths + collect_confidential_scenario_paths(project_root))
