"""Helpers for loading and rebuilding run artifacts.

Supports flat aggregate files (all_results.json), provider-specific wrapper files
(givecare_results.json), per-model result documents, and run directories.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from invisiblebench.results_io import flatten_model_results, write_json


class ArtifactLoadError(ValueError):
    """Raised when a results source cannot be interpreted."""


def _read_json(path: Path) -> Any:
    with open(path) as f:
        return json.load(f)


def _is_model_result_doc(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("scenarios"), list) and "model" in data


def load_model_result_documents(source: Path) -> List[Dict[str, Any]]:
    """Load one or more per-model result documents from a source path."""
    if not source.exists():
        raise ArtifactLoadError(f"Path not found: {source}")

    if source.is_file():
        data = _read_json(source)
        if _is_model_result_doc(data):
            return [data]
        raise ArtifactLoadError(f"Not a per-model result JSON: {source}")

    if source.is_dir():
        model_dir = source / "model_results"
        if model_dir.exists():
            source = model_dir

        docs: List[Dict[str, Any]] = []
        for path in sorted(source.glob("*.json")):
            data = _read_json(path)
            if _is_model_result_doc(data):
                docs.append(data)
        if docs:
            return docs

    raise ArtifactLoadError(f"No per-model result JSONs found in: {source}")


def load_result_rows(source: Path) -> List[Dict[str, Any]]:
    """Load flat scenario rows from any supported artifact source."""
    if not source.exists():
        raise ArtifactLoadError(f"Path not found: {source}")

    if source.is_file():
        data = _read_json(source)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"]
        if _is_model_result_doc(data):
            return flatten_model_results([data])
        raise ArtifactLoadError(f"Unsupported results file format: {source}")

    if source.is_dir():
        all_results = source / "all_results.json"
        if all_results.exists():
            return load_result_rows(all_results)

        givecare_results = source / "givecare_results.json"
        if givecare_results.exists():
            return load_result_rows(givecare_results)

        return flatten_model_results(load_model_result_documents(source))

    raise ArtifactLoadError(f"Unsupported results source: {source}")


def detect_transcripts_dir(source: Path) -> Path | None:
    """Infer transcripts directory from any supported artifact source."""
    if source.is_dir():
        candidate = source / "transcripts"
        if candidate.exists():
            return candidate
        if source.name == "model_results":
            candidate = source.parent / "transcripts"
            if candidate.exists():
                return candidate
        return None

    parent = source.parent
    if source.name in {"all_results.json", "givecare_results.json"}:
        candidate = parent / "transcripts"
        return candidate if candidate.exists() else None

    if source.suffix == ".json" and parent.name == "model_results":
        candidate = parent.parent / "transcripts"
        return candidate if candidate.exists() else None

    return None


def write_aggregate_results(run_source: Path, rows: List[Dict[str, Any]] | None = None) -> Path:
    """Write/refresh all_results.json for a run dir or model_results dir."""
    if rows is None:
        rows = load_result_rows(run_source)

    if run_source.is_dir() and run_source.name == "model_results":
        target_dir = run_source.parent
    elif run_source.is_dir():
        target_dir = run_source
    else:
        target_dir = run_source.parent.parent if run_source.parent.name == "model_results" else run_source.parent

    return write_json(target_dir / "all_results.json", rows)
