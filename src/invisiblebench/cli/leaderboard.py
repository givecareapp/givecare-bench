#!/usr/bin/env python3
"""Leaderboard management for InvisibleBench."""
from __future__ import annotations

from pathlib import Path

from invisiblebench.utils.benchmark_inventory import get_project_root

try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


def _leaderboard_output() -> Path:
    """Return the leaderboard output directory."""
    return get_project_root() / "data" / "leaderboard"


def _out(msg: str) -> None:
    console = Console() if RICH_AVAILABLE else None
    if console:
        console.print(msg)
        return

    import re

    print(re.sub(r"\[/?[^\]]+\]", "", msg))


def _retired_write_error(action: str, target: str | None = None) -> int:
    suffix = f" {target}" if target else ""
    _out(f"[red]bench leaderboard {action}{suffix} is retired for safety-care/v1.[/red]")
    _out(
        "[yellow]Generate from a scored scan JSONL and run strict QA instead:[/yellow]\n"
        "  uv run python -m invisiblebench.publish <scan>/per_run.jsonl <web-target>\n"
        "or inspect locally with:\n"
        "  uv run python scripts/generate_leaderboard.py --input <scan>/per_run.jsonl "
        "--output data/leaderboard\n"
        "  uv run python scripts/qa_leaderboard.py --scan <scan>/per_run.jsonl "
        "--leaderboard data/leaderboard/leaderboard.json --strict"
    )
    return 1


def add_results(results_path: Path) -> int:
    """Retired: public leaderboard writes use the fail-closed publish chain."""
    return _retired_write_error("add", str(results_path))


def rebuild_leaderboard() -> int:
    """Retired: public leaderboard writes use the fail-closed publish chain."""
    return _retired_write_error("rebuild")


def run_leaderboard(
    action: str,
    results_path: str | None = None,
    verbose: bool = False,
) -> int:
    """Dispatch leaderboard subcommands."""
    if action == "add":
        if not results_path:
            print("Usage: bench leaderboard add <retired>")
            return 1
        return add_results(Path(results_path))

    if action == "rebuild":
        return rebuild_leaderboard()

    if action == "status":
        from invisiblebench.cli.health import run_health
        return run_health(verbose=verbose)

    print(f"Unknown leaderboard action: {action}")
    print("Usage: bench leaderboard [add|rebuild|status]")
    return 1
