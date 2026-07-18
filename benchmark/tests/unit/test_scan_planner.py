from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from invisiblebench.api import CostBudgetExceededError
from invisiblebench.evaluation.check_registry import check_definition_hashes
from invisiblebench.evaluation.mode_engine import ModeEngineOutput
from invisiblebench.judge import (
    REPO_ROOT,
    attach_scan_provenance,
    scan_run,
    transcripts_for_run,
    write_outputs,
)
from invisiblebench.utils.manifest import scenario_corpus_hash
from scripts.run_scan import (
    DEFAULT_SCAN_OUTPUT_ROOT,
    _create_output_dir,
    apply_scan_profile,
    build_scan_plan,
    load_scan_profile,
)


def test_default_scan_output_root_uses_safety_care_namespace() -> None:
    assert DEFAULT_SCAN_OUTPUT_ROOT == (
        Path(__file__).resolve().parents[3] / "results" / "safety_care_scan"
    )
    assert "v3_scan" not in DEFAULT_SCAN_OUTPUT_ROOT.parts


def test_scan_output_directory_avoids_same_second_collisions(tmp_path: Path) -> None:
    first = _create_output_dir(tmp_path)
    second = _create_output_dir(tmp_path)

    assert first != second
    assert first.parent == second.parent == tmp_path


def test_scan_provenance_pins_exact_transcripts_and_behavior_contract(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run_1"
    transcript = run_dir / "transcripts" / "model_s1.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"role":"assistant","content":"hello"}\n')
    manifest = {
        "schema": "invisiblebench-run-manifest/v2",
        "run_id": "run-id",
        "git_sha": "a" * 40,
        "git_dirty": False,
        "benchmark_version": "4.0.0",
        "scenario_hash": scenario_corpus_hash(REPO_ROOT),
        "scenario_ids": ["s1"],
        "scoring_config_hash": hashlib.sha256(
            (REPO_ROOT / "benchmark" / "configs" / "scoring.yaml").read_bytes()
        ).hexdigest(),
        "check_definition_hashes": check_definition_hashes(),
        "model_ids": ["provider/model"],
        "harness": "llm",
        "mode": "raw",
        "transcript_policy": {
            "system_prompt_hash": "c" * 64,
            "temperature": 0.7,
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest))
    (run_dir / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "run_id": "run-id",
                "status": "complete",
                "model_ids": ["provider/model"],
                "expected_transcripts": 1,
                "transcript_count": 1,
                "error_count": 0,
                "missing_count": 0,
                "resolved_model_ids": ["provider/model-version"],
                "resolved_providers": ["provider"],
                "transcripts": [
                    {
                        "model_id": "provider/model",
                        "scenario_id": "s1",
                        "transcript_path": "transcripts/model_s1.jsonl",
                    }
                ],
            }
        )
    )

    plan = attach_scan_provenance(
        {"profile": "publish", "judge_model": "openai/gpt-5-mini"},
        run_dirs=[run_dir],
        transcript_pairs=[
            {
                "model_id": "provider/model",
                "scenario_id": "s1",
                "transcript_path": transcript,
            }
        ],
    )

    assert plan["schema"] == "invisiblebench-scan-plan/v2"
    assert plan["provenance_complete"] is True
    assert plan["model_ids"] == ["provider/model"]
    assert plan["scenario_ids"] == ["s1"]
    assert len(plan["comparability_fingerprint"]) == 64
    assert len(plan["scenario_corpus_sha256"]) == 64
    assert len(plan["scoring_config_sha256"]) == 64
    assert len(plan["transcript_hashes"][0]["sha256"]) == 64
    assert plan["source_runs"][0]["artifact_id"] == "run_1"
    assert str(tmp_path) not in json.dumps(plan)

    summary_path = run_dir / "transcript_run.json"
    summary = json.loads(summary_path.read_text())
    summary["status"] = "partial"
    summary_path.write_text(json.dumps(summary))
    incomplete = attach_scan_provenance(
        {"profile": "publish", "judge_model": "openai/gpt-5-mini"},
        run_dirs=[run_dir],
        transcript_pairs=[
            {
                "model_id": "provider/model",
                "scenario_id": "s1",
                "transcript_path": transcript,
            }
        ],
    )
    assert incomplete["provenance_complete"] is False


