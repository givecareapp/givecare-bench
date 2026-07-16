"""Scan artifact validation counters and diagnostics shared by generation and QA."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from invisiblebench.evaluation.verifiers.base import FAILURE_VERDICT_VALUES, Verdict
from invisiblebench.scoring.contract import is_gate_result as _is_gate_result

_ARTIFACT_ISSUE_POLICY: dict[str, dict[str, Any]] = {
    "eligible_not_applicable_mode_verdicts": {
        "classification": "resolved_coverage",
        "strict_blocker": False,
        "meaning": "Eligible check found no current cue or obligation; counts as resolved coverage.",
    },
    "gate_eligible_not_applicable_mode_verdicts": {
        "classification": "resolved_coverage_raw_gate",
        "strict_blocker": False,
        "meaning": (
            "Safety gate check found no current cue or obligation; classified separately "
            "for audit but still resolved coverage."
        ),
    },
    "unclear_mode_verdicts": {
        "classification": "unresolved_coverage",
        "strict_blocker": True,
        "meaning": "Literal UNCLEAR verdicts require adjudication or regeneration before strict QA.",
    },
    "gate_unclear_mode_verdicts": {
        "classification": "unresolved_gate_coverage",
        "strict_blocker": True,
        "meaning": "Safety gate UNCLEAR verdicts are always publish blockers.",
    },
    "scorer_parse_errors": {
        "classification": "diagnostic_retry_artifact",
        "strict_blocker": False,
        "meaning": (
            "Verifier parse failures from retry attempts; final PASS/FAIL/NOT_APPLICABLE/UNCLEAR "
            "verdict remains authoritative."
        ),
    },
    "scorer_raw_outputs_truncated_samples": {
        "classification": "diagnostic_retry_artifact",
        "strict_blocker": False,
        "meaning": (
            "Bounded raw-output samples from failed verifier parse attempts were truncated for "
            "artifact hygiene; final verdict remains authoritative."
        ),
    },
}


def artifact_issue_policy() -> dict[str, dict[str, Any]]:
    """Return the Safety/Care artifact issue classification policy."""
    return deepcopy(_ARTIFACT_ISSUE_POLICY)


def observed_prompt_hashes(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Collect the distinct verifier-template hashes actually present in scan rows."""
    hashes: dict[str, set[str]] = {}
    for row in rows:
        for result in row.get("mode_results") or []:
            mode_id = result.get("mode_id")
            prompt_hash = result.get("prompt_hash")
            if mode_id and prompt_hash:
                hashes.setdefault(str(mode_id), set()).add(str(prompt_hash))
    return {mode_id: sorted(values) for mode_id, values in sorted(hashes.items())}


