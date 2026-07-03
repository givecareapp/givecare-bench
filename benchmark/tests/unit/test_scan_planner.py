from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from invisiblebench.evaluation.mode_engine import ModeEngineOutput
from invisiblebench.judge import transcripts_for_run, write_outputs
from scripts.run_scan import (
    DEFAULT_SCAN_OUTPUT_ROOT,
    apply_scan_profile,
    build_scan_plan,
    load_scan_profile,
)


def test_default_scan_output_root_uses_safety_care_namespace() -> None:
    assert DEFAULT_SCAN_OUTPUT_ROOT == (
        Path(__file__).resolve().parents[3] / "results" / "safety_care_scan"
    )
    assert "v3_scan" not in DEFAULT_SCAN_OUTPUT_ROOT.parts


def test_scan_profile_filters_modes_and_overrides_repetitions() -> None:
    modes = {
        "crisis.passive-ideation": {
            "id": "crisis.passive-ideation",
            "layer": "safety",
            "dimension": "crisis",
            "severity": "S5",
            "scope": "trigger",
            "eligibility": {"scenario_tags_any": ["passive_ideation"]},
        },
        "belonging.self-diminishment": {
            "id": "belonging.self-diminishment",
            "layer": "care",
            "dimension": "belonging",
            "severity": "S2",
            "scope": "universal",
        },
    }
    routing = {
        "crisis.passive-ideation": {"route": "hybrid_llm", "repetitions": 3},
        "belonging.self-diminishment": {"route": "llm_primary", "repetitions": 3},
    }
    profile = load_scan_profile("dev")
    assert profile["include_dimensions"] == {"crisis", "scope", "identity"}
    assert "include_legacy_buckets" not in profile

    filtered_modes, filtered_routing = apply_scan_profile(modes, routing, profile)

    assert set(filtered_modes) == {"crisis.passive-ideation"}
    assert filtered_routing["crisis.passive-ideation"]["repetitions"] == 1
    assert filtered_routing["crisis.passive-ideation"]["adaptive_repetitions"] is True


def test_build_scan_plan_counts_profiled_llm_calls() -> None:
    modes = {
        "crisis.passive-ideation": {
            "id": "crisis.passive-ideation",
            "layer": "safety",
            "dimension": "crisis",
            "severity": "S5",
            "scope": "trigger",
            "eligibility": {"scenario_tags_any": ["passive_ideation"]},
        },
        "identity.human-claim": {
            "id": "identity.human-claim",
            "layer": "safety",
            "dimension": "identity",
            "severity": "S4_GATE",
            "scope": "universal",
        },
    }
    routing = {
        "crisis.passive-ideation": {"route": "hybrid_llm", "repetitions": 1},
        "identity.human-claim": {"route": "regex_with_llm_edge", "repetitions": 1},
    }
    profile = load_scan_profile("full")

    plan = build_scan_plan(
        [{"scenario_id": "s1", "failure_mode_tags": ["passive_ideation"]}],
        modes,
        routing,
        profile,
        judge_model="google/gemini-2.5-flash-lite",
        llm_enabled=True,
    )

    assert plan["transcript_count"] == 1
    assert plan["eligible_checks"] == 2
    assert plan["planned_llm_calls"] == 1
    assert plan["by_mode"]["crisis.passive-ideation"]["planned_llm_calls"] == 1
    assert plan["by_mode"]["identity.human-claim"]["planned_llm_calls"] == 0


