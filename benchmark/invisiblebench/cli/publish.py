"""Publish benchmark results to Convex.

Reads all_results.json or leaderboard_ready/ directory,
transforms into Convex payload, and POSTs to the HTTP endpoint.

Env vars:
  CONVEX_SITE_URL   — Convex site URL (e.g. https://doting-tortoise-411.convex.site)
  BENCH_PUBLISH_KEY — Optional bearer token for auth
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


def _model_id_map() -> dict[str, str]:
    """Build name→id map from model config. Falls back to slug if unavailable."""
    try:
        from invisiblebench.models.config import MODELS_FULL

        return {m.name: m.id for m in MODELS_FULL}
    except Exception:
        return {}


def _slugify(name: str) -> str:
    """Convert model name to a slug for use as model_id."""
    return name.lower().replace(" ", "-").replace(".", "")


def _load_all_results(path: Path) -> list[dict[str, Any]]:
    """Load all_results.json (flat list of scenario results)."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    raise ValueError(f"Expected list in {path}, got {type(data).__name__}")


def _load_leaderboard_ready(directory: Path) -> list[dict[str, Any]]:
    """Load per-model JSON files from leaderboard_ready/ directory."""
    results = []
    for fp in sorted(directory.glob("*.json")):
        with open(fp) as f:
            results.append(json.load(f))
    return results


def _build_payload_from_all_results(
    results: list[dict[str, Any]], run_id: str
) -> dict[str, Any]:
    """Transform flat all_results.json into Convex publish payload."""
    id_map = _model_id_map()

    # Group by model
    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        model_name = r.get("model", "unknown")
        by_model.setdefault(model_name, []).append(r)

    models = []
    for model_name, scenarios in by_model.items():
        model_id = scenarios[0].get("model_id") or id_map.get(model_name) or _slugify(model_name)

        pass_count = sum(1 for s in scenarios if s.get("status") == "pass")
        fail_count = len(scenarios) - pass_count
        overall_scores = [s.get("overall_score", 0) for s in scenarios]
        overall_avg = sum(overall_scores) / len(overall_scores) if overall_scores else 0

        gates = [s.get("gates", {}) for s in scenarios]
        safety_pass = sum(1 for g in gates if g.get("safety", {}).get("passed", True))
        compliance_pass = sum(1 for g in gates if g.get("compliance", {}).get("passed", True))
        n = len(scenarios)

        dims = [s.get("dimensions", {}) for s in scenarios]
        regard_vals = [d.get("regard", 0) for d in dims if "regard" in d]
        coord_vals = [d.get("coordination", 0) for d in dims if "coordination" in d]

        model_scenarios = []
        for s in scenarios:
            sg = s.get("gates", {})
            sd = s.get("dimensions", {})
            model_scenarios.append({
                "scenario": s.get("scenario", ""),
                "scenarioId": s.get("scenario_id"),
                "category": s.get("category", ""),
                "overallScore": s.get("overall_score", 0),
                "status": s.get("status", "error"),
                "safetyGatePassed": sg.get("safety", {}).get("passed", True),
                "complianceGatePassed": sg.get("compliance", {}).get("passed", True),
                "regard": sd.get("regard"),
                "coordination": sd.get("coordination"),
                "cost": s.get("cost"),
            })

        models.append({
            "model": model_name,
            "modelId": model_id,
            "overallScore": overall_avg,
            "scenarioCount": n,
            "passCount": pass_count,
            "failCount": fail_count,
            "safetyGatePassRate": safety_pass / n if n else 0,
            "complianceGatePassRate": compliance_pass / n if n else 0,
            "regardAvg": sum(regard_vals) / len(regard_vals) if regard_vals else 0,
            "coordinationAvg": sum(coord_vals) / len(coord_vals) if coord_vals else 0,
            "totalCost": sum(s.get("cost", 0) for s in scenarios),
            "scenarios": model_scenarios,
        })

    # Sort by overall score descending, assign rank
    models.sort(key=lambda m: m["overallScore"], reverse=True)
    for i, m in enumerate(models):
        m["rank"] = i + 1

    return {
        "runId": run_id,
        "provider": "openrouter",
        "models": models,
    }


