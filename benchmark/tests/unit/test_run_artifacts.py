from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.results_io import write_json, write_model_results
from invisiblebench.run_artifacts import (
    detect_transcripts_dir,
    load_model_result_documents,
    load_result_rows,
    write_aggregate_results,
)

SAMPLE_ROWS = [
    {
        "model": "Model A",
        "model_id": "provider/model-a",
        "scenario": "Scenario 1",
        "scenario_id": "s1",
        "category": "safety",
        "overall_score": 0.8,
        "dimensions": {"regard": 0.9, "coordination": 0.7},
        "status": "pass",
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
        "status": "fail",
    },
]


def test_load_result_rows_from_all_results(tmp_path: Path) -> None:
    path = write_json(tmp_path / "all_results.json", SAMPLE_ROWS)
    rows = load_result_rows(path)
    assert rows == SAMPLE_ROWS


def test_load_result_rows_from_provider_wrapper(tmp_path: Path) -> None:
    path = write_json(tmp_path / "givecare_results.json", {"metadata": {}, "results": SAMPLE_ROWS})
    rows = load_result_rows(path)
    assert rows == SAMPLE_ROWS


def test_load_result_rows_from_model_results_dir(tmp_path: Path) -> None:
    model_dir = tmp_path / "model_results"
    write_model_results(SAMPLE_ROWS, model_dir, benchmark_version="1.2.0")

    docs = load_model_result_documents(model_dir)
    assert len(docs) == 1
    assert docs[0]["model"] == "Model A"

    rows = load_result_rows(model_dir)
    assert len(rows) == 2
    assert {row["scenario_id"] for row in rows} == {"s1", "s2"}


def test_write_aggregate_results_rebuilds_all_results(tmp_path: Path) -> None:
    model_dir = tmp_path / "model_results"
    write_model_results(SAMPLE_ROWS, model_dir, benchmark_version="1.2.0")

    out = write_aggregate_results(model_dir)
    assert out == tmp_path / "all_results.json"
    loaded = json.loads(out.read_text())
    assert len(loaded) == 2


def test_detect_transcripts_dir_from_model_results_file(tmp_path: Path) -> None:
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()
    model_dir = tmp_path / "model_results"
    written = write_model_results(SAMPLE_ROWS, model_dir, benchmark_version="1.2.0")

    assert detect_transcripts_dir(written[0]) == transcripts_dir
