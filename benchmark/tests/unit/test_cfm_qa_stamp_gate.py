"""QA-stamp gate: build_cfm.py must refuse to emit a public artifact-v2
payload (comparative_failure_modes + model_profiles) unless the scan it
reads carries a fresh strict-QA stamp recorded by invisiblebench.publish.

VISION.md: no side doors. Before this gate, `python -m delivery.build_cfm
--scan <path> --out <path>` could write anywhere with zero verification that
<path> was ever scored or strict-QA'd, or that it's the same scan the
currently-stamped leaderboard was generated from. Mirrors
test_qa_stamp_gate.py's coverage of delivery/sync_web_bench.py, adapted for
build_cfm's scan-identity check instead of a leaderboard-bytes check.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from delivery.build_cfm import (
    QAStampError,
    build_and_write_cfm,
    build_cfm_section,
)

MINIMAL_CATALOG = """\
schema: cfm-catalog/v1
comparative_failure_modes: []
"""


def _write_catalog(tmp_path: Path) -> Path:
    p = tmp_path / "catalog.yaml"
    p.write_text(MINIMAL_CATALOG)
    return p


def _write_scan(tmp_path: Path, name: str = "per_run.jsonl", content: str = "") -> Path:
    scan = tmp_path / name
    scan.write_text(content)
    return scan


def _stamp_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "leaderboard" / ".qa-stamp"


def _write_fresh_stamp(stamp_path: Path, scan_path: Path) -> None:
    """A stamp shaped like the one invisiblebench.publish writes: leaderboard
    hash (irrelevant to build_cfm) plus scan path + content hash (what
    build_cfm actually checks)."""
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(
            {
                "leaderboard_sha256": "irrelevant-for-cfm",
                "scan_path": str(scan_path),
                "scan_sha256": hashlib.sha256(scan_path.read_bytes()).hexdigest(),
                "strict": True,
                "qa_passed_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )


def test_missing_stamp_refuses_write(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)
    out = tmp_path / "cfm.json"

    with pytest.raises(QAStampError, match="No QA stamp"):
        build_and_write_cfm(scan, out, catalog, qa_stamp_path=_stamp_path(tmp_path))

    assert not out.exists()


def test_stale_stamp_refuses_write(tmp_path: Path) -> None:
    """Scan content changed after the stamp was written (regenerated or
    hand-edited post-QA) — the recorded scan_sha256 goes stale, the same
    failure mode as sync_web_bench's leaderboard-bytes staleness check."""
    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path, content='{"model": "original"}\n')
    stamp_path = _stamp_path(tmp_path)
    _write_fresh_stamp(stamp_path, scan)

    scan.write_text('{"model": "mutated-after-qa"}\n')
    out = tmp_path / "cfm.json"

    with pytest.raises(QAStampError, match="hash mismatch"):
        build_and_write_cfm(scan, out, catalog, qa_stamp_path=stamp_path)

    assert not out.exists()


def test_scan_identity_mismatch_refuses_write(tmp_path: Path) -> None:
    """The stamp is internally fresh but for a DIFFERENT scan than the one
    passed to build_cfm — e.g. an unrelated or older scan reused against a
    stamp from a newer publish run. build_cfm must verify scan identity
    against the stamp, not just that some stamp exists."""
    catalog = _write_catalog(tmp_path)
    stamped_scan = _write_scan(tmp_path, name="stamped_run.jsonl", content='{"model": "stamped"}\n')
    stamp_path = _stamp_path(tmp_path)
    _write_fresh_stamp(stamp_path, stamped_scan)

    other_scan = _write_scan(tmp_path, name="other_run.jsonl", content='{"model": "different-scan"}\n')
    out = tmp_path / "cfm.json"

    with pytest.raises(QAStampError, match="hash mismatch"):
        build_and_write_cfm(other_scan, out, catalog, qa_stamp_path=stamp_path)

    assert not out.exists()