def scan_check_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return per-model, per-check coverage without deriving a score or rank."""
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        model = str(row.get("model") or "")
        model_id = str(row.get("model_id") or model)
        for result in row.get("mode_results") or []:
            check_id = str(result.get("mode_id") or "")
            if not check_id:
                continue
            key = (model, model_id, check_id)
            record = records.setdefault(
                key,
                {
                    "model": model,
                    "model_id": model_id,
                    "check_id": check_id,
                    "total": 0,
                    "eligible": 0,
                    "ineligible": 0,
                    "pass": 0,
                    "fail": 0,
                    "not_applicable": 0,
                    "unclear": 0,
                    "scorer_errors": 0,
                    "retry_parse_errors": 0,
                },
            )
            record["total"] += 1
            record["eligible" if result.get("eligible") else "ineligible"] += 1
            verdict_key = {
                Verdict.PASS.value: "pass",
                Verdict.FAIL.value: "fail",
                Verdict.NOT_APPLICABLE.value: "not_applicable",
                Verdict.UNCLEAR.value: "unclear",
            }.get(result.get("verdict"))
            if verdict_key:
                record[verdict_key] += 1

            rationale = str(result.get("rationale_code") or "")
            if (
                rationale in {
                    "prompt_missing",
                    "missing_verifier_prompt",
                    "no_verifier_available",
                }
                or rationale.startswith("prompt_file_missing:")
                or rationale.startswith("verifier_exception")
            ):
                record["scorer_errors"] += 1
            extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
            record["retry_parse_errors"] += _list_len(extra.get("parse_errors"))

    return {
        "schema": "invisiblebench-check-coverage/v1",
        "records": [records[key] for key in sorted(records)],
    }


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else int(bool(value))


def _diagnostic_record(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "model": row.get("model"),
        "model_id": row.get("model_id"),
        "scenario_id": row.get("scenario_id"),
        "check_id": result.get("mode_id"),
        "verdict": result.get("verdict"),
        "eligible": bool(result.get("eligible")),
    }
    for key in ("severity", "rationale_code", "scorer_type", "scorer_version", "confidence"):
        value = result.get(key)
        if value is not None:
            record[key] = value
    return record


def _append_bounded(
    samples: dict[str, list[dict[str, Any]]],
    key: str,
    record: dict[str, Any],
    limit: int,
) -> None:
    if len(samples[key]) < limit:
        samples[key].append(record)


def scan_artifact_validation_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Summarize scan-row hygiene fields that must stay visible in artifacts.

    ``raw_outputs_truncated`` stores bounded diagnostic samples from verifier
    parse-error attempts. These counters classify scorer-output parse/truncation
    evidence without changing final PASS/FAIL/UNCLEAR semantics.
    """
    totals = {
        "rows": len(rows),
        "manual_adjudications": 0,
        "eligible_not_applicable_mode_verdicts": 0,
        "gate_eligible_not_applicable_mode_verdicts": 0,
        "unclear_mode_verdicts": 0,
        "gate_unclear_mode_verdicts": 0,
        "fail_without_evidence": 0,
        "prompt_missing": 0,
        "no_verifier_available": 0,
        "fatal_verifier_errors": 0,
        "scorer_parse_error_results": 0,
        "scorer_parse_errors": 0,
        "scorer_raw_outputs_truncated_results": 0,
        "scorer_raw_outputs_truncated_samples": 0,
    }
    for row in rows:
        for result in row.get("mode_results") or []:
            eligible = bool(result.get("eligible"))
            verdict = result.get("verdict")
            rationale = str(result.get("rationale_code") or "")
            extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
            parse_errors = extra.get("parse_errors") if isinstance(extra, dict) else None
            raw_outputs = extra.get("raw_outputs_truncated") if isinstance(extra, dict) else None

            if result.get("scorer_type") == "manual_adjudication":
                totals["manual_adjudications"] += 1
            if eligible and verdict == Verdict.NOT_APPLICABLE.value:
                totals["eligible_not_applicable_mode_verdicts"] += 1
                if _is_gate_result(result):
                    totals["gate_eligible_not_applicable_mode_verdicts"] += 1
            if eligible and verdict == Verdict.UNCLEAR.value:
                totals["unclear_mode_verdicts"] += 1
                if _is_gate_result(result):
                    totals["gate_unclear_mode_verdicts"] += 1
            if eligible and verdict in FAILURE_VERDICT_VALUES and not result.get("evidence"):
                totals["fail_without_evidence"] += 1
            if eligible and rationale in {"prompt_missing", "missing_verifier_prompt"}:
                totals["prompt_missing"] += 1
            if rationale == "no_verifier_available" or rationale.startswith("prompt_file_missing:"):
                totals["no_verifier_available"] += 1
            if rationale.startswith("verifier_exception"):
                totals["fatal_verifier_errors"] += 1
            if parse_errors:
                totals["scorer_parse_error_results"] += 1
                totals["scorer_parse_errors"] += _list_len(parse_errors)
            if raw_outputs:
                totals["scorer_raw_outputs_truncated_results"] += 1
                totals["scorer_raw_outputs_truncated_samples"] += _list_len(raw_outputs)

    return totals


def scan_artifact_validation_diagnostics(
    rows: list[dict[str, Any]],
    *,
    limit_per_issue: int = 25,
) -> dict[str, Any]:
    """Return bounded row/check samples behind artifact-validation counters.

    Diagnostics intentionally omit evidence quotes and raw verifier output. The
    counters in ``artifact_validation`` remain authoritative for totals; this
    payload makes non-publishable residue traceable without forcing maintainers
    to search the full scan JSONL.
    """
    diagnostics: dict[str, Any] = {
        "limit_per_issue": limit_per_issue,
        "unclear_mode_verdicts": [],
        "eligible_not_applicable_mode_verdicts": [],
        "gate_eligible_not_applicable_mode_verdicts": [],
        "scorer_parse_error_results": [],
        "scorer_raw_outputs_truncated_results": [],
    }
    samples: dict[str, list[dict[str, Any]]] = {
        key: diagnostics[key]
        for key in (
            "unclear_mode_verdicts",
            "eligible_not_applicable_mode_verdicts",
            "gate_eligible_not_applicable_mode_verdicts",
            "scorer_parse_error_results",
            "scorer_raw_outputs_truncated_results",
        )
    }

    for row in rows:
        for result in row.get("mode_results") or []:
            eligible = bool(result.get("eligible"))
            verdict = result.get("verdict")
            extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
            parse_errors = extra.get("parse_errors") if isinstance(extra, dict) else None
            raw_outputs = extra.get("raw_outputs_truncated") if isinstance(extra, dict) else None
            record = _diagnostic_record(row, result)

            if eligible and verdict == Verdict.UNCLEAR.value:
                _append_bounded(samples, "unclear_mode_verdicts", record, limit_per_issue)
            if eligible and verdict == Verdict.NOT_APPLICABLE.value:
                _append_bounded(
                    samples,
                    "eligible_not_applicable_mode_verdicts",
                    record,
                    limit_per_issue,
                )
                if _is_gate_result(result):
                    _append_bounded(
                        samples,
                        "gate_eligible_not_applicable_mode_verdicts",
                        record,
                        limit_per_issue,
                    )
            if parse_errors:
                parse_record = {**record, "parse_error_count": _list_len(parse_errors)}
                _append_bounded(
                    samples,
                    "scorer_parse_error_results",
                    parse_record,
                    limit_per_issue,
                )
            if raw_outputs:
                truncated_record = {
                    **record,
                    "truncated_sample_count": _list_len(raw_outputs),
                }
                _append_bounded(
                    samples,
                    "scorer_raw_outputs_truncated_results",
                    truncated_record,
                    limit_per_issue,
                )

    return diagnostics


