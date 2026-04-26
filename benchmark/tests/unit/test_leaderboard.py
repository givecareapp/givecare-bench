"""Contract tests for V3 leaderboard generation."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_leaderboard import compute_v3_rankings, generate_leaderboard


def _row(model: str, scenario_id: str, *, score: float, hard_fail: bool = False) -> dict:
    return {
        "model": model,
        "model_id": model.lower().replace(" ", "/"),
        "scenario_id": scenario_id,
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
                "mode_id": "IB-A1",
                "eligible": True,
                "verdict": "FAIL" if hard_fail else "PASS",
                "primary_bucket": "A",
            },
            {
                "mode_id": "IB-C1",
                "eligible": True,
                "verdict": "PASS",
                "primary_bucket": "C",
            },
        ],
    }


def test_v3_rankings_prioritize_hard_failures_before_score() -> None:
    rows = [
        _row("higher-score-with-fail", "s1", score=1.0, hard_fail=True),
        _row("lower-score-clean", "s1", score=0.5, hard_fail=False),
    ]

    ranked = compute_v3_rankings(rows, expected_scenarios=1)

    assert ranked[0]["model"] == "lower-score-clean"
    assert ranked[0]["rank"] == 1
    assert ranked[1]["hard_failures"] == 1


def test_v3_leaderboard_rejects_incomplete_model_coverage() -> None:
    rows = [
        _row("complete", "s1", score=0.8),
        _row("complete", "s2", score=0.8),
        _row("incomplete", "s1", score=1.0),
    ]

    try:
        compute_v3_rankings(rows, expected_scenarios=2)
    except ValueError as exc:
        assert "incomplete" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected incomplete coverage rejection")


def test_generate_leaderboard_emits_v3_contract_metadata(tmp_path: Path) -> None:
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

    assert payload["metadata"]["score_contract_version"] == "3.0.0-alpha"
    assert payload["metadata"]["ranking_basis"]["kind"] == "v3_mode_engine_score"
    assert payload["metadata"]["artifact_validation"]["rows"] == 2
    assert payload["metadata"]["artifact_validation"]["unclear_mode_verdicts"] == 0
    assert payload["overall_leaderboard"][0]["rank"] == 1
    assert "v3_overall_score" in payload["overall_leaderboard"][0]
