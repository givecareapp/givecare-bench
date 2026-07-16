#!/usr/bin/env python3
"""QA gate for safety-care/v1 leaderboard artifacts.

Checks the scan JSONL and generated leaderboard agree on source and meet
publication hygiene requirements. This script is intentionally local-only; it
never calls a model or external service.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invisiblebench.evaluation.check_registry import (  # noqa: E402
    check_definition_hashes,
    check_prompt_hashes,
    load_checks,
)

# scoring.yaml is the single owner of threshold values; QA reads it through
# scoring_contract so a bump never silently diverges from the gate.
from invisiblebench.evaluation.scoring_contract import coverage_floor  # noqa: E402
from invisiblebench.evaluation.verifiers.base import (  # noqa: E402
    FAILURE_VERDICT_VALUES,
    PASS_VERDICT_VALUES,
    Verdict,
)
from invisiblebench.scoring.contract import (  # noqa: E402
    CLAIM_READY_STATUS,
    is_claim_capable_check,
)
from invisiblebench.scoring.contract import is_gate_result as _is_gate_result  # noqa: E402
from invisiblebench.utils.artifact_validation import (  # noqa: E402
    artifact_issue_policy,
    observed_prompt_hashes,
    scan_artifact_validation_diagnostics,
    scan_artifact_validation_summary,
    scan_check_coverage,
    scan_current_contract_validation_diagnostics,
    scan_current_contract_validation_summary,
)
from invisiblebench.utils.benchmark_inventory import (  # noqa: E402
    collect_public_scenario_ids,
    get_benchmark_version,
)
from invisiblebench.utils.io import artifact_reference  # noqa: E402
from invisiblebench.utils.io import load_json as _load_json  # noqa: E402
from invisiblebench.utils.io import load_jsonl as _load_jsonl  # noqa: E402
from invisiblebench.utils.manifest import scenario_corpus_hash  # noqa: E402
from invisiblebench.version import SCANNED_ROW_CONTRACT_VERSION  # noqa: E402

# Statuses allowed to carry a published hard-fail claim. Binary claim model:
# only `claim_ready` publishes; everything else is disclosed development evidence.
CALIBRATED_STATUSES = {CLAIM_READY_STATUS}
# Resolved = the verdict classes mode_engine counts toward coverage. Eligible
# NOT_APPLICABLE means the verifier found no current cue/obligation for this
# check; it is resolved coverage, while UNCLEAR remains unresolved.
RESOLVED_VERDICTS = PASS_VERDICT_VALUES | FAILURE_VERDICT_VALUES | {Verdict.NOT_APPLICABLE.value}


def calibration_errors(
    rows: list[dict[str, Any]],
    modes: dict[str, dict[str, Any]],
) -> list[str]:
    """Calibration gate: uncalibrated checks cannot carry hard-fail claims.

    Two boundaries, both unconditional:
    - every claim-carrying check (hard_fail or S5/S4_GATE severity) must
      declare a `calibration:` block with an evidence status;
    - every published hard_fail_reason must come from a check whose declared
      status is `claim_ready`.
    """
    errors: list[str] = []
    claim_checks = {
        check_id
        for check_id, mode in modes.items()
        if is_claim_capable_check(mode)
    }
    missing = sorted(
        check_id
        for check_id in claim_checks
        if not (modes[check_id].get("calibration") or {}).get("status")
    )
    if missing:
        errors.append(f"claim_check_missing_calibration={missing}")

    uncalibrated: Counter[str] = Counter()
    for row in rows:
        for reason in row.get("hard_fail_reasons") or []:
            mode_id = str(reason.get("mode_id"))
            calibration = (modes.get(mode_id) or {}).get("calibration") or {}
            if calibration.get("status") not in CALIBRATED_STATUSES:
                uncalibrated[mode_id] += 1
    if uncalibrated:
        errors.append(f"hard_fail_from_uncalibrated_check={dict(uncalibrated)}")
    return errors


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


def _validate_safety_care_artifact(
    leaderboard: dict[str, Any],
    effective_models: int,
    effective_scenarios: int | None,
    scan_path: Path,
) -> list[str]:
    """Validate the safety-care/v1 artifact shape. Returns a list of error strings."""
    errors: list[str] = []

    # Schema version
    schema = leaderboard.get("schema")
    if schema != "safety-care/v1":
        errors.append(f"schema={schema!r} expected='safety-care/v1'")

    # No composite at top level
    for forbidden in (
        "overall_score",
        "composite",
        "rank",
        "overall_leaderboard",
        "_deprecated_v3",
    ):
        if forbidden in leaderboard:
            errors.append(f"forbidden_top_level_key={forbidden!r}")

    # notes.no_composite must be True
    notes = leaderboard.get("notes") or {}
    if not notes.get("no_composite"):
        errors.append("notes.no_composite missing or False")

    # scan_metadata: source_artifact must match scan_path
    scan_meta = leaderboard.get("scan_metadata") or {}
    expected_source_artifact = artifact_reference(scan_path, REPO_ROOT)
    if scan_meta.get("source_artifact") != expected_source_artifact:
        errors.append(
            "leaderboard_source_mismatch="
            f"{scan_meta.get('source_artifact')!r} expected={expected_source_artifact!r}"
        )
    if scan_meta.get("total_models") != effective_models:
        errors.append(
            f"leaderboard_total_models={scan_meta.get('total_models')} "
            f"expected={effective_models}"
        )
    if effective_scenarios is not None and scan_meta.get("total_scenarios") != effective_scenarios:
        errors.append(
            f"leaderboard_total_scenarios={scan_meta.get('total_scenarios')} "
            f"expected={effective_scenarios}"
        )
    if not isinstance(scan_meta.get("artifact_validation"), dict):
        errors.append("scan_metadata.artifact_validation missing or not an object")
    if not isinstance(scan_meta.get("artifact_diagnostics"), dict):
        errors.append("scan_metadata.artifact_diagnostics missing or not an object")
    if not isinstance(scan_meta.get("check_coverage"), dict):
        errors.append("scan_metadata.check_coverage missing or not an object")
    # Presence is required unconditionally: without this the current-contract
    # strict gate (missing scenarios / check instances) is only run when the
    # block happens to be present, so an artifact that omits it silently
    # bypasses strict QA. Parallel to artifact_validation/artifact_diagnostics.
    if not isinstance(scan_meta.get("current_contract_validation"), dict):
        errors.append("scan_metadata.current_contract_validation missing or not an object")
    if scan_meta.get("artifact_issue_policy") != artifact_issue_policy():
        errors.append("scan_metadata.artifact_issue_policy missing or mismatch")

    # Per-model entries: safety lines + care qualities + no composite
    models = leaderboard.get("models")
    if not isinstance(models, list):
        errors.append("leaderboard_missing_models_list")
        return errors

    _SAFETY_LINES = ("crisis", "scope", "identity", "autonomy")
    _CARE_QUALITIES = ("belonging", "attunement", "relational", "advocacy", "trauma_awareness")

    for entry in models:
        name = entry.get("model", "<unnamed>")

        # No composite keys in model entry
        for forbidden in ("overall_score", "composite", "rank"):
            if forbidden in entry:
                errors.append(f"forbidden_model_key={forbidden!r} model={name!r}")

        # Safety lines
        safety = entry.get("safety") or {}
        lines = safety.get("lines") or {}
        for dim in _SAFETY_LINES:
            if dim not in lines:
                errors.append(f"missing_safety_line={dim!r} model={name!r}")
            else:
                line_entry = lines[dim]
                if "rate" not in line_entry:
                    errors.append(f"safety_line_missing_rate dim={dim!r} model={name!r}")
                if "n" not in line_entry:
                    errors.append(f"safety_line_missing_n dim={dim!r} model={name!r}")
                if "ci95" not in line_entry:
                    errors.append(f"safety_line_missing_ci95 dim={dim!r} model={name!r}")

        # Care qualities
        care = entry.get("care") or {}
        qualities = care.get("qualities") or {}
        for quality in _CARE_QUALITIES:
            if quality not in qualities:
                errors.append(f"missing_care_quality={quality!r} model={name!r}")
            else:
                q_entry = qualities[quality]
                # trauma_awareness is a stub — only n and status required
                if quality == "trauma_awareness":
                    if q_entry.get("n") != 0:
                        errors.append(
                            f"trauma_awareness_stub_n_nonzero n={q_entry.get('n')} model={name!r}"
                        )
                else:
                    if "calibration_status" not in q_entry:
                        errors.append(
                            f"care_quality_missing_calibration_status "
                            f"quality={quality!r} model={name!r}"
                        )

    return errors


def _validate_artifact_validation_metadata(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    artifact_validation = (leaderboard.get("scan_metadata") or {}).get("artifact_validation")
    if not isinstance(artifact_validation, dict):
        return errors

    expected = scan_artifact_validation_summary(rows)
    for field, expected_value in expected.items():
        actual = artifact_validation.get(field)
        if actual != expected_value:
            errors.append(f"artifact_validation.{field}={actual} expected={expected_value}")
    return errors


def _validate_artifact_diagnostics_metadata(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    diagnostics = (leaderboard.get("scan_metadata") or {}).get("artifact_diagnostics")
    if not isinstance(diagnostics, dict):
        return errors

    expected = scan_artifact_validation_diagnostics(rows)
    for field, expected_value in expected.items():
        actual = diagnostics.get(field)
        if actual != expected_value:
            errors.append(f"artifact_diagnostics.{field} mismatch")
    return errors


def _validate_check_coverage_metadata(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[str]:
    coverage = (leaderboard.get("scan_metadata") or {}).get("check_coverage")
    if not isinstance(coverage, dict):
        return []
    if coverage != scan_check_coverage(rows):
        return ["scan_metadata.check_coverage mismatch"]
    return []


def _active_mode_ids(checks_dir: Path | None = None) -> list[str]:
    modes, routing = load_checks(checks_dir)
    return sorted(
        mode_id
        for mode_id, mode in modes.items()
        if mode.get("status", "active") == "active" and routing.get(mode_id)
    )


def _validate_current_contract_metadata(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    checks_dir: Path | None,
) -> list[str]:
    errors: list[str] = []
    scan_meta = leaderboard.get("scan_metadata") or {}
    validation = scan_meta.get("current_contract_validation")
    diagnostics = scan_meta.get("current_contract_diagnostics")

    if validation is None and diagnostics is None:
        return errors
    if not isinstance(validation, dict):
        errors.append("scan_metadata.current_contract_validation missing or not an object")
        return errors
    if not isinstance(diagnostics, dict):
        errors.append("scan_metadata.current_contract_diagnostics missing or not an object")
        return errors

    expected_scenario_ids = collect_public_scenario_ids(REPO_ROOT)
    expected_check_ids = _active_mode_ids(checks_dir)
    expected_validation = scan_current_contract_validation_summary(
        rows,
        expected_scenario_ids=expected_scenario_ids,
        expected_check_ids=expected_check_ids,
    )
    for field, expected_value in expected_validation.items():
        actual = validation.get(field)
        if actual != expected_value:
            errors.append(f"current_contract_validation.{field}={actual} expected={expected_value}")

    expected_diagnostics = scan_current_contract_validation_diagnostics(
        rows,
        expected_scenario_ids=expected_scenario_ids,
        expected_check_ids=expected_check_ids,
    )
    for field, expected_value in expected_diagnostics.items():
        actual = diagnostics.get(field)
        if actual != expected_value:
            errors.append(f"current_contract_diagnostics.{field} mismatch")
    return errors


def _strict_current_contract_errors(validation: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in (
        "missing_scenarios",
        "extra_scenarios",
        "rows_with_missing_checks",
        "missing_check_instances",
        "rows_with_extra_checks",
        "extra_check_instances",
    ):
        value = validation.get(field)
        if value:
            errors.append(f"current_contract_{field}={value}")
    return errors


def _strict_provenance_errors(
    leaderboard: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    scan_path: Path,
    checks_dir: Path | None,
) -> list[str]:
    metadata = leaderboard.get("scan_metadata") or {}
    errors: list[str] = []
    expected_version = get_benchmark_version(REPO_ROOT)
    actual_version = metadata.get("benchmark_version")
    if actual_version != expected_version:
        errors.append(
            f"benchmark_version={actual_version!r} expected={expected_version!r}"
        )

    source_merge = metadata.get("source_merge")
    if not isinstance(source_merge, dict):
        errors.append("source_merge missing or not an object")
    else:
        expected_merge = {
            "schema": "invisiblebench-scan-merge/v2",
            "benchmark_version": expected_version,
            "result_contract_version": SCANNED_ROW_CONTRACT_VERSION,
            "provenance_complete": True,
            "profile": "publish",
            "row_count": len(rows),
            "output_file": scan_path.name,
            "output_sha256": hashlib.sha256(scan_path.read_bytes()).hexdigest(),
            "scenario_corpus_sha256": scenario_corpus_hash(REPO_ROOT),
            "scoring_config_sha256": hashlib.sha256(
                (REPO_ROOT / "benchmark" / "configs" / "scoring.yaml").read_bytes()
            ).hexdigest(),
        }
        for field, expected in expected_merge.items():
            if source_merge.get(field) != expected:
                errors.append(f"source_merge.{field} mismatch")
        fingerprint = source_merge.get("comparability_fingerprint")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            errors.append("source_merge.comparability_fingerprint missing or invalid")
        expected_definitions = check_definition_hashes(checks_dir)
        if source_merge.get("check_definition_hashes") != expected_definitions:
            errors.append("source_merge.check_definition_hashes missing or mismatch")
        sources = source_merge.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append("source_merge.sources missing or empty")
        elif any(
            not isinstance(source, dict)
            or not isinstance(source.get("scan_plan_sha256"), str)
            or len(source["scan_plan_sha256"]) != 64
            for source in sources
        ):
            errors.append("source_merge.sources scan plan hashes missing or invalid")
    if {row.get("contract_version") for row in rows} != {
        SCANNED_ROW_CONTRACT_VERSION
    }:
        errors.append("scan row contract mismatch")

    expected_hashes = check_prompt_hashes(checks_dir)
    if metadata.get("check_prompt_hashes") != expected_hashes:
        errors.append("check_prompt_hashes missing or mismatch")

    observed = observed_prompt_hashes(rows)
    if metadata.get("observed_prompt_hashes") != observed:
        errors.append("observed_prompt_hashes missing or mismatch")
    missing = [
        (
            row.get("model_id") or row.get("model"),
            row.get("scenario_id"),
            result.get("mode_id"),
        )
        for row in rows
        for result in row.get("mode_results") or []
        if result.get("eligible")
        and result.get("scorer_type") == "llm_verifier"
        and result.get("mode_id") in expected_hashes
        and not result.get("prompt_hash")
    ]
    if missing:
        errors.append(f"llm_results_missing_prompt_hash={missing[:10]}")
    mismatches = {
        mode_id: hashes
        for mode_id, hashes in observed.items()
        if mode_id in expected_hashes and hashes != [expected_hashes[mode_id]]
    }
    if mismatches:
        errors.append(f"observed_prompt_hash_mismatch={mismatches}")
    return errors


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
    checks_dir: Path | None = None,
) -> list[str]:
    """Return QA errors. Empty list means the artifact passes.

    Validates TWO things:
    1. Scan JSONL quality (coverage, UNCLEAR, evidence, calibration) — unchanged.
    2. Leaderboard artifact shape — now safety-care/v1 (no composite/rank/overall_score).
    """
    errors: list[str] = []
    rows = _load_jsonl(scan_path)
    leaderboard = _load_json(leaderboard_path)

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

    # Validate safety-care/v1 artifact shape
    errors.extend(
        _validate_safety_care_artifact(leaderboard, effective_models, effective_scenarios, scan_path)
    )
    errors.extend(_validate_artifact_validation_metadata(leaderboard, rows))
    errors.extend(_validate_artifact_diagnostics_metadata(leaderboard, rows))
    errors.extend(_validate_check_coverage_metadata(leaderboard, rows))
    errors.extend(_validate_current_contract_metadata(leaderboard, rows, checks_dir=checks_dir))
    current_contract_validation = (leaderboard.get("scan_metadata") or {}).get(
        "current_contract_validation"
    )
    if strict and isinstance(current_contract_validation, dict):
        errors.extend(_strict_current_contract_errors(current_contract_validation))
    if strict:
        errors.extend(
            _strict_provenance_errors(
                leaderboard,
                rows,
                scan_path=scan_path,
                checks_dir=checks_dir,
            )
        )

    prompt_missing = 0
    no_verifier = 0
    fatal_errors = 0
    fail_without_evidence = 0
    gate_unclear: Counter[str] = Counter()
    all_unclear: Counter[str] = Counter()
    manual_without_evidence = 0
    floor = coverage_floor()
    coverage_below_floor: dict[tuple[str, str], float] = {}
    coverage_rate_stale = 0

    for row in rows:
        row_eligible = 0
        row_resolved = 0

        for result in row.get("mode_results") or []:
            mode_id = str(result.get("mode_id"))
            rationale = str(result.get("rationale_code") or "")
            eligible = bool(result.get("eligible"))
            verdict = result.get("verdict")
            evidence = result.get("evidence") or []

            if eligible:
                row_eligible += 1
                if verdict in RESOLVED_VERDICTS:
                    row_resolved += 1
            if eligible and rationale in {"prompt_missing", "missing_verifier_prompt"}:
                prompt_missing += 1
            if rationale == "no_verifier_available" or rationale.startswith("prompt_file_missing:"):
                no_verifier += 1
            if rationale.startswith("verifier_exception"):
                fatal_errors += 1
            if eligible and verdict == Verdict.FAIL.value and not evidence:
                fail_without_evidence += 1
            if eligible and verdict == Verdict.UNCLEAR.value:
                all_unclear[mode_id] += 1
                if _is_gate_result(result):
                    gate_unclear[mode_id] += 1
            if (
                result.get("scorer_type") == "manual_adjudication"
                and not evidence
                and verdict != Verdict.NOT_APPLICABLE.value
            ):
                manual_without_evidence += 1

        # Coverage floor: recomputed from mode_results so a merge that changed
        # verdicts without restamping coverage_rate cannot slip an
        # under-covered row past the gate. A missing stamp is tolerated (the
        # recompute is authoritative); a present-but-wrong stamp means the
        # artifact disagrees with itself.
        row_coverage = row_resolved / row_eligible if row_eligible else 0.0
        stamped = row.get("coverage_rate")
        if stamped is not None and abs(float(stamped) - row_coverage) > 1e-9:
            coverage_rate_stale += 1
        if row_coverage < floor:
            key = (str(row.get("model")), str(row.get("scenario_id")))
            coverage_below_floor[key] = round(row_coverage, 4)

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
    if coverage_rate_stale:
        errors.append(f"coverage_rate_stale={coverage_rate_stale}")
    if coverage_below_floor:
        sample = dict(sorted(coverage_below_floor.items())[:10])
        errors.append(
            f"coverage_below_floor(floor={floor})="
            f"count={len(coverage_below_floor)} sample={sample}"
        )

    modes, _routing = load_checks(checks_dir)
    errors.extend(calibration_errors(rows, modes))

    manual_scan = _manual_scan_records(rows)
    if manual_adjudications_path is not None:
        if not manual_adjudications_path.exists():
            errors.append(f"manual_adjudications_file_missing={manual_adjudications_path}")
            return errors
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
            if (
                not file_record.get("evidence")
                and file_record.get("final_verdict") != Verdict.NOT_APPLICABLE.value
            ):
                errors.append(f"manual_adjudication_without_evidence key={key}")
    elif manual_scan and strict:
        errors.append(f"manual_adjudications_file_required count={len(manual_scan)}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="QA scan + safety-care/v1 leaderboard artifact")
    parser.add_argument("--scan", required=True, type=Path, help="per_run.jsonl scan artifact")
    parser.add_argument("--leaderboard", required=True, type=Path, help="Generated leaderboard.json (safety-care/v1)")
    parser.add_argument("--manual-adjudications", type=Path, default=None)
    parser.add_argument("--expected-rows", type=int, default=None)
    parser.add_argument("--expected-models", type=int, default=None)
    parser.add_argument("--expected-scenarios", type=int, default=None)
    parser.add_argument(
        "--expected-contract", default=None,
        help="Retired compatibility option; ignored in safety-care/v1 validation",
    )
    parser.add_argument(
        "--expected-stage", default=None,
        help="Retired compatibility option; ignored in safety-care/v1 validation",
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
        print("Leaderboard QA failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Leaderboard QA passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
