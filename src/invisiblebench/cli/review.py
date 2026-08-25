"""Discover and operate the existing blind-review workflow."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from invisiblebench._agent_cli import emit_json
from invisiblebench.utils.benchmark_inventory import get_project_root


def _repo_root() -> Path:
    return get_project_root()


def _default_review_dir() -> Path:
    configured = os.environ.get("REVIEW_DIR")
    return Path(configured).expanduser() if configured else _repo_root() / "internal" / "review"


def _server_live(*, host: str, port: int) -> bool:
    probe_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with urlopen(f"http://{probe_host}:{port}/health", timeout=0.3) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def _batch_count(path: Path) -> int:
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"review batch must be a JSON array: {path}")
    return len(data)


def _token_counts(path: Path) -> tuple[int, int]:
    reviewers = 0
    admins = 0
    if not path.exists():
        return reviewers, admins
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = dict(part.split("=", 1) for part in line.split() if "=" in part)
        if fields.get("role") == "reviewer":
            reviewers += 1
        elif fields.get("role") == "admin":
            admins += 1
    return reviewers, admins


def _annotation_count(path: Path) -> int:
    if not path.exists():
        return 0
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)
    try:
        row = connection.execute(
            "SELECT COUNT(*) FROM annotations WHERE verdict IS NOT NULL AND verdict <> ''"
        ).fetchone()
    finally:
        connection.close()
    return int(row[0]) if row else 0


def run_review_status(
    *,
    review_dir: Path | None,
    host: str,
    port: int,
    json_output: bool,
) -> int:
    directory = (review_dir or _default_review_dir()).expanduser().resolve()
    batch_path = directory / "batch.json"
    try:
        reviewers, admins = _token_counts(directory / "tokens.txt")
        data: dict[str, Any] = {
            "review_dir": str(directory),
            "batch_path": str(batch_path),
            "batch_cards": _batch_count(batch_path),
            "reviewers": reviewers,
            "admin_tokens": admins,
            "annotations": _annotation_count(directory / "reviews.db"),
            "server_live": _server_live(host=host, port=port),
            "server_url": f"http://{host}:{port}",
        }
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
        if json_output:
            emit_json(status="error", command="review.status", error=str(exc))
        else:
            print(f"review status failed: {exc}", file=sys.stderr)
        return 1

    if json_output:
        emit_json(command="review.status", data=data)
    else:
        print(f"Review dir:   {data['review_dir']}")
        print(f"Batch:        {data['batch_cards']} cards")
        print(f"Reviewers:    {data['reviewers']}")
        print(f"Annotations:  {data['annotations']}")
        print(
            f"Server:       {'live' if data['server_live'] else 'offline'} ({data['server_url']})"
        )
    return 0


def run_review_build(
    *,
    review_dir: Path | None,
    scan: Path | None,
    yes: bool,
    publication: bool = False,
) -> int:
    root = _repo_root()
    if scan is not None and review_dir is None:
        print("review build --scan requires --out-dir", file=sys.stderr)
        return 2
    if publication and scan is None:
        print("review build --publication requires --scan", file=sys.stderr)
        return 2
    directory = (review_dir or _default_review_dir()).expanduser()
    if scan is None:
        batch_path = directory / "batch.json"
        if batch_path.exists() and not yes:
            print(
                f"refusing to replace {batch_path}; pass --yes after confirming no review is active",
                file=sys.stderr,
            )
            return 2
        command = [
            sys.executable,
            str(root / "scripts" / "review_ui" / "export_batch.py"),
            "--out",
            str(batch_path),
        ]
    else:
        command = [
            sys.executable,
            str(root / "scripts" / "review_ui" / "export_scan_adjudication.py"),
            "--scan",
            str(scan.expanduser()),
            "--out-dir",
            str(directory),
        ]
        if publication:
            command.append("--publication")
    result = subprocess.run(command, cwd=root, check=False)
    return result.returncode


def run_review_serve(
    *,
    review_dir: Path | None,
    host: str,
    port: int,
    publication: bool,
    yes: bool,
) -> int:
    if host not in {"127.0.0.1", "localhost", "::1"} and not yes:
        print("non-loopback review serving requires --yes", file=sys.stderr)
        return 2
    root = _repo_root()
    directory = (review_dir or _default_review_dir()).expanduser().resolve()
    if not (directory / "batch.json").is_file():
        print(f"review batch not found: {directory / 'batch.json'}", file=sys.stderr)
        return 2
    app = root / "scripts" / "review_ui" / "app.py"
    env = os.environ.copy()
    env.update(
        {
            "REVIEW_DIR": str(directory),
            "REVIEW_HOST": host,
            "REVIEW_PORT": str(port),
        }
    )
    if publication:
        env["REVIEW_EVIDENCE_MODE"] = "publication"
    result = subprocess.run(
        ["uv", "run", "--script", str(app)],
        cwd=root,
        env=env,
        check=False,
    )
    return result.returncode
