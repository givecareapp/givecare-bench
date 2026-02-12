"""
Safety report card generator for InvisibleBench v2.

Generates per-model pass/fail tables for safety and compliance gates,
plus quality leaderboards for gate-passing models.
"""

from __future__ import annotations

from typing import Any


def _short_scenario_name(scenario_id: str) -> str:
    """Convert scenario_id to a short display name for matrix columns."""
    # e.g. "cssrs_passive_ideation" -> "CSSRS Passive"
    parts = scenario_id.replace("_", " ").split()
    # Take first 2-3 meaningful words, title-case
    name = " ".join(parts[:3]).title()
    # Truncate to 18 chars for table columns
    if len(name) > 18:
        name = name[:16] + ".."
    return name


def generate_safety_report_card(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate per-model pass/fail table for all safety/compliance gate scenarios.

    Args:
        results: List of scenario result dicts (from all_results.json).
            Each must have: model, scenario_id, gates (with safety/compliance sub-dicts).

    Returns:
        Dict with:
        - 'models': per-model gate summaries with failures
        - 'scenario_matrix': scenario_id -> {model: "PASS"/"FAIL"}
        - 'scenario_names': scenario_id -> short display name
        - 'quality': per-model regard/coordination scores (gate-passers first)
    """
    # Group results by model
    by_model: dict[str, list[dict]] = {}
    for r in results:
        model = r.get("model", "unknown")
        by_model.setdefault(model, []).append(r)

    model_reports = []
    # Collect all scenario IDs across models (ordered by first appearance)
    all_scenario_ids: list[str] = []
    seen_ids: set[str] = set()
    # Map scenario_id -> display name from results
    scenario_names: dict[str, str] = {}

    for model, model_results in by_model.items():
        safety_passed = 0
        safety_failed = 0
        compliance_passed = 0
        compliance_failed = 0
        failures: list[dict[str, Any]] = []

        for r in model_results:
            sid = r.get("scenario_id", "")
            if sid not in seen_ids:
                all_scenario_ids.append(sid)
                seen_ids.add(sid)
                # Use scenario display name if available, else derive from ID
                scenario_names[sid] = r.get("scenario", "") or _short_scenario_name(sid)

            gates = r.get("gates") or {}
            safety_gate = gates.get("safety", {})
            compliance_gate = gates.get("compliance", {})

            s_pass = safety_gate.get("passed", True)
            c_pass = compliance_gate.get("passed", True)

            if s_pass:
                safety_passed += 1
            else:
                safety_failed += 1
                failures.append({
                    "scenario_id": sid,
                    "scenario": scenario_names.get(sid, sid),
                    "gate": "safety",
                    "reasons": safety_gate.get("reasons", []),
                })

            if c_pass:
                compliance_passed += 1
            else:
                compliance_failed += 1
                failures.append({
                    "scenario_id": sid,
                    "scenario": scenario_names.get(sid, sid),
                    "gate": "compliance",
                    "reasons": compliance_gate.get("reasons", []),
                })

        total = len(model_results)
        model_reports.append({
            "model": model,
            "safety_gate": {
                "passed": safety_passed,
                "failed": safety_failed,
                "total": total,
                "pass_rate": safety_passed / total if total else 0.0,
            },
            "compliance_gate": {
                "passed": compliance_passed,
                "failed": compliance_failed,
                "total": total,
                "pass_rate": compliance_passed / total if total else 0.0,
            },
            "overall_gate_pass": safety_failed == 0 and compliance_failed == 0,
            "failures": failures,
        })

    # Build scenario matrix: scenario_id -> {model: "PASS"/"FAIL"}
    scenario_matrix: dict[str, dict[str, str]] = {}
    for sid in all_scenario_ids:
        scenario_matrix[sid] = {}

    for model, model_results in by_model.items():
        for r in model_results:
            sid = r.get("scenario_id", "")
            gates = r.get("gates") or {}
            s_pass = gates.get("safety", {}).get("passed", True)
            c_pass = gates.get("compliance", {}).get("passed", True)
            scenario_matrix[sid][model] = "PASS" if (s_pass and c_pass) else "FAIL"

    # Build quality scores per model
    quality = _compute_quality(by_model, model_reports)

    return {
        "models": model_reports,
        "scenario_matrix": scenario_matrix,
        "scenario_names": scenario_names,
        "quality": quality,
    }


def _compute_quality(
    by_model: dict[str, list[dict]], model_reports: list[dict]
) -> list[dict[str, Any]]:
    """Compute regard/coordination quality scores per model."""
    gate_pass_lookup = {m["model"]: m["overall_gate_pass"] for m in model_reports}

    quality = []
    for model, model_results in by_model.items():
        regard_scores = []
        coord_scores = []
        for r in model_results:
            dims = r.get("dimensions") or {}
            rg = dims.get("regard")
            co = dims.get("coordination")
            if isinstance(rg, (int, float)):
                regard_scores.append(rg)
            if isinstance(co, (int, float)):
                coord_scores.append(co)

        avg_regard = sum(regard_scores) / len(regard_scores) if regard_scores else 0.0
        avg_coord = sum(coord_scores) / len(coord_scores) if coord_scores else 0.0

        quality.append({
            "model": model,
            "all_gates_pass": gate_pass_lookup.get(model, False),
            "regard": round(avg_regard, 4),
            "coordination": round(avg_coord, 4),
            "quality_score": round((avg_regard + avg_coord) / 2, 4),
        })

    # Gate-passers first, then by quality score descending
    quality.sort(key=lambda x: (-int(x["all_gates_pass"]), -x["quality_score"]))
    return quality
