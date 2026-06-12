from __future__ import annotations

import json
from pathlib import Path

from delivery.sync_web_bench import project_leaderboard

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_project_leaderboard_strips_private_paths_and_matches_web_shape() -> None:
    projected = project_leaderboard(
        {
            "metadata": {
                "benchmark_version": "3.0.0",
                "generated_at": "2026-04-30T00:00:00+00:00",
                "total_scenarios": 1,
                "active_modes": 53,
            },
            "overall_leaderboard": [
                {
                    "model": "Test Model",
                    "model_id": "test/model",
                    "v3_overall_score": 0.75,
                    "scenario_count": 1,
                    "hard_failures": 1,
                    "hard_fail_rate": 1.0,
                    "safety_gate_pass_rate": 0.0,
                    "compliance_gate_pass_rate": 1.0,
                    "dimension_scores": {
                        "communication_quality": 0.6,
                        "caregiver_coordination": 0.7,
                        "boundary_integrity": 1.0,
                    },
                    "unclear_mode_verdicts": 0,
                    "mode_failure_rates": {
                        "IB-A8": {"eligible": 1, "failures": 1},
                        "IB-D2-infodump": {"eligible": 1, "failures": 0},
                    },
                    "scenarios": [
                        {
                            "scenario_id": "masked_crisis",
                            "category": "safety",
                            "transcript_path": "/private/run/transcript.jsonl",
                            "overall_score": 0.2,
                            "hard_fail": True,
                            "hard_fail_reasons": ["IB-A8"],
                            "notable_modes": [
                                {
                                    "mode_id": "IB-A8",
                                    "verdict": "FAIL",
                                    "evidence": [
                                        {"role": "assistant", "turn": 2, "quote": "probably fine"}
                                    ],
                                }
                            ],
                        }
                    ],
                    "rank": 1,
                }
            ],
        }
    )

    assert set(projected) == {"metadata", "models", "findings"}
    assert projected["metadata"]["models"] == 1
    assert projected["models"][0]["dimensions"]["safety"] == 0.0
    assert projected["models"][0]["blind_spots"][0]["check"] == "IB-A8"
    assert projected["findings"]["a8_false_reassurance"]["Test Model"]["fails"] == 1
    assert "/private" not in str(projected)


def test_checked_in_web_leaderboard_matches_canonical_projection() -> None:
    source = json.loads((PROJECT_ROOT / "data/leaderboard/leaderboard.json").read_text())
    checked_in = json.loads((PROJECT_ROOT / "data/leaderboard/leaderboard_web.json").read_text())
    projected = project_leaderboard(source)

    assert checked_in["metadata"]["benchmark_version"] == projected["metadata"]["benchmark_version"]
    assert checked_in["metadata"]["models"] == projected["metadata"]["models"]
    assert checked_in["metadata"]["scenarios"] == projected["metadata"]["scenarios"]
    assert checked_in["metadata"]["scored_at"] == projected["metadata"]["scored_at"]
    assert checked_in == projected
