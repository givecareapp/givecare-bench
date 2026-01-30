#!/usr/bin/env python3
"""
Health check for InvisibleBench results and leaderboard.

Usage:
    bench health              # Check current leaderboard health
    bench health --verbose    # Include per-scenario details
"""
from __future__ import annotations

import json
from collections import defaultdict
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


def load_leaderboard() -> Dict[str, Any]:
    """Load the current leaderboard."""
    root = get_project_root()
    lb_path = root / "benchmark" / "website" / "data" / "leaderboard.json"
    if not lb_path.exists():
        raise FileNotFoundError(f"Leaderboard not found: {lb_path}")
    with open(lb_path) as f:
        return json.load(f)


def analyze_leaderboard(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze leaderboard for issues."""
    results = {
        "models": [],
        "scenario_issues": defaultdict(list),
        "clean_models": [],
        "models_with_errors": [],
        "models_incomplete": [],
    }
    
    total_scenarios = data["metadata"].get("total_scenarios", 29)
    
    for model_data in data["overall_leaderboard"]:
        model_name = model_data["model"]
        scenarios = model_data.get("scenarios", [])
        
        # Check for errors
        errors = [s for s in scenarios if s.get("status") == "error"]
        
        # Check for missing scenarios
        scenario_count = len(scenarios)
        missing = total_scenarios - scenario_count
        
        model_info = {
            "name": model_name,
            "score": model_data["overall_score"],
            "scenarios_run": scenario_count,
            "errors": len(errors),
            "error_scenarios": [e["scenario"] for e in errors],
            "missing": missing,
        }
        results["models"].append(model_info)
        
        # Categorize
        if errors:
            results["models_with_errors"].append(model_info)
            for e in errors:
                results["scenario_issues"][e["scenario"]].append(model_name)
        
        if missing > 0:
            results["models_incomplete"].append(model_info)
        
        if not errors and missing == 0:
            results["clean_models"].append(model_info)
    
    # Find scenarios that fail on multiple models (likely scenario bugs)
    results["suspect_scenarios"] = {
        scenario: models 
        for scenario, models in results["scenario_issues"].items()
        if len(models) >= 3
    }
    
    return results


def print_health_report(analysis: Dict[str, Any], verbose: bool = False) -> None:
    """Print health report."""
    console = Console() if RICH_AVAILABLE else None
    
    def out(msg: str, style: str = None):
        if console and style:
            console.print(msg, style=style)
        elif console:
            console.print(msg)
        else:
            # Strip rich markup for plain output
            import re
            plain = re.sub(r'\[/?[^\]]+\]', '', msg)
            print(plain)
    
    out("\n[bold]═══ InvisibleBench Health Report ═══[/bold]\n", "bold")
    
    # Summary stats
    total_models = len(analysis["models"])
    clean = len(analysis["clean_models"])
    with_errors = len(analysis["models_with_errors"])
    incomplete = len(analysis["models_incomplete"])
    
    out(f"Models: {total_models} total, [green]{clean} clean[/green], [yellow]{with_errors} with errors[/yellow], [red]{incomplete} incomplete[/red]\n")
    
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
            out(f"  • {m['name']}: missing {m['missing']} scenario(s)")
        out("")
    
    # Suspect scenarios (failing on 3+ models)
    if analysis["suspect_scenarios"]:
        out("[bold magenta]🔍 Suspect scenarios (failing on 3+ models):[/bold magenta]", "bold magenta")
        for scenario, models in sorted(analysis["suspect_scenarios"].items(), key=lambda x: -len(x[1])):
            out(f"  • {scenario}: {len(models)} models")
            if verbose:
                out(f"    [{', '.join(models)}]", "dim")
        out("")
    
    # Clean models
    if analysis["clean_models"]:
        out("[bold green]✓ Clean models:[/bold green]", "bold green")
        for m in analysis["clean_models"]:
            out(f"  • {m['name']} ({m['score']:.3f})")
        out("")
    
    # Leaderboard
    if RICH_AVAILABLE and console:
        table = Table(title="Current Leaderboard")
        table.add_column("#", style="dim")
        table.add_column("Model")
        table.add_column("Score", justify="right")
        table.add_column("Status")
        
        for i, m in enumerate(sorted(analysis["models"], key=lambda x: -x["score"]), 1):
            if m["errors"] > 0:
                status = f"[yellow]⚠ {m['errors']} errors[/yellow]"
            elif m["missing"] > 0:
                status = f"[red]✗ {m['missing']} missing[/red]"
            else:
                status = "[green]✓[/green]"
            
            table.add_row(str(i), m["name"], f"{m['score']:.3f}", status)
        
        console.print(table)
    
    out("")


def run_health(verbose: bool = False) -> int:
    """Run health check and print report."""
    try:
        data = load_leaderboard()
        analysis = analyze_leaderboard(data)
        print_health_report(analysis, verbose=verbose)
        
        # Return non-zero if there are issues
        if analysis["models_with_errors"] or analysis["models_incomplete"]:
            return 1
        return 0
    except Exception as e:
        print(f"Error running health check: {e}")
        return 2


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point for standalone usage."""
    import argparse
    parser = argparse.ArgumentParser(description="Check InvisibleBench health")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed info")
    args = parser.parse_args(argv)
    return run_health(verbose=args.verbose)


if __name__ == "__main__":
    import sys
    sys.exit(main())
