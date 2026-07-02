"""Tests for the CLI runner's ModeEngine scoring adapter."""

from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.cli.runner import ModeEngineScoringAdapter


class _FakeModeEngineOutput:
    def __init__(self) -> None:
        self.eligible_count = 2
        self.resolved_count = 2
        self.unclear_count = 0
        self.coverage_rate = 1.0

    def to_dict(self) -> dict:
        return {
            "overall_score": 0.75,
            "hard_fail": False,
            "hard_fail_reasons": [],
            "dimension_scores": {
                "crisis": 1.0,
                "scope": 1.0,
                "belonging": 0.75,
            },
            "blindspot_profile": {},
            "mode_results": [
                {
                    "mode_id": "crisis.passive-ideation",
                    "eligible": True,
                    "verdict": "PASS",
                    "severity": "S5",
                    "layer": "safety",
                    "dimension": "crisis",
                },
                {
                    "mode_id": "scope.diagnosis",
                    "eligible": True,
                    "verdict": "PASS",
                    "severity": "S5",
                    "layer": "safety",
                    "dimension": "scope",
                },
            ],
            "claim_surface": {},
            "engine_version": "test",
            "eligible_count": self.eligible_count,
            "resolved_count": self.resolved_count,
            "unclear_count": self.unclear_count,
            "coverage_rate": self.coverage_rate,
        }


class _FakeModeEngine:
    def __init__(self) -> None:
        self.transcript: list[dict] | None = None
        self.scenario: dict | None = None

    def evaluate(self, *, transcript: list[dict], scenario: dict) -> _FakeModeEngineOutput:
        self.transcript = transcript
        self.scenario = scenario
        return _FakeModeEngineOutput()


def test_mode_engine_adapter_scores_existing_transcript(tmp_path: Path) -> None:
    transcript_path = tmp_path / "transcript.jsonl"
    transcript_path.write_text(
        json.dumps({"turn": 1, "role": "user", "content": "I need help."}) + "\n"
        + json.dumps({"turn": 1, "role": "assistant", "content": "I'm here with you."}) + "\n",
        encoding="utf-8",
    )
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps({"scenario_id": "s1", "category": "empathy"}),
        encoding="utf-8",
    )
    engine = _FakeModeEngine()
    scorer = ModeEngineScoringAdapter(engine=engine, llm_model="judge-model")

    result = scorer.score(
        transcript_path=str(transcript_path),
        scenario_path=str(scenario_path),
        run_id="run-1",
    )

    assert engine.transcript is not None
    assert engine.scenario == {"scenario_id": "s1", "category": "empathy"}
    assert result["contract_version"] == "3.2.0"
    assert result["result_surface"] == "raw/internal"
    assert result["score_model"] == "raw-diagnostic/v1"
    assert result["public_score_model"] == "safety-care/v1"
    assert result["judge_model"] == "judge-model"
    assert result["gates"]["crisis"]["passed"] is True
    assert result["gates"]["scope"]["passed"] is True
    assert result["coverage"] == {
        "eligible": 2,
        "resolved": 2,
        "unclear": 0,
        "rate": 1.0,
    }
    assert "coverage_invalid" not in result
