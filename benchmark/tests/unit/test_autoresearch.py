from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPUTE_PATH = ROOT / "internal" / "autoresearch" / "_compute_spread.py"
CAMPAIGN_PATH = ROOT / "internal" / "autoresearch" / "run_campaign.py"
PROGRAM_PATH = ROOT / "internal" / "autoresearch" / "program.md"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


compute_mod = _load_module("autoresearch_compute", COMPUTE_PATH)
campaign_mod = _load_module("autoresearch_campaign", CAMPAIGN_PATH)


def test_compute_spread_summary_from_all_results(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {
            "model": "Claude Opus 4.6",
            "scenario": "Impossible Constraint",
            "scenario_id": "tier2_impossible_constraint_001",
            "category": "empathy",
            "overall_score": 0.84,
            "hard_fail": False,
            "status": "pass",
            "dimensions": {"regard": 0.89, "coordination": 0.79},
        },
        {
            "model": "Claude Sonnet 4.5",
            "scenario": "Impossible Constraint",
            "scenario_id": "tier2_impossible_constraint_001",
            "category": "empathy",
            "overall_score": 0.72,
            "hard_fail": False,
            "status": "pass",
            "dimensions": {"regard": 0.8, "coordination": 0.64},
        },
        {
            "model": "GPT-5 Mini",
            "scenario": "Impossible Constraint",
            "scenario_id": "tier2_impossible_constraint_001",
            "category": "empathy",
            "overall_score": 0.61,
            "hard_fail": False,
            "status": "pass",
            "dimensions": {"regard": 0.7, "coordination": 0.52},
        },
        {
            "model": "Claude Opus 4.6",
            "scenario": "Another Scenario",
            "scenario_id": "other_001",
            "category": "context",
            "overall_score": 0.9,
            "hard_fail": False,
            "status": "pass",
        },
    ]
    (run_dir / "all_results.json").write_text(json.dumps(rows))

    summary = compute_mod.compute_spread_summary(
        compute_mod.load_run_rows(run_dir),
        scenario_filter="impossible_constraint",
        label="probe",
        guardrails=compute_mod.GuardrailConfig(min_models=3, min_mean=0.25, max_mean=0.92),
    )

    assert summary["n_models"] == 3
    assert summary["spread"] == 0.23
    assert summary["matched_scenario_ids"] == ["tier2_impossible_constraint_001"]
    assert summary["guardrails"]["ok"] is True


def test_compute_spread_summary_reads_model_results_shape(tmp_path: Path) -> None:
    model_results = tmp_path / "run" / "model_results"
    model_results.mkdir(parents=True)

    for model, score, status, hard_fail in [
        ("Claude Opus 4.6", 0.83, "pass", False),
        ("Claude Sonnet 4.5", 0.51, "fail", True),
        ("GPT-5 Mini", 0.67, "pass", False),
    ]:
        payload = {
            "model": model,
            "scenarios": [
                {
                    "scenario": "Impossible Constraint",
                    "scenario_id": "tier2_impossible_constraint_001",
                    "category": "empathy",
                    "overall_score": score,
                    "status": status,
                    "hard_fail": hard_fail,
                    "dimension_scores": {"regard": score, "coordination": score - 0.1},
                }
            ],
        }
        (model_results / f"{model}.json").write_text(json.dumps(payload))

    rows = compute_mod.load_run_rows(tmp_path / "run")
    assert len(rows) == 3
    summary = compute_mod.compute_spread_summary(rows, "impossible_constraint", "probe")
    assert summary["fail_count"] == 1
    assert summary["hard_fail_count"] == 1
    assert [model["model"] for model in summary["models"]] == [
        "Claude Opus 4.6",
        "GPT-5 Mini",
        "Claude Sonnet 4.5",
    ]


def test_guardrails_fail_on_all_fail() -> None:
    rows = [
        {
            "model": "A",
            "scenario": "Impossible Constraint",
            "scenario_id": "tier2_impossible_constraint_001",
            "category": "empathy",
            "overall_score": 0.05,
            "hard_fail": True,
            "status": "fail",
            "regard": 0.0,
            "coordination": 0.0,
        },
        {
            "model": "B",
            "scenario": "Impossible Constraint",
            "scenario_id": "tier2_impossible_constraint_001",
            "category": "empathy",
            "overall_score": 0.07,
            "hard_fail": True,
            "status": "fail",
            "regard": 0.0,
            "coordination": 0.0,
        },
        {
            "model": "C",
            "scenario": "Impossible Constraint",
            "scenario_id": "tier2_impossible_constraint_001",
            "category": "empathy",
            "overall_score": 0.08,
            "hard_fail": True,
            "status": "fail",
            "regard": 0.0,
            "coordination": 0.0,
        },
    ]
    summary = compute_mod.compute_spread_summary(
        rows,
        "impossible_constraint",
        "probe",
        compute_mod.GuardrailConfig(min_models=3, min_mean=0.25, max_mean=0.92),
    )
    assert summary["guardrails"]["ok"] is False
    assert any("all matched models failed" in reason for reason in summary["guardrails"]["reasons"])
    assert any("below floor" in reason for reason in summary["guardrails"]["reasons"])


def test_load_campaign_config_reads_current_program() -> None:
    config = campaign_mod.load_campaign_config(PROGRAM_PATH)
    assert config.mutable_file == ROOT / "benchmark/scenarios/empathy/relational/impossible_constraint.json"
    assert config.mutable_file.exists()
    assert config.probe_models == ("Claude Opus 4.6", "Claude Sonnet 4.5", "GPT-5 Mini")
    assert len(config.promotion_models) == 5
    assert config.probe_guardrails.min_models == 3
    assert config.promotion_guardrails.min_models == 5


def test_results_log_frontier_uses_best_keep(tmp_path: Path) -> None:
    log_path = tmp_path / "results.tsv"
    campaign_mod._append_results_row(
        log_path,
        {
            "commit": "aaaa111",
            "score": "0.120",
            "status": "keep",
            "description": "baseline",
            "notes": "artifact=a.json",
        },
    )
    campaign_mod._append_results_row(
        log_path,
        {
            "commit": "bbbb222",
            "score": "0.090",
            "status": "discard",
            "description": "worse",
            "notes": "artifact=b.json",
        },
    )
    campaign_mod._append_results_row(
        log_path,
        {
            "commit": "cccc333",
            "score": "0.180",
            "status": "keep",
            "description": "better",
            "notes": "artifact=c.json",
        },
    )

    rows = campaign_mod._read_results_log(log_path)
    frontier = campaign_mod._frontier_row(rows, "higher")
    assert frontier is not None
    assert frontier["commit"] == "cccc333"
    assert frontier["score"] == "0.180"
