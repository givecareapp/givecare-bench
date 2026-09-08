"""Current scan, projection, strict-QA, and owner-driver integration proof."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.tests.fixtures.current_scan import write_current_qa_fixture
from invisiblebench.scoring.care import model_care_distribution, scenario_care
from invisiblebench.scoring.safety import model_safety_rates, scenario_safety
from invisiblebench.utils.io import load_jsonl
from scripts.generate_leaderboard import generate_leaderboard
from scripts.qa_leaderboard import validate_leaderboard

_DIMENSIONS = {
    "crisis.one": {"layer": "safety", "dimension": "crisis"},
    "belonging.one": {"layer": "care", "dimension": "belonging"},
}


@pytest.fixture(scope="module")
def current_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return write_current_qa_fixture(tmp_path_factory.mktemp("current-qa"))


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _decision(result: dict[str, object]) -> str:
    return json.dumps(
        {
            "verdict": result["verdict"],
            "rationale": result["rationale"],
            "evidence": result["evidence"],
        },
        separators=(",", ":"),
    )


def test_safety_and_care_keep_unclear_visible_in_denominators() -> None:
    safety_rows = [
        scenario_safety(
            [
                {"mode_id": "crisis.one", "verdict": "PASS"},
                {"mode_id": "crisis.one", "verdict": "UNCLEAR"},
                {"mode_id": "crisis.one", "verdict": "NOT_APPLICABLE"},
            ],
            _DIMENSIONS,
        ),
        scenario_safety([{"mode_id": "crisis.one", "verdict": "FAIL"}], _DIMENSIONS),
    ]
    safety = model_safety_rates(safety_rows)["crisis"]
    assert safety["observed_failure_rate"] == pytest.approx(0.5)
    assert safety["failure_scenarios"] == 1
    assert safety["eligible_scenarios"] == 2
    assert safety["denominator"] == 3
    assert safety["counts"] == {"PASS": 1, "FAIL": 1, "UNCLEAR": 1, "NOT_APPLICABLE": 1}

    care = model_care_distribution(
        [
            scenario_care(
                [
                    {"mode_id": "belonging.one", "verdict": "PASS"},
                    {"mode_id": "belonging.one", "verdict": "UNCLEAR"},
                    {"mode_id": "belonging.one", "verdict": "NOT_APPLICABLE"},
                ],
                _DIMENSIONS,
            )
        ]
    )["belonging"]
    assert care["pass_rate"] == pytest.approx(0.5)
    assert care["denominator"] == 2
    assert care["counts"] == {"PASS": 1, "FAIL": 0, "UNCLEAR": 1, "NOT_APPLICABLE": 1}


def test_strict_qa_rejects_source_manifest_byte_drift(current_fixture: dict[str, Path]) -> None:
    manifest = current_fixture["source_run"] / "run_manifest.json"
    original = manifest.read_bytes()
    try:
        manifest.write_bytes(original.replace(b'"git_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"', b'"git_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"'))
        errors = validate_leaderboard(
            current_fixture["scan"], current_fixture["leaderboard"], strict=True
        )
        assert any("provenance rebuilt from retained sources" in error for error in errors)
    finally:
        manifest.write_bytes(original)


@pytest.mark.parametrize("kind", ["check", "scenario"])
def test_strict_qa_rejects_missing_roster_entry(
    current_fixture: dict[str, Path], kind: str
) -> None:
    scan = current_fixture["scan"]
    original = scan.read_bytes()
    try:
        rows = load_jsonl(scan)
        if kind == "check":
            rows[0]["mode_results"] = rows[0]["mode_results"][1:]
        else:
            rows.pop()
        _write_rows(scan, rows)
        errors = validate_leaderboard(scan, current_fixture["leaderboard"], strict=True)
        assert errors
        if kind == "check":
            assert any("mode" in error or "projection" in error for error in errors)
        else:
            assert any("scenario" in error or "plan" in error for error in errors)
    finally:
        scan.write_bytes(original)


def test_strict_qa_rejects_forged_fail_evidence(current_fixture: dict[str, Path]) -> None:
    scan = current_fixture["scan"]
    original = scan.read_bytes()
    try:
        rows = load_jsonl(scan)
        result = rows[0]["mode_results"][0]
        result["verdict"] = "FAIL"
        result["evidence"] = [{"role": "assistant", "turn": 1, "quote": "forged"}]
        result["extra"]["raw_response"] = _decision(result)
        _write_rows(scan, rows)
        errors = validate_leaderboard(scan, current_fixture["leaderboard"], strict=True)
        assert any("does not match its cited role and turn" in error for error in errors)
    finally:
        scan.write_bytes(original)


def test_strict_qa_rejects_changed_raw_decision(current_fixture: dict[str, Path]) -> None:
    scan = current_fixture["scan"]
    original = scan.read_bytes()
    try:
        rows = load_jsonl(scan)
        result = rows[0]["mode_results"][0]
        result["extra"]["raw_response"] = json.dumps(
            {"verdict": "FAIL", "rationale": "changed", "evidence": []}
        )
        _write_rows(scan, rows)
        errors = validate_leaderboard(scan, current_fixture["leaderboard"], strict=True)
        assert any("raw_response verdict mismatch" in error for error in errors)
        assert any("raw_response rationale mismatch" in error for error in errors)
    finally:
        scan.write_bytes(original)


def test_strict_qa_rejects_unknown_public_field(current_fixture: dict[str, Path]) -> None:
    leaderboard = current_fixture["leaderboard"]
    original = leaderboard.read_bytes()
    try:
        payload = json.loads(original)
        payload["private_field"] = "must not publish"
        leaderboard.write_text(json.dumps(payload))
        errors = validate_leaderboard(current_fixture["scan"], leaderboard, strict=True)
        assert any("leaderboard unknown fields" in error for error in errors)
    finally:
        leaderboard.write_bytes(original)


def test_semantic_unclear_is_publishable_but_technical_unclear_is_rejected(
    current_fixture: dict[str, Path],
) -> None:
    scan = current_fixture["scan"]
    leaderboard = current_fixture["leaderboard"]
    original_scan = scan.read_bytes()
    original_leaderboard = leaderboard.read_bytes()
    try:
        rows = load_jsonl(scan)
        row = rows[0]
        result = row["mode_results"][0]
        result["verdict"] = "UNCLEAR"
        result["extra"]["raw_response"] = _decision(result)
        row["resolved_count"] -= 1
        row["unclear_count"] += 1
        row["coverage_rate"] = row["resolved_count"] / row["eligible_count"]
        _write_rows(scan, rows)
        generate_leaderboard(scan, leaderboard)
        assert validate_leaderboard(scan, leaderboard, strict=True) == []

        result["rationale_code"] = "invalid_judge_output"
        result["extra"]["validation_error"] = "fixture technical error"
        _write_rows(scan, rows)
        generate_leaderboard(scan, leaderboard)
        errors = validate_leaderboard(scan, leaderboard, strict=True)
        assert any("technical judge error=invalid_judge_output" in error for error in errors)
    finally:
        scan.write_bytes(original_scan)
        leaderboard.write_bytes(original_leaderboard)
