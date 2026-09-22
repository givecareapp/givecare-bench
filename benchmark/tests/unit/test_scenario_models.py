"""The same model validates authored data and the harness input."""

import json
from pathlib import Path

import pytest

from invisiblebench.models.scenario import BranchCondition, Scenario
from invisiblebench.utils.benchmark_inventory import collect_public_scenario_paths


def payload():
    return {"scenario_id": "fixture", "title": "Fixture", "category": "safety",
            "persona": {"name": "Alex", "age": 40, "care_recipient": "Mother", "care_duration": "1 year", "context": {}},
            "turns": [{"turn_number": 1, "user_message": "Help", "criteria": [{"description": "Be kind"}]}]}


def test_every_public_scenario_uses_the_runtime_contract():
    for path in collect_public_scenario_paths():
        scenario = Scenario.model_validate_json(path.read_bytes())
        assert scenario.all_turns
        assert scenario.scenario_id


@pytest.mark.parametrize("field", ["tier", "scoring_dimensions"])
def test_retired_scenario_fields_are_rejected(field):
    raw = payload()
    raw[field] = {}
    with pytest.raises(ValueError, match="retired"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize("field", ["t", "rubric", "expected_behaviors", "autofail_triggers", "gray_zone_scoring"])
def test_retired_turn_fields_are_rejected(field):
    raw = payload()
    raw["turns"][0][field] = []
    with pytest.raises(ValueError, match="retired"):
        Scenario.model_validate(raw)


def test_turn_numbers_are_unique_across_sessions():
    raw = payload()
    turn = raw.pop("turns")[0]
    raw["sessions"] = [{"session_number": i, "time_elapsed": "a day", "turns": [turn]} for i in [1, 2]]
    with pytest.raises(ValueError, match="unique and increasing"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize("condition", [
    {"type": "noul", "instructions": "Does it help?", "min": float("nan")},
    {"type": "noul", "instructions": "Does it help?", "values": ["help"]},
    {"type": "regex"}, {"type": "contains_any", "values": []},
])
def test_branch_contract_rejects_unusable_conditions(condition):
    with pytest.raises(ValueError):
        BranchCondition.model_validate(condition)


def test_generated_schema_matches_its_owner():
    import yaml
    saved = yaml.safe_load(Path("benchmark/scenarios/SCENARIO_SCHEMA.yaml").read_text())
    assert saved == Scenario.model_json_schema()
