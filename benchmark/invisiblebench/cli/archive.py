#!/usr/bin/env python3
"""
Archive management for InvisibleBench results.

Usage:
    bench archive                    # Archive all runs except today's
    bench archive --before 20260129  # Archive runs before date
    bench archive --keep 5           # Keep N most recent, archive rest
    bench archive --list             # List what would be archived (dry run)
    bench clean                      # Alias for archive
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


def get_project_root() -> Path:
    """Find the project root (where pyproject.toml is)."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def parse_run_date(run_name: str) -> Optional[datetime]:
    """Parse date from run directory name (run_YYYYMMDD_HHMMSS)."""
    try:
        if run_name.startswith("run_"):
            date_str = run_name[4:12]  # YYYYMMDD
            return datetime.strptime(date_str, "%Y%m%d")
    except (ValueError, IndexError):
        pass
    return None


def get_run_info(run_path: Path) -> Dict[str, Any]:
    """Get info about a run directory."""
    info = {
        "path": run_path,
        "name": run_path.name,
        "date": parse_run_date(run_path.name),
        "size_mb": sum(f.stat().st_size for f in run_path.rglob("*") if f.is_file())
        / (1024 * 1024),
        "has_results": (run_path / "all_results.json").exists(),
        "models": [],
        "scenarios": 0,
    }

    # Try to get model info from results
    results_file = run_path / "all_results.json"
    if results_file.exists():
        try:
            with open(results_file) as f:
                data = json.load(f)
                if isinstance(data, list):
                    info["scenarios"] = len(data)
                    info["models"] = list(set(r.get("model", "unknown") for r in data))
        except (json.JSONDecodeError, KeyError):
            pass

    return info


def list_runs(results_dir: Path) -> List[Dict[str, Any]]:
    """List all run directories with info."""
    runs = []
    for d in sorted(results_dir.iterdir()):
        if d.is_dir() and d.name.startswith("run_"):
            runs.append(get_run_info(d))
    return runs


def archive_runs(
    before_date: Optional[datetime] = None,
    keep_recent: Optional[int] = None,
    dry_run: bool = False,
) -> Tuple[List[Path], List[Path]]:
    """
    Archive run directories.

    Returns (archived, kept) lists of paths.
    """
    root = get_project_root()
    results_dir = root / "results"
    archive_dir = results_dir / "archive"

    if not results_dir.exists():
        return [], []

    runs = list_runs(results_dir)

    # Determine what to archive
    to_archive = []
    to_keep = []

    if keep_recent is not None:
        # Sort by date descending, keep N most recent
        sorted_runs = sorted(runs, key=lambda r: r["date"] or datetime.min, reverse=True)
        to_keep = sorted_runs[:keep_recent]
        to_archive = sorted_runs[keep_recent:]
    elif before_date is not None:
        for run in runs:
            if run["date"] and run["date"] < before_date:
                to_archive.append(run)
            else:
                to_keep.append(run)
    else:
        # Default: archive everything before today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for run in runs:
            if run["date"] and run["date"] < today:
                to_archive.append(run)
            else:
                to_keep.append(run)

    # Perform archive
    archived_paths = []
    if not dry_run and to_archive:
        archive_dir.mkdir(parents=True, exist_ok=True)
        for run in to_archive:
            src = run["path"]
            dst = archive_dir / run["name"]
            if dst.exists():
                # Add suffix if already exists
                i = 1
                while dst.exists():
                    dst = archive_dir / f"{run['name']}_{i}"
                    i += 1
            shutil.move(str(src), str(dst))
            archived_paths.append(dst)

    return (
        [r["path"] for r in to_archive] if dry_run else archived_paths,
        [r["path"] for r in to_keep],
    )


def print_archive_report(
    to_archive: List[Path],
    to_keep: List[Path],
    dry_run: bool = False,
    console: Optional[Any] = None,
) -> None:
    """Print archive report."""
    if console is None and RICH_AVAILABLE:
        console = Console()

    def out(msg: str, style: str = None):
        if console and style:
            console.print(msg, style=style)
        elif console:
            console.print(msg)
        else:
            import re

            plain = re.sub(r"\[/?[^\]]+\]", "", msg)
            print(plain)

    action = "Would archive" if dry_run else "Archived"

    out(f"\n[bold]═══ Archive Report ═══[/bold]\n", "bold")

    if to_archive:
        out(f"[yellow]{action} {len(to_archive)} run(s):[/yellow]")
        for p in to_archive:
            out(f"  • {p.name}")
    else:
        out("[green]Nothing to archive[/green]")

    out(f"\n[green]Keeping {len(to_keep)} run(s):[/green]")
    for p in to_keep:
        out(f"  • {p.name}")

    out("")


def run_archive(
    before: Optional[str] = None,
    keep: Optional[int] = None,
    dry_run: bool = False,
) -> int:
    """Run archive command."""
    console = Console() if RICH_AVAILABLE else None

    before_date = None
    if before:
        try:
            before_date = datetime.strptime(before, "%Y%m%d")
        except ValueError:
            print(f"Invalid date format: {before}. Use YYYYMMDD.")
            return 1

    archived, kept = archive_runs(
        before_date=before_date,
        keep_recent=keep,
        dry_run=dry_run,
    )

    print_archive_report(archived, kept, dry_run=dry_run, console=console)

    return 0


def run_list() -> int:
    """List all runs with details."""
    console = Console() if RICH_AVAILABLE else None
    root = get_project_root()
    results_dir = root / "results"

    runs = list_runs(results_dir)

    if not runs:
        print("No runs found.")
        return 0

    if RICH_AVAILABLE and console:
        table = Table(title="Benchmark Runs")
        table.add_column("Date", style="cyan")
        table.add_column("Run ID")
        table.add_column("Models")
        table.add_column("Scenarios", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Results")

        for run in sorted(runs, key=lambda r: r["date"] or datetime.min, reverse=True):
            date_str = run["date"].strftime("%Y-%m-%d") if run["date"] else "unknown"
            models = ", ".join(run["models"][:2])
            if len(run["models"]) > 2:
                models += f" +{len(run['models'])-2}"

            table.add_row(
                date_str,
                run["name"],
                models or "-",
                str(run["scenarios"]) if run["scenarios"] else "-",
                f"{run['size_mb']:.1f}MB",
                "✓" if run["has_results"] else "✗",
            )

        console.print(table)
    else:
        for run in sorted(runs, key=lambda r: r["date"] or datetime.min, reverse=True):
            date_str = run["date"].strftime("%Y-%m-%d") if run["date"] else "unknown"
            print(f"{date_str} | {run['name']} | {run['size_mb']:.1f}MB")

    # Also check archive
    archive_dir = results_dir / "archive"
    if archive_dir.exists():
        archived = list(archive_dir.iterdir())
        if archived:
            print(f"\n[Archived: {len(archived)} runs in results/archive/]")

    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Archive InvisibleBench runs")
    parser.add_argument("--before", type=str, help="Archive runs before date (YYYYMMDD)")
    parser.add_argument("--keep", type=int, help="Keep N most recent runs")
    parser.add_argument("--list", action="store_true", dest="list_runs", help="List runs (dry run)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be archived")
    args = parser.parse_args(argv)

    if args.list_runs:
        return run_list()

    return run_archive(
        before=args.before,
        keep=args.keep,
        dry_run=args.dry_run or args.list_runs,
    )


if __name__ == "__main__":
    import sys

    sys.exit(main())
