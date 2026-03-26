from __future__ import annotations

import json
from pathlib import Path

import pytest

import invisiblebench.adapters.givecare_orchestrator as givecare_orchestrator


class _DummyScenario:
    scenario_id = "test_orchestrator_error"
    risk_triggers = []

    def model_dump(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "title": "Orchestrator transport error",
            "category": "safety",
        }


def _seed_state() -> dict[str, object]:
    return {
        "memory_state": {},
        "recent_messages": [],
        "followups": [],
        "critical_events": [],
        "alerts": [],
        "diagnostics": [],
        "assessment_runs": [],
        "eligibility_facts": [],
        "bootstrap_patches": [],
        "resource_offers": [],
        "resource_lookups": [],
        "nearby_queries": [],
        "screenings_run": [],
        "conversation_state": {
            "currentLoop": "activeSupport",
            "currentStage": "ongoing-support",
            "pendingPromptType": None,
            "pendingPromptInstrument": None,
            "assessmentOverdue": False,
            "benefitsScreeningDue": False,
            "sdoh30Due": False,
            "flaggedZoneCount": 0,
            "openAssessment": None,
            "cadence": {"hasSdoh6": False, "hasSdoh30": False, "flaggedZoneCount": 0},
            "skillDiscovery": None,
            "skillDiscoveryText": None,
            "zipCode": None,
            "latitude": None,
            "longitude": None,
            "bootstrapNeededFacts": [],
            "bootstrapCollectedFacts": [],
            "scoreSnapshot": None,
        },
    }


def test_run_scenario_fails_closed_on_bridge_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        givecare_orchestrator.ScenarioModel,
        "from_file",
        staticmethod(lambda _path: _DummyScenario()),
    )
    monkeypatch.setattr(
        givecare_orchestrator,
        "_turns_for_scenario",
        lambda _scenario: [{"turn_number": 1, "user_message": "hello"}],
    )
    monkeypatch.setattr(givecare_orchestrator, "_conversation_seed", lambda _scenario: _seed_state())
    monkeypatch.setattr(givecare_orchestrator, "_build_bridge_payload", lambda **_kwargs: {})

    def _raise_bridge_error(_payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("bridge down")

    monkeypatch.setattr(givecare_orchestrator, "_call_bridge", _raise_bridge_error)

    with pytest.raises(RuntimeError, match="Turn 1"):
        givecare_orchestrator.run_scenario("test-model", "unused.json", tmp_path)

    transcript_path = tmp_path / "test-model_test_orchestrator_error.jsonl"
    assert transcript_path.exists()

    rows = [json.loads(line) for line in transcript_path.read_text().splitlines()]
    assert rows[-1]["error"] is True
    assert "bridge down" in rows[-1]["content"]
