from __future__ import annotations

import json
from pathlib import Path

from invisiblebench.utils.verifier_corpus import (
    build_verifier_corpus_manifest,
    build_verifier_corpus_summary,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


class TestVerifierCorpusManifest:
    def test_build_manifest_resolves_transcripts_and_detail_rewrites(self, tmp_path: Path) -> None:
        leaderboard_dir = tmp_path / "results" / "leaderboard_ready"
        transcript_dir_main = tmp_path / "results" / "run_20260330_130332" / "transcripts"
        transcript_dir_partial = (
            tmp_path / "results" / "partial_runs" / "run_20260330_033649_up_to_deepseek" / "transcripts"
        )
        scenario_results_dir = (
            tmp_path / "results" / "partial_runs" / "run_20260330_033649_up_to_deepseek" / "scenario_results"
        )

        transcript_dir_main.mkdir(parents=True)
        transcript_dir_partial.mkdir(parents=True)
        scenario_results_dir.mkdir(parents=True)

        (transcript_dir_main / "openai_gpt-5.4_tier1_scope_honesty_001.jsonl").write_text("{}\n")
        (
            transcript_dir_partial / "google_gemini-3.1-pro-preview_tier1_scope_honesty_001.jsonl"
        ).write_text("{}\n")
        (
            scenario_results_dir / "openai_gpt-5.4_tier1_scope_honesty_001.json"
        ).write_text("{}\n")

        _write_json(
            leaderboard_dir / "GPT-5.4.json",
            {
                "model": "GPT-5.4",
                "model_id": "openai/gpt-5.4",
                "provider": None,
                "scenarios": [
                    {
                        "scenario": "Scope Honesty",
                        "scenario_id": "tier1_scope_honesty_001",
                        "category": "context",
                        "overall_score": 0.5,
                        "status": "pass",
                        "success": True,
                        "hard_fail": False,
                        "hard_fail_reasons": [],
                        "judge_model": "judge-a",
                        "contract_version": "2.1.0",
                        "detail_json": "results/run_20260330_033649/scenario_results/openai_gpt-5.4_tier1_scope_honesty_001.json",
                        "detail_html": "results/run_20260330_033649/reports/openai_gpt-5.4_tier1_scope_honesty_001.html",
                    }
                ],
            },
        )
        _write_json(
            leaderboard_dir / "Gemini_3.1_Pro.json",
            {
                "model": "Gemini 3.1 Pro",
                "model_id": "google/gemini-3.1-pro",
                "provider": None,
                "scenarios": [
                    {
                        "scenario": "Scope Honesty",
                        "scenario_id": "tier1_scope_honesty_001",
                        "category": "context",
                        "overall_score": 0.0,
                        "status": "error",
                        "success": False,
                        "hard_fail": True,
                        "hard_fail_reasons": ["Transcript generation failed"],
                        "judge_model": "judge-a",
                        "contract_version": "2.1.0",
                    }
                ],
            },
        )

        manifest = build_verifier_corpus_manifest(
            tmp_path,
            leaderboard_dir=Path("results/leaderboard_ready"),
            transcript_dirs=(
                Path("results/run_20260330_130332/transcripts"),
                Path("results/partial_runs/run_20260330_033649_up_to_deepseek/transcripts"),
            ),
        )

        assert len(manifest) == 2

        gpt_row = next(row for row in manifest if row["model"] == "GPT-5.4")
        assert gpt_row["transcript_found"] is True
        assert gpt_row["transcript_source_run"] == "run_20260330_130332"
        assert (
            gpt_row["detail_json_resolved"]
            == "results/partial_runs/run_20260330_033649_up_to_deepseek/scenario_results/openai_gpt-5.4_tier1_scope_honesty_001.json"
        )
        assert gpt_row["detail_json_exists"] is True
        assert gpt_row["detail_html_exists"] is False

        gemini_row = next(row for row in manifest if row["model"] == "Gemini 3.1 Pro")
        assert gemini_row["transcript_found"] is True
        assert gemini_row["transcript_path"].endswith(
            "google_gemini-3.1-pro-preview_tier1_scope_honesty_001.jsonl"
        )
        assert gemini_row["status"] == "error"

    def test_build_summary_aggregates_model_stats(self, tmp_path: Path) -> None:
        manifest = [
            {
                "model": "A",
                "transcript_found": True,
                "transcript_source_run": "run_a",
                "status": "pass",
                "hard_fail": False,
                "detail_json_exists": True,
                "detail_html_exists": False,
            },
            {
                "model": "A",
                "transcript_found": True,
                "transcript_source_run": "run_a",
                "status": "error",
                "hard_fail": True,
                "detail_json_exists": False,
                "detail_html_exists": False,
            },
            {
                "model": "B",
                "transcript_found": False,
                "transcript_source_run": None,
                "status": "fail",
                "hard_fail": True,
                "detail_json_exists": False,
                "detail_html_exists": False,
            },
        ]

        summary = build_verifier_corpus_summary(manifest)

        assert summary["traces"] == 3
        assert summary["models"] == 2
        assert summary["transcripts_found"] == 2
        assert summary["error_rows"] == 1
        assert summary["hard_fails"] == 2

        model_a = next(row for row in summary["models_by_name"] if row["model"] == "A")
        assert model_a["traces"] == 2
        assert model_a["transcripts_found"] == 2
        assert model_a["error_rows"] == 1
        assert model_a["source_runs"] == ["run_a"]
