"""Model selection resolves catalog entries without inventing models or prices."""

import pytest

from invisiblebench.cli.run_command import resolve_models

CATALOG = [
    {"id": "vendor/atlas", "name": "Atlas Large"},
    {"id": "vendor/breeze", "name": "Breeze"},
    {"id": "other/atlas-lite", "name": "Atlas Lite"},
    {"id": "vendor/routed-only", "name": "Comet"},
]


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("1", [0]),
        ("4", [3]),
        ("1-3", [0, 1, 2]),
        ("3-", [2, 3]),
        ("1,3", [0, 2]),
        ("99", []),
        ("large", [0]),
        ("atlas", [0, 2]),
        ("ATLAS", [0, 2]),
        ("Atlas", [0, 2]),
        ("routed-only", [3]),
        ("1,comet", [0, 3]),
        ("1-2,comet", [0, 1, 3]),
        ("1,atlas large", [0]),
        (" 1 , comet ", [0, 3]),
        ("", []),
        (",,,", []),
    ],
)
def test_catalog_selection(spec, expected):
    assert resolve_models(spec, CATALOG) == expected


def test_empty_catalog_has_no_numeric_selection():
    assert resolve_models("1", []) == []


def test_unknown_name_lists_available_models():
    with pytest.raises(ValueError, match="No model matching 'missing'.*Available models"):
        resolve_models("missing", CATALOG)


def test_unknown_model_id_cannot_invent_catalog_pricing():
    before = [row.copy() for row in CATALOG]
    with pytest.raises(ValueError, match="No catalog pricing"):
        resolve_models("unknown/new-model", CATALOG)
    assert CATALOG == before
