"""Contract tests for `--out` JSON file export and live-write approval gating.

These cover the agent-friendly CLI guarantees added in the April 2026 pass:
- `--out PATH` writes the full payload to disk and emits a summary envelope
- Disk-write failures emit `{status:"error", ...}` rather than raising
- Live writes (publish, leaderboard add/rebuild, archive) refuse in
  non-interactive shells unless `--yes` is passed
- Read commands never prompt
- `archive` without `--before` or `--keep` exits 2

Tests monkeypatch the expensive bits (run collection, publish, leaderboard)
so they run in the same process with no subprocess overhead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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


def test_publish_refuses_noninteractive(force_noninteractive, capsys):
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["publish", "results/fake_does_not_exist"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "non-interactive shell" in err
    assert "publish" in err


def test_leaderboard_add_refuses_noninteractive(force_noninteractive, capsys):
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["leaderboard", "add", "results/fake_does_not_exist"])
    assert exc.value.code == 2
    assert "non-interactive shell" in capsys.readouterr().err


def test_leaderboard_rebuild_refuses_noninteractive(force_noninteractive, capsys):
    with pytest.raises(SystemExit) as exc:
        runner_mod.main(["leaderboard", "rebuild"])
    assert exc.value.code == 2


def test_yes_bypasses_publish_gate(monkeypatch, force_noninteractive):
    calls: dict[str, Any] = {}

    def fake_run_publish(results: str, url: Any = None) -> int:
        calls["results"] = results
        calls["url"] = url
        return 0

    # monkeypatch the module path used by the dispatch import
    from invisiblebench.cli import publish as publish_mod

    monkeypatch.setattr(publish_mod, "run_publish", fake_run_publish)

    rc = runner_mod.main(["--yes", "publish", "results/fake"])
    assert rc == 0
    assert calls["results"] == "results/fake"


def test_leaderboard_status_does_not_prompt(
    monkeypatch, force_noninteractive, capsys, tmp_path
):
    """Reads must never prompt, even in non-interactive shells."""
    # Minimal valid leaderboard
    lb_file = tmp_path / "leaderboard.json"
    lb_file.write_text(json.dumps({"overall_leaderboard": [{"x": 1}]}))

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
