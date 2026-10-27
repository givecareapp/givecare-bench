"""The same model validates authored data and the harness input."""

from pathlib import Path

import pytest

from invisiblebench.models.scenario import BranchCondition, Scenario
from invisiblebench.utils.benchmark_inventory import collect_public_scenario_paths


def payload():
    return {
        "scenario_id": "fixture",
        "title": "Fixture",
        "category": "safety",
        "persona": {
            "name": "Alex",
            "age": 40,
            "care_recipient": "Mother",
            "care_duration": "1 year",
            "context": {},
        },
        "turns": [
            {"turn_number": 1, "user_message": "Help"}
        ],
    }


def test_every_public_scenario_uses_the_runtime_contract():
    for path in collect_public_scenario_paths():
        scenario = Scenario.model_validate_json(path.read_bytes())
        assert scenario.all_turns
        assert scenario.scenario_id


@pytest.mark.parametrize(
    "field",
    [
        "tier",
        "scoring_dimensions",
        "eligible_modes",
        "dif_variables",
        "failure_mode_tags",
        "cue_anchors",
        "risk_triggers",
    ],
)
def test_retired_scenario_fields_are_rejected(field):
    raw = payload()
    raw[field] = {}
    with pytest.raises(ValueError, match="retired"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize(
    "field",
    ["t", "rubric", "expected_behaviors", "autofail_triggers", "gray_zone_scoring", "criteria"],
)
def test_retired_turn_fields_are_rejected(field):
    raw = payload()
    raw["turns"][0][field] = []
    with pytest.raises(ValueError, match="retired"):
        Scenario.model_validate(raw)


def test_turn_numbers_are_unique_across_sessions():
    raw = payload()
    turn = raw.pop("turns")[0]
    raw["sessions"] = [
        {"session_number": i, "time_elapsed": "a day", "turns": [turn]} for i in [1, 2]
    ]
    with pytest.raises(ValueError, match="unique and increasing"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize(
    "condition",
    [
        {"type": "noul", "instructions": "Does it help?", "min": float("nan")},
        {"type": "noul", "instructions": "Does it help?", "values": ["help"]},
        {"type": "noul"},
        {"type": "noul", "instructions": "   "},
    ],
)
def test_branch_contract_rejects_unusable_conditions(condition):
    with pytest.raises(ValueError):
        BranchCondition.model_validate(condition)


@pytest.mark.parametrize(
    "condition",
    [
        {"type": "contains_any", "values": ["might work"]},
        {"type": "contains_all", "values": ["crisis", "988"]},
        {"type": "not_contains", "values": ["988"]},
        {"type": "regex", "pattern": "always be here"},
    ],
)
def test_scenario_rejects_keyword_branch_conditions(condition):
    """Keywords cannot tell endorsement from refusal; only a judged question may branch."""
    raw = payload()
    raw["turns"].append(
        {
            "turn_number": 2,
            "user_message": "Default",
            "branches": [{"condition": condition, "user_message": "Branched"}],
        }
    )
    with pytest.raises(ValueError, match="noul"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize("message", ["", "  \n"])
def test_scenario_rejects_a_blank_branch_message(message):
    raw = payload()
    raw["turns"].append(
        {
            "turn_number": 2,
            "user_message": "Default",
            "branches": [
                {
                    "condition": {"type": "noul", "instructions": "Did it miss the cue?"},
                    "user_message": message,
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="branch user_message"):
        Scenario.model_validate(raw)


def test_generated_schema_matches_its_owner():
    import yaml

    saved = yaml.safe_load(Path("benchmark/scenarios/SCENARIO_SCHEMA.yaml").read_text())
    assert saved == Scenario.model_json_schema()


def test_branches_carry_no_authoring_notes():
    raw = payload()
    raw["turns"][0]["branches"] = [
        {
            "condition": {"type": "noul", "instructions": "Did it help?"},
            "user_message": "Help",
            "criteria": [{"description": "Be kind"}],
        }
    ]
    with pytest.raises(ValueError, match="criteria"):
        Scenario.model_validate(raw)
