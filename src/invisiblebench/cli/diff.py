"""Diff/comparison utilities: run reference resolution, result aggregation, and diff reporting."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from invisiblebench.cli._console import make_console as _console
from invisiblebench.run_artifacts import load_result_rows
from invisiblebench.utils.benchmark_inventory import get_project_root

try:
    from rich.table import Table

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False
    Table = None  # type: ignore


def _infer_run_dir_for_output(source: Path) -> Path:
    if source.is_dir():
        return source.parent if source.name == "model_results" else source
    if source.parent.name == "model_results":
        return source.parent.parent
    return source.parent


def resolve_run_reference(run_ref: str, project_root: Path | None = None) -> Path:
    """Resolve a run reference to an all_results.json path.

    Accepted formats:
    - Path to all_results.json
    - Path to a run directory containing all_results.json
    - Run ID or unique prefix matching a run directory in results/ or results/archive/
    """
    root = project_root or get_project_root()
    ref_path = Path(run_ref).expanduser()
    candidates_to_try = [ref_path]
    if not ref_path.is_absolute():
        candidates_to_try.append(root / ref_path)

    # Explicit path reference (file or directory)
    for candidate in candidates_to_try:
        if candidate.is_file():
            if candidate.name != "all_results.json":
                raise ValueError(
                    f"Expected an all_results.json file, got: {run_ref} ({candidate.name})"
                )
            return candidate.resolve()

        if candidate.is_dir():
            for name in ("all_results.json", "givecare_results.json"):
                results_file = candidate / name
                if results_file.exists():
                    return results_file.resolve()
            model_results_dir = candidate / "model_results"
            if model_results_dir.exists():
                return candidate.resolve()
            raise ValueError(f"Run directory missing supported result artifacts: {candidate}")

    # Run ID / prefix reference
    results_dir = root / "results"
    search_dirs = [results_dir, results_dir / "archive"]

    names_to_match = {run_ref}
    if not run_ref.startswith("run_"):
        names_to_match.add(f"run_{run_ref}")

    matched_runs: list[Path] = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for child in search_dir.iterdir():
            if not child.is_dir() or not child.name.startswith("run_"):
                continue
            if any(child.name.startswith(name) for name in names_to_match):
                matched_runs.append(child)

    if not matched_runs:
        raise ValueError(
            f"Could not resolve run reference '{run_ref}'. "
            "Provide an all_results.json path, run directory, or unique run ID prefix."
        )

    if len(matched_runs) > 1:
        matches = ", ".join(str(p.relative_to(root)) for p in sorted(matched_runs))
        raise ValueError(f"Ambiguous run reference '{run_ref}' matched multiple runs: {matches}")

    run_dir = matched_runs[0]
    for name in ("all_results.json", "givecare_results.json"):
        resolved_results = run_dir / name
        if resolved_results.exists():
            return resolved_results.resolve()
    if (run_dir / "model_results").exists():
        return run_dir.resolve()
    raise ValueError(f"Resolved run is missing supported result artifacts: {run_dir}")


def load_run_results(results_path: Path) -> list[dict[str, Any]]:
    """Load a run's result rows from any supported artifact source."""
    return [row for row in load_result_rows(results_path) if isinstance(row, dict)]


