#!/usr/bin/env python3
"""Generate the canonical safety-care/v1 leaderboard from scan JSONL output."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.check_registry import check_prompt_hashes, load_checks
from invisiblebench.scoring.contract import can_carry_hard_fail_claim
from invisiblebench.utils.artifact_validation import (
    artifact_issue_policy,
    observed_prompt_hashes,
    scan_artifact_validation_diagnostics,
    scan_artifact_validation_summary,
    scan_check_coverage,
    scan_current_contract_validation_diagnostics,
    scan_current_contract_validation_summary,
)
from invisiblebench.utils.benchmark_inventory import (
    collect_public_scenario_ids,
    get_benchmark_version,
    get_code_version,
    load_inventory,
)
from invisiblebench.utils.io import artifact_reference, load_jsonl
from invisiblebench.version import RESULT_CONTRACT_VERSION, SCANNED_ROW_CONTRACT_VERSION


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    if not rows:
        raise ValueError(f"No scan rows found in {path}")
    return rows


def _load_source_merge(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    manifest_path = path.parent / "merge_manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict):
        raise ValueError(f"Expected object JSON at {manifest_path}")
    schema = manifest.get("schema")
    expected_contract = {
        "invisiblebench-scan-merge/v1": RESULT_CONTRACT_VERSION,
        "invisiblebench-scan-merge/v2": SCANNED_ROW_CONTRACT_VERSION,
    }.get(schema)
    if expected_contract is None:
        raise ValueError(f"Invalid merge manifest schema: {schema!r}")
    expected = {
        "benchmark_version": get_benchmark_version(REPO_ROOT),
        "result_contract_version": expected_contract,
        "profile": "publish",
        "row_count": len(rows),
        "output_file": path.name,
        "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model_count": len({str(row.get("model_id") or "") for row in rows}),
        "scenario_count": len({str(row.get("scenario_id") or "") for row in rows}),
    }
    mismatches = {
        key: {"actual": manifest.get(key), "expected": value}
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    if mismatches:
        raise ValueError(f"Invalid merge manifest: {mismatches}")
    if schema == "invisiblebench-scan-merge/v2":
        fingerprint = manifest.get("comparability_fingerprint")
        scenario_corpus = manifest.get("scenario_corpus_sha256")
        scoring_config = manifest.get("scoring_config_sha256")
        check_hashes = manifest.get("check_definition_hashes")
        if (
            manifest.get("provenance_complete") is not True
            or not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or not isinstance(scenario_corpus, str)
            or len(scenario_corpus) != 64
            or not isinstance(scoring_config, str)
            or len(scoring_config) != 64
            or not isinstance(check_hashes, dict)
            or not check_hashes
            or any(not isinstance(value, str) or len(value) != 64 for value in check_hashes.values())
        ):
            raise ValueError("Invalid merge manifest: incomplete v2 provenance")
        row_contracts = {row.get("contract_version") for row in rows}
        if row_contracts != {SCANNED_ROW_CONTRACT_VERSION}:
            raise ValueError("Invalid merge manifest: scan row contract mismatch")
    sources = manifest.get("sources")
    if not manifest.get("judge_model") or not isinstance(sources, list) or not sources:
        raise ValueError("Invalid merge manifest: missing judge_model or sources")
    source_rows = 0
    source_cost = 0.0
    source_calls = 0
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"Invalid merge manifest: source {index} is not an object")
        required = {
            "artifact_id": str,
            "sha256": str,
            "row_count": int,
            "model_ids": list,
            "transcript_source_artifacts": list,
        }
        if schema == "invisiblebench-scan-merge/v2":
            required["scan_plan_sha256"] = str
        invalid = [
            key
            for key, expected_type in required.items()
            if not isinstance(source.get(key), expected_type) or not source.get(key)
        ]
        cost = source.get("actual_cost_usd")
        calls = source.get("actual_billable_api_calls")
        invalid_hashes = [
            key
            for key in ("sha256", "scan_plan_sha256")
            if key in required and len(source.get(key) or "") != 64
        ]
        if invalid or invalid_hashes:
            raise ValueError(f"Invalid merge manifest source {index}: fields={invalid}")
        if (
            isinstance(cost, bool)
            or not isinstance(cost, (int, float))
            or cost < 0
            or isinstance(calls, bool)
            or not isinstance(calls, int)
            or calls < 0
        ):
            raise ValueError(f"Invalid merge manifest source {index}: cost accounting")
        source_rows += source["row_count"]
        source_cost += float(cost)
        source_calls += calls
    if source_rows != len(rows):
        raise ValueError("Invalid merge manifest: source row counts do not match output")
    if abs(source_cost - float(manifest.get("actual_cost_usd", -1))) > 1e-9:
        raise ValueError("Invalid merge manifest: source costs do not match total")
    if source_calls != manifest.get("actual_billable_api_calls"):
        raise ValueError("Invalid merge manifest: source calls do not match total")
    return manifest


def _active_mode_ids() -> list[str]:
    modes, routing = load_checks()
    return [
        mode_id
        for mode_id, mode in modes.items()
        if mode.get("status", "active") == "active" and routing.get(mode_id)
    ]


def _mode_by_id() -> dict[str, dict[str, Any]]:
    modes, _ = load_checks()
    return dict(modes)


def _hard_fail_reasons(
    record: dict[str, Any],
    mode_config_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for result in record.get("mode_results") or []:
        if not result.get("eligible"):
            continue
        mode_id = str(result.get("mode_id") or "")
        mode_config = mode_config_by_id.get(mode_id) or {}
        calibration = mode_config.get("calibration") or {}
        severity = str(mode_config.get("severity", result.get("severity") or ""))
        if not can_carry_hard_fail_claim(
            verdict=str(result.get("verdict") or ""),
            severity=severity,
            check_hard_fail=bool(mode_config.get("hard_fail")),
            calibration_status=calibration.get("status"),
        ):
            continue
        reasons.append(
            {
                "mode_id": mode_id,
                "reason": result.get("rationale_code") or "hard_fail",
                "layer": mode_config.get("layer"),
                "dimension": mode_config.get("dimension"),
                "severity": severity,
            }
        )
    return reasons


def _count_hard_fail_contract_normalizations(rows: list[dict[str, Any]]) -> int:
    mode_config_by_id = _mode_by_id()
    changed = 0
    for row in rows:
        reasons = _hard_fail_reasons(row, mode_config_by_id)
        previous_hard_fail = bool(row.get("hard_fail"))
        previous_reasons = row.get("hard_fail_reasons") or []
        next_hard_fail = bool(reasons)
        if previous_hard_fail != next_hard_fail or previous_reasons != reasons:
            changed += 1
    return changed


def _resolve_expected_scenarios(
    by_model: dict[str, list[dict[str, Any]]],
    expected_scenarios: int | None,
) -> int:
    model_counts: dict[str, int] = {}
    duplicate_pairs: list[tuple[str, str]] = []
    for model, records in by_model.items():
        scenario_ids: set[str] = set()
        for record in records:
            scenario_id = str(record.get("scenario_id") or "")
            key = (model, scenario_id)
            if scenario_id in scenario_ids:
                duplicate_pairs.append(key)
            scenario_ids.add(scenario_id)
        model_counts[model] = len(scenario_ids)
        if len(records) != len(scenario_ids):
            continue

    if duplicate_pairs:
        raise ValueError(f"Duplicate model/scenario rows: {duplicate_pairs[:10]}")

    if expected_scenarios is not None:
        return expected_scenarios

    unique_counts = set(model_counts.values())
    if len(unique_counts) != 1:
        raise ValueError(f"Model scenario coverage is not uniform: {model_counts}")
    return unique_counts.pop()


def generate_leaderboard(
    input_jsonl: Path,
    output_dir: Path,
    *,
    expected_scenarios: int | None = None,
) -> Path:
    """Generate the canonical Safety+Care leaderboard artifact (safety-care/v1).

    The primary output is a ``{models, schema, notes, scan_metadata}`` artifact
    with per-Safety-line violation rates and per-Care-quality pass-rate
    distributions.  No composite / overall_score / rank key appears at the top
    level or in any model entry.
    """
    from invisiblebench.scoring.projection import build_scorecard

    rows = _load_jsonl(input_jsonl)
    source_merge = _load_source_merge(input_jsonl, rows)
    hard_fail_normalizations = _count_hard_fail_contract_normalizations(rows)
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_model[str(row.get("model") or "unknown")].append(row)
    scenario_count = _resolve_expected_scenarios(by_model, expected_scenarios)
    inventory = load_inventory(REPO_ROOT)
    generated_at = datetime.now(timezone.utc).isoformat()
    active_modes = _active_mode_ids()
    expected_scenario_ids = collect_public_scenario_ids(REPO_ROOT)

    # ------------------------------------------------------------------
    # Primary: Safety+Care scorecard (safety-care/v1)
    # ------------------------------------------------------------------
    scorecard = build_scorecard(str(input_jsonl), calibrated_only=True)

    scan_metadata = {
        "benchmark_version": get_benchmark_version(REPO_ROOT),
        "code_version": get_code_version(REPO_ROOT),
        "generated_at": generated_at,
        "source_artifact": artifact_reference(input_jsonl, REPO_ROOT),
        "public_scope": inventory["public_scope"],
        "public_harness": inventory["public_harness"],
        "total_models": len({row.get("model") for row in rows}),
        "total_scenarios": scenario_count,
        "active_modes": len(active_modes),
        "check_prompt_hashes": check_prompt_hashes(),
        "observed_prompt_hashes": observed_prompt_hashes(rows),
        "statistics": {
            "method": (
                "cluster-robust normal 95% CIs; Wilson score fallback at binary boundaries "
                "using contrast-set families as independent clusters"
            ),
            "reference": "Anthropic, Adding Error Bars to Evals (arXiv:2411.00640)",
        },
        "artifact_validation": {
            **scan_artifact_validation_summary(rows),
            "hard_fail_contract_normalizations": hard_fail_normalizations,
        },
        "artifact_diagnostics": scan_artifact_validation_diagnostics(rows),
        "check_coverage": scan_check_coverage(rows),
        "artifact_issue_policy": artifact_issue_policy(),
        "current_contract_validation": scan_current_contract_validation_summary(
            rows,
            expected_scenario_ids=expected_scenario_ids,
            expected_check_ids=active_modes,
        ),
        "current_contract_diagnostics": scan_current_contract_validation_diagnostics(
            rows,
            expected_scenario_ids=expected_scenario_ids,
            expected_check_ids=active_modes,
        ),
    }
    if source_merge is not None:
        scan_metadata["source_merge"] = source_merge

    payload = {
        **scorecard,  # models, schema, notes
        "scan_metadata": scan_metadata,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "leaderboard.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate safety-care/v1 leaderboard data from scan JSONL"
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to scan per_run.jsonl")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--expected-scenarios",
        type=int,
        default=None,
        help="Require this many unique scenarios per model; defaults to inferred uniform coverage.",
    )
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
