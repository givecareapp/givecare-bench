"""Contract tests for `--out` JSON file export and live-write approval gating.

These cover the agent-friendly CLI guarantees added in the April 2026 pass:
- `--out PATH` writes the full payload to disk and emits a summary envelope
- Disk-write failures emit `{status:"error", ...}` rather than raising
- Retired leaderboard writes stay blocked; archive live writes refuse in
  non-interactive shells unless `--yes` is passed
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
from invisiblebench.cli.run_command import _raw_score_percent, _raw_score_range

# -------------------- --out flag --------------------


def test_run_output_formats_raw_score_labels() -> None:
    assert _raw_score_percent(0.73) == "raw 73%"
    assert (
        _raw_score_range(0.73, min_score=0.51, max_score=0.94, pass_rate=67)
        == "raw 73% [raw 51-94%] pass@1=67%"
    )


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


def test_leaderboard_add_refuses_noninteractive(force_noninteractive, capsys):
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["leaderboard", "add", "results/fake_does_not_exist"])
    assert exc.value.code == 2
    assert "non-interactive shell" in capsys.readouterr().err


def test_leaderboard_rebuild_refuses_noninteractive(force_noninteractive, capsys):
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["leaderboard", "rebuild"])
    assert exc.value.code == 2


def test_leaderboard_add_is_retired_with_yes(capsys):
    rc = runner_mod.main(["--yes", "leaderboard", "add", "results/fake_does_not_exist"])

    assert rc == 1
    assert "retired for safety-care/v1" in capsys.readouterr().out


def test_leaderboard_rebuild_is_retired_with_yes(capsys):
    rc = runner_mod.main(["--yes", "leaderboard", "rebuild"])

    assert rc == 1
    assert "retired for safety-care/v1" in capsys.readouterr().out


def test_json_leaderboard_add_retired_error_omits_stale_payload(capsys):
    rc = runner_mod.main(
        ["--json", "--yes", "leaderboard", "add", "results/fake_does_not_exist"]
    )

    assert rc == 1
    captured = capsys.readouterr()
    stdout = captured.out.strip().splitlines()
    assert len(stdout) == 1
    envelope = json.loads(stdout[0])
    assert envelope["status"] == "error"
    assert envelope["command"] == "leaderboard"
    assert envelope["data"]["action"] == "add"
    assert envelope["data"]["exit_code"] == 1
    assert "retired for safety-care/v1" in envelope["data"]["message"]
    assert "leaderboard" not in envelope["data"]


def test_run_update_leaderboard_propagates_retired_path_failure(tmp_path: Path) -> None:
    from invisiblebench.cli.run_command import _update_leaderboard

    with pytest.raises(RuntimeError, match="--update-leaderboard is retired for safety-care/v1"):
        _update_leaderboard(tmp_path / "all_results.json")


def test_run_update_leaderboard_help_is_marked_retired(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--update-leaderboard" in output
    assert "Retired for safety-care/v1" in output


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


def test_benchmark_cancel_does_not_create_run_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "cancelled_should_not_exist"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

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
        auto_confirm=False,
        scenario_filter=["context_regulatory_data_privacy_001"],
    )

    assert rc == 0
    assert not output_dir.exists()


def test_benchmark_manifest_and_rows_share_run_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_dir = tmp_path / "run"
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(run_command_mod, "RICH_AVAILABLE", False)

    class FakeModelAPIClient:
        pass

    monkeypatch.setattr(
        "invisiblebench.api.client.ModelAPIClient",
        FakeModelAPIClient,
    )

    def fake_run_single_scenario(**kwargs: Any) -> dict[str, Any]:
        scenario = kwargs["scenario"]
        return {
            "model": kwargs["model"]["name"],
            "model_id": kwargs["model"]["id"],
            "scenario": scenario["name"],
            "scenario_id": kwargs["scenario_id"],
            "category": scenario["category"],
            "overall_score": 1.0,
            "hard_fail": False,
            "hard_fail_reasons": [],
            "failure_categories": {},
            "gates": {
                "crisis": {"passed": True, "reasons": []},
                "scope": {"passed": True, "reasons": []},
                "identity": {"passed": True, "reasons": []},
                "autonomy": {"passed": True, "reasons": []},
            },
            "dimensions": {},
            "dimension_scores": {},
            "cost": 0.0,
            "status": "pass",
            "run_id": kwargs["run_id"],
            "judge_model": "fake-judge",
            "judge_prompt_hash": None,
            "judge_temp": None,
            "contract_version": "3.2.0",
            "success": True,
            "coverage": {"eligible": 0, "resolved": 0, "unclear": 0, "rate": 1.0},
        }

    monkeypatch.setattr(run_command_mod, "_run_single_scenario", fake_run_single_scenario)

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

    assert rc == 0
    manifest = json.loads((output_dir / "run_manifest.json").read_text())
    rows = json.loads((output_dir / "all_results.json").read_text())
    assert len(rows) == 1
    assert manifest["run_id"] == rows[0]["run_id"]


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
