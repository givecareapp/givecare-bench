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
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from invisiblebench.utils.benchmark_inventory import get_project_root

LEADERBOARD_DIR = "data/leaderboard"
LEADERBOARD_ARTIFACT = "data/leaderboard/leaderboard.json"
WEB_LEADERBOARD_ARTIFACT = "data/leaderboard/leaderboard_web.json"

Runner = Callable[[Sequence[str]], int]


def _run(cmd: Sequence[str]) -> int:
    return subprocess.run(list(cmd), cwd=get_project_root()).returncode


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
