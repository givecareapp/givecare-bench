"""PUBLISH verb: generate → strict QA gate → web sync, fail-closed.

This module owns the publication *sequencing* (DESIGN.md job 4): the strict
QA gate runs before the public web target is written, and any stage failure
aborts the chain — a bad scan can never reach the public surface. Stage
internals still live in scripts/generate_leaderboard.py, scripts/
qa_leaderboard.py, and delivery/sync_web_bench.py (their migration into this
module is a separate move); `scripts/publish.sh` is a thin shim over
`python -m invisiblebench.publish`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from invisiblebench.utils.benchmark_inventory import get_project_root

LEADERBOARD_DIR = "data/leaderboard"
LEADERBOARD_ARTIFACT = "data/leaderboard/leaderboard.json"
WEB_LEADERBOARD_ARTIFACT = "data/leaderboard/leaderboard_web.json"
QA_STAMP_FILENAME = ".qa-stamp"

Runner = Callable[[Sequence[str]], int]


def _run(cmd: Sequence[str]) -> int:
    return subprocess.run(list(cmd), cwd=get_project_root()).returncode


def _write_qa_stamp(root: Path, scan_path: Path) -> Path:
    """Stamp the just-QA'd leaderboard artifact so sync_web_bench.py and
    build_cfm.py can prove freshness (VISION.md: no side doors — a direct
    sync_web_bench.py or build_cfm.py call with no fresh stamp must refuse,
    not silently ship whatever leaderboard.json/scan happens to be on disk).

    ``scan_sha256`` records the exact scan bytes strict QA ran against, so a
    downstream consumer that reads the scan directly (build_cfm.py) can verify
    it's looking at the same scan the stamped leaderboard was generated from —
    not just a scan at a path that happens to match."""
    leaderboard_path = root / LEADERBOARD_ARTIFACT
    stamp_path = root / LEADERBOARD_DIR / QA_STAMP_FILENAME
    stamp = {
        "leaderboard_sha256": hashlib.sha256(leaderboard_path.read_bytes()).hexdigest(),
        "scan_path": str(scan_path),
        "scan_sha256": hashlib.sha256(scan_path.read_bytes()).hexdigest(),
        "strict": True,
        "qa_passed_at": datetime.now(UTC).isoformat(),
    }
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(json.dumps(stamp, indent=2) + "\n")
    return stamp_path


@dataclass
class PublishResult:
    ok: bool
    stages_run: list[str] = field(default_factory=list)
    failed_stage: str | None = None
    error: str | None = None


def publish(
    scan: Path | str,
    web_target: Path | str,
    *,
    runner: Runner = _run,
    repo_root: Path | None = None,
) -> PublishResult:
    """Run the fail-closed publish chain. The web target is written only if
    generation and the strict QA gate both pass."""
    root = repo_root or get_project_root()
    scan = Path(scan)
    scan_abs = scan if scan.is_absolute() else root / scan
    result = PublishResult(ok=False)

    if not scan_abs.is_file():
        result.error = (
            f"scored scan not found: {scan} — run scripts/run_scan.py "
            "--profile publish --enable-llm <run_dir> first"
        )
        return result

    qa_cmd = [
        sys.executable,
        "scripts/qa_leaderboard.py",
        "--scan",
        str(scan),
        "--leaderboard",
        LEADERBOARD_ARTIFACT,
        "--strict",
    ]
    manual_adj = scan_abs.parent / "manual_adjudications.json"
    if manual_adj.is_file():
        qa_cmd += ["--manual-adjudications", str(manual_adj)]

    stages: list[tuple[str, list[str]]] = [
        (
            "generate",
            [
                sys.executable,
                "scripts/generate_leaderboard.py",
                "--input",
                str(scan),
                "--output",
                LEADERBOARD_DIR,
            ],
        ),
        ("qa", qa_cmd),
        (
            "sync-local-web",
            [
                sys.executable,
                "delivery/sync_web_bench.py",
                "--source",
                LEADERBOARD_ARTIFACT,
                "--target",
                WEB_LEADERBOARD_ARTIFACT,
            ],
        ),
        (
            "sync-web",
            [
                sys.executable,
                "delivery/sync_web_bench.py",
                "--source",
                LEADERBOARD_ARTIFACT,
                "--target",
                str(web_target),
            ],
        ),
    ]

    for name, cmd in stages:
        result.stages_run.append(name)
        code = runner(cmd)
        if code != 0:
            result.failed_stage = name
            result.error = f"stage {name!r} failed with exit code {code}"
            return result
        if name == "qa":
            _write_qa_stamp(root, scan_abs)

    result.ok = True
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed leaderboard publish: generate -> strict QA -> web sync",
    )
    parser.add_argument("scan", help="scored per_run.jsonl")
    parser.add_argument("web_target", help="web-bench leaderboard JSON target")
    args = parser.parse_args(argv)

    result = publish(args.scan, args.web_target)
    if not result.ok:
        print(f"publish FAILED: {result.error}", file=sys.stderr)
        if result.failed_stage == "qa":
            print("QA gate failed; web-bench target was NOT written.", file=sys.stderr)
        return 1
    print("publish OK: QA gate passed and web-bench payload synced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
