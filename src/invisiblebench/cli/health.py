#!/usr/bin/env python3
"""Health check for InvisibleBench results and leaderboard."""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from invisiblebench.utils.benchmark_inventory import get_project_root
from invisiblebench.utils.io import leaderboard_rows

try:
    from rich.console import Console
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


def load_leaderboard() -> dict[str, Any]:
    """Load the current leaderboard."""
    root = get_project_root()
    lb_path = root / "data" / "leaderboard" / "leaderboard.json"
    if lb_path.exists():
        with open(lb_path) as f:
            return json.load(f)
    raise FileNotFoundError(f"Leaderboard not found: {lb_path}")


def analyze_leaderboard(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze leaderboard for issues."""
    if data.get("schema") != "safety-care/v1":
        if "overall_leaderboard" in data:
            raise ValueError(
                "health only accepts safety-care/v1 leaderboards; "
                "retired overall_leaderboard artifacts require explicit archive tooling"
            )
        raise ValueError(
            f"health only accepts safety-care/v1 leaderboards; got schema={data.get('schema')!r}"
        )
    return _analyze_safety_care_leaderboard(data)


def _analyze_safety_care_leaderboard(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze the current lean safety-care/v1 leaderboard shape."""
    expected_safety = {"crisis", "scope", "identity", "autonomy"}
    expected_care = {"belonging", "attunement", "relational", "advocacy", "trauma_awareness"}
    scan_meta = data.get("scan_metadata") or {}
    results = {
        "schema": "safety-care/v1",
        "models": [],
        "scenario_issues": defaultdict(list),
        "clean_models": [],
        "models_with_errors": [],
        "models_incomplete": [],
        "suspect_scenarios": {},
        "schema_warnings": [],
    }

    for model_data in leaderboard_rows(data):
        model_name = str(model_data.get("model") or "<unknown>")
        safety_lines = set(((model_data.get("safety") or {}).get("lines") or {}).keys())
        care_qualities = set(((model_data.get("care") or {}).get("qualities") or {}).keys())
        missing_safety = sorted(expected_safety - safety_lines)
        missing_care = sorted(expected_care - care_qualities)
        missing = len(missing_safety) + len(missing_care)
        model_info = {
            "name": model_name,
            "score": None,
            "scenarios_run": scan_meta.get("total_scenarios", 0),
            "errors": 0,
            "error_scenarios": [],
            "missing": missing,
            "missing_safety_lines": missing_safety,
            "missing_care_qualities": missing_care,
        }
        results["models"].append(model_info)
        if missing:
            results["models_incomplete"].append(model_info)
        else:
            results["clean_models"].append(model_info)

    artifact_validation = scan_meta.get("artifact_validation")
    if isinstance(artifact_validation, dict):
        _append_artifact_validation_warnings(results["schema_warnings"], artifact_validation)
    current_contract_validation = scan_meta.get("current_contract_validation")
    if isinstance(current_contract_validation, dict):
        _append_current_contract_warnings(
            results["schema_warnings"], current_contract_validation
        )

    return results


def _append_artifact_validation_warnings(
    warnings: list[str], artifact_validation: dict[str, Any]
) -> None:
    """Expose non-publishable scan residue already stamped in the artifact."""
    warning_fields = (
        ("unclear_mode_verdicts", "strict_qa_blocker_unclear_mode_verdicts"),
        ("gate_unclear_mode_verdicts", "gate_unclear_mode_verdicts"),
        ("fail_without_evidence", "fail_without_evidence"),
        ("prompt_missing", "prompt_missing"),
        ("no_verifier_available", "no_verifier_available"),
        ("fatal_verifier_errors", "fatal_verifier_errors"),
    )
    for field, label in warning_fields:
        value = int(artifact_validation.get(field) or 0)
        if value:
            warnings.append(f"{label}={value}")

    parse_rows = int(artifact_validation.get("scorer_parse_error_results") or 0)
    parse_errors = int(artifact_validation.get("scorer_parse_errors") or 0)
    if parse_rows or parse_errors:
        warnings.append(f"scorer_parse_errors={parse_errors} across {parse_rows} rows")

    truncated_rows = int(artifact_validation.get("scorer_raw_outputs_truncated_results") or 0)
    truncated_samples = int(
        artifact_validation.get("scorer_raw_outputs_truncated_samples") or 0
    )
    if truncated_rows or truncated_samples:
        warnings.append(
            "scorer_raw_outputs_truncated="
            f"{truncated_samples} samples across {truncated_rows} rows"
        )


def _append_current_contract_warnings(
    warnings: list[str], current_contract_validation: dict[str, Any]
) -> None:
    """Expose current scenario/check contract gaps stamped by generation."""
    for field in (
        "missing_scenarios",
        "extra_scenarios",
        "rows_with_missing_checks",
        "missing_check_instances",
        "rows_with_extra_checks",
        "extra_check_instances",
    ):
        value = int(current_contract_validation.get(field) or 0)
        if value:
            warnings.append(f"current_contract_{field}={value}")


def append_local_web_projection_health(
    analysis: dict[str, Any],
    *,
    root: Path | None = None,
) -> None:
    """Append read-only health warnings for the checked-in web projection.

    This intentionally does not write `leaderboard_web.json`; publish/sync is
    guarded elsewhere. The health check only makes stale generated artifacts
    visible.
    """
    root = root or get_project_root()
    source = root / "data" / "leaderboard" / "leaderboard.json"
    target = root / "data" / "leaderboard" / "leaderboard_web.json"
    warnings = analysis.setdefault("schema_warnings", [])

    if not source.exists():
        return
    if not target.exists():
        warnings.append(f"local_web_projection_missing={target}")
        return

    try:
        sync_path = root / "delivery" / "sync_web_bench.py"
        if not sync_path.exists():
            sync_path = get_project_root() / "delivery" / "sync_web_bench.py"
        spec = importlib.util.spec_from_file_location("invisiblebench_delivery_sync_web_bench", sync_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {sync_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        compute_sync_status = module.compute_sync_status
        status = compute_sync_status(source, target)
    except (OSError, ValueError, json.JSONDecodeError, ImportError, AttributeError) as exc:
        warnings.append(f"local_web_projection_check_failed={type(exc).__name__}: {exc}")
        return

    if not status.in_sync:
        warnings.append(
            "local_web_projection_drift="
            f"target={status.target} "
            f"source_generated_at={status.source_generated_at} "
            f"target_generated_at={status.target_generated_at}"
        )


def print_health_report(analysis: dict[str, Any], verbose: bool = False) -> None:
    """Print health report."""
    console = Console() if RICH_AVAILABLE else None

    def out(msg: str, style: str | None = None):
        if console and style:
            console.print(msg, style=style)
        elif console:
            console.print(msg)
        else:
            # Strip rich markup for plain output
            import re

            plain = re.sub(r"\[/?[^\]]+\]", "", msg)
            print(plain)

    out("\n[bold]═══ InvisibleBench Health Report ═══[/bold]\n", "bold")

    # Summary stats
    total_models = len(analysis["models"])
    clean = len(analysis["clean_models"])
    with_errors = len(analysis["models_with_errors"])
    incomplete = len(analysis["models_incomplete"])

    out(
        f"Models: {total_models} total, [green]{clean} clean[/green], [yellow]{with_errors} with errors[/yellow], [red]{incomplete} incomplete[/red]\n"
    )
    if analysis.get("schema") == "safety-care/v1":
        out("Contract: safety-care/v1 lean leaderboard (no composite/rank)\n", "dim")

    # Models with errors
    if analysis["models_with_errors"]:
        out("[bold yellow]⚠ Models with errors:[/bold yellow]", "bold yellow")
        for m in analysis["models_with_errors"]:
            out(f"  • {m['name']}: {m['errors']} errors")
            if verbose:
                for scenario in m["error_scenarios"]:
                    out(f"    - {scenario}", "dim")
        out("")

    # Incomplete models
    if analysis["models_incomplete"]:
        out("[bold red]✗ Incomplete models:[/bold red]", "bold red")
        for m in analysis["models_incomplete"]:
            if analysis.get("schema") == "safety-care/v1":
                parts = []
                if m.get("missing_safety_lines"):
                    parts.append(f"safety={','.join(m['missing_safety_lines'])}")
                if m.get("missing_care_qualities"):
                    parts.append(f"care={','.join(m['missing_care_qualities'])}")
                out(f"  • {m['name']}: missing {'; '.join(parts)}")
            else:
                out(f"  • {m['name']}: missing {m['missing']} scenario(s)")
        out("")

    # Suspect scenarios (failing on 3+ models)
    if analysis["suspect_scenarios"]:
        out(
            "[bold magenta]🔍 Suspect scenarios (failing on 3+ models):[/bold magenta]",
            "bold magenta",
        )
        for scenario, models in sorted(
            analysis["suspect_scenarios"].items(), key=lambda x: -len(x[1])
        ):
            out(f"  • {scenario}: {len(models)} models")
            if verbose:
                out(f"    [{', '.join(models)}]", "dim")
        out("")

    # Schema field warnings
    schema_warnings = analysis.get("schema_warnings", [])
    if schema_warnings:
        out("[bold yellow]⚠ Schema warnings:[/bold yellow]", "bold yellow")
        for w in schema_warnings:
            out(f"  • {w}")
        out("")

    # Clean models
    if analysis["clean_models"]:
        out("[bold green]✓ Clean models:[/bold green]", "bold green")
        for m in analysis["clean_models"]:
            if m.get("score") is None:
                out(f"  • {m['name']}")
            else:
                out(f"  • {m['name']} ({m['score']:.3f})")
        out("")

    # Leaderboard
    if RICH_AVAILABLE and console:
        table = Table(title="Current Leaderboard")
        table.add_column("#", style="dim")
        table.add_column("Model")
        if analysis.get("schema") == "safety-care/v1":
            table.add_column("Scenarios", justify="right")
        else:
            table.add_column("Score", justify="right")
        table.add_column("Status")

        if analysis.get("schema") == "safety-care/v1":
            ordered_models = sorted(analysis["models"], key=lambda x: x["name"])
        else:
            ordered_models = sorted(analysis["models"], key=lambda x: -x["score"])

        for i, m in enumerate(ordered_models, 1):
            if m["errors"] > 0:
                status = f"[yellow]⚠ {m['errors']} errors[/yellow]"
            elif m["missing"] > 0:
                status = f"[red]✗ {m['missing']} missing[/red]"
            else:
                status = "[green]✓[/green]"

            metric = (
                str(m.get("scenarios_run", 0))
                if analysis.get("schema") == "safety-care/v1"
                else f"{m['score']:.3f}"
            )
            table.add_row(str(i), m["name"], metric, status)

        console.print(table)

    out("")


def run_health(verbose: bool = False) -> int:
    """Run health check and print report."""
    try:
        data = load_leaderboard()
    except FileNotFoundError as e:
        print(f"Error running health check: {e}")
        return 2

    try:
        analysis = analyze_leaderboard(data)
    except ValueError as e:
        print(f"Error running health check: {e}")
        return 1

    append_local_web_projection_health(analysis)
    print_health_report(analysis, verbose=verbose)

    # Return non-zero if there are issues
    if analysis["models_with_errors"] or analysis["models_incomplete"]:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for standalone usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Check InvisibleBench health")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")
    args = parser.parse_args(argv)
    return run_health(verbose=args.verbose)


if __name__ == "__main__":
    import sys

    sys.exit(main())
