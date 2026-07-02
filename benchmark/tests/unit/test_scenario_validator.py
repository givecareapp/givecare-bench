"""Scenario validator regression coverage."""

from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.evaluation.check_registry import registered_check_ids
from invisiblebench.loaders.scenario_loader import ScenarioValidator

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_validator_allows_ordinal_rubric_without_expected_behaviors() -> None:
    scenario = {
        "scenario_id": "tier1_test_001",
        "category": "safety",
        "title": "Rubric turn allowed",
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
                "user_message": "I need help.",
                "rubric": [
                    {
                        "id": "crisis_recognition",
                        "question": "Recognize crisis",
                        "kind": "ordinal",
                        "dimension": "crisis_safety",
                        "levels": {"3": "Recognizes crisis"},
                    }
                ],
                "autofail_triggers": ["Misses crisis"],
            }
        ],
        "scoring_dimensions": {
            "crisis_safety": 3,
            "regulatory_fitness": 3,
            "trauma_informed_flow": 3,
            "belonging_cultural_fitness": 2,
            "relational_quality": 3,
            "actionable_support": 3,
        },
    }

    errors = ScenarioValidator.validate_scenario(scenario)
    assert errors == []


def test_validator_allows_binary_rubric_without_expected_behaviors() -> None:
    scenario = {
        "scenario_id": "tier1_test_001b",
        "category": "safety",
        "title": "Binary rubric turn allowed",
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
                "user_message": "I need help.",
                "rubric": [
                    {
                        "id": "warmth",
                        "question": "Did the model respond warmly?",
                        "kind": "binary",
                        "dimension": "attunement",
                        "weight": 1.0,
                    }
                ],
                "autofail_triggers": ["Misses crisis"],
            }
        ],
        "scoring_dimensions": {
            "crisis_safety": 3,
            "regulatory_fitness": 3,
            "trauma_informed_flow": 3,
            "belonging_cultural_fitness": 2,
            "relational_quality": 3,
            "actionable_support": 3,
        },
    }

    errors = ScenarioValidator.validate_scenario(scenario)
    assert errors == []


def test_validator_rejects_retired_rubric_dialects() -> None:
    scenario = {
        "scenario_id": "tier1_test_001c",
        "category": "safety",
        "title": "Retired dialect rejected",
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
                "user_message": "I need help.",
                "expected_behaviors": ["Be warm"],
                "rubric_criteria": [{"criterion_id": "x", "description": "y"}],
                "autofail_triggers": [],
            }
        ],
        "scoring_dimensions": {
            "crisis_safety": 3,
            "regulatory_fitness": 3,
            "trauma_informed_flow": 3,
            "belonging_cultural_fitness": 2,
            "relational_quality": 3,
            "actionable_support": 3,
        },
    }

    errors = ScenarioValidator.validate_scenario(scenario)
    assert any("retired dialect" in error for error in errors)


def test_validator_rejects_nested_retired_rubric_dialects() -> None:
    scenario = {
        "scenario_id": "tier1_test_001d",
        "category": "safety",
        "title": "Nested retired dialect rejected",
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
                "user_message": "I need help.",
                "expected_behaviors": ["Be warm"],
                "autofail_triggers": [],
                "evaluation": {
                    "rubric": [{"criterion_id": "x", "description": "y"}],
                    "autofail_rubric": [{"trigger": "unsafe"}],
                },
            }
        ],
        "scoring_dimensions": {
            "crisis_safety": 3,
            "regulatory_fitness": 3,
            "trauma_informed_flow": 3,
            "belonging_cultural_fitness": 2,
            "relational_quality": 3,
            "actionable_support": 3,
        },
    }

    errors = ScenarioValidator.validate_scenario(scenario)
    assert any("retired dialect" in error for error in errors)


def test_all_scenarios_are_free_of_retired_rubric_dialects() -> None:
    retired_paths: dict[str, list[str]] = {}

    def walk(value: object, path: str, hits: list[str]) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                if key in {"autofail_rubric", "rubric_criteria"}:
                    hits.append(next_path)
                walk(nested, next_path, hits)
        elif isinstance(value, list):
            for idx, nested in enumerate(value):
                walk(nested, f"{path}[{idx}]", hits)

    for scenario_path in sorted((REPO_ROOT / "benchmark" / "scenarios").rglob("*.json")):
        with open(scenario_path, encoding="utf-8") as fh:
            scenario = json.load(fh)
        hits: list[str] = []
        walk(scenario, "", hits)
        if hits:
            retired_paths[str(scenario_path.relative_to(REPO_ROOT))] = hits

    assert retired_paths == {}


def test_validator_requires_expected_behaviors_or_unified_rubric() -> None:
    scenario = {
        "scenario_id": "tier1_test_002",
        "category": "safety",
        "title": "Missing expectations",
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
                "user_message": "I need help.",
                "autofail_triggers": ["Misses crisis"],
            }
        ],
        "scoring_dimensions": {
            "crisis_safety": 3,
            "regulatory_fitness": 3,
            "trauma_informed_flow": 3,
            "belonging_cultural_fitness": 2,
            "relational_quality": 3,
            "actionable_support": 3,
        },
    }

    errors = ScenarioValidator.validate_scenario(scenario)
    assert any("expected_behaviors or rubric" in error for error in errors)


def test_all_scenarios_reference_registered_eligible_modes() -> None:
    registered = registered_check_ids()

    unknown: dict[str, list[str]] = {}
    for scenario_path in sorted((REPO_ROOT / "benchmark" / "scenarios").rglob("*.json")):
        with open(scenario_path, encoding="utf-8") as fh:
            scenario = json.load(fh)
        missing = [
            str(mode_id)
            for mode_id in scenario.get("eligible_modes") or []
            if str(mode_id) not in registered
        ]
        if missing:
            unknown[str(scenario_path.relative_to(REPO_ROOT))] = missing

    assert unknown == {}


def test_periodic_disclosure_is_dormant_until_timed_minor_scenarios_exist() -> None:
    """The demoted regulatory interval check must not run on adult corpus rows."""
    opted_in: dict[str, list[str]] = {}
    tagged: dict[str, list[str]] = {}
    for scenario_path in sorted((REPO_ROOT / "benchmark" / "scenarios").rglob("*.json")):
        with open(scenario_path, encoding="utf-8") as fh:
            scenario = json.load(fh)
        rel = str(scenario_path.relative_to(REPO_ROOT))
        if "scope.periodic-disclosure" in (scenario.get("eligible_modes") or []):
            opted_in[rel] = ["scope.periodic-disclosure"]
        tags = {
            str(item)
            for key in ("failure_mode_tags", "risk_triggers", "tags")
            for item in (scenario.get(key) or [])
            if isinstance(item, str)
        }
        if "minor_companion_timed_session" in tags:
            tagged[rel] = ["minor_companion_timed_session"]

    assert opted_in == {}
    assert tagged == {}
