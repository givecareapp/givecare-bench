from __future__ import annotations

from pathlib import Path

import tomllib

import invisiblebench
import invisiblebench.score as score_module
from invisiblebench.utils.benchmark_inventory import get_project_root


class _FakeOrchestrator:
    init_args: dict[str, object] = {}
    score_args: dict[str, object] = {}

    def __init__(self, *, scoring_config_path: str, enable_state_persistence: bool, enable_llm: bool):
        type(self).init_args = {
            "scoring_config_path": scoring_config_path,
            "enable_state_persistence": enable_state_persistence,
            "enable_llm": enable_llm,
        }

    def score(self, *, transcript_path: str, scenario_path: str, rules_path: str):
        type(self).score_args = {
            "transcript_path": transcript_path,
            "scenario_path": scenario_path,
            "rules_path": rules_path,
        }
        return {"overall_score": 1.0, "dimension_scores": {}}


def test_score_uses_repo_default_config_paths(monkeypatch) -> None:
    monkeypatch.setattr(score_module, "ScoringOrchestrator", _FakeOrchestrator)

    result = score_module.score("transcript.jsonl", "scenario.json")

    root = get_project_root()
    assert result["overall_score"] == 1.0
    assert _FakeOrchestrator.init_args == {
        "scoring_config_path": str(root / "benchmark" / "configs" / "scoring.yaml"),
        "enable_state_persistence": False,
        "enable_llm": False,
    }
    assert _FakeOrchestrator.score_args == {
        "transcript_path": "transcript.jsonl",
        "scenario_path": "scenario.json",
        "rules_path": str(root / "benchmark" / "configs" / "rules" / "base.yaml"),
    }


def test_package_version_matches_pyproject() -> None:
    pyproject = Path("pyproject.toml")
    expected_version = tomllib.loads(pyproject.read_text())["project"]["version"]

    assert invisiblebench.__version__ == expected_version