def _row_check_ids(row: dict[str, Any]) -> set[str]:
    return {
        str(result.get("mode_id"))
        for result in row.get("mode_results") or []
        if result.get("mode_id") is not None
    }


def scan_current_contract_validation_summary(
    rows: list[dict[str, Any]],
    *,
    expected_scenario_ids: list[str] | set[str],
    expected_check_ids: list[str] | set[str],
) -> dict[str, int]:
    """Summarize whether scan rows cover the current scenario/check contract."""
    expected_scenarios = {str(scenario_id) for scenario_id in expected_scenario_ids}
    expected_checks = {str(check_id) for check_id in expected_check_ids}
    observed_scenarios = {
        str(row.get("scenario_id"))
        for row in rows
        if row.get("scenario_id") is not None
    }

    row_check_counts = [len(_row_check_ids(row)) for row in rows]
    rows_with_missing_checks = 0
    rows_with_extra_checks = 0
    missing_check_instances = 0
    extra_check_instances = 0

    for row in rows:
        check_ids = _row_check_ids(row)
        missing_checks = expected_checks - check_ids
        extra_checks = check_ids - expected_checks
        if missing_checks:
            rows_with_missing_checks += 1
            missing_check_instances += len(missing_checks)
        if extra_checks:
            rows_with_extra_checks += 1
            extra_check_instances += len(extra_checks)

    return {
        "expected_scenarios": len(expected_scenarios),
        "observed_scenarios": len(observed_scenarios),
        "missing_scenarios": len(expected_scenarios - observed_scenarios),
        "extra_scenarios": len(observed_scenarios - expected_scenarios),
        "expected_checks": len(expected_checks),
        "min_checks_per_row": min(row_check_counts) if row_check_counts else 0,
        "max_checks_per_row": max(row_check_counts) if row_check_counts else 0,
        "rows_with_missing_checks": rows_with_missing_checks,
        "missing_check_instances": missing_check_instances,
        "rows_with_extra_checks": rows_with_extra_checks,
        "extra_check_instances": extra_check_instances,
    }


def scan_current_contract_validation_diagnostics(
    rows: list[dict[str, Any]],
    *,
    expected_scenario_ids: list[str] | set[str],
    expected_check_ids: list[str] | set[str],
    limit_per_issue: int = 25,
) -> dict[str, Any]:
    """Return bounded samples for current-contract coverage mismatches."""
    expected_scenarios = {str(scenario_id) for scenario_id in expected_scenario_ids}
    expected_checks = {str(check_id) for check_id in expected_check_ids}
    observed_scenarios = {
        str(row.get("scenario_id"))
        for row in rows
        if row.get("scenario_id") is not None
    }

    diagnostics: dict[str, Any] = {
        "limit_per_issue": limit_per_issue,
        "missing_scenarios": sorted(expected_scenarios - observed_scenarios)[:limit_per_issue],
        "extra_scenarios": sorted(observed_scenarios - expected_scenarios)[:limit_per_issue],
        "missing_checks": [],
        "extra_checks": [],
        "missing_checks_by_check": {},
        "extra_checks_by_check": {},
    }
    missing_by_check: dict[str, int] = {}
    extra_by_check: dict[str, int] = {}

    for row in rows:
        check_ids = _row_check_ids(row)
        missing_checks = sorted(expected_checks - check_ids)
        extra_checks = sorted(check_ids - expected_checks)
        base_record = {
            "model": row.get("model"),
            "model_id": row.get("model_id"),
            "scenario_id": row.get("scenario_id"),
        }
        if missing_checks:
            for check_id in missing_checks:
                missing_by_check[check_id] = missing_by_check.get(check_id, 0) + 1
            if len(diagnostics["missing_checks"]) < limit_per_issue:
                diagnostics["missing_checks"].append(
                    {**base_record, "missing_check_ids": missing_checks}
                )
        if extra_checks:
            for check_id in extra_checks:
                extra_by_check[check_id] = extra_by_check.get(check_id, 0) + 1
            if len(diagnostics["extra_checks"]) < limit_per_issue:
                diagnostics["extra_checks"].append(
                    {**base_record, "extra_check_ids": extra_checks}
                )

    diagnostics["missing_checks_by_check"] = dict(sorted(missing_by_check.items()))
    diagnostics["extra_checks_by_check"] = dict(sorted(extra_by_check.items()))
    return diagnostics
