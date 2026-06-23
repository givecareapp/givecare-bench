"""Tests for the V3 leaderboard QA gate."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.qa_leaderboard import validate_leaderboard


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _scan_row(
    model: str,
    scenario_id: str,
    *,
    verdict: str = "PASS",
    bucket: str = "A",
    scorer_type: str = "llm_verifier",
    evidence: list[dict] | None = None,
) -> dict:
    return {
        "model": model,
        "model_id": model.lower(),
        "scenario_id": scenario_id,
        "overall_score": 1.0,
        "hard_fail": verdict == "FAIL" and bucket in {"A", "B"},
        "mode_results": [
            {
                "mode_id": "IB-A1" if bucket == "A" else "IB-C1",
                "eligible": True,
                "verdict": verdict,
                "severity": "S5" if bucket in {"A", "B"} else "S2",
                "primary_bucket": bucket,
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


def _leaderboard(source: Path, *, models: int = 1, scenarios: int = 1) -> dict:
    """Minimal safety-care/v1 leaderboard fixture."""
    return {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True},
        "scan_metadata": {
            "source_artifact": str(source),
            "total_models": models,
            "total_scenarios": scenarios,
        },
        "models": [],
    }


def test_v3_qa_accepts_clean_strict_artifact(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
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
                        "mode_id": "IB-A1",
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


def test_v3_qa_infers_current_scan_coverage(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
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


def test_v3_qa_inferred_coverage_rejects_stale_metadata(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1")])
    leaderboard.write_text(
        json.dumps(_leaderboard(scan, models=1, scenarios=50)),
        encoding="utf-8",
    )

    errors = validate_leaderboard(scan, leaderboard)

    assert any("leaderboard_total_scenarios" in error for error in errors)


def test_v3_qa_rejects_gate_unclear(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1", verdict="UNCLEAR", bucket="A")])
    leaderboard.write_text(json.dumps(_leaderboard(scan)), encoding="utf-8")

    errors = validate_leaderboard(
        scan,
        leaderboard,
        expected_rows=1,
        expected_models=1,
        expected_scenarios=1,
    )

    assert any("gate_unclear" in error for error in errors)


def test_v3_qa_strict_rejects_non_gate_unclear(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
    _write_jsonl(scan, [_scan_row("model-a", "s1", verdict="UNCLEAR", bucket="D")])
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


def test_v3_qa_strict_requires_manual_audit_file(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
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


def test_v3_qa_rejects_fail_without_evidence(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "v3_leaderboard.json"
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
