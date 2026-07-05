"""QA-stamp gate: sync_web_bench.py must refuse to write a public web-bench
payload unless the source leaderboard.json carries a fresh strict-QA stamp
(written by invisiblebench.publish immediately after strict QA passes).

VISION.md: no side doors. Before this gate, calling
`python delivery/sync_web_bench.py --source ... --target ...` directly (the
individual steps CLAUDE.md documents "for debugging") could ship a
leaderboard.json that was regenerated or hand-edited after strict QA last
passed, or that was never QA'd at all — the shape validation in
project_leaderboard() alone can't tell "just QA'd" apart from "structurally
fine but unvetted".
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from delivery.sync_web_bench import (
    QAStampError,
    _qa_stamp_path,
    compute_sync_status,
    sync_leaderboard,
)


def _minimal_source() -> dict:
    """Smallest dict that passes project_leaderboard()'s shape validation."""
    return {
        "schema": "safety-care/v1",
        "notes": {"no_composite": True},
        "scan_metadata": {"generated_at": "2026-01-01T00:00:00+00:00"},
        "models": [
            {
                "model": "Test Model",
                "safety": {"lines": {}},
                "care": {
                    "qualities": {
                        "belonging": {"calibration_status": "not_claim_ready"},
                    }
                },
            }
        ],
    }


def _write_source(tmp_path: Path, data: dict | None = None) -> Path:
    source = tmp_path / "data" / "leaderboard" / "leaderboard.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps(data if data is not None else _minimal_source()))
    return source


def _write_fresh_stamp(source: Path) -> Path:
    stamp_path = _qa_stamp_path(source)
    stamp_path.write_text(
        json.dumps(
            {
                "leaderboard_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "scan_path": "results/fake_scan/per_run.jsonl",
                "strict": True,
                "qa_passed_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )
    return stamp_path


def test_missing_stamp_refuses_write(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    target = tmp_path / "web.json"

    with pytest.raises(QAStampError, match="No QA stamp"):
        sync_leaderboard(source, target)

    assert not target.exists()


def test_stale_stamp_refuses_write(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    _write_fresh_stamp(source)  # stamp matches current bytes...
    changed = _minimal_source()
    changed["models"][0]["model"] = "Test Model (changed after QA)"
    source.write_text(json.dumps(changed))
    # ...but the source content changed after the stamp was written, e.g. a
    # hand-edit or a re-run of generate_leaderboard.py without re-running QA.
    target = tmp_path / "web.json"

    with pytest.raises(QAStampError, match="stale"):
        sync_leaderboard(source, target)

    assert not target.exists()


def test_fresh_stamp_allows_write(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    _write_fresh_stamp(source)
    target = tmp_path / "web.json"

    status = sync_leaderboard(source, target)

    assert target.exists()
    assert status.in_sync
    written = json.loads(target.read_text())
    assert written["schema"] == "safety-care/v1"


def test_unsafe_debug_bypass_writes_without_stamp(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _write_source(tmp_path)
    target = tmp_path / "web.json"

    status = sync_leaderboard(source, target, unsafe_debug_bypass=True)

    assert target.exists()
    assert status.in_sync
    stderr = capsys.readouterr().err
    assert "UNSAFE DEBUG BYPASS" in stderr
    assert "no side doors" in stderr


def test_unsafe_debug_bypass_writes_over_stale_stamp(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    _write_fresh_stamp(source)
    changed = _minimal_source()
    changed["models"][0]["model"] = "Test Model (changed after QA)"
    source.write_text(json.dumps(changed))
    target = tmp_path / "web.json"

    status = sync_leaderboard(source, target, unsafe_debug_bypass=True)

    assert target.exists()
    assert status.in_sync


def test_already_in_sync_never_needs_a_stamp(tmp_path: Path) -> None:
    """A no-op sync (target already matches the projection) doesn't write, so
    it must not raise even with zero stamp — nothing is being shipped."""
    source = _write_source(tmp_path)
    target = tmp_path / "web.json"
    from delivery.sync_web_bench import _projected_bytes

    target.write_bytes(_projected_bytes(source))

    status = sync_leaderboard(source, target)
    assert status.in_sync


def test_check_mode_never_gated_by_stamp(tmp_path: Path) -> None:
    """--check is a read-only status query; it must work with no stamp at all."""
    source = _write_source(tmp_path)
    target = tmp_path / "web.json"

    status = compute_sync_status(source, target)
    assert status.in_sync is False
    assert not target.exists()


def test_cli_refuses_missing_stamp_with_nonzero_exit(tmp_path: Path) -> None:
    from delivery.sync_web_bench import main

    source = _write_source(tmp_path)
    target = tmp_path / "web.json"

    exit_code = main(["--source", str(source), "--target", str(target)])

    assert exit_code == 1
    assert not target.exists()


def test_cli_unsafe_debug_bypass_flag_writes(tmp_path: Path) -> None:
    from delivery.sync_web_bench import main

    source = _write_source(tmp_path)
    target = tmp_path / "web.json"

    exit_code = main(["--source", str(source), "--target", str(target), "--unsafe-debug-bypass"])

    assert exit_code == 0
    assert target.exists()