def aggregate_results_by_model(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate per-model average overall score and status counts."""
    by_model: dict[str, dict[str, Any]] = {}

    for row in results:
        model = str(row.get("model") or row.get("model_id") or "unknown_model")
        if model not in by_model:
            by_model[model] = {
                "score_sum": 0.0,
                "score_count": 0,
                "status_counts": {"pass": 0, "fail": 0, "error": 0},
            }

        model_stats = by_model[model]

        score = row.get("overall_score")
        if isinstance(score, (int, float)):
            model_stats["score_sum"] += float(score)
            model_stats["score_count"] += 1

        status = str(row.get("status", "")).lower()
        if status in ("pass", "fail", "error"):
            model_stats["status_counts"][status] += 1
        elif row.get("hard_fail"):
            model_stats["status_counts"]["fail"] += 1
        else:
            model_stats["status_counts"]["pass"] += 1

    for model_stats in by_model.values():
        score_count = model_stats["score_count"]
        model_stats["avg_overall_score"] = (
            model_stats["score_sum"] / score_count if score_count else None
        )
        model_stats["hard_failure_count"] = (
            model_stats["status_counts"]["fail"] + model_stats["status_counts"]["error"]
        )
        del model_stats["score_sum"]
        del model_stats["score_count"]

    return by_model


def compute_run_diff(
    base_by_model: dict[str, dict[str, Any]], new_by_model: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Compute per-model deltas and regression flags."""
    model_names = sorted(set(base_by_model) | set(new_by_model))
    comparisons: list[dict[str, Any]] = []

    for model in model_names:
        base_stats = base_by_model.get(model)
        new_stats = new_by_model.get(model)

        base_avg = base_stats["avg_overall_score"] if base_stats else None
        new_avg = new_stats["avg_overall_score"] if new_stats else None
        delta = (new_avg - base_avg) if (base_avg is not None and new_avg is not None) else None

        base_hard_failures = base_stats["hard_failure_count"] if base_stats else None
        new_hard_failures = new_stats["hard_failure_count"] if new_stats else None

        regressed = False
        if delta is not None and delta < 0:
            regressed = True
        if (
            base_hard_failures is not None
            and new_hard_failures is not None
            and new_hard_failures > base_hard_failures
        ):
            regressed = True

        comparisons.append(
            {
                "model": model,
                "base_avg_overall_score": base_avg,
                "new_avg_overall_score": new_avg,
                "delta_avg_overall_score": delta,
                "base_status_counts": base_stats["status_counts"] if base_stats else None,
                "new_status_counts": new_stats["status_counts"] if new_stats else None,
                "regressed": regressed,
            }
        )

    return comparisons


def _format_score(value: float | None) -> str:
    """Format a score value for terminal output."""
    if value is None:
        return "N/A"
    return f"{value:.3f}"


def _format_delta(value: float | None) -> str:
    """Format a score delta value for terminal output."""
    if value is None:
        return "N/A"
    return f"{value:+.3f}"


def _format_status_counts(counts: dict[str, int] | None) -> str:
    """Format pass/fail/error status counts for terminal output."""
    if not counts:
        return "N/A"
    return f"{counts.get('pass', 0)}/{counts.get('fail', 0)}/{counts.get('error', 0)}"


def _print_diff_table(comparisons: list[dict[str, Any]]) -> None:
    """Print per-model diff table with regression indicators."""
    headers = [
        "Model",
        "Base Avg",
        "New Avg",
        "Delta",
        "Base P/F/E",
        "New P/F/E",
        "Reg",
    ]

    if _RICH_AVAILABLE:
        console = _console()
        table = Table(title="Benchmark Diff (per model)")
        table.add_column("Model", no_wrap=True)
        table.add_column("Base Avg", justify="right")
        table.add_column("New Avg", justify="right")
        table.add_column("Delta", justify="right")
        table.add_column("Base P/F/E", justify="right")
        table.add_column("New P/F/E", justify="right")
        table.add_column("Reg", justify="center")

        for comp in comparisons:
            delta = comp["delta_avg_overall_score"]
            regressed = comp["regressed"]

            if delta is None:
                delta_str = "[dim]N/A[/dim]"
            elif delta < 0:
                delta_str = f"[red]{_format_delta(delta)}[/red]"
            elif delta > 0:
                delta_str = f"[green]{_format_delta(delta)}[/green]"
            else:
                delta_str = _format_delta(delta)

            regression_str = "[red]YES[/red]" if regressed else "NO"

            table.add_row(
                str(comp["model"]),
                _format_score(comp["base_avg_overall_score"]),
                _format_score(comp["new_avg_overall_score"]),
                delta_str,
                _format_status_counts(comp["base_status_counts"]),
                _format_status_counts(comp["new_status_counts"]),
                regression_str,
            )

        console.print(table)
        return

    rows: list[list[str]] = []
    for comp in comparisons:
        rows.append(
            [
                str(comp["model"]),
                _format_score(comp["base_avg_overall_score"]),
                _format_score(comp["new_avg_overall_score"]),
                _format_delta(comp["delta_avg_overall_score"]),
                _format_status_counts(comp["base_status_counts"]),
                _format_status_counts(comp["new_status_counts"]),
                "YES" if comp["regressed"] else "NO",
            ]
        )

    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(row: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    print(_fmt_row(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(_fmt_row(row))


def diff_command(args) -> int:
    """Compare two benchmark runs."""
    try:
        base_results = resolve_run_reference(args.base_run)
        new_results = resolve_run_reference(args.new_run)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    try:
        base_rows = load_run_results(base_results)
        new_rows = load_run_results(new_results)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    base_by_model = aggregate_results_by_model(base_rows)
    new_by_model = aggregate_results_by_model(new_rows)
    comparisons = compute_run_diff(base_by_model, new_by_model)

    print(f"Base run: {base_results}")
    print(f"New run:  {new_results}")
    _print_diff_table(comparisons)
    print(f"Compared {len(comparisons)} model(s).")
    return 0
