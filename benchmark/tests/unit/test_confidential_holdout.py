"""Tests for confidential scenario holdout enforcement helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_confidential_holdout_blocks_by_default() -> None:
    validate_module = _load_module(
        "validate_submission",
        "benchmark/scripts/community/validate_submission.py",
    )
    data = {
        "scenarios": [
            {"scenario_id": "conf_test", "confidential": True},
            {"scenario_id": "tier1_public_001", "confidential": False},
        ]
    }
    errors = validate_module.validate_confidential_holdout(
        data,
        {"conf_test"},
        include_confidential=False,
    )
    assert errors

    errors_allowed = validate_module.validate_confidential_holdout(
        data,
        {"conf_test"},
        include_confidential=True,
    )
    assert errors_allowed == []


def test_generate_leaderboard_detects_confidential() -> None:
    leaderboard_module = _load_module(
        "generate_leaderboard",
        "benchmark/scripts/community/generate_leaderboard.py",
    )
    result = {
        "scenarios": [
            {"scenario_id": "conf_test", "confidential": True},
            {"scenario_id": "tier1_public_001"},
        ]
    }
    assert leaderboard_module.has_confidential_scenarios(result, {"conf_test"}) is True
    assert leaderboard_module.has_confidential_scenarios(result, set()) is True
