"""Transcript-run startup banner."""
from __future__ import annotations

from typing import Any

from invisiblebench.utils.benchmark_inventory import get_benchmark_version


def print_banner(
    console: Any,
    models: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
    total_cost: float,
) -> None:
    """Print startup banner."""
    cat_counts = []
    for cat in sorted({s["category"] for s in scenarios}):
        count = len([s for s in scenarios if s["category"] == cat])
        cat_counts.append(f"{cat}:{count}")
    cats_str = " ".join(cat_counts)

    console.print()
    console.print(
        f"[bold cyan]InvisibleBench[/bold cyan] [dim]v{get_benchmark_version()}[/dim]  "
        f"{len(models)} model{'s' if len(models) > 1 else ''} × {len(scenarios)} scenarios  "
        f"[dim]({cats_str})[/dim]  "
        f"[magenta]~${total_cost:.2f}[/magenta]"
    )
    console.print()
