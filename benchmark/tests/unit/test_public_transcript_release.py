from __future__ import annotations

import json
from pathlib import Path

import pytest

from delivery.build_public_transcript_release import build_release


def _write_run(
    root: Path,
    *,
    name: str,
    model_id: str,
    model_name: str,
    scenario_ids: list[str],
    scenario_hash: str = "corpus-hash",
) -> Path:
    run_dir = root / name
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)
    entries = []
    for scenario_id in scenario_ids:
        transcript_path = transcripts_dir / f"{model_id.replace('/', '_')}_{scenario_id}.jsonl"
        transcript_path.write_text(
            json.dumps({"turn": 1, "role": "user", "content": f"prompt {scenario_id}"})
            + "\n"
            + json.dumps(
                {
                    "turn": 1,
                    "role": "assistant",
                    "content": f"reply {scenario_id}",
                    "provider_request_id": "private-id",
                }
            )
            + "\n"
        )
        entries.append(
            {
                "model": model_name,
                "model_id": model_id,
                "scenario": f"Scenario {scenario_id}",
                "scenario_id": scenario_id,
                "category": "safety",
                "transcript_path": str(transcript_path.relative_to(run_dir)),
            }
        )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": f"uuid-{name}",
                "git_sha": "benchmark-sha",
                "scenario_hash": scenario_hash,
                "model_ids": [model_id],
                "run_date": "2026-07-10T00:00:00+00:00",
                "benchmark_version": "4.0.0",
                "contract_version": "3.2.0",
            }
        )
    )
    (run_dir / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "benchmark_version": "4.0.0",
                "transcript_count": len(entries),
                "transcripts": entries,
            }
        )
    )
    return run_dir


def test_build_release_emits_complete_hashed_bundles_without_local_paths(tmp_path: Path) -> None:
    model_a_main = _write_run(
        tmp_path,
        name="run_a_main",
        model_id="provider/model-a",
        model_name="Model A",
        scenario_ids=["s1"],
    )
    model_a_recovery = _write_run(
        tmp_path,
        name="run_a_recovery",
        model_id="provider/model-a",
        model_name="Model A",
        scenario_ids=["s2"],
    )
    model_b = _write_run(
        tmp_path,
        name="run_b",
        model_id="provider/model-b",
        model_name="Model B",
        scenario_ids=["s1", "s2"],
    )
    output = tmp_path / "release"

    manifest_path = build_release(
        sources={
            "provider/model-a": [model_a_main, model_a_recovery],
            "provider/model-b": [model_b],
        },
        output_dir=output,
        expected_scenario_ids=["s1", "s2"],
        benchmark_version="4.0.0",
        result_contract_version="2.1.0",
    )

    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema"] == "invisiblebench-transcripts/v1"
    assert manifest["benchmark_version"] == "4.0.0"
    assert manifest["scenario_hash"] == "corpus-hash"
    assert manifest["model_count"] == 2
    assert manifest["scenario_count"] == 2
    assert manifest["transcript_count"] == 4
    assert manifest["claim_posture"] == "descriptive_evidence_only"
    assert manifest["synthetic_scenarios"] is True
    assert "unverified model outputs" in manifest["content_notice"]
    assert [model["model_id"] for model in manifest["models"]] == [
        "provider/model-a",
        "provider/model-b",
    ]
    assert manifest["models"][0]["source_runs"] == [
        {
            "artifact_id": "run_a_main",
            "manifest_run_id": "uuid-run_a_main",
            "benchmark_version": "4.0.0",
            "git_sha": "benchmark-sha",
            "run_date": "2026-07-10T00:00:00+00:00",
            "model_actual_cost_usd": None,
            "run_actual_cost_usd": None,
            "run_actual_billable_api_calls": None,
            "runtime_cost_ceiling_usd": None,
        },
        {
            "artifact_id": "run_a_recovery",
            "manifest_run_id": "uuid-run_a_recovery",
            "benchmark_version": "4.0.0",
            "git_sha": "benchmark-sha",
            "run_date": "2026-07-10T00:00:00+00:00",
            "model_actual_cost_usd": None,
            "run_actual_cost_usd": None,
            "run_actual_billable_api_calls": None,
            "runtime_cost_ceiling_usd": None,
        },
    ]

    bundle_path = output / manifest["models"][0]["file"]
    bundle = json.loads(bundle_path.read_text())
    assert bundle["synthetic_scenarios"] is True
    assert bundle["content_notice"] == manifest["content_notice"]
    assert [row["scenario_id"] for row in bundle["transcripts"]] == ["s1", "s2"]
    assert len(bundle["transcripts"][0]["sha256"]) == 64
    assert bundle["transcripts"][0]["turns"][1]["content"] == "reply s1"
    assert "provider_request_id" not in bundle["transcripts"][0]["turns"][1]
    assert str(tmp_path) not in manifest_path.read_text()
    assert str(tmp_path) not in bundle_path.read_text()
    assert manifest["models"][0]["sha256"]
    assert manifest["models"][0]["bytes"] == bundle_path.stat().st_size


def test_build_release_rejects_incomplete_model_coverage(tmp_path: Path) -> None:
    run_dir = _write_run(
        tmp_path,
        name="run_incomplete",
        model_id="provider/model-a",
        model_name="Model A",
        scenario_ids=["s1"],
    )

    with pytest.raises(ValueError, match="scenario coverage mismatch"):
        build_release(
            sources={"provider/model-a": [run_dir]},
            output_dir=tmp_path / "release",
            expected_scenario_ids={"s1", "s2"},
            benchmark_version="4.0.0",
            result_contract_version="2.1.0",
        )


def test_build_release_rejects_mixed_corpus_hashes(tmp_path: Path) -> None:
    run_a = _write_run(
        tmp_path,
        name="run_a",
        model_id="provider/model-a",
        model_name="Model A",
        scenario_ids=["s1"],
        scenario_hash="hash-a",
    )
    run_b = _write_run(
        tmp_path,
        name="run_b",
        model_id="provider/model-b",
        model_name="Model B",
        scenario_ids=["s1"],
        scenario_hash="hash-b",
    )

    with pytest.raises(ValueError, match="mixed scenario hashes"):
        build_release(
            sources={"provider/model-a": [run_a], "provider/model-b": [run_b]},
            output_dir=tmp_path / "release",
            expected_scenario_ids={"s1"},
            benchmark_version="4.0.0",
            result_contract_version="2.1.0",
        )
