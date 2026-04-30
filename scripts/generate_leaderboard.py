#!/usr/bin/env python3
"""Generate a V3 mode-engine leaderboard from V3 scan JSONL output."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.utils.benchmark_inventory import (
    get_benchmark_version,
    get_code_version,
    load_inventory,
)

SCORING_CONFIG = REPO_ROOT / "benchmark" / "configs" / "scoring.yaml"
FAILURE_MODES = REPO_ROOT / "benchmark" / "configs" / "failure_modes.yaml"
SCORER_ROUTING = REPO_ROOT / "benchmark" / "configs" / "scorer_routing.yaml"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"No V3 scan rows found in {path}")
    return rows


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _active_mode_ids() -> list[str]:
    modes = _load_yaml(FAILURE_MODES).get("modes") or []
    routing = _load_yaml(SCORER_ROUTING)
    routed = {key for key, value in routing.items() if isinstance(value, dict)}
    return [
        str(mode["id"])
        for mode in modes
        if mode.get("status", "active") == "active" and str(mode.get("id")) in routed
    ]


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _dimension_mean(records: list[dict[str, Any]], dimension: str) -> float | None:
    values = [
        float(record["dimension_scores"][dimension])
        for record in records
        if isinstance(record.get("dimension_scores"), dict)
        and isinstance(record["dimension_scores"].get(dimension), int | float)
    ]
    return _mean(values)


def _mode_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for mode_result in record.get("mode_results") or []:
            if mode_result.get("eligible"):
                counts[str(mode_result.get("verdict"))] += 1
    return dict(counts)


def _blindspot_hits(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for record in records
        for value in (record.get("blindspot_profile") or {}).values()
        if value is True
    )


def _public_gate_pass_rate(records: list[dict[str, Any]], bucket: str) -> float | None:
    applicable = []
    for record in records:
        mode_results = [
            result
            for result in record.get("mode_results") or []
            if result.get("eligible") and result.get("primary_bucket") == bucket
        ]
        if not mode_results:
            continue
        applicable.append(not any(result.get("verdict") == "FAIL" for result in mode_results))
    if not applicable:
        return None
    return sum(1 for passed in applicable if passed) / len(applicable)


def _scenario_summary(record: dict[str, Any]) -> dict[str, Any]:
    notable_modes = []
    for result in record.get("mode_results") or []:
        verdict = result.get("verdict")
        if verdict not in {"FAIL", "UNCLEAR"} and result.get("scorer_type") != "manual_adjudication":
            continue
        notable_modes.append(
            {
                "mode_id": result.get("mode_id"),
                "eligible": result.get("eligible"),
                "verdict": verdict,
                "severity": result.get("severity"),
                "primary_bucket": result.get("primary_bucket"),
                "rationale_code": result.get("rationale_code"),
                "scorer_type": result.get("scorer_type"),
                "evidence": result.get("evidence") or [],
            }
        )

    return {
        "scenario_id": record.get("scenario_id"),
        "category": record.get("category"),
        "transcript_path": record.get("transcript_path"),
        "overall_score": record.get("overall_score"),
        "hard_fail": record.get("hard_fail"),
        "hard_fail_reasons": record.get("hard_fail_reasons") or [],
        "dimension_scores": record.get("dimension_scores") or {},
        "blindspot_profile": record.get("blindspot_profile") or {},
        "notable_modes": notable_modes,
    }


def _mode_failure_rates(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"eligible": 0, "failures": 0, "unclear": 0})
    for record in records:
        for result in record.get("mode_results") or []:
            if not result.get("eligible"):
                continue
            mode_id = str(result.get("mode_id"))
            totals[mode_id]["eligible"] += 1
            if result.get("verdict") == "FAIL":
                totals[mode_id]["failures"] += 1
            if result.get("verdict") == "UNCLEAR":
                totals[mode_id]["unclear"] += 1

    return {
        mode_id: {
            **counts,
            "failure_rate": counts["failures"] / counts["eligible"] if counts["eligible"] else 0.0,
            "unclear_rate": counts["unclear"] / counts["eligible"] if counts["eligible"] else 0.0,
        }
        for mode_id, counts in sorted(totals.items())
    }


def _artifact_validation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "rows": len(rows),
        "manual_adjudications": 0,
        "unclear_mode_verdicts": 0,
        "gate_unclear_mode_verdicts": 0,
        "fail_without_evidence": 0,
        "prompt_missing": 0,
        "no_verifier_available": 0,
        "fatal_verifier_errors": 0,
    }
    for row in rows:
        for result in row.get("mode_results") or []:
            eligible = bool(result.get("eligible"))
            verdict = result.get("verdict")
            rationale = str(result.get("rationale_code") or "")
            if result.get("scorer_type") == "manual_adjudication":
                totals["manual_adjudications"] += 1
            if eligible and verdict == "UNCLEAR":
                totals["unclear_mode_verdicts"] += 1
                if result.get("primary_bucket") in {"A", "B"}:
                    totals["gate_unclear_mode_verdicts"] += 1
            if eligible and verdict == "FAIL" and not result.get("evidence"):
                totals["fail_without_evidence"] += 1
            if eligible and rationale in {"prompt_missing", "missing_verifier_prompt"}:
                totals["prompt_missing"] += 1
            if rationale == "no_verifier_available" or rationale.startswith("prompt_file_missing:"):
                totals["no_verifier_available"] += 1
            if rationale.startswith("verifier_exception"):
                totals["fatal_verifier_errors"] += 1
    return totals


def compute_v3_rankings(rows: list[dict[str, Any]], *, expected_scenarios: int = 50) -> list[dict[str, Any]]:
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_model[str(row.get("model") or "unknown")].append(row)

    incomplete = {model: len(records) for model, records in by_model.items() if len(records) != expected_scenarios}
    if incomplete:
        import sys
        print(f"Warning: incomplete models: {incomplete}", file=sys.stderr)
        severely = {m: c for m, c in incomplete.items() if c < expected_scenarios * 0.8}
        if severely:
            raise ValueError(f"Models below 80% coverage: {severely}")

    ranked_rows: list[dict[str, Any]] = []
    for model, records in by_model.items():
        scenario_scores = [float(record.get("overall_score", 0.0)) for record in records]
        hard_fails = sum(1 for record in records if record.get("hard_fail"))
        hard_fail_rate = hard_fails / len(records) if records else 0.0
        mode_counts = _mode_counts(records)
        unclear = mode_counts.get("UNCLEAR", 0)
        eligible = sum(mode_counts.values())
        blindspot_hits = _blindspot_hits(records)

        ranked_rows.append(
            {
                "model": model,
                "model_id": records[0].get("model_id"),
                "v3_overall_score": _mean(scenario_scores) or 0.0,
                "scenario_count": len(records),
                "hard_failures": hard_fails,
                "hard_fail_rate": hard_fail_rate,
                "safety_gate_pass_rate": _public_gate_pass_rate(records, "A"),
                "compliance_gate_pass_rate": _public_gate_pass_rate(records, "B"),
                "dimension_scores": {
                    "communication_quality": _dimension_mean(records, "communication_quality"),
                    "caregiver_coordination": _dimension_mean(records, "caregiver_coordination"),
                    "boundary_integrity": _dimension_mean(records, "boundary_integrity"),
                },
                "mode_verdict_counts": mode_counts,
                "eligible_mode_verdicts": eligible,
                "unclear_mode_verdicts": unclear,
                "unclear_mode_verdict_rate": unclear / eligible if eligible else 0.0,
                "blindspot_hits": blindspot_hits,
                "mode_failure_rates": _mode_failure_rates(records),
                "scenarios": [
                    _scenario_summary(record)
                    for record in sorted(records, key=lambda record: str(record.get("scenario_id")))
                ],
            }
        )

    ranked_rows.sort(
        key=lambda row: (
            int(row["hard_failures"]),
            -float(row["v3_overall_score"]),
            int(row["blindspot_hits"]),
            float(row["unclear_mode_verdict_rate"]),
            str(row["model"]),
        )
    )
    for rank, row in enumerate(ranked_rows, start=1):
        row["rank"] = rank
    return ranked_rows


def generate_leaderboard(input_jsonl: Path, output_dir: Path, *, expected_scenarios: int = 50) -> Path:
    rows = _load_jsonl(input_jsonl)
    scoring = _load_yaml(SCORING_CONFIG)
    inventory = load_inventory(REPO_ROOT)
    generated_at = datetime.now(timezone.utc).isoformat()
    active_modes = _active_mode_ids()

    payload = {
        "metadata": {
            "benchmark_version": get_benchmark_version(REPO_ROOT),
            "code_version": get_code_version(REPO_ROOT),
            "score_contract_version": scoring.get("contract_version"),
            "publication_stage": scoring.get("version_stage"),
            "generated_at": generated_at,
            "source_artifact": str(input_jsonl),
            "public_scope": inventory["public_scope"],
            "public_harness": inventory["public_harness"],
            "total_models": len({row.get("model") for row in rows}),
            "total_scenarios": expected_scenarios,
            "active_modes": len(active_modes),
            "ranking_basis": {
                "kind": "v3_mode_engine_score",
                "primary_sort": [
                    "fewest_v3_hard_failures",
                    "highest_v3_overall_score",
                    "fewest_blindspot_hits",
                    "lowest_unclear_mode_verdict_rate",
                ],
                "note": "Rows are generated from V3 ModeEngine outputs, not repaired V2.1 scorer rows.",
            },
            "scenario_detail_policy": (
                "Per-scenario rows include summaries plus notable FAIL/UNCLEAR/manual mode results; "
                "the full verifier ledger is the source_artifact scan JSONL."
            ),
            "artifact_validation": _artifact_validation_summary(rows),
            "claim_surface": scoring.get("public_claim_surface", {}),
            "publication_threshold": scoring.get("publication_threshold", {}),
        },
        "overall_leaderboard": compute_v3_rankings(rows, expected_scenarios=expected_scenarios),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "leaderboard.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate V3 leaderboard data from V3 scan JSONL")
    parser.add_argument("--input", required=True, type=Path, help="Path to V3 scan per_run.jsonl")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--expected-scenarios", type=int, default=50)
    args = parser.parse_args()

    try:
        out_path = generate_leaderboard(
            args.input,
            args.output,
            expected_scenarios=args.expected_scenarios,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
