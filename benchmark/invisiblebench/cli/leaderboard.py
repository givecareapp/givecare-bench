#!/usr/bin/env python3
"""
Leaderboard management for InvisibleBench.

Usage:
    bench leaderboard add results/run_*/all_results.json   # Add/update models from a run
    bench leaderboard rebuild                               # Rebuild from leaderboard_ready/
    bench leaderboard status                                # Show current leaderboard + health
    bench leaderboard status -v                             # Verbose (per-scenario details)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console

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


def _canonical_dir() -> Path:
    """Return the leaderboard_ready/ directory."""
    return get_project_root() / "results" / "leaderboard_ready"


def _leaderboard_output() -> Path:
    """Return the leaderboard output directory."""
    return get_project_root() / "benchmark" / "website" / "data"


def _prepare(input_path: Path, output_dir: Path) -> List[str]:
    """Run prepare_for_leaderboard.py and return list of model names added."""
    root = get_project_root()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "benchmark" / "scripts" / "validation" / "prepare_for_leaderboard.py"),
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    # Parse model names from output lines like "✓ Claude Opus 4.6: /tmp/..."
    models = []
    for line in result.stdout.splitlines():
        if line.startswith("✓ "):
            name = line.split(":")[0].removeprefix("✓ ").strip()
            models.append(name)
    return models


def _generate(input_dir: Path, output_dir: Path) -> None:
    """Run generate_leaderboard.py."""
    root = get_project_root()
    subprocess.run(
        [
            sys.executable,
            str(root / "benchmark" / "scripts" / "leaderboard" / "generate_leaderboard.py"),
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def add_results(results_path: Path) -> int:
    """Add model results to the leaderboard.

    Extracts per-model canonical files from an all_results.json,
    copies them into leaderboard_ready/, regenerates leaderboard.json,
    and runs health check.
    """
    console = Console() if RICH_AVAILABLE else None

    def out(msg: str) -> None:
        if console:
            console.print(msg)
        else:
            import re
            print(re.sub(r"\[/?[^\]]+\]", "", msg))

    if not results_path.exists():
        out(f"[red]File not found: {results_path}[/red]")
        return 1

    canonical = _canonical_dir()
    canonical.mkdir(parents=True, exist_ok=True)

    # Prepare per-model files in a temp dir first
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        models = _prepare(results_path, tmp)

        if not models:
            out("[red]No models found in results file[/red]")
            return 1

        # Check scenario count mismatch before copying
        existing_counts: Dict[str, int] = {}
        for f in canonical.glob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            existing_counts[data.get("model", f.stem)] = len(data.get("scenarios", []))

        new_counts: Dict[str, int] = {}
        for f in tmp.glob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            new_counts[data.get("model", f.stem)] = len(data.get("scenarios", []))

        if existing_counts:
            existing_max = max(existing_counts.values())
            new_max = max(new_counts.values()) if new_counts else 0
            if new_max != existing_max and new_max > 0:
                out(
                    f"[yellow]⚠ Scenario count mismatch: existing models have {existing_max} scenarios, "
                    f"new model(s) have {new_max}[/yellow]"
                )
                out("[yellow]  Scores are comparable but health check will note the difference.[/yellow]")

        # Copy into canonical dir (overwrite existing models)
        for f in tmp.glob("*.json"):
            dest = canonical / f.name
            dest.write_text(f.read_text())

        out(f"\n[green]Added/updated {len(models)} model(s):[/green]")
        for m in models:
            count = new_counts.get(m, "?")
            out(f"  • {m} ({count} scenarios)")

    # Regenerate leaderboard
    out("\n[bold]Regenerating leaderboard...[/bold]")
    _generate(canonical, _leaderboard_output())

    # Run health check
    out("")
    from invisiblebench.cli.health import run_health
    return run_health(verbose=False)


def rebuild_leaderboard() -> int:
    """Rebuild leaderboard.json from leaderboard_ready/ canonical files."""
    console = Console() if RICH_AVAILABLE else None

    def out(msg: str) -> None:
        if console:
            console.print(msg)
        else:
            import re
            print(re.sub(r"\[/?[^\]]+\]", "", msg))

    canonical = _canonical_dir()
    if not canonical.exists() or not list(canonical.glob("*.json")):
        out("[red]No canonical files found in results/leaderboard_ready/[/red]")
        out("[dim]Run 'bench leaderboard add <results.json>' first.[/dim]")
        return 1

    files = list(canonical.glob("*.json"))
    out(f"[bold]Rebuilding leaderboard from {len(files)} canonical file(s)...[/bold]")

    _generate(canonical, _leaderboard_output())

    out("[green]Leaderboard rebuilt.[/green]\n")
    from invisiblebench.cli.health import run_health
    return run_health(verbose=False)


def run_leaderboard(
    action: str,
    results_path: Optional[str] = None,
    verbose: bool = False,
) -> int:
    """Dispatch leaderboard subcommands."""
    if action == "add":
        if not results_path:
            print("Usage: bench leaderboard add <path/to/all_results.json>")
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
