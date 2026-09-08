#!/usr/bin/env python3
"""Generate an aggregate candidate from a completed judgment ledger."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.scoring import generate_leaderboard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", required=True, type=Path, help="Scan bundle directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        print(generate_leaderboard(args.scan, args.output))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
