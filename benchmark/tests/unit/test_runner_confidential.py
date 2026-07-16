from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.cli import runner


def test_get_scenarios_includes_private_confidential_when_requested(
    tmp_path: Path, monkeypatch
) -> None:
    confidential_dir = tmp_path / "private_confidential"
    confidential_dir.mkdir()
    confidential_path = confidential_dir / "holdout.json"
    confidential_path.write_text(json.dumps({"scenario_id": "conf_holdout_001", "turns": []}))

    monkeypatch.setenv(
        "INVISIBLEBENCH_PRIVATE_CONFIDENTIAL_SCENARIOS_DIR",
        str(confidential_dir),
    )

    scenarios = runner.get_scenarios(include_confidential=True)

    assert any(
        Path(scenario["path"]) == confidential_path and scenario["category"] == "confidential"
        for scenario in scenarios
    )


def test_scenario_filter_matches_partial_stem_and_normalized_name() -> None:
    scenario = {
        "path": "benchmark/scenarios/context/regulatory/data_privacy_inquiry.json",
        "name": "Data Privacy Inquiry",
        "scenario_id": "context_regulatory_data_privacy_001",
    }

    assert runner._scenario_matches_filter(scenario, "data_privacy") is True
    assert runner._scenario_matches_filter(scenario, "dataprivacy") is True
    assert runner._scenario_matches_filter(scenario, "privacy inquiry") is True
    assert runner._scenario_matches_filter(scenario, "scope_honesty") is False


def test_get_scenarios_exposes_json_scenario_id_for_filtering() -> None:
    scenarios = runner.get_scenarios()

    assert any(
        runner._scenario_matches_filter(scenario, "context_regulatory_data_privacy_001")
        for scenario in scenarios
    )


def test_main_passes_confidential_flag_to_llm_benchmark(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        runner,
        "MODELS_FULL",
        [
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
    )

    def fake_run_benchmark(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(runner, "run_benchmark", fake_run_benchmark)

    exit_code = runner.main([
        "-m",
        "1",
        "--dry-run",
        "--confidential",
    ])

    assert exit_code == 0
    assert captured["include_confidential"] is True
