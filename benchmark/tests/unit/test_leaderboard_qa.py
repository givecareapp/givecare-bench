"""Tests for the safety-care/v1 leaderboard QA gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.qa_leaderboard as qa_leaderboard
from invisiblebench.utils.artifact_validation import (
    artifact_issue_policy,
    scan_artifact_validation_diagnostics,
    scan_artifact_validation_summary,
    scan_current_contract_validation_diagnostics,
    scan_current_contract_validation_summary,
)
from scripts.qa_leaderboard import validate_leaderboard


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _scan_row(
    model: str,
    scenario_id: str,
    *,
    verdict: str = "PASS",
    layer: str = "safety",
    dimension: str = "crisis",
    scorer_type: str = "llm_verifier",
    evidence: list[dict] | None = None,
) -> dict:
    mode_id_by_dimension = {
        "crisis": "crisis.passive-ideation",
        "scope": "scope.diagnosis",
        "belonging": "belonging.self-diminishment",
        "advocacy": "advocacy.institution-allegiance",
    }
    severity = "S5" if layer == "safety" else "S2"
    return {
        "model": model,
        "model_id": model.lower(),
        "scenario_id": scenario_id,
        "overall_score": 1.0,
        "hard_fail": verdict == "FAIL" and layer == "safety" and severity in {"S5", "S4_GATE"},
        "mode_results": [
            {
                "mode_id": mode_id_by_dimension.get(dimension, f"{dimension}.test-check"),
                "eligible": True,
                "verdict": verdict,
                "severity": severity,
                "layer": layer,
                "dimension": dimension,
                "scorer_type": scorer_type,
                "confidence": 1.0,
                "evidence": evidence if evidence is not None else [
                    {"role": "assistant", "turn": 1, "quote": "safe response"}
                ],
                "rationale_code": "ok",
                "extra": {},
            }
        ],
    }


def _read_rows(source: Path) -> list[dict]:
    if not source.exists():
        return []
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line]


# The current-contract validation block is compared by QA against the repo's
# real scenario/check contract. So a fixture built from synthetic "s1" rows can
# report complete coverage, the autouse fixture below patches those two id
# sources to the ids the fixture actually emitted. Tests that exercise coverage
# gaps re-patch them directly.
_CONTRACT_IDS: dict[str, list[str]] = {"scenarios": [], "checks": []}


@pytest.fixture(autouse=True)
def _default_contract_ids(monkeypatch):
    _CONTRACT_IDS["scenarios"] = []
    _CONTRACT_IDS["checks"] = []
    monkeypatch.setattr(
        qa_leaderboard,
        "collect_public_scenario_ids",
        lambda _root: list(_CONTRACT_IDS["scenarios"]),
    )
    monkeypatch.setattr(
        qa_leaderboard,
        "_active_mode_ids",
        lambda checks_dir=None: list(_CONTRACT_IDS["checks"]),
    )
    monkeypatch.setattr(qa_leaderboard, "check_prompt_hashes", lambda checks_dir=None: {})
    monkeypatch.setattr(qa_leaderboard, "get_benchmark_version", lambda _root: "4.0.0")
    yield


def _leaderboard(source: Path, *, models: int = 1, scenarios: int = 1) -> dict:
    """Minimal safety-care/v1 leaderboard fixture."""
    rows = _read_rows(source)
    scenario_ids = sorted({str(row.get("scenario_id")) for row in rows if row.get("scenario_id")})
    check_ids = sorted(
        {
            str(result.get("mode_id"))
            for row in rows
            for result in row.get("mode_results") or []
            if result.get("mode_id")
        }
    )
    _CONTRACT_IDS["scenarios"] = scenario_ids
    _CONTRACT_IDS["checks"] = check_ids
    return {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True},
        "scan_metadata": {
            "benchmark_version": "4.0.0",
            "check_prompt_hashes": {},
            "observed_prompt_hashes": {},
            "source_artifact": str(source),
            "total_models": models,
            "total_scenarios": scenarios,
            "artifact_validation": scan_artifact_validation_summary(rows),
            "artifact_diagnostics": scan_artifact_validation_diagnostics(rows),
            "current_contract_validation": scan_current_contract_validation_summary(
                rows,
                expected_scenario_ids=scenario_ids,
                expected_check_ids=check_ids,
            ),
            "current_contract_diagnostics": scan_current_contract_validation_diagnostics(
                rows,
                expected_scenario_ids=scenario_ids,
                expected_check_ids=check_ids,
            ),
            "artifact_issue_policy": artifact_issue_policy(),
        },
        "models": [],
    }


def test_safety_care_qa_accepts_clean_strict_artifact(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    manual = tmp_path / "manual_adjudications.json"
    row = _scan_row("model-a", "s1")
    row["mode_results"][0].update(
        {
            "scorer_type": "manual_adjudication",
            "extra": {"previous_verdict": "UNCLEAR", "previous_rationale_code": "parse_failed"},
        }
    )
    _write_jsonl(scan, [row])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")
    manual.write_text(
        json.dumps(
            {
                "manual_adjudications": [
                    {
                        "model_id": "model-a",
                        "scenario_id": "s1",
                        "mode_id": "crisis.passive-ideation",
                        "previous_verdict": "UNCLEAR",
                        "final_verdict": "PASS",
                        "rationale_code": "ok",
                        "evidence": [{"role": "assistant", "turn": 1, "quote": "safe response"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    errors = validate_leaderboard(
        scan,
        leaderboard,
        manual_adjudications_path=manual,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert errors == []


def test_safety_care_qa_infers_current_scan_coverage(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    rows = [
        _scan_row("model-a", "s1"),
        _scan_row("model-a", "s2"),
        _scan_row("model-b", "s1"),
        _scan_row("model-b", "s2"),
    ]
    _write_jsonl(scan, rows)
    leaderboard.write_text(
        json.dumps(_leaderboard(scan, models=2, scenarios=2)),
        encoding="utf-8",
    )

    errors = validate_leaderboard(scan, leaderboard)

    assert errors == []


def test_safety_care_qa_inferred_coverage_rejects_stale_metadata(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    leaderboard.write_text(
        json.dumps(_leaderboard(scan, models=1, scenarios=50)),
        encoding="utf-8",
    )

    errors = validate_leaderboard(scan, leaderboard)

    assert any("leaderboard_total_scenarios" in error for error in errors)


def test_safety_care_qa_rejects_deprecated_v3_block(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    payload = _leaderboard(scan)
    payload["_deprecated_v3"] = {"overall_leaderboard": []}
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(scan, leaderboard)

    assert any("forbidden_top_level_key='_deprecated_v3'" in error for error in errors)


def test_safety_care_qa_rejects_gate_unclear(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1", verdict="UNCLEAR", dimension="crisis")])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
    )

    assert any("gate_unclear" in error for error in errors)


def test_safety_care_qa_strict_rejects_non_gate_unclear(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(
        scan,
        [_scan_row("model-a", "s1", verdict="UNCLEAR", layer="care", dimension="advocacy")],
    )
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert any("all_unclear" in error for error in errors)


def test_safety_care_qa_strict_requires_manual_audit_file(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    row = _scan_row("model-a", "s1")
    row["mode_results"][0].update(
        {
            "scorer_type": "manual_adjudication",
            "extra": {"previous_verdict": "UNCLEAR", "previous_rationale_code": "parse_failed"},
        }
    )
    _write_jsonl(scan, [row])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert any("manual_adjudications_file_required" in error for error in errors)


def test_safety_care_qa_reports_missing_manual_audit_file(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    missing_manual = tmp_path / "missing_manual_adjudications.json"
    row = _scan_row("model-a", "s1")
    row["mode_results"][0].update(
        {
            "scorer_type": "manual_adjudication",
            "extra": {"previous_verdict": "UNCLEAR", "previous_rationale_code": "parse_failed"},
        }
    )
    _write_jsonl(scan, [row])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        manual_adjudications_path=missing_manual,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert errors == [f"manual_adjudications_file_missing={missing_manual}"]


def test_safety_care_qa_rejects_fail_without_evidence(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1", verdict="FAIL", evidence=[])])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
    )

    assert any("fail_without_evidence" in error for error in errors)


def test_safety_care_qa_rejects_artifact_validation_mismatch(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    row = _scan_row("model-a", "s1")
    row["mode_results"].append(
        {
            "mode_id": "scope.diagnosis",
            "eligible": True,
            "verdict": "NOT_APPLICABLE",
            "severity": "S4",
            "layer": "safety",
            "dimension": "scope",
            "scorer_type": "llm_verifier",
            "confidence": 1.0,
            "evidence": [],
            "rationale_code": "no_diagnosis_made",
            "extra": {},
        }
    )
    row["mode_results"][0]["extra"] = {
        "parse_errors": ["ValueError: bad json"],
        "raw_outputs_truncated": ["not json"],
    }
    _write_jsonl(scan, [row])
    payload = _leaderboard(scan)
    payload["scan_metadata"]["artifact_validation"]["scorer_parse_errors"] = 0
    payload["scan_metadata"]["artifact_validation"]["eligible_not_applicable_mode_verdicts"] = 0
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(scan, leaderboard)

    assert "artifact_validation.scorer_parse_errors=0 expected=1" in errors
    assert "artifact_validation.eligible_not_applicable_mode_verdicts=0 expected=1" in errors


def test_safety_care_qa_classifies_retry_artifacts_as_non_blocking(
    tmp_path: Path,
) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    row = _scan_row("model-a", "s1")
    row["mode_results"][0]["extra"] = {
        "parse_errors": ["ValueError: bad json"],
        "raw_outputs_truncated": ["not json"],
    }
    _write_jsonl(scan, [row])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert errors == []


def test_safety_care_qa_strict_rejects_current_contract_gaps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    rows = _read_rows(scan)
    expected_scenario_ids = ["s1", "s2"]
    expected_check_ids = ["autonomy.coercion", "crisis.passive-ideation"]
    monkeypatch.setattr(
        qa_leaderboard,
        "collect_public_scenario_ids",
        lambda _root: expected_scenario_ids,
    )
    monkeypatch.setattr(
        qa_leaderboard,
        "_active_mode_ids",
        lambda checks_dir=None: expected_check_ids,
    )

    payload = _leaderboard(scan)
    payload["scan_metadata"]["current_contract_validation"] = (
        scan_current_contract_validation_summary(
            rows,
            expected_scenario_ids=expected_scenario_ids,
            expected_check_ids=expected_check_ids,
        )
    )
    payload["scan_metadata"]["current_contract_diagnostics"] = (
        scan_current_contract_validation_diagnostics(
            rows,
            expected_scenario_ids=expected_scenario_ids,
            expected_check_ids=expected_check_ids,
        )
    )
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    non_strict_errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
    )
    strict_errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert non_strict_errors == []
    assert "current_contract_missing_scenarios=1" in strict_errors
    assert "current_contract_rows_with_missing_checks=1" in strict_errors
    assert "current_contract_missing_check_instances=1" in strict_errors


def test_safety_care_qa_requires_current_contract_validation_block(tmp_path: Path) -> None:
    """Omitting the current-contract block must not silently bypass strict QA.

    Deleting both current_contract_* keys used to make the strict current-contract
    blockers (missing scenarios / check instances) disappear, because the gate
    only ran when the block was present. Presence is now required unconditionally.
    """
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    payload = _leaderboard(scan)
    del payload["scan_metadata"]["current_contract_validation"]
    del payload["scan_metadata"]["current_contract_diagnostics"]
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
        strict=True,
    )

    assert "scan_metadata.current_contract_validation missing or not an object" in errors


def test_safety_care_qa_rejects_missing_artifact_diagnostics(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    payload = _leaderboard(scan)
    del payload["scan_metadata"]["artifact_diagnostics"]
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(scan, leaderboard)

    assert "scan_metadata.artifact_diagnostics missing or not an object" in errors


def test_safety_care_qa_rejects_missing_artifact_issue_policy(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    payload = _leaderboard(scan)
    del payload["scan_metadata"]["artifact_issue_policy"]
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(scan, leaderboard)

    assert "scan_metadata.artifact_issue_policy missing or mismatch" in errors


def test_safety_care_qa_rejects_artifact_diagnostics_mismatch(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "safety_care_leaderboard.json"
    row = _scan_row("model-a", "s1", verdict="UNCLEAR", layer="care", dimension="advocacy")
    _write_jsonl(scan, [row])
    payload = _leaderboard(scan)
    payload["scan_metadata"]["artifact_diagnostics"]["unclear_mode_verdicts"] = []
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(scan, leaderboard)

    assert "artifact_diagnostics.unclear_mode_verdicts mismatch" in errors


def test_strict_qa_rejects_stale_benchmark_version(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    payload = _leaderboard(scan)
    payload["scan_metadata"]["benchmark_version"] = "3.1.0"
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")

    errors = validate_leaderboard(scan, leaderboard, strict=True)

    assert "benchmark_version='3.1.0' expected='4.0.0'" in errors


def test_strict_qa_rejects_stale_observed_prompt_hash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "leaderboard.json"
    row = _scan_row("model-a", "s1")
    row["mode_results"][0]["prompt_hash"] = "old-prompt-hash"
    _write_jsonl(scan, [row])
    payload = _leaderboard(scan)
    payload["scan_metadata"]["check_prompt_hashes"] = {
        "crisis.passive-ideation": "current-prompt-hash"
    }
    payload["scan_metadata"]["observed_prompt_hashes"] = {
        "crisis.passive-ideation": ["old-prompt-hash"]
    }
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        qa_leaderboard,
        "check_prompt_hashes",
        lambda checks_dir=None: {"crisis.passive-ideation": "current-prompt-hash"},
    )

    errors = validate_leaderboard(scan, leaderboard, strict=True)

    assert any("observed_prompt_hash_mismatch" in error for error in errors)


def test_strict_qa_rejects_llm_result_without_prompt_hash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    payload = _leaderboard(scan)
    payload["scan_metadata"]["check_prompt_hashes"] = {
        "crisis.passive-ideation": "current-prompt-hash"
    }
    leaderboard.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        qa_leaderboard,
        "check_prompt_hashes",
        lambda checks_dir=None: {"crisis.passive-ideation": "current-prompt-hash"},
    )

    errors = validate_leaderboard(scan, leaderboard, strict=True)

    assert any("llm_results_missing_prompt_hash" in error for error in errors)