def test_stamp_missing_scan_sha256_refuses_write(tmp_path: Path) -> None:
    """Old-format stamps (written before this scan-identity gate existed)
    lack scan_sha256 entirely — refuse rather than silently treating an
    unverifiable stamp as a pass."""
    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)
    stamp_path = _stamp_path(tmp_path)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(
        json.dumps(
            {
                "leaderboard_sha256": "abc",
                "scan_path": str(scan),
                "strict": True,
                "qa_passed_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )
    out = tmp_path / "cfm.json"

    with pytest.raises(QAStampError, match="scan_sha256"):
        build_and_write_cfm(scan, out, catalog, qa_stamp_path=stamp_path)

    assert not out.exists()


def test_fresh_stamp_allows_write(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)
    stamp_path = _stamp_path(tmp_path)
    _write_fresh_stamp(stamp_path, scan)
    out = tmp_path / "cfm.json"

    section = build_and_write_cfm(scan, out, catalog, qa_stamp_path=stamp_path)

    assert out.exists()
    assert json.loads(out.read_text())["schema"] == "cfm/v1"
    assert section["schema"] == "cfm/v1"


def test_unsafe_debug_bypass_writes_without_stamp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)
    out = tmp_path / "cfm.json"

    build_and_write_cfm(
        scan, out, catalog, qa_stamp_path=_stamp_path(tmp_path), unsafe_debug_bypass=True
    )

    assert out.exists()
    stderr = capsys.readouterr().err
    assert "UNSAFE DEBUG BYPASS" in stderr
    assert "no side doors" in stderr


def test_unsafe_debug_bypass_writes_over_scan_mismatch(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    stamped_scan = _write_scan(tmp_path, name="stamped_run.jsonl", content='{"model": "stamped"}\n')
    stamp_path = _stamp_path(tmp_path)
    _write_fresh_stamp(stamp_path, stamped_scan)

    other_scan = _write_scan(tmp_path, name="other_run.jsonl", content='{"model": "different"}\n')
    out = tmp_path / "cfm.json"

    build_and_write_cfm(
        other_scan, out, catalog, qa_stamp_path=stamp_path, unsafe_debug_bypass=True
    )

    assert out.exists()


def test_pure_build_cfm_section_never_gated(tmp_path: Path) -> None:
    """The read-only computation entry point (used directly by
    test_build_cfm.py and any future read-only/--check tooling) must never
    require a stamp — only the write-to-disk path (build_and_write_cfm) is
    gated, same split as sync_web_bench.py's project_leaderboard() vs
    sync_leaderboard()."""
    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)

    section = build_cfm_section(scan, catalog)
    assert section["schema"] == "cfm/v1"


def test_cli_refuses_missing_stamp_with_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from delivery.build_cfm import _cli

    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)
    out = tmp_path / "cfm.json"
    stamp_path = _stamp_path(tmp_path)

    argv = [
        "build_cfm",
        "--scan", str(scan),
        "--catalog", str(catalog),
        "--out", str(out),
        "--qa-stamp", str(stamp_path),
    ]
    monkeypatch.setattr("sys.argv", argv)

    with pytest.raises(SystemExit) as exc:
        _cli()

    assert exc.value.code == 1
    assert not out.exists()


def test_cli_unsafe_debug_bypass_flag_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from delivery.build_cfm import _cli

    catalog = _write_catalog(tmp_path)
    scan = _write_scan(tmp_path)
    out = tmp_path / "cfm.json"
    stamp_path = _stamp_path(tmp_path)

    argv = [
        "build_cfm",
        "--scan", str(scan),
        "--catalog", str(catalog),
        "--out", str(out),
        "--qa-stamp", str(stamp_path),
        "--unsafe-debug-bypass",
    ]
    monkeypatch.setattr("sys.argv", argv)

    _cli()  # must not raise

    assert out.exists()
