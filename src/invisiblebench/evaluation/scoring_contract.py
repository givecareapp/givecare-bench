"""Typed accessors for benchmark/configs/scoring.yaml.

scoring.yaml is the single owner of publication thresholds; runtime code and
QA scripts read them through this module instead of re-hardcoding values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from invisiblebench.utils.benchmark_inventory import get_project_root


def scoring_config_path() -> Path:
    return get_project_root() / "benchmark" / "configs" / "scoring.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    return yaml.safe_load(scoring_config_path().read_text()) or {}


def coverage_floor() -> float:
    """Minimum resolved/eligible rate for a scenario result to be publishable."""
    return float(_load()["coverage_floor"])


def contract_version() -> str:
    return str(_load()["contract_version"])


def version_stage() -> str:
    return str(_load()["version_stage"])
