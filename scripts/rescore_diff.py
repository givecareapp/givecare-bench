#!/usr/bin/env python3
"""Replay a frozen scan bundle without model calls."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.judge import load_scan, replay_scan  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", required=True, type=Path, help="Frozen scan bundle directory")
    args = parser.parse_args()
    try:
        differences = replay_scan(args.frozen)
        count = len(load_scan(args.frozen, complete=True)[1])
    except (OSError, ValueError) as exc:
        print(f"Cannot replay: {exc}", file=sys.stderr)
        return 2
    if differences:
        print("\n".join(differences))
        return 1
    print(f"CLEAN: {count} saved attempts replayed; no API calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
