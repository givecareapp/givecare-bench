"""Pins for the PUBLISH verb's fail-closed sequencing.

The boundary that matters: the web-sync stage must never run unless the
strict QA gate passed, and nothing runs without a scored scan.
"""

from __future__ import annotations

from pathlib import Path

from invisiblebench.publish import publish


def _fake_runner(fail_stage: str | None, calls: list[str]):
    def run(cmd):
        script = next(part for part in cmd if str(part).endswith(".py"))
        name = Path(script).stem
        calls.append(name)
        if fail_stage and fail_stage in name:
            return 1
        return 0

    return run


def _scan(tmp_path: Path) -> Path:
    scan = tmp_path / "per_run.jsonl"
    scan.write_text("{}\n")
    return scan


def test_qa_failure_blocks_web_sync(tmp_path: Path) -> None:
    calls: list[str] = []
    result = publish(
        _scan(tmp_path),
        tmp_path / "web.json",
        runner=_fake_runner("qa_leaderboard", calls),
    )
    assert not result.ok
    assert result.failed_stage == "qa"
    assert "sync_web_bench" not in calls


def test_generate_failure_blocks_everything_downstream(tmp_path: Path) -> None:
    calls: list[str] = []
    result = publish(
        _scan(tmp_path),
        tmp_path / "web.json",
        runner=_fake_runner("generate_leaderboard", calls),
    )
    assert not result.ok
    assert result.failed_stage == "generate"
    assert calls == ["generate_leaderboard"]


def test_happy_path_runs_stages_in_order(tmp_path: Path) -> None:
    calls: list[str] = []
    result = publish(
        _scan(tmp_path),
        tmp_path / "web.json",
        runner=_fake_runner(None, calls),
    )
    assert result.ok
    assert calls == ["generate_leaderboard", "qa_leaderboard", "sync_web_bench"]


def test_missing_scan_runs_nothing(tmp_path: Path) -> None:
    calls: list[str] = []
    result = publish(
        tmp_path / "absent.jsonl",
        tmp_path / "web.json",
        runner=_fake_runner(None, calls),
    )
    assert not result.ok
    assert calls == []
    assert "scored scan not found" in (result.error or "")
