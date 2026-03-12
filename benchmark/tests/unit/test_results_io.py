from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.results_io import (
    aggregate_model_results,
    flatten_model_results,
    write_model_results,
)


def _sample_rows() -> list[dict]:
    return [
        {
            "model": "Model A",
            "model_id": "provider/model-a",
            "scenario": "Scenario 1",
            "scenario_id": "s1",
            "category": "safety",
            "overall_score": 0.8,
            "dimensions": {"regard": 0.9, "coordination": 0.7},
            "gates": {"safety": {"passed": True, "reasons": []}},
            "cost": 0.1,
            "status": "pass",
            "run_id": "run-123",
        },
        {
            "model": "Model A",
            "model_id": "provider/model-a",
            "scenario": "Scenario 2",
            "scenario_id": "s2",
            "category": "context",
            "overall_score": 0.2,
            "dimensions": {"regard": 0.2, "coordination": 0.2},
            "hard_fail": True,
            "hard_fail_reasons": ["Missed crisis"],
            "cost": 0.2,
            "status": "fail",
            "run_id": "run-123",
        },
        {
            "model": "Model B",
            "model_id": "provider/model-b",
            "scenario": "Scenario 3",
            "scenario_id": "s3",
            "category": "empathy",
            "overall_score": 0.6,
            "dimension_scores": {"regard": 0.7, "coordination": 0.5},
            "cost": 0.3,
            "status": "pass",
        },
    ]


def test_aggregate_model_results_groups_rows_and_preserves_metadata() -> None:
    docs = aggregate_model_results(
        _sample_rows(),
        benchmark_version="1.2.3",
        mode="benchmark",
        run_metadata={"run_id": "run-123", "provider": "openrouter"},
        timestamp="2026-03-12T00:00:00",
    )

    assert set(docs.keys()) == {"Model A", "Model B"}

    model_a = docs["Model A"]
    assert model_a["model_id"] == "provider/model-a"
    assert model_a["benchmark_version"] == "1.2.3"
    assert model_a["mode"] == "benchmark"
    assert model_a["run_metadata"]["run_id"] == "run-123"
    assert model_a["scenario_count"] == 2
    assert model_a["passed"] == 1
    assert model_a["failed"] == 1
    assert model_a["overall_score"] == 0.5
    assert model_a["dimension_scores"]["regard"] == 0.55
    assert model_a["scenarios"][0]["scenario_id"] == "s1"
    assert model_a["scenarios"][0]["gates"]["safety"]["passed"] is True


def test_write_model_results_writes_one_json_per_model(tmp_path: Path) -> None:
    written = write_model_results(
        _sample_rows(),
        tmp_path,
        benchmark_version="1.2.3",
        mode="benchmark",
    )

    assert len(written) == 2
    assert sorted(p.name for p in written) == ["Model_A.json", "Model_B.json"]

    model_a = json.loads((tmp_path / "Model_A.json").read_text())
    assert model_a["model"] == "Model A"
    assert model_a["scenario_count"] == 2
    assert model_a["total_cost"] == 0.30000000000000004


def test_flatten_model_results_restores_flat_rows() -> None:
    docs = aggregate_model_results(_sample_rows(), benchmark_version="1.2.3")
    rows = flatten_model_results(docs.values())

    assert len(rows) == 3
    rows_by_id = {row["scenario_id"]: row for row in rows}
    assert rows_by_id["s1"]["model_id"] == "provider/model-a"
    assert rows_by_id["s1"]["dimensions"] == {"regard": 0.9, "coordination": 0.7}
    assert rows_by_id["s2"]["hard_fail"] is True
    assert rows_by_id["s3"]["dimensions"] == {"regard": 0.7, "coordination": 0.5}
