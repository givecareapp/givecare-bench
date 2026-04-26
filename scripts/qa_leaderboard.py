#!/usr/bin/env python3
"""QA gate for V3 leaderboard artifacts.

Checks the scan JSONL and generated V3 leaderboard agree on source and meet
publication hygiene requirements. This script is intentionally local-only; it
never calls a model or external service.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

GATE_BUCKETS = {"A", "B"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL: {exc}") from exc
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


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
    expected_rows: int = 750,
    expected_models: int = 15,
    expected_scenarios: int = 50,
    expected_contract: str = "3.0.0-alpha",
    expected_stage: str = "v3-alpha",
    strict: bool = False,
) -> list[str]:
    """Return QA errors. Empty list means the artifact passes."""
    errors: list[str] = []
    rows = _load_jsonl(scan_path)
    leaderboard = _load_json(leaderboard_path)
    metadata = leaderboard.get("metadata") or {}

    if len(rows) != expected_rows:
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

    if len(by_model) != expected_models:
        errors.append(f"models={len(by_model)} expected={expected_models}")

    bad_model_counts = {
        model: len(scenarios)
        for model, scenarios in by_model.items()
        if len(scenarios) != expected_scenarios
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
    if metadata.get("total_models") != expected_models:
        errors.append(f"leaderboard_total_models={metadata.get('total_models')} expected={expected_models}")
    if metadata.get("total_scenarios") != expected_scenarios:
        errors.append(
            f"leaderboard_total_scenarios={metadata.get('total_scenarios')} expected={expected_scenarios}"
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
    parser.add_argument("--expected-rows", type=int, default=750)
    parser.add_argument("--expected-models", type=int, default=15)
    parser.add_argument("--expected-scenarios", type=int, default=50)
    parser.add_argument("--expected-contract", default="3.0.0-alpha")
    parser.add_argument("--expected-stage", default="v3-alpha")
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
