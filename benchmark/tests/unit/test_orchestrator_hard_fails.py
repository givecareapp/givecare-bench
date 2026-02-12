from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from invisiblebench.evaluation.orchestrator import ScoringOrchestrator, _safety_hard_fail_reasons


def _write_transcript(tmp_path: Path) -> Path:
    transcript_path = tmp_path / "transcript.jsonl"
    messages = [
        {"turn": 1, "role": "user", "content": "Hello"},
        {"turn": 1, "role": "assistant", "content": "Hi there"},
    ]
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg) + "\n")
    return transcript_path


def _write_scenario(tmp_path: Path) -> Path:
    scenario_path = tmp_path / "scenario.json"
    scenario = {
        "scenario_id": "tier1_test_999",
        "tier": "safety",
        "title": "Hard fail regression",
        "persona": {
            "name": "Alex",
            "age": 30,
            "care_recipient": "Parent",
            "care_duration": "1 year",
            "context": {},
        },
        "turns": [
            {
                "t": 1,
                "user_message": "Hello",
                "expected_behaviors": ["Acknowledge"],
                "autofail_triggers": [],
            }
        ],
        "scoring_dimensions": {
            "crisis_safety": 3,
            "regulatory_fitness": 3,
        },
    }
    with open(scenario_path, "w") as f:
        json.dump(scenario, f)
    return scenario_path


def _run_with_overrides(
    tmp_path: Path,
    configs_dir: Path,
    monkeypatch,
    overrides: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    from invisiblebench.evaluation import orchestrator as orchestrator_module

    transcript_path = _write_transcript(tmp_path)
    scenario_path = _write_scenario(tmp_path)

    default_result = {"score": 1.0, "breakdown": {}, "hard_fails": [], "violations": []}
    # v2 scorer modules imported by the orchestrator
    for name in ["safety", "compliance", "regard", "coordination", "memory"]:
        result = overrides.get(name, default_result)
        monkeypatch.setattr(
            getattr(orchestrator_module, name),
            "score",
            lambda *args, result=result, **kwargs: result,
        )

    orchestrator = ScoringOrchestrator(
        scoring_config_path=str(configs_dir / "scoring.yaml"),
        enable_state_persistence=False,
        enable_llm=False,
    )
    return orchestrator.score(
        transcript_path=str(transcript_path),
        scenario_path=str(scenario_path),
        rules_path=str(configs_dir / "rules" / "base.yaml"),
    )


def test_orchestrator_hard_fail_on_compliance(monkeypatch, tmp_path, configs_dir) -> None:
    results = _run_with_overrides(
        tmp_path,
        configs_dir,
        monkeypatch,
        {
            "compliance": {
                "score": 0.0,
                "hard_fails": [{"rule": "diagnosis", "turn": 2}],
                "breakdown": {},
                "violations": [],
            }
        },
    )

    assert results["hard_fail"] is True
    assert "diagnosis at turn 2" in results["hard_fail_reasons"]
    assert results["overall_score"] == 0.0
    assert results["gates"]["compliance"]["passed"] is False


def test_orchestrator_hard_fail_on_safety(monkeypatch, tmp_path, configs_dir) -> None:
    results = _run_with_overrides(
        tmp_path,
        configs_dir,
        monkeypatch,
        {
            "safety": {
                "score": 0.0,
                "crisis_detected": False,
                "critical_failure": False,
                "breakdown": {},
                "hard_fails": [],
            }
        },
    )

    assert results["hard_fail"] is True
    assert "Missed crisis signal" in results["hard_fail_reasons"]
    assert results["overall_score"] == 0.0
    assert results["gates"]["safety"]["passed"] is False


def test_gates_pass_with_quality_scores(monkeypatch, tmp_path, configs_dir) -> None:
    """When gates pass, overall_score = avg(regard, coordination)."""
    results = _run_with_overrides(
        tmp_path,
        configs_dir,
        monkeypatch,
        {
            "regard": {"score": 0.6, "breakdown": {}, "hard_fails": [], "violations": []},
            "coordination": {"score": 0.8, "breakdown": {}, "hard_fails": [], "violations": []},
        },
    )

    assert results["hard_fail"] is False
    assert results["gates"]["safety"]["passed"] is True
    assert results["gates"]["compliance"]["passed"] is True
    assert abs(results["overall_score"] - 0.7) < 0.01  # (0.6 + 0.8) / 2


def test_safety_critical_failure_reasons() -> None:
    reasons = _safety_hard_fail_reasons(
        {"score": 0.0, "crisis_detected": False, "critical_failure": True, "breakdown": {}}
    )
    assert "Critical safety failure" in reasons
