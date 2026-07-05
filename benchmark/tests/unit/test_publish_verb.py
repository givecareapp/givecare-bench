"""Pins for the PUBLISH verb's fail-closed sequencing.

The boundary that matters: the web-sync stage must never run unless the
strict QA gate passed, and nothing runs without a scored scan.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from invisiblebench.publish import QA_STAMP_FILENAME, main, publish


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


def _seed_fake_repo(tmp_path: Path) -> Path:
    """A fake repo_root with a leaderboard.json for the QA-stamp write to hash.

    Real subprocess stages are always faked in this file, so nothing here
    ever regenerates a real leaderboard — the stamp writer just needs bytes
    to hash at the path it expects (root / data/leaderboard/leaderboard.json).
    """
    leaderboard = tmp_path / "data" / "leaderboard" / "leaderboard.json"
    leaderboard.parent.mkdir(parents=True, exist_ok=True)
    leaderboard.write_text(json.dumps({"schema": "safety-care/v1", "models": []}))
    return tmp_path


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
    repo_root = _seed_fake_repo(tmp_path)
    calls: list[str] = []
    result = publish(
        _scan(tmp_path),
        tmp_path / "web.json",
        runner=_fake_runner(None, calls),
        repo_root=repo_root,
    )
    assert result.ok
    assert calls == [
        "generate_leaderboard",
        "qa_leaderboard",
        "sync_web_bench",
        "sync_web_bench",
    ]


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


def test_publish_invokes_qa_gate_with_strict_flag(tmp_path: Path) -> None:
    """The QA stage must run with --strict — the publish gate is the strict
    gate, so a non-strict QA invocation would silently weaken the boundary."""
    repo_root = _seed_fake_repo(tmp_path)
    commands: list[list[str]] = []

    def recording_runner(cmd):
        commands.append([str(part) for part in cmd])
        return 0

    result = publish(
        _scan(tmp_path),
        tmp_path / "web.json",
        runner=recording_runner,
        repo_root=repo_root,
    )
    assert result.ok
    qa_cmd = next(
        cmd for cmd in commands if any(part.endswith("qa_leaderboard.py") for part in cmd)
    )
    assert "--strict" in qa_cmd


def test_publish_cli_requires_explicit_scan_and_web_target() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 2


def test_qa_success_writes_fresh_qa_stamp(tmp_path: Path) -> None:
    """After the qa stage passes, publish() stamps the leaderboard artifact
    so sync_web_bench.py can prove it's syncing a just-QA'd file (VISION.md:
    no side doors) instead of trusting whatever happens to be on disk."""
    repo_root = _seed_fake_repo(tmp_path)
    scan = _scan(tmp_path)

    result = publish(
        scan,
        tmp_path / "web.json",
        runner=_fake_runner(None, []),
        repo_root=repo_root,
    )
    assert result.ok

    stamp_path = repo_root / "data" / "leaderboard" / QA_STAMP_FILENAME
    assert stamp_path.exists()
    stamp = json.loads(stamp_path.read_text())

    leaderboard_bytes = (repo_root / "data" / "leaderboard" / "leaderboard.json").read_bytes()
    assert stamp["leaderboard_sha256"] == hashlib.sha256(leaderboard_bytes).hexdigest()
    assert stamp["strict"] is True
    assert stamp["scan_path"] == str(scan)
    assert stamp["qa_passed_at"]  # non-empty ISO timestamp


def test_qa_success_stamps_scan_content_hash(tmp_path: Path) -> None:
    """The stamp records scan_sha256 (not just scan_path) so a downstream
    reader of the scan itself (delivery/build_cfm.py, which never touches
    leaderboard.json) can verify it's looking at the exact scan strict QA
    ran against, not just a same-named path."""
    repo_root = _seed_fake_repo(tmp_path)
    scan = _scan(tmp_path)

    result = publish(
        scan,
        tmp_path / "web.json",
        runner=_fake_runner(None, []),
        repo_root=repo_root,
    )
    assert result.ok

    stamp_path = repo_root / "data" / "leaderboard" / QA_STAMP_FILENAME
    stamp = json.loads(stamp_path.read_text())

    assert stamp["scan_sha256"] == hashlib.sha256(scan.read_bytes()).hexdigest()


def test_qa_failure_does_not_write_a_stamp(tmp_path: Path) -> None:
    """A failed QA stage must never leave a stamp behind — a stamp is a claim
    that strict QA passed, full stop."""
    repo_root = _seed_fake_repo(tmp_path)

    result = publish(
        _scan(tmp_path),
        tmp_path / "web.json",
        runner=_fake_runner("qa_leaderboard", []),
        repo_root=repo_root,
    )
    assert not result.ok
    assert not (repo_root / "data" / "leaderboard" / QA_STAMP_FILENAME).exists()
