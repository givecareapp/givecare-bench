"""Result writing utilities for benchmark runs.

Primary durable artifact: one JSON per model/provider per run.
Aggregate files (all_results.json, givecare_results.json) are derived compatibility outputs.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from invisiblebench.failure_taxonomy import compute_quality_summary, compute_reliability_summary


def _safe_filename(value: str) -> str:
    """Return a filesystem-safe JSON stem."""
    safe = value.replace("/", "_").replace(" ", "_")
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in safe)


def _coerce_dimension_scores(result: Dict[str, Any]) -> Dict[str, Any]:
    dims = result.get("dimensions")
    if isinstance(dims, dict) and dims:
        return dims
    dim_scores = result.get("dimension_scores")
    if isinstance(dim_scores, dict):
        return dim_scores
    return {}


def aggregate_model_results(
    results: List[Dict[str, Any]],
    *,
    benchmark_version: str = "unknown",
    timestamp: str | None = None,
    mode: str | None = None,
    run_metadata: Dict[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Group flat scenario rows into per-model result documents.

    Output shape is compatible with existing leaderboard tooling while preserving
    richer per-scenario fields for local run recovery and diagnostics.
    """
    models: Dict[str, Dict[str, Any]] = {}
    ts = timestamp or datetime.now().isoformat()

    for result in results:
        model_name = result.get("model", result.get("model_id", "unknown"))
        model_id = result.get("model_id", model_name)
        provider = result.get("provider")

        if model_name not in models:
            models[model_name] = {
                "model": model_name,
                "model_name": model_name,
                "model_id": model_id,
                "provider": provider,
                "scenarios": [],
                "dimension_scores": {},
                "overall_scores": [],
                "total_cost": 0.0,
                "benchmark_version": benchmark_version,
                "timestamp": ts,
            }
            if mode is not None:
                models[model_name]["mode"] = mode
            if run_metadata:
                models[model_name]["run_metadata"] = dict(run_metadata)

        scenario_doc = {
            "scenario": result.get("scenario"),
            "scenario_id": result.get("scenario_id"),
            "tier": result.get("tier", result.get("category", "unknown")),
            "category": result.get("category", result.get("tier", "unknown")),
            "overall_score": result.get("overall_score", 0.0),
            "dimension_scores": _coerce_dimension_scores(result),
            "status": result.get("status", "error"),
        }

        for key in (
            "hard_fail",
            "hard_fail_reasons",
            "failure_categories",
            "gates",
            "success",
            "cost",
            "run_id",
            "judge_model",
            "judge_prompt_hash",
            "judge_temp",
            "contract_version",
            "transcript_path",
            "detail_json",
            "detail_html",
            "error",
            "runs",
            "run_stats",
            "run_summary",
            "harness_mode",
            "orchestrator_model",
        ):
            if key in result:
                scenario_doc[key] = result[key]

        models[model_name]["scenarios"].append(scenario_doc)

        for dim, score in _coerce_dimension_scores(result).items():
            if isinstance(score, (int, float)):
                models[model_name]["dimension_scores"].setdefault(dim, []).append(float(score))

        score_val = result.get("overall_score", 0.0)
        if isinstance(score_val, (int, float)):
            models[model_name]["overall_scores"].append(float(score_val))

        cost = result.get("cost", 0.0)
        if isinstance(cost, (int, float)):
            models[model_name]["total_cost"] += float(cost)

    for model_data in models.values():
        for dim, scores in list(model_data["dimension_scores"].items()):
            model_data["dimension_scores"][dim] = sum(scores) / len(scores) if scores else 0.0

        overall_scores = model_data.pop("overall_scores")
        model_data["overall_score"] = (
            sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
        )
        model_data["scenario_count"] = len(model_data["scenarios"])
        model_data["passed"] = sum(
            1 for s in model_data["scenarios"] if s.get("status") == "pass" and not s.get("hard_fail")
        )
        model_data["failed"] = model_data["scenario_count"] - model_data["passed"]
        model_data["quality_summary"] = compute_quality_summary(model_data["scenarios"])
        model_data["reliability_summary"] = compute_reliability_summary(model_data["scenarios"])

    return models


def write_model_results(
    results: List[Dict[str, Any]],
    output_dir: Path,
    *,
    benchmark_version: str = "unknown",
    timestamp: str | None = None,
    mode: str | None = None,
    run_metadata: Dict[str, Any] | None = None,
) -> List[Path]:
    """Write one JSON file per model/provider and return written paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    docs = aggregate_model_results(
        results,
        benchmark_version=benchmark_version,
        timestamp=timestamp,
        mode=mode,
        run_metadata=run_metadata,
    )
    written: List[Path] = []
    for model_name, model_data in docs.items():
        path = output_dir / f"{_safe_filename(model_name)}.json"
        with open(path, "w") as f:
            json.dump(model_data, f, indent=2)
        written.append(path)
    return written


def write_json(path: Path, data: Any) -> Path:
    """Write JSON with parent directory creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def flatten_model_results(model_files: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten per-model result documents back into all_results-style rows."""
    rows: List[Dict[str, Any]] = []
    for doc in model_files:
        model = doc.get("model", doc.get("model_name", "unknown"))
        model_id = doc.get("model_id", model)
        provider = doc.get("provider")
        for scenario in doc.get("scenarios", []):
            row = {
                "model": model,
                "model_id": model_id,
                "scenario": scenario.get("scenario"),
                "scenario_id": scenario.get("scenario_id"),
                "category": scenario.get("category", scenario.get("tier", "unknown")),
                "overall_score": scenario.get("overall_score", 0.0),
                "dimensions": scenario.get("dimension_scores", {}),
                "status": scenario.get("status", "error"),
            }
            if provider is not None:
                row["provider"] = provider
            for key in (
                "hard_fail",
                "hard_fail_reasons",
                "failure_categories",
                "gates",
                "success",
                "cost",
                "run_id",
                "judge_model",
                "judge_prompt_hash",
                "judge_temp",
                "contract_version",
                "error",
                "runs",
                "run_stats",
                "run_summary",
                "detail_json",
                "detail_html",
                "harness_mode",
                "orchestrator_model",
            ):
                if key in scenario:
                    row[key] = scenario[key]
            rows.append(row)
    return rows