def test_run_scan_normalizes_transcripts_subdir_to_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_scan.py must accept a transcripts/ subdir as input and silently
    redirect to the parent run dir.  We verify this by patching scan_run and
    checking the run_dir it receives is the parent, not the transcripts/ subdir.
    """
    run_dir = tmp_path / "run_20260612_192912"
    run_dir.mkdir()
    # Create a marker that makes the parent look like a run dir.
    (run_dir / "run_manifest.json").write_text("{}")
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir()

    # Put one real transcript in transcripts/ so scan_run would have something.
    (transcripts_dir / "dummy.jsonl").write_text(
        '{"role":"user","content":"hi"}\n'
    )

    import scripts.run_scan as run_scan_mod

    observed_run_dirs: list[Path] = []

    def _stub_scan_run(rd, *args, **kwargs):
        observed_run_dirs.append(rd)
        return [], []

    monkeypatch.setattr(run_scan_mod, "scan_run", _stub_scan_run)
    monkeypatch.setattr(sys, "argv", ["run_scan.py", str(transcripts_dir)])

    rc = run_scan_mod.main()

    # scan_run must have been called with the parent run dir, not transcripts/.
    assert observed_run_dirs, "scan_run was never called"
    assert observed_run_dirs[0] == run_dir, (
        f"Expected run dir {run_dir}, got {observed_run_dirs[0]}"
    )
    # When scan_run returns nothing, main exits with code 3 (no transcripts scanned).
    assert rc == 3


def test_transcripts_for_run_infers_scenario_from_known_suffix_without_results(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run_20260701_230329"
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)
    transcript = (
        transcripts_dir
        / "nvidia_nemotron-3-super-120b-a12b_context_regulatory_data_privacy_001.jsonl"
    )
    transcript.write_text('{"turn":1,"role":"user","content":"hi"}\n')

    pairs = transcripts_for_run(run_dir)

    assert len(pairs) == 1
    assert pairs[0]["scenario_id"] == "context_regulatory_data_privacy_001"
    assert pairs[0]["category"] == "context"
    assert pairs[0]["model_id"] == "nvidia/nemotron-3-super-120b-a12b"
    assert pairs[0]["model"] == "Nemotron 3 Super 120B"


def test_transcripts_for_run_uses_transcript_stage_artifact_when_present(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run_20260703_010101"
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir(parents=True)
    ready = transcripts_dir / "test_model_context_regulatory_data_privacy_001.jsonl"
    error = transcripts_dir / "test_model_context_regulatory_data_privacy_002.jsonl"
    ready.write_text('{"turn":1,"role":"user","content":"hi"}\n')
    error.write_text('{"turn":1,"role":"assistant","content":"[ERROR: timeout]","error":true}\n')
    (run_dir / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "status": "partial",
                "expected_transcripts": 2,
                "transcript_count": 1,
                "error_count": 1,
                "transcripts": [
                    {
                        "model": "Test Model",
                        "model_id": "test/model",
                        "scenario_id": "context_regulatory_data_privacy_001",
                        "category": "context",
                        "transcript_path": str(ready),
                    }
                ],
                "errors": [
                    {
                        "model": "Test Model",
                        "model_id": "test/model",
                        "scenario_id": "context_regulatory_data_privacy_002",
                        "category": "context",
                        "reason": "timeout",
                    }
                ],
            }
        )
    )

    pairs = transcripts_for_run(run_dir)

    assert len(pairs) == 1
    assert pairs[0]["transcript_path"] == ready
    assert pairs[0]["scenario_id"] == "context_regulatory_data_privacy_001"
    assert pairs[0]["model_id"] == "test/model"


def test_write_outputs_notes_when_llm_verifiers_are_enabled(tmp_path: Path) -> None:
    output_dir = tmp_path / "scan"
    run_dir = tmp_path / "run_1"
    out = ModeEngineOutput(
        overall_score=1.0,
        hard_fail=False,
        blindspot_profile={"diagnosis_overreach": False},
        eligible_count=1,
        resolved_count=1,
        unclear_count=0,
        coverage_rate=1.0,
    )

    write_outputs(
        output_dir,
        [{"model": "M", "scenario_id": "s1", **out.to_dict()}],
        [out],
        [run_dir],
        {
            "profile": "dev",
            "llm_enabled": True,
            "planned_llm_calls": 3,
            "estimated_cost_usd": 0.001,
        },
    )

    summary = (output_dir / "summary.md").read_text()
    assert "LLM-dependent modes ran for routes included in the selected scan profile." in summary
    assert "no api_client wired" not in summary
    assert "Per-model raw/internal hard-fail compatibility rates" in summary
    assert "public Safety/Care output remains `safety-care/v1`" in summary

    per_model_rates = json.loads((output_dir / "per_model_rates.json").read_text())
    assert per_model_rates["M"]["result_surface"] == "raw/internal"
    assert per_model_rates["M"]["score_model"] == "raw-diagnostic/v1"
    assert per_model_rates["M"]["public_score_model"] == "safety-care/v1"

    per_run = (output_dir / "per_run.jsonl").read_text().strip()
    row = json.loads(per_run)
    assert row["result_surface"] == "raw/internal"
    assert row["score_model"] == "raw-diagnostic/v1"
    assert row["public_score_model"] == "safety-care/v1"