def test_scan_provenance_marks_old_source_manifest_incomplete(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_1"
    transcript = run_dir / "transcripts" / "model_s1.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"role":"assistant","content":"hello"}\n')
    (run_dir / "run_manifest.json").write_text(json.dumps({"run_id": "old"}))

    plan = attach_scan_provenance(
        {"profile": "publish", "judge_model": "openai/gpt-5-mini"},
        run_dirs=[run_dir],
        transcript_pairs=[
            {
                "model_id": "provider/model",
                "scenario_id": "s1",
                "transcript_path": transcript,
            }
        ],
    )

    assert plan["provenance_complete"] is False


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
    assert plan["base_llm_calls"] == 1
    assert plan["conditional_llm_calls"] == 1
    assert plan["planned_llm_calls"] == 2
    assert plan["by_mode"]["crisis.passive-ideation"]["planned_llm_calls"] == 1
    assert plan["by_mode"]["identity.human-claim"]["base_llm_calls"] == 0
    assert plan["by_mode"]["identity.human-claim"]["conditional_llm_calls"] == 1
    assert plan["by_mode"]["identity.human-claim"]["planned_llm_calls"] == 1


def test_publish_scan_profile_adds_unclear_tiebreak_budget() -> None:
    modes = {
        "attunement.infodump": {
            "id": "attunement.infodump",
            "layer": "care",
            "dimension": "attunement",
            "severity": "S2",
            "scope": "universal",
        }
    }
    routing = {"attunement.infodump": {"route": "llm_primary", "repetitions": 3}}
    profile = load_scan_profile("publish")

    filtered_modes, filtered_routing = apply_scan_profile(modes, routing, profile)
    plan = build_scan_plan(
        [{"scenario_id": "s1"}],
        filtered_modes,
        filtered_routing,
        profile,
        judge_model="openai/gpt-5-mini",
        llm_enabled=True,
    )

    assert filtered_routing["attunement.infodump"]["repetitions"] == 3
    assert filtered_routing["attunement.infodump"]["unclear_tiebreak_repetitions"] == 2
    assert filtered_routing["attunement.infodump"]["unclear_adjudication_repetitions"] == 3
    assert plan["base_llm_calls"] == 3
    assert plan["conditional_llm_calls"] == 0
    assert plan["budget_llm_calls"] == 8
    assert plan["planned_llm_calls"] == 8
    assert plan["by_mode"]["attunement.infodump"]["planned_llm_calls"] == 8
    assert plan["estimated_base_cost_usd"] == pytest.approx(0.015)
    assert plan["estimated_budget_cost_usd"] == pytest.approx(0.04)
    assert plan["estimated_cost_usd"] == plan["estimated_budget_cost_usd"]
    assert plan["maximum_reasonable_cost_ceiling_usd"] == pytest.approx(1.04)


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
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_scan.py",
            "--output-root",
            str(tmp_path / "scan_out"),
            str(transcripts_dir),
        ],
    )

    rc = run_scan_mod.main()

    # scan_run must have been called with the parent run dir, not transcripts/.
    assert observed_run_dirs, "scan_run was never called"
    assert observed_run_dirs[0] == run_dir, (
        f"Expected run dir {run_dir}, got {observed_run_dirs[0]}"
    )
    # When scan_run returns nothing, main exits with code 3 (no transcripts scanned).
    assert rc == 3


