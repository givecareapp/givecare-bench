from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from scripts.qa_leaderboard import main, write_qa_stamp


def test_writer_binds_exact_scan_and_leaderboard_bytes(tmp_path: Path) -> None:
    scan = tmp_path / "per_run.jsonl"
    leaderboard = tmp_path / "leaderboard.json"
    scan.write_bytes(b'{"model":"test"}\n')
    leaderboard.write_bytes(b'{"schema":"safety-care/v1"}\n')

    stamp_path = write_qa_stamp(scan, leaderboard, repo_root=tmp_path)
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))

    assert stamp_path == tmp_path / "data" / "leaderboard" / ".qa-stamp"
    assert stamp["strict"] is True
    assert stamp["scan_sha256"] == hashlib.sha256(scan.read_bytes()).hexdigest()
    assert stamp["leaderboard_sha256"] == hashlib.sha256(leaderboard.read_bytes()).hexdigest()
    assert stamp["qa_passed_at"]
    assert stamp_path.stat().st_mode & 0o777 == 0o644


def test_stamp_requires_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["qa_leaderboard.py", "--scan", "scan", "--leaderboard", "board", "--stamp"],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2


@pytest.mark.parametrize("flag", ["--expected-contract", "--expected-stage"])
def test_retired_compatibility_flags_are_rejected(
    flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qa_leaderboard.py",
            "--scan",
            "scan",
            "--leaderboard",
            "board",
            flag,
            "legacy",
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
