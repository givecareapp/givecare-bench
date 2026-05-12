#!/usr/bin/env python3
"""Leaderboard management for InvisibleBench."""
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

from invisiblebench.results_io import write_model_results
from invisiblebench.run_artifacts import load_result_rows
from invisiblebench.run_audit import find_existing_audit_file
from invisiblebench.utils.benchmark_inventory import (
    PUBLIC_CATEGORIES,
    get_benchmark_version,
    get_project_root,
)
from invisiblebench.utils.turn_index import lint_turn_indices

try:
    from rich.console import Console

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


def _canonical_dir() -> Path:
    """Return the leaderboard_ready/ directory."""
    return get_project_root() / "results" / "leaderboard_ready"


def _leaderboard_output() -> Path:
    """Return the leaderboard output directory."""
    return get_project_root() / "data" / "leaderboard"


def _prepare(input_path: Path, output_dir: Path) -> list[str]:
    """Normalize flat result rows into canonical per-model files."""
    rows = load_result_rows(input_path)
    if not rows:
        return []
    written = write_model_results(
        rows,
        output_dir,
        benchmark_version=get_benchmark_version(get_project_root()),
    )
    models = []
    for path in written:
        data = json.loads(path.read_text())
        models.append(data.get("model", data.get("model_name", path.stem)))
    return models


def _generate(input_dir: Path, output_dir: Path) -> None:
    """Run scripts/generate_leaderboard.py without requiring scripts/ to be a package."""
    script_path = get_project_root() / "scripts" / "generate_leaderboard.py"
    spec = importlib.util.spec_from_file_location("generate_leaderboard_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load leaderboard generator from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.generate_leaderboard(input_dir, output_dir)


def _load_run_manifest(source: Path) -> dict[str, Any]:
    candidates = []
    if source.is_dir():
        candidates.append(source / "run_manifest.json")
        candidates.append(source.parent / "run_manifest.json")
    else:
        candidates.append(source.parent / "run_manifest.json")
        if source.parent.name == "model_results":
            candidates.append(source.parent.parent / "run_manifest.json")

    for candidate in candidates:
        if candidate.exists():
            return json.loads(candidate.read_text())
    return {}


def _validate_public_scope(source: Path) -> str | None:
    manifest = _load_run_manifest(source)
    if manifest:
        harness = manifest.get("harness")
        mode = manifest.get("mode")
        if harness and (harness != "llm" or mode != "raw"):
            return (
                "Public leaderboard is benchmark-core only. "
                f"Received harness={harness!r}, mode={mode!r}."
            )
    return None


def _lint_public_scenarios() -> list[str]:
    scenario_root = get_project_root() / "benchmark" / "scenarios"
    warnings: list[str] = []
    for category in PUBLIC_CATEGORIES:
        for scenario_path in sorted((scenario_root / category).rglob("*.json")):
            data = json.loads(scenario_path.read_text())
            scenario_id = data.get("scenario_id", scenario_path.name)
            warnings.extend(
                f"{scenario_id}: {warning}" for warning in lint_turn_indices(data)
            )
    return warnings


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

    scope_error = _validate_public_scope(results_path)
    if scope_error:
        out(f"[red]{scope_error}[/red]")
        return 1

    lint_warnings = _lint_public_scenarios()
    if lint_warnings:
        out("[red]Scenario turn-index lint must pass before leaderboard updates.[/red]")
        for warning in lint_warnings[:10]:
            out(f"  • {warning}")
        if len(lint_warnings) > 10:
            out(f"  • ... +{len(lint_warnings) - 10} more")
        return 1

    audit_file = find_existing_audit_file(results_path)
    if audit_file is not None:
        with open(audit_file) as f:
            audit = json.load(f)
        if not audit.get("publishable", False):
            out(
                f"[red]Run audit blocks leaderboard add:[/red] owner={audit.get('primary_owner', 'benchmark')} "
                f"status={audit.get('summary_status', 'BLOCK')}"
            )
            out(f"[dim]See {audit_file}[/dim]")
            return 1

    canonical = _canonical_dir()
    canonical.mkdir(parents=True, exist_ok=True)

    # Accept either a flat all_results.json or a run/model_results directory.
    per_model_source: Path | None = None
    if results_path.is_dir():
        model_results_dir = results_path / "model_results"
        if model_results_dir.exists():
            per_model_source = model_results_dir
        elif list(results_path.glob("*.json")):
            per_model_source = results_path
        else:
            out(f"[red]No model_results/ or JSON files found in: {results_path}[/red]")
            return 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        if per_model_source is not None:
            models = []
            for f in per_model_source.glob("*.json"):
                if f.name.startswith("."):
                    continue
                data = json.loads(f.read_text())
                model_name = data.get("model", data.get("model_name", f.stem))
                models.append(model_name)
                (tmp / f.name).write_text(f.read_text())
        else:
            models = _prepare(results_path, tmp)

        if not models:
            out("[red]No models found in results file[/red]")
            return 1

        existing_counts: dict[str, int] = {}
        for f in canonical.glob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            existing_counts[data.get("model", f.stem)] = len(data.get("scenarios", []))

        new_counts: dict[str, int] = {}
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

        for f in tmp.glob("*.json"):
            dest = canonical / f.name
            dest.write_text(f.read_text())

        out(f"\n[green]Added/updated {len(models)} model(s):[/green]")
        for m in models:
            count = new_counts.get(m, "?")
            out(f"  • {m} ({count} scenarios)")

    out("\n[bold]Regenerating leaderboard...[/bold]")
    _generate(canonical, _leaderboard_output())

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

    lint_warnings = _lint_public_scenarios()
    if lint_warnings:
        out("[red]Scenario turn-index lint must pass before leaderboard rebuild.[/red]")
        return 1

    files = list(canonical.glob("*.json"))
    out(f"[bold]Rebuilding leaderboard from {len(files)} canonical file(s)...[/bold]")

    _generate(canonical, _leaderboard_output())

    out("[green]Leaderboard rebuilt.[/green]\n")
    from invisiblebench.cli.health import run_health
    return run_health(verbose=False)


def run_leaderboard(
    action: str,
    results_path: str | None = None,
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