def test_run_scan_enable_llm_aborts_when_api_client_init_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--enable-llm must fail closed when the API client cannot initialize.

    Continuing without a client silently downgrades the scan: every eligible
    LLM check resolves NOT_APPLICABLE and the degradation only surfaces as a
    log line. An explicitly requested live LLM scan aborts instead; --dry-run
    still plans without a client.
    """
    run_dir = tmp_path / "run_20260612_192912"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text("{}")
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir()
    (transcripts_dir / "dummy.jsonl").write_text('{"role":"user","content":"hi"}\n')

    import scripts.run_scan as run_scan_mod

    def _failing_client():
        raise ValueError("OPENROUTER_API_KEY not set")

    scan_calls: list[Path] = []

    def _stub_scan_run(rd, *args, **kwargs):
        scan_calls.append(rd)
        return [], []

    monkeypatch.setattr(run_scan_mod, "ModelAPIClient", _failing_client)
    monkeypatch.setattr(run_scan_mod, "scan_run", _stub_scan_run)

    monkeypatch.setattr(sys, "argv", ["run_scan.py", "--enable-llm", str(run_dir)])
    assert run_scan_mod.main() == 2
    assert not scan_calls, "live scan must abort before scanning any transcript"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_scan.py",
            "--enable-llm",
            "--dry-run",
            "--output-root",
            str(tmp_path / "scan_out"),
            str(run_dir),
        ],
    )
    assert run_scan_mod.main() == 0
    assert not scan_calls, "dry-run must not invoke scan_run"


def test_scan_run_skips_checkpointed_rows_and_reports_each_completed_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from invisiblebench import judge as judge_module

    pairs = [
        {"model_id": "provider/model", "scenario_id": "s1"},
        {"model_id": "provider/model", "scenario_id": "s2"},
    ]
    output = ModeEngineOutput(overall_score=1.0, hard_fail=False)

    monkeypatch.setattr(judge_module, "transcripts_for_run", lambda _run_dir: pairs)
    monkeypatch.setattr(
        judge_module,
        "_scan_pair",
        lambda pair, *_args: ({**pair, **output.to_dict()}, output),
    )
    completed: list[tuple[str, str]] = []

    records, outputs = scan_run(
        tmp_path,
        object(),
        skip_keys={("provider/model", "s1")},
        progress_callback=lambda record, _output: completed.append(
            (record["model_id"], record["scenario_id"])
        ),
    )

    assert [record["scenario_id"] for record in records] == ["s2"]
    assert outputs == [output]
    assert completed == [("provider/model", "s2")]


def test_run_scan_preserves_and_resumes_completed_rows_after_cost_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.run_scan as run_scan_mod

    run_dir = tmp_path / "run_20260710_000000"
    transcripts = run_dir / "transcripts"
    transcripts.mkdir(parents=True)
    (transcripts / "test_model_context_regulatory_data_privacy_001.jsonl").write_text(
        '{"turn":1,"role":"user","content":"help"}\n'
        '{"turn":1,"role":"assistant","content":"ok"}\n'
    )
    output_root = tmp_path / "scan_out"

    class _FakeClient:
        pass

    mode_output = ModeEngineOutput(overall_score=1.0, hard_fail=False)
    record = {
        "model": "Test Model",
        "model_id": "test/model",
        "scenario_id": "context_regulatory_data_privacy_001",
        "category": "context",
        "transcript_path": str(next(transcripts.iterdir())),
        **mode_output.to_dict(),
    }

    def _capped_scan(*_args, progress_callback, **_kwargs):
        progress_callback(record, mode_output)
        raise CostBudgetExceededError("test ceiling")

    monkeypatch.setattr(run_scan_mod, "ModelAPIClient", _FakeClient)
    monkeypatch.setattr(run_scan_mod, "scan_run", _capped_scan)
    base_args = [
        "run_scan.py",
        "--enable-llm",
        "--max-cost-usd",
        "1",
        "--output-root",
        str(output_root),
        str(run_dir),
    ]
    monkeypatch.setattr(sys, "argv", base_args)

    assert run_scan_mod.main() == 4
    [scan_dir] = list(output_root.iterdir())
    state = json.loads((scan_dir / run_scan_mod.CHECKPOINT_FILENAME).read_text())
    assert state["status"] == "cost_ceiling"
    assert state["completed_rows"] == 1
    assert (scan_dir / run_scan_mod.PARTIAL_FILENAME).exists()

    def _resumed_scan(*_args, skip_keys, **_kwargs):
        assert skip_keys == {("test/model", "context_regulatory_data_privacy_001")}
        return [], []

    monkeypatch.setattr(run_scan_mod, "scan_run", _resumed_scan)
    monkeypatch.setattr(sys, "argv", [*base_args, "--resume", str(scan_dir)])

    assert run_scan_mod.main() == 0
    state = json.loads((scan_dir / run_scan_mod.CHECKPOINT_FILENAME).read_text())
    assert state["status"] == "complete"
    assert state["completed_rows"] == 1
    assert not (scan_dir / run_scan_mod.PARTIAL_FILENAME).exists()
    assert len((scan_dir / "per_run.jsonl").read_text().splitlines()) == 1


def test_live_llm_scan_requires_explicit_cost_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.run_scan as run_scan_mod

    run_dir = tmp_path / "run_20260710_000000"
    transcripts = run_dir / "transcripts"
    transcripts.mkdir(parents=True)
    transcript = transcripts / (
        "test_model_context_regulatory_data_privacy_001.jsonl"
    )
    transcript.write_text(
        '{"turn":1,"role":"user","content":"help"}\n'
        '{"turn":1,"role":"assistant","content":"ok"}\n'
    )

    class _FakeClient:
        pass

    scan_called = False

    def _unexpected_scan(*args, **kwargs):
        nonlocal scan_called
        scan_called = True
        return [], []

    monkeypatch.setattr(run_scan_mod, "ModelAPIClient", _FakeClient)
    monkeypatch.setattr(run_scan_mod, "scan_run", _unexpected_scan)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_scan.py", "--enable-llm", str(run_dir)],
    )

    assert run_scan_mod.main() == 2
    assert scan_called is False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_scan.py",
            "--enable-llm",
            "--max-cost-usd",
            "1000000",
            str(run_dir),
        ],
    )
    assert run_scan_mod.main() == 2
    assert scan_called is False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_scan.py",
            "--enable-llm",
            "--max-cost-usd",
            "0",
            str(run_dir),
        ],
    )
    assert run_scan_mod.main() == 2
    assert scan_called is False


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
        cost_snapshot={
            "total": 0.012345,
            "calls": 3,
            "by_model": {"openai/gpt-5-mini": 0.012345},
        },
    )

    summary = (output_dir / "summary.md").read_text()
    assert "LLM-dependent modes ran for routes included in the selected scan profile." in summary
    assert "no api_client wired" not in summary
    assert "Per-model raw/internal hard-fail compatibility rates" in summary
    assert "public Safety/Care output remains `safety-care/v1`" in summary
    assert "Actual verifier cost: $0.0123" in summary

    cost_report = json.loads((output_dir / "cost_report.json").read_text())
    assert cost_report["actual_cost_usd"] == 0.012345
    assert cost_report["actual_billable_api_calls"] == 3

    per_model_rates = json.loads((output_dir / "per_model_rates.json").read_text())
    assert per_model_rates["M"]["result_surface"] == "raw/internal"
    assert per_model_rates["M"]["score_model"] == "raw-diagnostic/v1"
    assert per_model_rates["M"]["public_score_model"] == "safety-care/v1"

    per_run = (output_dir / "per_run.jsonl").read_text().strip()
    row = json.loads(per_run)
    assert row["result_surface"] == "raw/internal"
    assert row["score_model"] == "raw-diagnostic/v1"
    assert row["public_score_model"] == "safety-care/v1"
