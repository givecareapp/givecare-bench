from __future__ import annotations

import json
from pathlib import Path

import pytest

from delivery.combine_scans import combine_scans


def _write_scan(
    root: Path,
    *,
    name: str,
    model_id: str,
    scenarios: list[str],
    judge_model: str = "openai/gpt-5-mini",
    cost: float = 1.25,
) -> Path:
    scan_dir = root / name
    scan_dir.mkdir()
    scan = scan_dir / "per_run.jsonl"
    scan.write_text(
        "".join(
            json.dumps(
                {
                    "model": model_id,
                    "model_id": model_id,
                    "scenario_id": scenario_id,
                    "transcript_path": f"/private/{name}/transcripts/{scenario_id}.jsonl",
                    "mode_results": [{"mode_id": "check.one"}],
                }
            )
            + "\n"
            for scenario_id in scenarios
        )
    )
    (scan_dir / "scan_plan.json").write_text(
        json.dumps({"profile": "publish", "judge_model": judge_model})
    )
    (scan_dir / "cost_report.json").write_text(
        json.dumps({"actual_cost_usd": cost, "actual_billable_api_calls": 10})
    )
    return scan


def test_combine_scans_writes_uniform_rows_and_hashed_lineage(tmp_path: Path) -> None:
    scan_a = _write_scan(
        tmp_path, name="scan_a", model_id="provider/model-a", scenarios=["s2", "s1"]
    )
    scan_b = _write_scan(
        tmp_path, name="scan_b", model_id="provider/model-b", scenarios=["s1", "s2"]
    )
    output = tmp_path / "combined" / "per_run.jsonl"

    manifest_path = combine_scans(
        inputs=[scan_a, scan_b],
        output=output,
        benchmark_version="4.0.0",
        result_contract_version="2.1.0",
    )

    rows = [json.loads(line) for line in output.read_text().splitlines()]
    manifest = json.loads(manifest_path.read_text())
    assert [(row["model_id"], row["scenario_id"]) for row in rows] == [
        ("provider/model-a", "s1"),
        ("provider/model-a", "s2"),
        ("provider/model-b", "s1"),
        ("provider/model-b", "s2"),
    ]
    assert manifest["schema"] == "invisiblebench-scan-merge/v1"
    assert manifest["benchmark_version"] == "4.0.0"
    assert manifest["result_contract_version"] == "2.1.0"
    assert manifest["profile"] == "publish"
    assert manifest["judge_model"] == "openai/gpt-5-mini"
    assert manifest["model_count"] == 2
    assert manifest["scenario_count"] == 2
    assert manifest["row_count"] == 4
    assert manifest["actual_cost_usd"] == 2.5
    assert len(manifest["output_sha256"]) == 64
    assert all(len(source["sha256"]) == 64 for source in manifest["sources"])
    assert [source["transcript_source_artifacts"] for source in manifest["sources"]] == [
        ["scan_a"],
        ["scan_b"],
    ]
    assert str(tmp_path) not in manifest_path.read_text()


def test_combine_scans_rejects_mismatched_scenario_coverage(tmp_path: Path) -> None:
    scan_a = _write_scan(
        tmp_path, name="scan_a", model_id="provider/model-a", scenarios=["s1", "s2"]
    )
    scan_b = _write_scan(
        tmp_path, name="scan_b", model_id="provider/model-b", scenarios=["s1"]
    )

    with pytest.raises(ValueError, match="scenario coverage mismatch"):
        combine_scans(
            inputs=[scan_a, scan_b],
            output=tmp_path / "out" / "per_run.jsonl",
            benchmark_version="4.0.0",
            result_contract_version="2.1.0",
        )


def test_combine_scans_rejects_mixed_judges(tmp_path: Path) -> None:
    scan_a = _write_scan(
        tmp_path, name="scan_a", model_id="provider/model-a", scenarios=["s1"]
    )
    scan_b = _write_scan(
        tmp_path,
        name="scan_b",
        model_id="provider/model-b",
        scenarios=["s1"],
        judge_model="other/judge",
    )

    with pytest.raises(ValueError, match="mixed judge_model"):
        combine_scans(
            inputs=[scan_a, scan_b],
            output=tmp_path / "out" / "per_run.jsonl",
            benchmark_version="4.0.0",
            result_contract_version="2.1.0",
        )


def test_combine_scans_rejects_missing_actual_cost(tmp_path: Path) -> None:
    scan_a = _write_scan(
        tmp_path, name="scan_a", model_id="provider/model-a", scenarios=["s1"]
    )
    scan_b = _write_scan(
        tmp_path, name="scan_b", model_id="provider/model-b", scenarios=["s1"]
    )
    (scan_b.parent / "cost_report.json").write_text(
        json.dumps({"actual_cost_usd": None, "actual_billable_api_calls": None})
    )

    with pytest.raises(ValueError, match="actual cost accounting"):
        combine_scans(
            inputs=[scan_a, scan_b],
            output=tmp_path / "out" / "per_run.jsonl",
            benchmark_version="4.0.0",
            result_contract_version="2.1.0",
        )
