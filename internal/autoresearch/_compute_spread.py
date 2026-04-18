#!/usr/bin/env python3
"""Compute scenario differentiation metrics from benchmark artifacts.

This module is the fixed evaluator for internal autoresearch campaigns.
It reads benchmark outputs, isolates one scenario across a chosen model set,
computes a spread-oriented objective, and reports guardrail failures that are
important for benchmark design (for example, collapse into universal failure).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class GuardrailConfig:
    min_models: int = 3
    min_mean: float = 0.2
    max_mean: float = 0.95
    forbid_errors: bool = True
    forbid_all_fail: bool = True
    forbid_all_hard_fail: bool = True


def normalize_filter(value: str) -> str:
    return _NORMALIZE_RE.sub("_", value.lower()).strip("_")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _dimension_value(row: dict[str, Any], key: str) -> float:
    dimensions = row.get("dimensions") or {}
    dimension_scores = row.get("dimension_scores") or {}
    return _as_float(dimensions.get(key, dimension_scores.get(key, 0.0)))


def normalize_result_row(row: dict[str, Any], default_model: str | None = None) -> dict[str, Any]:
    model = row.get("model") or row.get("model_name") or row.get("model_id") or default_model or "?"
    status = str(row.get("status") or ("fail" if row.get("hard_fail") else "pass"))
    gates = row.get("gates") or {}
    return {
        "model": str(model),
        "model_id": row.get("model_id"),
        "scenario": str(row.get("scenario") or row.get("title") or row.get("scenario_id") or "?"),
        "scenario_id": str(row.get("scenario_id") or row.get("id") or "?"),
        "category": row.get("category") or row.get("tier") or "?",
        "overall_score": _as_float(row.get("overall_score", 0.0)),
        "hard_fail": bool(row.get("hard_fail", False)),
        "status": status,
        "success": bool(row.get("success", status == "pass")),
        "regard": _dimension_value(row, "regard"),
        "coordination": _dimension_value(row, "coordination"),
        "gates": gates,
    }


def _rows_from_payload(payload: Any, default_model: str | None = None) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [normalize_result_row(row, default_model) for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("scenarios"), list):
        model = payload.get("model") or payload.get("model_name") or payload.get("model_id") or default_model
        return [
            normalize_result_row(row, str(model) if model else None)
            for row in payload["scenarios"]
            if isinstance(row, dict)
        ]
    return [normalize_result_row(payload, default_model)] if payload.get("scenario_id") else []


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_run_rows(run_dir: Path) -> list[dict[str, Any]]:
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    all_results_path = run_dir / "all_results.json"
    if all_results_path.exists():
        rows = _rows_from_payload(_load_json(all_results_path))
        if rows:
            return rows

    model_results_dir = run_dir / "model_results"
    if model_results_dir.exists():
        rows: list[dict[str, Any]] = []
        for path in sorted(model_results_dir.glob("*.json")):
            rows.extend(_rows_from_payload(_load_json(path)))
        if rows:
            return rows

    rows = []
    for path in sorted(run_dir.glob("*.json")):
        if path.name in {"all_results.json", "run_manifest.json", "run_audit.json"}:
            continue
        rows.extend(_rows_from_payload(_load_json(path)))
    return rows


def load_leaderboard_rows(results_dir: Path) -> list[dict[str, Any]]:
    if not results_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        rows.extend(_rows_from_payload(_load_json(path)))
    return rows


def filter_rows(rows: Iterable[dict[str, Any]], scenario_filter: str) -> list[dict[str, Any]]:
    normalized_filter = normalize_filter(scenario_filter)
    matched: list[dict[str, Any]] = []
    for row in rows:
        scenario = normalize_filter(str(row.get("scenario", "")))
        scenario_id = normalize_filter(str(row.get("scenario_id", "")))
        if normalized_filter in scenario or normalized_filter in scenario_id:
            matched.append(row)
    return matched


def evaluate_guardrails(summary: dict[str, Any], config: GuardrailConfig) -> dict[str, Any]:
    reasons: list[str] = []
    n_models = int(summary.get("n_models", 0))
    mean = _as_float(summary.get("mean", 0.0))

    if summary.get("error"):
        reasons.append(str(summary["error"]))
    if n_models < config.min_models:
        reasons.append(f"matched only {n_models} models; need at least {config.min_models}")
    if config.forbid_errors and int(summary.get("error_count", 0)) > 0:
        reasons.append("one or more probe models errored")
    if config.forbid_all_fail and bool(summary.get("all_fail", False)):
        reasons.append("all matched models failed")
    if config.forbid_all_hard_fail and bool(summary.get("all_hard_fail", False)):
        reasons.append("all matched models hard-failed")
    if mean < config.min_mean:
        reasons.append(f"mean score {mean:.3f} is below floor {config.min_mean:.3f}")
    if mean > config.max_mean:
        reasons.append(f"mean score {mean:.3f} is above ceiling {config.max_mean:.3f}")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "config": asdict(config),
    }


def compute_spread_summary(
    rows: Sequence[dict[str, Any]],
    scenario_filter: str,
    label: str,
    guardrails: GuardrailConfig | None = None,
) -> dict[str, Any]:
    matched = filter_rows(rows, scenario_filter)
    if not matched:
        summary = {
            "label": label,
            "scenario": scenario_filter,
            "error": f"No matching results for '{scenario_filter}'",
            "n_models": 0,
            "spread": 0.0,
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "stdev": 0.0,
            "pass_count": 0,
            "fail_count": 0,
            "error_count": 0,
            "hard_fail_count": 0,
            "all_pass": False,
            "all_fail": False,
            "all_hard_fail": False,
            "same_status": False,
            "matched_scenarios": [],
            "matched_scenario_ids": [],
            "models": [],
        }
        summary["guardrails"] = evaluate_guardrails(summary, guardrails or GuardrailConfig())
        return summary

    scores = [_as_float(row.get("overall_score", 0.0)) for row in matched]
    statuses = [str(row.get("status", "?")) for row in matched]
    pass_count = sum(status == "pass" for status in statuses)
    fail_count = sum(status == "fail" for status in statuses)
    error_count = sum(status == "error" for status in statuses)
    hard_fail_count = sum(bool(row.get("hard_fail", False)) for row in matched)

    models = [
        {
            "model": row["model"],
            "scenario": row["scenario"],
            "scenario_id": row["scenario_id"],
            "overall_score": round(_as_float(row.get("overall_score", 0.0)), 3),
            "hard_fail": bool(row.get("hard_fail", False)),
            "status": str(row.get("status", "?")),
            "regard": round(_as_float(row.get("regard", 0.0)), 3),
            "coordination": round(_as_float(row.get("coordination", 0.0)), 3),
        }
        for row in matched
    ]
    models.sort(key=lambda item: (-item["overall_score"], item["model"]))

    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0
    summary = {
        "label": label,
        "scenario": scenario_filter,
        "matched_scenarios": sorted({str(row["scenario"]) for row in matched}),
        "matched_scenario_ids": sorted({str(row["scenario_id"]) for row in matched}),
        "n_models": len(matched),
        "spread": round(max(scores) - min(scores), 3),
        "mean": round(mean, 3),
        "min": round(min(scores), 3),
        "max": round(max(scores), 3),
        "stdev": round(stdev, 3),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "error_count": error_count,
        "hard_fail_count": hard_fail_count,
        "all_pass": pass_count == len(matched),
        "all_fail": fail_count == len(matched),
        "all_hard_fail": hard_fail_count == len(matched),
        "same_status": len(set(statuses)) == 1,
        "models": models,
    }
    summary["guardrails"] = evaluate_guardrails(summary, guardrails or GuardrailConfig())
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    if summary.get("error"):
        print(f"WARNING: {summary['error']}")
        return

    print(f"Scenario:   {summary['scenario']}")
    print(f"Matched:    {', '.join(summary['matched_scenario_ids'])}")
    print(f"Models:     {summary['n_models']}")
    print(f"Spread:     {summary['spread']:.3f}")
    print(f"Mean:       {summary['mean']:.3f}")
    print(f"Range:      {summary['min']:.3f} - {summary['max']:.3f}")
    print(
        "Statuses:   "
        f"pass={summary['pass_count']} fail={summary['fail_count']} error={summary['error_count']} "
        f"hard_fail={summary['hard_fail_count']}"
    )
    print(f"Guardrails: {'OK' if summary['guardrails']['ok'] else 'FAIL'}")
    if summary["guardrails"]["reasons"]:
        for reason in summary["guardrails"]["reasons"]:
            print(f"  - {reason}")
    print()
    for model in summary["models"]:
        fail = " FAIL" if model["hard_fail"] else ""
        print(f"  {model['model']:<24} {model['overall_score']:.3f}{fail} [{model['status']}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, help="Benchmark run directory")
    parser.add_argument("--scenario", required=True, help="Scenario name or id filter")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--label", required=True, help="Experiment label")
    parser.add_argument("--min-models", type=int, default=3)
    parser.add_argument("--min-mean", type=float, default=0.2)
    parser.add_argument("--max-mean", type=float, default=0.95)
    parser.add_argument("--allow-errors", action="store_true")
    parser.add_argument("--allow-all-fail", action="store_true")
    parser.add_argument("--allow-all-hard-fail", action="store_true")
    args = parser.parse_args()

    guardrails = GuardrailConfig(
        min_models=args.min_models,
        min_mean=args.min_mean,
        max_mean=args.max_mean,
        forbid_errors=not args.allow_errors,
        forbid_all_fail=not args.allow_all_fail,
        forbid_all_hard_fail=not args.allow_all_hard_fail,
    )

    rows = load_run_rows(Path(args.run_dir))
    summary = compute_spread_summary(rows, args.scenario, args.label, guardrails)
    print_summary(summary)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
