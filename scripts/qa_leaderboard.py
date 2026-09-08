#!/usr/bin/env python3
"""Check a candidate against current source evidence and exact score recomputation."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invisiblebench.scoring import validate_leaderboard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", required=True, type=Path, help="Scan bundle directory")
    parser.add_argument("--leaderboard", required=True, type=Path)
    args = parser.parse_args()
    errors = validate_leaderboard(args.scan, args.leaderboard)
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("QA passed")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
