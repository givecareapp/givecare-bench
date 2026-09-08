"""Typed access to the active benchmark scoring contract."""

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
    path = scoring_config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"scoring config must be an object: {path}")
    return data


def contract_version() -> str:
    return str(_load()["contract_version"])


def version_stage() -> str:
    return str(_load()["version_stage"])


def engine_version() -> str:
    return str(_load()["engine_version"])


def verdicts() -> tuple[str, ...]:
    value = _load().get("verdicts") or []
    return tuple(str(item) for item in value)


def output_fields() -> tuple[str, ...]:
    value = _load().get("output_fields") or []
    return tuple(str(item) for item in value)


__all__ = [
    "contract_version",
    "engine_version",
    "output_fields",
    "scoring_config_path",
    "verdicts",
    "version_stage",
]
