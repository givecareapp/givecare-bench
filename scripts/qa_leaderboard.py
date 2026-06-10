#!/usr/bin/env python3
"""QA gate for V3 leaderboard artifacts.

Checks the scan JSONL and generated V3 leaderboard agree on source and meet
publication hygiene requirements. This script is intentionally local-only; it
never calls a model or external service.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.utils.io import load_json as _load_json  # noqa: E402
from invisiblebench.utils.io import load_jsonl as _load_jsonl  # noqa: E402

GATE_BUCKETS = {"A", "B"}
SCORING_CONFIG = REPO_ROOT / "benchmark" / "configs" / "scoring.yaml"


def _scoring_contract() -> tuple[str, str]:
    """Expected (contract_version, version_stage) from the scoring config.

    scoring.yaml is the single owner of these values; QA defaults read it at
    runtime so a contract bump never silently diverges from the gate.
    """
    data = yaml.safe_load(SCORING_CONFIG.read_text()) or {}
    return str(data["contract_version"]), str(data["version_stage"])


def _manual_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("model_id")),
        str(record.get("scenario_id")),
        str(record.get("mode_id")),
    )


def _manual_scan_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        for result in row.get("mode_results") or []:
            if result.get("scorer_type") != "manual_adjudication":
                continue
            records.append(
                {
                    "model": row.get("model"),
                    "model_id": row.get("model_id"),
                    "scenario_id": row.get("scenario_id"),
                    "mode_id": result.get("mode_id"),
                    "final_eligible": result.get("eligible"),
                    "final_verdict": result.get("verdict"),
                    "rationale_code": result.get("rationale_code"),
                    "confidence": result.get("confidence"),
                    "evidence": result.get("evidence") or [],
                    "previous_verdict": (result.get("extra") or {}).get("previous_verdict"),
                    "previous_rationale_code": (result.get("extra") or {}).get("previous_rationale_code"),
                    "source_transcript": row.get("transcript_path"),
                }
            )
    return records


def validate_leaderboard(
    scan_path: Path,
    leaderboard_path: Path,
    *,
    manual_adjudications_path: Path | None = None,
    expected_rows: int | None = None,
    expected_models: int | None = None,
    expected_scenarios: int | None = None,
    expected_contract: str | None = None,
    expected_stage: str | None = None,
    strict: bool = False,
) -> list[str]:
    """Return QA errors. Empty list means the artifact passes."""
    if expected_contract is None or expected_stage is None:
        contract, stage = _scoring_contract()
        expected_contract = expected_contract or contract
        expected_stage = expected_stage or stage
    errors: list[str] = []
    rows = _load_jsonl(scan_path)
    leaderboard = _load_json(leaderboard_path)
    metadata = leaderboard.get("metadata") or {}

    if expected_rows is not None and len(rows) != expected_rows:
        errors.append(f"rows={len(rows)} expected={expected_rows}")

    by_model: dict[str, set[str]] = defaultdict(set)
    seen_pairs: set[tuple[str, str]] = set()
    duplicate_pairs: list[tuple[str, str]] = []
    for row in rows:
        model = str(row.get("model") or "")
        scenario_id = str(row.get("scenario_id") or "")
        by_model[model].add(scenario_id)
        pair = (model, scenario_id)
        if pair in seen_pairs:
            duplicate_pairs.append(pair)
        seen_pairs.add(pair)

    effective_models = expected_models if expected_models is not None else len(by_model)
    if len(by_model) != effective_models:
        errors.append(f"models={len(by_model)} expected={effective_models}")

    if expected_scenarios is None:
        observed_counts = {model: len(scenarios) for model, scenarios in by_model.items()}
        unique_counts = set(observed_counts.values())
        if len(unique_counts) == 1:
            effective_scenarios = unique_counts.pop()
        else:
            effective_scenarios = None
            errors.append(f"scenario_count_mismatch={observed_counts}")
    else:
        effective_scenarios = expected_scenarios

    bad_model_counts = {
        model: len(scenarios)
        for model, scenarios in by_model.items()
        if effective_scenarios is not None and len(scenarios) != effective_scenarios
    }
    if bad_model_counts:
        errors.append(f"scenario_count_mismatch={bad_model_counts}")

    if duplicate_pairs:
        errors.append(f"duplicate_model_scenario_pairs={duplicate_pairs[:10]}")

    if metadata.get("source_artifact") != str(scan_path):
        errors.append(
            "leaderboard_source_mismatch="
            f"{metadata.get('source_artifact')!r} expected={str(scan_path)!r}"
        )
    if metadata.get("score_contract_version") != expected_contract:
        errors.append(
            "score_contract_version="
            f"{metadata.get('score_contract_version')!r} expected={expected_contract!r}"
        )
    if metadata.get("publication_stage") != expected_stage:
        errors.append(
            f"publication_stage={metadata.get('publication_stage')!r} expected={expected_stage!r}"
        )
    if metadata.get("total_models") != effective_models:
        errors.append(
            f"leaderboard_total_models={metadata.get('total_models')} expected={effective_models}"
        )
    if effective_scenarios is not None and metadata.get("total_scenarios") != effective_scenarios:
        errors.append(
            f"leaderboard_total_scenarios={metadata.get('total_scenarios')} "
            f"expected={effective_scenarios}"
        )

    prompt_missing = 0
    no_verifier = 0
    fatal_errors = 0
    fail_without_evidence = 0
    gate_unclear: Counter[str] = Counter()
    all_unclear: Counter[str] = Counter()
    manual_without_evidence = 0

    for row in rows:
        for result in row.get("mode_results") or []:
            mode_id = str(result.get("mode_id"))
            rationale = str(result.get("rationale_code") or "")
            eligible = bool(result.get("eligible"))
            verdict = result.get("verdict")
            evidence = result.get("evidence") or []

            if eligible and rationale in {"prompt_missing", "missing_verifier_prompt"}:
                prompt_missing += 1
            if rationale == "no_verifier_available" or rationale.startswith("prompt_file_missing:"):
                no_verifier += 1
            if rationale.startswith("verifier_exception"):
                fatal_errors += 1
            if eligible and verdict == "FAIL" and not evidence:
                fail_without_evidence += 1
            if eligible and verdict == "UNCLEAR":
                all_unclear[mode_id] += 1
                if result.get("primary_bucket") in GATE_BUCKETS:
                    gate_unclear[mode_id] += 1
            if result.get("scorer_type") == "manual_adjudication" and not evidence and verdict != "NOT_APPLICABLE":
                manual_without_evidence += 1

    if prompt_missing:
        errors.append(f"prompt_missing={prompt_missing}")
    if no_verifier:
        errors.append(f"no_verifier_available={no_verifier}")
    if fatal_errors:
        errors.append(f"fatal_verifier_errors={fatal_errors}")
    if fail_without_evidence:
        errors.append(f"fail_without_evidence={fail_without_evidence}")
    if gate_unclear:
        errors.append(f"gate_unclear={dict(gate_unclear)}")
    if strict and all_unclear:
        errors.append(f"all_unclear={dict(all_unclear)}")
    if manual_without_evidence:
        errors.append(f"manual_without_evidence={manual_without_evidence}")

    manual_scan = _manual_scan_records(rows)
    if manual_adjudications_path is not None:
        manual_payload = _load_json(manual_adjudications_path)
        manual_file = manual_payload.get("manual_adjudications") or []
        if not isinstance(manual_file, list):
            errors.append("manual_adjudications_not_list")
            manual_file = []
        scan_by_key = {_manual_key(record): record for record in manual_scan}
        file_by_key = {_manual_key(record): record for record in manual_file if isinstance(record, dict)}
        missing = sorted(set(scan_by_key) - set(file_by_key))
        extra = sorted(set(file_by_key) - set(scan_by_key))
        if missing:
            errors.append(f"manual_adjudications_missing={missing[:10]}")
        if extra:
            errors.append(f"manual_adjudications_extra={extra[:10]}")
        for key, scan_record in scan_by_key.items():
            file_record = file_by_key.get(key)
            if not file_record:
                continue
            for field in ("final_verdict", "rationale_code", "previous_verdict"):
                if file_record.get(field) != scan_record.get(field):
                    errors.append(
                        f"manual_adjudication_mismatch key={key} field={field} "
                        f"scan={scan_record.get(field)!r} file={file_record.get(field)!r}"
                    )
            if not file_record.get("evidence") and file_record.get("final_verdict") != "NOT_APPLICABLE":
                errors.append(f"manual_adjudication_without_evidence key={key}")
    elif manual_scan and strict:
        errors.append(f"manual_adjudications_file_required count={len(manual_scan)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="QA V3 scan + leaderboard artifacts")
    parser.add_argument("--scan", required=True, type=Path, help="V3 per_run.jsonl scan artifact")
    parser.add_argument("--leaderboard", required=True, type=Path, help="Generated v3_leaderboard.json")
    parser.add_argument("--manual-adjudications", type=Path, default=None)
    parser.add_argument("--expected-rows", type=int, default=None)
    parser.add_argument("--expected-models", type=int, default=None)
    parser.add_argument("--expected-scenarios", type=int, default=None)
    parser.add_argument(
        "--expected-contract", default=None,
        help="Override; default reads contract_version from scoring.yaml",
    )
    parser.add_argument(
        "--expected-stage", default=None,
        help="Override; default reads version_stage from scoring.yaml",
    )
    parser.add_argument("--strict", action="store_true", help="Require zero UNCLEARs and manual audit file")
    args = parser.parse_args()

    errors = validate_leaderboard(
        args.scan,
        args.leaderboard,
        manual_adjudications_path=args.manual_adjudications,
        expected_rows=args.expected_rows,
        expected_models=args.expected_models,
        expected_scenarios=args.expected_scenarios,
        expected_contract=args.expected_contract,
        expected_stage=args.expected_stage,
        strict=args.strict,
    )
    if errors:
        print("V3 leaderboard QA failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("V3 leaderboard QA passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
