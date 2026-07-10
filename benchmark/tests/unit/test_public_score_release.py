from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from delivery.build_public_score_release import build_release


def _write_scan(root: Path, *, unclear: bool = False) -> Path:
    root.mkdir()
    scan = root / "per_run.jsonl"
    rows = []
    for model_id in ("provider/model-a", "provider/model-b"):
        for scenario_id in ("s1", "s2"):
            rows.append(
                {
                    "model": model_id,
                    "model_id": model_id,
                    "scenario_id": scenario_id,
                    "category": "safety",
                    "transcript_path": f"/private/run/transcripts/{scenario_id}.jsonl",
                    "overall_score": 0.99,
                    "score_model": "legacy-internal",
                    "eligible_count": 1,
                    "resolved_count": 0 if unclear else 1,
                    "unclear_count": 1 if unclear else 0,
                    "coverage_rate": 0.0 if unclear else 1.0,
                    "engine_version": "mode-engine-v1",
                    "mode_results": [
                        {
                            "mode_id": "check.one",
                            "eligible": True,
                            "verdict": "UNCLEAR" if unclear else "PASS",
                            "severity": "S3",
                            "layer": "care",
                            "dimension": "attunement",
                            "scorer_type": "llm_verifier",
                            "confidence": 1.0,
                            "evidence": [
                                {
                                    "role": "assistant",
                                    "turn": 2,
                                    "quote": "Exact evidence",
                                    "rationale": None,
                                }
                            ],
                            "rationale_code": "specific_response",
                            "adjudication_required": False,
                            "scorer_version": "llm_verifier-v0.2",
                            "prompt_hash": "abc123",
                            "secondary_tags": ["tag"],
                            "extra": {
                                "repetitions": 3,
                                "all_verdicts": ["PASS", "PASS", "PASS"],
                                "private_future_field": "omit",
                            },
                        }
                    ],
                }
            )
    scan.write_text("".join(json.dumps(row) + "\n" for row in rows))
    digest = hashlib.sha256(scan.read_bytes()).hexdigest()
    (root / "merge_manifest.json").write_text(
        json.dumps(
            {
                "schema": "invisiblebench-scan-merge/v1",
                "benchmark_version": "4.0.0",
                "result_contract_version": "2.1.0",
                "profile": "publish",
                "judge_model": "openai/gpt-5-mini",
                "model_count": 2,
                "scenario_count": 2,
                "row_count": 4,
                "actual_cost_usd": 2.5,
                "actual_billable_api_calls": 40,
                "output_file": scan.name,
                "output_sha256": digest,
                "sources": [],
            }
        )
    )
    return scan


def test_public_score_release_is_complete_auditable_and_allowlisted(tmp_path: Path) -> None:
    scan = _write_scan(tmp_path / "scan")
    output = tmp_path / "public"

    manifest_path = build_release(
        scan_path=scan,
        output_dir=output,
        expected_scenario_ids={"s1", "s2"},
        expected_mode_ids={"check.one"},
        benchmark_version="4.0.0",
        result_contract_version="2.1.0",
        claim_ready_check_count=0,
    )

    manifest = json.loads(manifest_path.read_text())
    assert manifest["schema"] == "invisiblebench-score-evidence/v1"
    assert manifest["model_count"] == 2
    assert manifest["scenario_count"] == 2
    assert manifest["row_count"] == 4
    assert manifest["mode_result_count"] == 4
    assert manifest["claim_posture"] == "research_evidence_only"
    assert manifest["source_scan_sha256"] == hashlib.sha256(scan.read_bytes()).hexdigest()

    bundle_path = output / manifest["models"][0]["file"]
    bundle = json.loads(bundle_path.read_text())
    assert bundle["rows"][0]["mode_results"][0]["evidence"][0]["quote"] == "Exact evidence"
    assert bundle["rows"][0]["mode_results"][0]["extra"] == {
        "repetitions": 3,
        "all_verdicts": ["PASS", "PASS", "PASS"],
    }
    serialized = bundle_path.read_text()
    assert "overall_score" not in serialized
    assert "score_model" not in serialized
    assert "transcript_path" not in serialized
    assert "/private/" not in serialized
    assert "private_future_field" not in serialized
    assert hashlib.sha256(bundle_path.read_bytes()).hexdigest() == manifest["models"][0]["sha256"]


def test_public_score_release_rejects_unresolved_rows(tmp_path: Path) -> None:
    scan = _write_scan(tmp_path / "scan", unclear=True)

    with pytest.raises(ValueError, match="unresolved verdict"):
        build_release(
            scan_path=scan,
            output_dir=tmp_path / "public",
            expected_scenario_ids={"s1", "s2"},
            expected_mode_ids={"check.one"},
            benchmark_version="4.0.0",
            result_contract_version="2.1.0",
            claim_ready_check_count=0,
        )
