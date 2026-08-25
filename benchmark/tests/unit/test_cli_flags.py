"""Contract tests for `--out` JSON file export and live-write approval gating.

These cover the agent-friendly CLI guarantees added in the April 2026 pass:
- `--out PATH` writes the full payload to disk and emits a summary envelope
- Disk-write failures emit `{status:"error", ...}` rather than raising
- Archive live writes refuse in non-interactive shells unless `--yes` is passed
- Read commands never prompt
- `archive` without `--before` or `--keep` exits 2

Tests monkeypatch the expensive bits (run collection, leaderboard)
so they run in the same process with no subprocess overhead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from invisiblebench.cli import run_command as run_command_mod
from invisiblebench.cli import runner as runner_mod

# -------------------- --out flag --------------------


def _fake_records() -> list[dict[str, Any]]:
    return [
        {
            "id": "run_20260101_000000",
            "date": "2026-01-01",
            "models": ["gpt-5.2"],
            "scenarios": 50,
            "size_mb": 1.23,
            "has_results": True,
        },
        {
            "id": "run_20260102_000000",
            "date": "2026-01-02",
            "models": ["claude"],
            "scenarios": 50,
            "size_mb": 0.99,
            "has_results": True,
        },
    ]


def test_out_flag_writes_payload_and_summary_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(runner_mod, "_collect_runs", _fake_records)

    out_path = tmp_path / "runs.json"
    rc = runner_mod._run_runs(
        limit=25, offset=0, json_output=True, out_path=str(out_path)
    )

    assert rc == 0
    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1, "exactly one envelope line on stdout"
    envelope = json.loads(stdout[0])
    assert envelope["status"] == "ok"
    assert envelope["command"] == "runs"
    assert envelope["data"]["record_count"] == 2
    assert envelope["data"]["byte_count"] > 0
    assert Path(envelope["data"]["path"]).exists()

    # File contains the full shape, not the summary
    on_disk = json.loads(out_path.read_text())
    assert on_disk["total"] == 2
    assert len(on_disk["runs"]) == 2
    assert on_disk["runs"][0]["id"] == "run_20260101_000000"


def test_out_flag_creates_parent_dirs(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(runner_mod, "_collect_runs", _fake_records)

    out_path = tmp_path / "nested" / "deeper" / "runs.json"
    rc = runner_mod._run_runs(
        limit=25, offset=0, json_output=True, out_path=str(out_path)
    )

    assert rc == 0
    assert out_path.exists()


def test_runs_json_classifies_manifest_only_artifacts(monkeypatch, tmp_path, capsys):
    from invisiblebench.cli import agent_commands

    run_dir = tmp_path / "run_20260702_010101"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(json.dumps({"run_id": "abc"}))
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: tmp_path)

    rc = runner_mod._run_runs(
        limit=25,
        offset=0,
        json_output=True,
    )

    assert rc == 0
    stdout = capsys.readouterr().out.strip().splitlines()
    envelope = json.loads(stdout[0])
    record = envelope["data"]["runs"][0]
    assert record["id"] == "run_20260702_010101"
    assert record["has_results"] is False
    assert record["artifact_state"] == "aborted_manifest_only"


def test_runs_json_classifies_transcript_only_artifacts(monkeypatch, tmp_path, capsys):
    from invisiblebench.cli import agent_commands

    run_dir = tmp_path / "run_20260702_020202"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "abc", "artifact_type": "transcript_run/v1"})
    )
    (run_dir / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "model_ids": ["test/model"],
                "expected_transcripts": 1,
                "transcript_count": 1,
                "error_count": 0,
                "missing_count": 0,
                "status": "complete",
            }
        )
    )
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: tmp_path)

    rc = runner_mod._run_runs(
        limit=25,
        offset=0,
        json_output=True,
    )

    assert rc == 0
    stdout = capsys.readouterr().out.strip().splitlines()
    envelope = json.loads(stdout[0])
    record = envelope["data"]["runs"][0]
    assert record["id"] == "run_20260702_020202"
    assert record["has_results"] is False
    assert record["artifact_state"] == "transcripts_ready"
    assert record["scenarios"] == 1


def test_runs_json_classifies_partial_transcript_artifacts(monkeypatch, tmp_path, capsys):
    from invisiblebench.cli import agent_commands

    run_dir = tmp_path / "run_20260702_030303"
    run_dir.mkdir()
    (run_dir / "run_manifest.json").write_text(
        json.dumps({"run_id": "abc", "artifact_type": "transcript_run/v1"})
    )
    (run_dir / "transcript_run.json").write_text(
        json.dumps(
            {
                "artifact_type": "transcript_run/v1",
                "model_ids": ["test/model"],
                "expected_transcripts": 2,
                "transcript_count": 1,
                "error_count": 0,
                "missing_count": 1,
                "status": "partial",
            }
        )
    )
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: tmp_path)

    rc = runner_mod._run_runs(
        limit=25,
        offset=0,
        json_output=True,
    )

    assert rc == 0
    stdout = capsys.readouterr().out.strip().splitlines()
    envelope = json.loads(stdout[0])
    record = envelope["data"]["runs"][0]
    assert record["id"] == "run_20260702_030303"
    assert record["has_results"] is False
    assert record["artifact_state"] == "transcripts_partial"
    assert record["scenarios"] == 1


def test_out_flag_unwritable_path_emits_error_envelope(monkeypatch, capsys):
    monkeypatch.setattr(runner_mod, "_collect_runs", _fake_records)

    # Force mkdir to fail deterministically
    def _raise(*a: Any, **kw: Any) -> None:
        raise PermissionError("simulated read-only fs")

    monkeypatch.setattr(Path, "mkdir", _raise)

    rc = runner_mod._run_runs(
        limit=25, offset=0, json_output=True, out_path="/tmp/nope/runs.json"
    )

    assert rc == 1
    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1
    envelope = json.loads(stdout[0])
    assert envelope["status"] == "error"
    assert envelope["command"] == "runs"
    assert "failed to write" in envelope["error"]


# -------------------- write-approval gating --------------------


@pytest.fixture
def force_noninteractive(monkeypatch):
    """Simulate a non-interactive shell so confirm_or_abort must refuse."""
    from invisiblebench import _agent_cli

    monkeypatch.setattr(_agent_cli, "is_tty", lambda: False)


def test_benchmark_dry_run_does_not_create_run_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "dry_run_should_not_exist"

    rc = run_command_mod.run_benchmark(
        models=[
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
        output_dir=output_dir,
        dry_run=True,
        auto_confirm=False,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 0
    assert not output_dir.exists()


def test_benchmark_noninteractive_without_yes_refuses_cleanly(
    tmp_path: Path,
    monkeypatch,
    capsys,
    force_noninteractive,
) -> None:
    """B-24: a non-interactive run without --yes refuses via confirm_or_abort
    (clean "[refused] ... pass --yes" message, exit 2) instead of crashing on
    a bare input() EOFError."""
    output_dir = tmp_path / "noninteractive_should_not_exist"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    with pytest.raises(SystemExit) as exc_info:
        run_command_mod.run_benchmark(
            models=[
                {
                    "id": "test/model",
                    "name": "Test Model",
                    "cost_per_m_input": 1.0,
                    "cost_per_m_output": 1.0,
                }
            ],
            output_dir=output_dir,
            dry_run=False,
            auto_confirm=False,
            max_cost_usd=1.0,
            scenario_filter=["context_regulatory_data_privacy_001"],
        )

    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "--yes" in err
    assert not output_dir.exists()


def test_benchmark_decline_exits_130(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """B-24: declining the confirm_or_abort prompt now exits 130 (matching
    archive's own prompt), not the old bare-input() "Cancelled" exit 0."""
    from invisiblebench import _agent_cli

    output_dir = tmp_path / "declined_should_not_exist"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(_agent_cli, "is_tty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    with pytest.raises(SystemExit) as exc_info:
        run_command_mod.run_benchmark(
            models=[
                {
                    "id": "test/model",
                    "name": "Test Model",
                    "cost_per_m_input": 1.0,
                    "cost_per_m_output": 1.0,
                }
            ],
            output_dir=output_dir,
            dry_run=False,
            auto_confirm=False,
            max_cost_usd=1.0,
            scenario_filter=["context_regulatory_data_privacy_001"],
        )

    assert exc_info.value.code == 130
    assert not output_dir.exists()


def test_benchmark_yes_flag_skips_prompt_entirely(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """--yes bypasses confirm_or_abort's prompt entirely, even in a
    non-interactive shell; input() must never be called."""
    from invisiblebench import _agent_cli

    output_dir = tmp_path / "yes_flag_should_not_prompt"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(_agent_cli, "is_tty", lambda: False)

    def _fail_if_called(_prompt):
        raise AssertionError("must not prompt when --yes is set")

    monkeypatch.setattr("builtins.input", _fail_if_called)

    rc = run_command_mod.run_benchmark(
        models=[
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
        output_dir=output_dir,
        dry_run=False,
        auto_confirm=True,
        max_cost_usd=1.0,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    # Prompt is skipped; the run then fails at API-client init because
    # conftest.py sets INVISIBLEBENCH_DISABLE_LLM=1 for all tests. That is
    # the expected next failure, not a crash from the confirmation gate.
    assert rc == 1
    assert "Failed to initialize API client" in capsys.readouterr().out
    assert not output_dir.exists()


def test_benchmark_live_run_requires_cost_ceiling(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_dir = tmp_path / "uncapped_should_not_exist"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    rc = run_command_mod.run_benchmark(
        models=[
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
        output_dir=output_dir,
        dry_run=False,
        auto_confirm=True,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 2
    assert "--max-cost-usd" in capsys.readouterr().out
    assert not output_dir.exists()


def test_benchmark_live_run_refuses_cost_ceiling_below_plan(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_dir = tmp_path / "over_budget_should_not_exist"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    rc = run_command_mod.run_benchmark(
        models=[
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
        output_dir=output_dir,
        dry_run=False,
        auto_confirm=True,
        max_cost_usd=0.0,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 2
    assert "exceeds --max-cost-usd" in capsys.readouterr().out
    assert not output_dir.exists()


def test_benchmark_live_run_refuses_meaningless_cost_ceiling(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    output_dir = tmp_path / "unbounded_ceiling_should_not_exist"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    rc = run_command_mod.run_benchmark(
        models=[
            {
                "id": "test/model",
                "name": "Test Model",
                "cost_per_m_input": 1.0,
                "cost_per_m_output": 1.0,
            }
        ],
        output_dir=output_dir,
        dry_run=False,
        auto_confirm=True,
        max_cost_usd=1_000_000.0,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 2
    assert "not a meaningful guardrail" in capsys.readouterr().out
    assert not output_dir.exists()


def test_legacy_inline_score_flag_is_removed(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["-m", "1", "--legacy-inline-score", "--dry-run"])

    assert exc.value.code == 2
    assert "legacy-inline-score" in capsys.readouterr().err


def test_runs_flag_is_removed(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["-m", "1", "--runs=3", "--dry-run"])

    assert exc.value.code == 2
    assert "--runs" in capsys.readouterr().err


def test_leaderboard_status_does_not_prompt(
    monkeypatch, force_noninteractive, capsys, tmp_path
):
    """Reads must never prompt, even in non-interactive shells."""
    # Minimal current safety-care/v1 leaderboard
    lb_file = tmp_path / "leaderboard.json"
    lb_file.write_text(json.dumps({"models": [{"x": 1}]}))

    from invisiblebench.cli import leaderboard as lb_mod

    monkeypatch.setattr(lb_mod, "_leaderboard_output", lambda: tmp_path)

    rc = runner_mod.main(["--json", "leaderboard", "status"])
    assert rc == 0
    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1
    env = json.loads(stdout[0])
    assert env["status"] == "ok"
    assert env["command"] == "leaderboard"


# -------------------- archive prompt fix --------------------


def test_archive_without_before_or_keep_exits_2(capsys):
    rc = runner_mod.main(["archive"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--before" in err or "--keep" in err


def test_archive_before_and_keep_together_refuses(capsys):
    """B-33: the combined rule is refused, not silently narrowed to --keep."""
    rc = runner_mod.main(
        ["archive", "--before", "20200101", "--keep", "5", "--dry-run"]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "pass one of" in err


def test_archive_yes_after_subcommand_works(monkeypatch, tmp_path):
    """B-33: --yes is now also accepted after the subcommand, not only as a
    top-level flag."""
    from invisiblebench.cli import archive as archive_mod

    monkeypatch.setattr(archive_mod, "get_project_root", lambda: tmp_path)
    (tmp_path / "results").mkdir()

    rc = runner_mod.main(["archive", "--keep", "5", "--yes"])
    assert rc == 0


def test_archive_yes_top_level_still_works(monkeypatch, tmp_path):
    """The pre-existing top-level --yes placement keeps working."""
    from invisiblebench.cli import archive as archive_mod

    monkeypatch.setattr(archive_mod, "get_project_root", lambda: tmp_path)
    (tmp_path / "results").mkdir()

    rc = runner_mod.main(["--yes", "archive", "--keep", "5"])
    assert rc == 0


def test_archive_without_yes_refuses_in_noninteractive_shell(
    monkeypatch, tmp_path, force_noninteractive
):
    from invisiblebench.cli import archive as archive_mod

    monkeypatch.setattr(archive_mod, "get_project_root", lambda: tmp_path)
    (tmp_path / "results").mkdir()

    with pytest.raises(SystemExit) as exc_info:
        runner_mod.main(["archive", "--keep", "5"])

    assert exc_info.value.code == 2


# -------------------- --transcripts-only removed --------------------


def test_transcripts_only_flag_is_removed(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        runner_mod.main(["-m", "1", "--transcripts-only", "--dry-run"])

    assert exc_info.value.code == 2
    assert "transcripts-only" in capsys.readouterr().err


# -------------------- doctor/health --json envelopes --------------------


def test_doctor_json_emits_standard_envelope(monkeypatch, tmp_path, capsys) -> None:
    from invisiblebench.cli import agent_commands

    runs_dir = tmp_path / "results"
    runs_dir.mkdir()
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: runs_dir)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    rc = runner_mod.main(["--json", "doctor"])

    assert rc == 0
    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1
    envelope = json.loads(stdout[0])
    assert envelope["status"] == "ok"
    assert envelope["command"] == "doctor"
    assert envelope["data"]["failures"] == 0
    assert len(envelope["data"]["checks"]) == 3


def test_doctor_json_reports_failures(monkeypatch, tmp_path, capsys) -> None:
    from invisiblebench.cli import agent_commands

    runs_dir = tmp_path / "results"
    runs_dir.mkdir()
    monkeypatch.setattr(agent_commands, "_runs_dir", lambda: runs_dir)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    rc = runner_mod.main(["--json", "doctor"])

    assert rc == 1
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["data"]["failures"] == 1
    failed = [c for c in envelope["data"]["checks"] if not c["passed"]]
    assert len(failed) == 1
    assert "API key" in failed[0]["name"]


def test_doctor_help_notes_probe_write(capsys) -> None:
    """B-33: doctor's read-only framing is qualified in its own help text."""
    with pytest.raises(SystemExit) as exc_info:
        runner_mod.main(["--help"])

    assert exc_info.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "creates runs dir if missing" in out


def test_health_json_emits_standard_envelope(monkeypatch, tmp_path, capsys) -> None:
    from invisiblebench.cli import health as health_mod

    lb_dir = tmp_path / "data" / "leaderboard"
    lb_dir.mkdir(parents=True)
    (lb_dir / "leaderboard.json").write_text(
        json.dumps(
            {
                "schema": "safety-care/v1",
                "models": [
                    {
                        "model": "test-model",
                        "safety": {"lines": {}},
                        "care": {"qualities": {}},
                    }
                ],
            }
        )
    )
    monkeypatch.setattr(health_mod, "get_project_root", lambda: tmp_path)

    rc = runner_mod.main(["--json", "health"])

    assert rc == 1  # missing safety lines / care qualities -> incomplete
    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1
    envelope = json.loads(stdout[0])
    assert envelope["status"] == "ok"
    assert envelope["command"] == "health"
    assert envelope["data"]["generated"] is True
    assert envelope["data"]["models_total"] == 1
    assert len(envelope["data"]["models_incomplete"]) == 1


def test_health_json_no_leaderboard_yet(monkeypatch, tmp_path, capsys) -> None:
    from invisiblebench.cli import health as health_mod

    monkeypatch.setattr(health_mod, "get_project_root", lambda: tmp_path)

    rc = runner_mod.main(["--json", "health"])

    assert rc == 0
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["command"] == "health"
    assert envelope["data"]["generated"] is False


# -------------------- leaderboard status --out without --json --------------------


def test_leaderboard_status_out_without_json_writes_file(
    monkeypatch, tmp_path, capsys
) -> None:
    """B-33: --out alone (no --json) now switches into write mode, matching
    get/runs semantics."""
    from invisiblebench.cli import leaderboard as lb_mod

    (tmp_path / "leaderboard.json").write_text(
        json.dumps({"schema": "safety-care/v1", "models": []})
    )
    monkeypatch.setattr(lb_mod, "_leaderboard_output", lambda: tmp_path)

    out_path = tmp_path / "out.json"
    rc = runner_mod.main(["leaderboard", "status", "--out", str(out_path)])

    assert rc == 0
    assert out_path.exists()
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["command"] == "leaderboard"
    assert envelope["data"]["path"] == str(out_path.resolve())


# -------------------- review build --publication forwarding --------------------


def test_review_build_scan_forwards_publication_flag(monkeypatch, tmp_path) -> None:
    """T4 leftover: review build --scan --publication forwards --publication
    to export_scan_adjudication.py."""
    from invisiblebench.cli import review as review_mod

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        from types import SimpleNamespace

        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(review_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(review_mod, "_repo_root", lambda: tmp_path)

    scan_file = tmp_path / "per_run.jsonl"
    scan_file.write_text("")
    out_dir = tmp_path / "batch"

    rc = runner_mod.main(
        [
            "review",
            "build",
            "--scan",
            str(scan_file),
            "--out-dir",
            str(out_dir),
            "--publication",
        ]
    )

    assert rc == 0
    assert "--publication" in calls[0]


def test_review_build_publication_without_scan_refuses(capsys) -> None:
    rc = runner_mod.main(["review", "build", "--publication"])
    assert rc == 2
    assert "--scan" in capsys.readouterr().err
