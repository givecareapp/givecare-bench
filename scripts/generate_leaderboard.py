#!/usr/bin/env python3
"""Generate the deterministic ``safety-care/v2`` public projection."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.check_registry import check_prompt_hashes, load_checks  # noqa: E402
from invisiblebench.scoring.projection import (  # noqa: E402
    OBSERVATION_TYPE,
    SCHEMA_VERSION,
    build_scorecard,
)
from invisiblebench.utils.benchmark_inventory import (  # noqa: E402
    get_benchmark_version,
    get_code_version,
    load_inventory,
)
from invisiblebench.utils.io import artifact_reference, load_jsonl  # noqa: E402

_OBSOLETE_ROW_KEYS = {
    "overall_score",
    "hard_fail",
    "hard_fail_reasons",
    "dimension_scores",
    "blindspot_profile",
    "claim_surface",
    "public_score_model",
    "result_surface",
    "score_model",
}


def _json_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    if not rows:
        raise ValueError(f"no scan rows found in {path}")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("scan rows must be JSON objects")
    return rows


def _active_mode_ids() -> list[str]:
    modes = load_checks()
    return sorted(str(mode_id) for mode_id in modes)


def _observed_prompt_hashes(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    observed: dict[str, set[str]] = {}
    for row in rows:
        for result in row.get("mode_results") or []:
            mode_id = str(result.get("mode_id") or "")
            prompt_hash = result.get("prompt_hash")
            if mode_id and isinstance(prompt_hash, str) and prompt_hash:
                observed.setdefault(mode_id, set()).add(prompt_hash)
    return {mode_id: sorted(values) for mode_id, values in sorted(observed.items())}


def _observed_judges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for row in rows:
        for result in row.get("mode_results") or []:
            judge = result.get("judge")
            if isinstance(judge, dict):
                key = json.dumps(judge, sort_keys=True, separators=(",", ":"))
                observed[key] = dict(judge)
    return [observed[key] for key in sorted(observed)]


def _load_scan_plan(path: Path) -> dict[str, Any] | None:
    plan_path = path.parent / "scan_plan.json"
    if not plan_path.is_file():
        return None
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid scan plan: {plan_path}: {exc}") from exc
    if not isinstance(plan, dict) or plan.get("schema") != "invisiblebench-scan-plan/v3":
        raise ValueError("active scans require invisiblebench-scan-plan/v3 provenance")
    return plan


def _validate_input_rows(rows: list[dict[str, Any]]) -> tuple[int, int, list[str]]:
    pairs: set[tuple[str, str]] = set()
    counts: Counter[str] = Counter()
    for row in rows:
        retired = sorted(_OBSOLETE_ROW_KEYS.intersection(row))
        if retired:
            raise ValueError(f"scan row contains retired fields: {retired}")
        model = str(row.get("model") or "")
        model_id = str(row.get("model_id") or "")
        scenario = str(row.get("scenario_id") or "")
        if not model or not model_id or not scenario:
            raise ValueError("scan row requires model, model_id, and scenario_id")
        pair = (model_id, scenario)
        if pair in pairs:
            raise ValueError(f"duplicate model/scenario row: {pair}")
        pairs.add(pair)
        counts[model_id] += 1
    if len(set(counts.values())) != 1:
        raise ValueError(f"model scenario coverage is not uniform: {dict(counts)}")
    return len(counts), next(iter(counts.values())), sorted(counts)


def generate_leaderboard(
    input_jsonl: Path,
    output_path: Path | None = None,
    *,
    expected_scenarios: int | None = None,
) -> Path:
    """Generate one inspectable Safety/Care projection from a scan ledger."""

    rows = _load_jsonl(input_jsonl)
    model_count, scenario_count, model_ids = _validate_input_rows(rows)
    if expected_scenarios is not None and scenario_count != expected_scenarios:
        raise ValueError(f"scenarios per model={scenario_count} expected={expected_scenarios}")
    scan_plan = _load_scan_plan(input_jsonl)
    projection = build_scorecard(input_jsonl)
    if projection["schema"] != SCHEMA_VERSION:
        raise ValueError(f"projection schema mismatch: {projection['schema']!r}")
    inventory = load_inventory(REPO_ROOT)
    scan_sha = hashlib.sha256(input_jsonl.read_bytes()).hexdigest()
    metadata: dict[str, Any] = {
        "benchmark_version": get_benchmark_version(REPO_ROOT),
        "code_version": get_code_version(REPO_ROOT),
        "generated_at": datetime.now(UTC).isoformat(),
        "source_artifact": artifact_reference(input_jsonl, REPO_ROOT),
        "source_sha256": scan_sha,
        "public_scope": inventory.get("public_scope"),
        "public_harness": inventory.get("public_harness"),
        "total_models": model_count,
        "total_scenarios": scenario_count,
        "active_checks": _active_mode_ids(),
        "check_prompt_hashes": check_prompt_hashes(),
        "observed_prompt_hashes": _observed_prompt_hashes(rows),
        "observed_judges": _observed_judges(rows),
        "row_count": len(rows),
        "model_ids": model_ids,
        "projection_sha256": _json_sha(projection["models"]),
        "observation_type": OBSERVATION_TYPE,
    }
    if scan_plan is not None:
        metadata["scan_plan"] = scan_plan
        metadata["scan_plan_sha256"] = _json_sha(scan_plan)

    payload = {
        **projection,
        "scan_metadata": metadata,
    }
    output = output_path or (input_jsonl.parent / "leaderboard.candidate.json")
    if output.suffix.lower() != ".json":
        output = output / "leaderboard.candidate.json"
    canonical_dir = (REPO_ROOT / "data" / "leaderboard").resolve()
    try:
        output.resolve().relative_to(canonical_dir)
    except ValueError:
        pass
    else:
        raise ValueError("generate_leaderboard cannot write the canonical data/leaderboard tree")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate safety-care/v2 leaderboard data")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--expected-scenarios", type=int, default=None)
    args = parser.parse_args()
    try:
        output = generate_leaderboard(
            args.input,
            args.output,
            expected_scenarios=args.expected_scenarios,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
