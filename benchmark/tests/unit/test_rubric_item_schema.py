"""Schema shape checks for v2 rubric item validation."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = PROJECT_ROOT / "benchmark" / "scenarios" / "schemas" / "rubric_item.schema.json"


def test_rubric_item_schema_exists_and_loads() -> None:
    assert SCHEMA_PATH.exists()
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "$defs" in schema


def test_rubric_item_required_fields_and_weight_bounds() -> None:
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    rubric_item = schema["$defs"]["rubric_item"]
    props = rubric_item["properties"]

    assert rubric_item["required"] == ["id", "question", "dimension"]
    assert props["weight"]["minimum"] == 0.5
    assert props["weight"]["maximum"] == 2.0
    assert props["weight"]["default"] == 1.0


def test_rubric_item_dimension_enum_matches_v2_dimensions() -> None:
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    dimensions = schema["$defs"]["dimension"]["enum"]
    assert dimensions == [
        "safety",
        "compliance",
        "attunement",
        "belonging",
        "false_refusal",
        "memory",
        "consistency",
    ]


def test_autofail_rubric_requires_true_triggers_hard_fail() -> None:
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    autofail = schema["$defs"]["autofail_rubric_item"]
    overlay = autofail["allOf"][1]

    assert overlay["required"] == ["triggers_hard_fail"]
    assert overlay["properties"]["triggers_hard_fail"]["const"] is True