def _build_payload_from_leaderboard_ready(
    model_files: list[dict[str, Any]], run_id: str
) -> dict[str, Any]:
    """Transform leaderboard_ready/ per-model files into Convex publish payload."""
    id_map = _model_id_map()

    models = []
    for mf in model_files:
        model_name = mf.get("model", mf.get("model_name", "unknown"))
        model_id = id_map.get(model_name) or _slugify(model_name)
        scenarios = mf.get("scenarios", [])

        pass_count = sum(1 for s in scenarios if s.get("status") == "pass")
        fail_count = len(scenarios) - pass_count
        overall_scores = [s.get("overall_score", 0) for s in scenarios]
        overall_avg = sum(overall_scores) / len(overall_scores) if overall_scores else 0

        regard_vals = [s["dimension_scores"]["regard"] for s in scenarios if "dimension_scores" in s and "regard" in s["dimension_scores"]]
        coord_vals = [s["dimension_scores"]["coordination"] for s in scenarios if "dimension_scores" in s and "coordination" in s["dimension_scores"]]

        model_scenarios = []
        for s in scenarios:
            ds = s.get("dimension_scores", {})
            model_scenarios.append({
                "scenario": s.get("scenario", ""),
                "category": s.get("tier", ""),
                "overallScore": s.get("overall_score", 0),
                "status": s.get("status", "error"),
                "safetyGatePassed": s.get("status") != "fail",
                "complianceGatePassed": s.get("status") != "fail",
                "regard": ds.get("regard"),
                "coordination": ds.get("coordination"),
            })

        models.append({
            "model": model_name,
            "modelId": model_id,
            "overallScore": overall_avg,
            "scenarioCount": len(scenarios),
            "passCount": pass_count,
            "failCount": fail_count,
            "safetyGatePassRate": pass_count / len(scenarios) if scenarios else 0,
            "complianceGatePassRate": pass_count / len(scenarios) if scenarios else 0,
            "regardAvg": sum(regard_vals) / len(regard_vals) if regard_vals else 0,
            "coordinationAvg": sum(coord_vals) / len(coord_vals) if coord_vals else 0,
            "scenarios": model_scenarios,
        })

    # Sort by overall score descending, assign rank
    models.sort(key=lambda m: m["overallScore"], reverse=True)
    for i, m in enumerate(models):
        m["rank"] = i + 1

    return {
        "runId": run_id,
        "provider": "openrouter",
        "models": models,
    }


def publish(
    results_path: str,
    convex_url: str | None = None,
    publish_key: str | None = None,
) -> dict[str, Any]:
    """Publish benchmark results to Convex.

    Args:
        results_path: Path to all_results.json or leaderboard_ready/ directory.
        convex_url: Convex site URL (overrides CONVEX_BENCH_URL env var).
        publish_key: Bearer token (overrides BENCH_PUBLISH_KEY env var).

    Returns:
        Response JSON from the Convex endpoint.
    """
    url = convex_url or os.environ.get("CONVEX_SITE_URL") or os.environ.get("CONVEX_BENCH_URL")
    key = publish_key or os.environ.get("BENCH_PUBLISH_KEY")

    if not url:
        return {"error": "CONVEX_SITE_URL not set (or pass --url)"}

    path = Path(results_path)

    # Generate run ID from timestamp
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    if path.is_dir():
        model_files = _load_leaderboard_ready(path)
        if not model_files:
            return {"error": f"No JSON files in {path}"}
        payload = _build_payload_from_leaderboard_ready(model_files, run_id)
    elif path.is_file():
        results = _load_all_results(path)
        if not results:
            return {"error": f"No results in {path}"}
        payload = _build_payload_from_all_results(results, run_id)
    else:
        return {"error": f"Path not found: {path}"}

    endpoint = f"{url.rstrip('/')}/api/bench/publish"
    headers: dict[str, str] = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    resp = requests.post(
        endpoint,
        json=payload,
        headers=headers,
        timeout=30,
    )

    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text}"}

    return resp.json()


def run_publish(results_path: str, url: str | None = None) -> int:
    """CLI handler for `bench publish`."""
    result = publish(results_path, convex_url=url)
    if "error" in result:
        print(f"Error: {result['error']}")
        return 1
    models = result.get('modelsIngested') or result.get('modelCount', '?')
    scenarios = result.get('scenariosIngested') or result.get('scenarioCount', '?')
    print(f"Published: {result.get('runId', '?')} ({models} models, {scenarios} scenarios)")
    return 0
