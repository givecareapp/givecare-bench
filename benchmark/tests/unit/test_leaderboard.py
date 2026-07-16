"""Contract tests for safety-care/v1 leaderboard generation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from invisiblebench.utils.artifact_validation import artifact_issue_policy
from scripts.generate_leaderboard import generate_leaderboard

_SAFETY_LINES = ("crisis", "scope", "identity", "autonomy")
_CARE_QUALITIES_V1 = ("belonging", "attunement", "relational", "advocacy")


def _row(model: str, scenario_id: str, *, score: float, hard_fail: bool = False) -> dict:
    return {
        "model": model,
        "model_id": model.lower().replace(" ", "/"),
        "scenario_id": scenario_id,
        "contract_version": "3.2.0",
        "overall_score": score,
        "hard_fail": hard_fail,
        "dimension_scores": {
            "communication_quality": score,
            "caregiver_coordination": score,
            "boundary_integrity": score,
        },
        "blindspot_profile": {"false_body_presence_claim": hard_fail},
        "mode_results": [
            {
                "mode_id": "crisis.passive-ideation",
                "eligible": True,
                "verdict": "FAIL" if hard_fail else "PASS",
                "layer": "safety",
                "dimension": "crisis",
                "severity": "S5",
            },
            {
                "mode_id": "belonging.self-diminishment",
                "eligible": True,
                "verdict": "PASS",
                "layer": "care",
                "dimension": "belonging",
                "severity": "S2",
            },
        ],
    }


def test_generate_leaderboard_emits_safety_care_schema(tmp_path: Path) -> None:
    """Top-level artifact must carry schema=safety-care/v1 with no composite keys."""
    input_path = tmp_path / "per_run.jsonl"
    input_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                _row("model-a", "s1", score=0.8),
                _row("model-b", "s1", score=0.9),
            ]
        )
        + "\n"
    )

    out_path = generate_leaderboard(input_path, tmp_path / "out", expected_scenarios=1)
    payload = json.loads(out_path.read_text())

    # Top-level schema
    assert payload["schema"] == "safety-care/v1"
    assert payload["notes"]["no_composite"] is True

    # No composite at top level
    assert "overall_score" not in payload
    assert "rank" not in payload
    assert "overall_leaderboard" not in payload
    assert "_deprecated_v3" not in payload

    # models list present
    assert isinstance(payload["models"], list)
    assert len(payload["models"]) == 2


def test_generate_leaderboard_model_entries_have_safety_and_care(tmp_path: Path) -> None:
    """Each model entry must have safety.lines (4 dims) and care.qualities."""
    input_path = tmp_path / "per_run.jsonl"
    input_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                _row("model-a", "s1", score=0.8),
                _row("model-a", "s2", score=0.9),
            ]
        )
        + "\n"
    )

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())
    model_entry = payload["models"][0]

    # No composite in model entry
    assert "overall_score" not in model_entry
    assert "rank" not in model_entry
    assert "composite" not in model_entry

    # Safety lines present
    safety = model_entry["safety"]
    for dim in _SAFETY_LINES:
        assert dim in safety["lines"], f"Missing safety line: {dim}"

    # Care qualities present
    care = model_entry["care"]
    for quality in _CARE_QUALITIES_V1:
        assert quality in care["qualities"], f"Missing care quality: {quality}"
    assert "trauma_awareness" in care["qualities"]


def test_generate_leaderboard_scan_metadata_present(tmp_path: Path) -> None:
    """scan_metadata must carry total_models, total_scenarios, source_artifact."""
    input_path = tmp_path / "per_run.jsonl"
    input_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                _row("model-a", "s1", score=0.8),
                _row("model-a", "s2", score=0.8),
                _row("model-b", "s1", score=0.9),
                _row("model-b", "s2", score=0.9),
            ]
        )
        + "\n"
    )

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())

    meta = payload["scan_metadata"]
    assert meta["total_models"] == 2
    assert meta["total_scenarios"] == 2
    assert meta["source_artifact"] == input_path.name
    assert meta["artifact_validation"]["rows"] == 4
    assert meta["check_coverage"]["schema"] == "invisiblebench-check-coverage/v1"
    assert len(meta["check_prompt_hashes"]) == 46
    assert meta["observed_prompt_hashes"] == {}


def test_generate_leaderboard_reports_per_check_coverage(tmp_path: Path) -> None:
    input_path = tmp_path / "per_run.jsonl"
    pass_row = _row("model-a", "s1", score=0.8)
    unclear_row = _row("model-a", "s2", score=0.8)
    unclear_row["mode_results"][0].update(
        {
            "verdict": "UNCLEAR",
            "rationale_code": "verifier_exception: timeout",
            "extra": {"parse_errors": ["bad json"]},
        }
    )
    input_path.write_text(
        "".join(json.dumps(row) + "\n" for row in (pass_row, unclear_row))
    )

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    records = json.loads(out_path.read_text())["scan_metadata"]["check_coverage"][
        "records"
    ]
    crisis = next(record for record in records if record["check_id"] == "crisis.passive-ideation")

    assert crisis == {
        "model": "model-a",
        "model_id": "model-a",
        "check_id": "crisis.passive-ideation",
        "total": 2,
        "eligible": 2,
        "ineligible": 0,
        "pass": 1,
        "fail": 0,
        "not_applicable": 0,
        "unclear": 1,
        "scorer_errors": 1,
        "retry_parse_errors": 1,
    }


def test_generate_leaderboard_embeds_validated_merge_lineage(tmp_path: Path) -> None:
    input_path = tmp_path / "per_run.jsonl"
    input_path.write_text(json.dumps(_row("model-a", "s1", score=0.8)) + "\n")
    scan_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    merge_manifest = {
        "schema": "invisiblebench-scan-merge/v2",
        "benchmark_version": "4.0.0",
        "result_contract_version": "3.2.0",
        "provenance_complete": True,
        "comparability_fingerprint": "f" * 64,
        "scenario_corpus_sha256": "e" * 64,
        "scoring_config_sha256": "9" * 64,
        "check_definition_hashes": {"check.one": "d" * 64},
        "profile": "publish",
        "judge_model": "openai/gpt-5-mini",
        "model_count": 1,
        "scenario_count": 1,
        "row_count": 1,
        "actual_cost_usd": 1.25,
        "actual_billable_api_calls": 10,
        "output_file": "per_run.jsonl",
        "output_sha256": scan_sha,
        "sources": [
            {
                "artifact_id": "scan_a",
                "file": "per_run.jsonl",
                "sha256": "a" * 64,
                "scan_plan_sha256": "b" * 64,
                "row_count": 1,
                "model_ids": ["model-a"],
                "transcript_source_artifacts": ["run_a"],
                "actual_cost_usd": 1.25,
                "actual_billable_api_calls": 10,
            }
        ],
    }
    (tmp_path / "merge_manifest.json").write_text(json.dumps(merge_manifest))

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())

    assert payload["scan_metadata"]["source_merge"] == merge_manifest


def test_generate_leaderboard_rejects_inconsistent_merge_lineage(tmp_path: Path) -> None:
    input_path = tmp_path / "per_run.jsonl"
    input_path.write_text(json.dumps(_row("model-a", "s1", score=0.8)) + "\n")
    (tmp_path / "merge_manifest.json").write_text(
        json.dumps(
            {
                "schema": "invisiblebench-scan-merge/v1",
                "benchmark_version": "4.0.0",
                "result_contract_version": "2.1.0",
                "profile": "publish",
                "judge_model": "openai/gpt-5-mini",
                "model_count": 1,
                "scenario_count": 1,
                "row_count": 1,
                "actual_cost_usd": 1.25,
                "actual_billable_api_calls": 10,
                "output_file": input_path.name,
                "output_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                "sources": [
                    {
                        "artifact_id": "scan_a",
                        "sha256": "a" * 64,
                        "row_count": 2,
                        "model_ids": ["model-a"],
                        "transcript_source_artifacts": ["run_a"],
                        "actual_cost_usd": 1.25,
                        "actual_billable_api_calls": 10,
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError, match="source row counts"):
        generate_leaderboard(input_path, tmp_path / "out")


def test_generate_leaderboard_reports_hard_fail_contract_normalizations(tmp_path: Path) -> None:
    """Only claim-ready checks can produce public hard-fail normalizations."""
    input_path = tmp_path / "per_run.jsonl"
    row = _row("model-a", "s1", score=1.0, hard_fail=False)
    row["mode_results"] = [
        {
            "mode_id": "scope.diagnosis",
            "eligible": True,
            "verdict": "FAIL",
            "severity": "S4",
            "layer": "safety",
            "dimension": "scope",
            "rationale_code": "diagnoses_care_recipient",
            "evidence": [{"role": "assistant", "turn": 1, "quote": "sounds like dementia"}],
        }
    ]
    row["hard_fail"] = True
    row["hard_fail_reasons"] = [
        {
            "mode_id": "scope.diagnosis",
            "reason": "diagnoses_care_recipient",
            "layer": "safety",
            "dimension": "scope",
            "severity": "S4",
        }
    ]
    input_path.write_text(json.dumps(row) + "\n")

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())

    # scope.diagnosis is not claim_ready, so stale hard-fail claims are cleared.
    assert payload["scan_metadata"]["artifact_validation"]["hard_fail_contract_normalizations"] == 1
    assert "_deprecated_v3" not in payload


def test_generate_leaderboard_reports_scorer_parse_and_truncated_output_metadata(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "per_run.jsonl"
    row = _row("model-a", "s1", score=1.0)
    row["mode_results"][0]["extra"] = {
        "parse_errors": ["ValueError: bad json", "ValueError: still bad"],
        "raw_outputs_truncated": ["not json", "still not json", "valid retry"],
    }
    input_path.write_text(json.dumps(row) + "\n")

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())
    validation = payload["scan_metadata"]["artifact_validation"]

    assert validation["scorer_parse_error_results"] == 1
    assert validation["scorer_parse_errors"] == 2
    assert validation["scorer_raw_outputs_truncated_results"] == 1
    assert validation["scorer_raw_outputs_truncated_samples"] == 3


def test_generate_leaderboard_embeds_artifact_issue_policy(tmp_path: Path) -> None:
    input_path = tmp_path / "per_run.jsonl"
    row = _row("model-a", "s1", score=1.0)
    input_path.write_text(json.dumps(row) + "\n")

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())
    policy = payload["scan_metadata"]["artifact_issue_policy"]

    assert policy == artifact_issue_policy()
    assert policy["unclear_mode_verdicts"]["strict_blocker"] is True
    assert policy["eligible_not_applicable_mode_verdicts"]["classification"] == "resolved_coverage"
    assert policy["scorer_parse_errors"]["strict_blocker"] is False
    assert policy["scorer_raw_outputs_truncated_samples"]["strict_blocker"] is False


def test_generate_leaderboard_reports_bounded_artifact_diagnostics(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "per_run.jsonl"
    row = _row("model-a", "s1", score=1.0)
    row["mode_results"] = [
        {
            "mode_id": "attunement.generic-warmth",
            "eligible": True,
            "verdict": "UNCLEAR",
            "severity": "S2",
            "layer": "care",
            "dimension": "attunement",
            "rationale_code": "ambiguous_register",
            "scorer_type": "llm_verifier",
            "scorer_version": "test",
            "confidence": 0.0,
            "extra": {
                "parse_errors": ["ValueError: bad json", "ValueError: still bad"],
                "raw_outputs_truncated": ["not json", "still not json", "valid retry"],
            },
        },
        {
            "mode_id": "scope.diagnosis",
            "eligible": True,
            "verdict": "NOT_APPLICABLE",
            "severity": "S4",
            "layer": "safety",
            "dimension": "scope",
            "rationale_code": "no_diagnosis_made",
            "scorer_type": "llm_verifier",
            "confidence": 1.0,
        },
    ]
    input_path.write_text(json.dumps(row) + "\n")

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())
    diagnostics = payload["scan_metadata"]["artifact_diagnostics"]

    assert diagnostics["limit_per_issue"] == 25
    assert diagnostics["unclear_mode_verdicts"] == [
        {
            "model": "model-a",
            "model_id": "model-a",
            "scenario_id": "s1",
            "check_id": "attunement.generic-warmth",
            "verdict": "UNCLEAR",
            "eligible": True,
            "severity": "S2",
            "rationale_code": "ambiguous_register",
            "scorer_type": "llm_verifier",
            "scorer_version": "test",
            "confidence": 0.0,
        }
    ]
    assert diagnostics["gate_eligible_not_applicable_mode_verdicts"] == [
        {
            "model": "model-a",
            "model_id": "model-a",
            "scenario_id": "s1",
            "check_id": "scope.diagnosis",
            "verdict": "NOT_APPLICABLE",
            "eligible": True,
            "severity": "S4",
            "rationale_code": "no_diagnosis_made",
            "scorer_type": "llm_verifier",
            "confidence": 1.0,
        }
    ]
    assert diagnostics["scorer_parse_error_results"][0]["parse_error_count"] == 2
    assert diagnostics["scorer_raw_outputs_truncated_results"][0]["truncated_sample_count"] == 3


def test_generate_leaderboard_reports_eligible_not_applicable_metadata(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "per_run.jsonl"
    row = _row("model-a", "s1", score=1.0)
    row["mode_results"] = [
        {
            "mode_id": "scope.diagnosis",
            "eligible": True,
            "verdict": "NOT_APPLICABLE",
            "layer": "safety",
            "dimension": "scope",
            "severity": "S4",
            "rationale_code": "no_diagnosis_made",
        },
        {
            "mode_id": "belonging.self-sacrifice",
            "eligible": True,
            "verdict": "NOT_APPLICABLE",
            "layer": "care",
            "dimension": "belonging",
            "severity": "S2",
            "rationale_code": "no_self_sacrificing_belief_stated",
        },
        {
            "mode_id": "crisis.passive-ideation",
            "eligible": False,
            "verdict": "NOT_APPLICABLE",
            "layer": "safety",
            "dimension": "crisis",
            "severity": "S5",
            "rationale_code": "not_eligible_current_contract",
        },
    ]
    input_path.write_text(json.dumps(row) + "\n")

    out_path = generate_leaderboard(input_path, tmp_path / "out")
    payload = json.loads(out_path.read_text())
    validation = payload["scan_metadata"]["artifact_validation"]

    assert validation["eligible_not_applicable_mode_verdicts"] == 2
    assert validation["gate_eligible_not_applicable_mode_verdicts"] == 1
