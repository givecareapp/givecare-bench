#!/usr/bin/env python3
"""Leaderboard status view for InvisibleBench.

Consumer projection writes go through Hound `corpus.project`, not this module.
Canonical leaderboard generation and strict QA remain explicit owner steps.
Only the read-only `status` health view remains.
"""
from __future__ import annotations

from pathlib import Path

from invisiblebench.utils.benchmark_inventory import get_project_root


def _leaderboard_output() -> Path:
    """Return the leaderboard output directory."""
    return get_project_root() / "data" / "leaderboard"


def run_leaderboard(action: str, verbose: bool = False) -> int:
    """Dispatch leaderboard subcommands (status only)."""
    if action == "status":
        from invisiblebench.cli.health import run_health

        return run_health(verbose=verbose)

    print(f"Unknown leaderboard action: {action}")
    print("Usage: bench leaderboard status")
    return 1
