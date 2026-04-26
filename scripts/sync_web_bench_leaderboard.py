#!/usr/bin/env python3
"""Mirror a leaderboard artifact into the static web-bench path."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "data" / "leaderboard" / "leaderboard.json"


@dataclass(frozen=True)
class SyncStatus:
    source: str
    target: str
    source_hash: str
    target_hash: str | None
    source_generated_at: str | None
    target_generated_at: str | None
    in_sync: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_generated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    data: Any = json.loads(path.read_text())
    metadata = data.get("metadata") or {}
    generated_at = metadata.get("generated_at")
    return str(generated_at) if generated_at is not None else None


def compute_sync_status(source: Path, target: Path) -> SyncStatus:
    if not source.exists():
        raise FileNotFoundError(f"Source leaderboard not found: {source}")

    source_hash = _sha256(source)
    target_hash = _sha256(target) if target.exists() else None
    return SyncStatus(
        source=str(source),
        target=str(target),
        source_hash=source_hash,
        target_hash=target_hash,
        source_generated_at=_read_generated_at(source),
        target_generated_at=_read_generated_at(target),
        in_sync=target_hash == source_hash,
    )


def sync_leaderboard(source: Path, target: Path) -> SyncStatus:
    status = compute_sync_status(source, target)
    if status.in_sync:
        return status

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return compute_sync_status(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync a leaderboard JSON artifact into web-bench public assets")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Source leaderboard artifact (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument("--target", type=Path, required=True, help="web-bench public leaderboard path")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the target differs instead of copying the source into place",
    )
    args = parser.parse_args()

    status = compute_sync_status(args.source, args.target)
    if args.check:
        print(json.dumps({"status": "ok" if status.in_sync else "drift", "data": asdict(status)}, indent=2))
        return 0 if status.in_sync else 1

    synced = sync_leaderboard(args.source, args.target)
    print(json.dumps({"status": "synced", "data": asdict(synced)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
