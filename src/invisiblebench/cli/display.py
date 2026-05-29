"""Terminal display components: ScenarioDisplay live table and startup banner."""
from __future__ import annotations

import threading
import time
from typing import Any

from invisiblebench.utils.benchmark_inventory import get_benchmark_version

try:
    from rich.text import Text

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False
    Text = None  # type: ignore


class ScenarioDisplay:
    """Renders full scenario list with live status updates. Thread-safe."""

    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, model_name: str, scenarios: list[dict[str, Any]], start_time: float):
        self.model_name = model_name
        self.scenarios = scenarios
        self.start_time = start_time
        self._lock = threading.Lock()
        self._spin_idx = 0

        self.categories = sorted({s["category"] for s in scenarios})
        self.by_category = {c: [s for s in scenarios if s["category"] == c] for c in self.categories}

        # State tracking: scenario path -> {"status": pending|running|pass|fail, "score": int|None}
        self.states: dict[str, dict[str, Any]] = {}
        for s in scenarios:
            self.states[s["path"]] = {"status": "pending", "score": None}

        # Category summaries
        self.cat_scores: dict[str, list[float]] = {c: [] for c in self.categories}
        self.cat_done: dict[str, bool] = dict.fromkeys(self.categories, False)
        self.cat_start_time: dict[str, float] = {}
        self.cat_elapsed: dict[str, float] = dict.fromkeys(self.categories, 0.0)

        # Counters
        self.completed = 0
        self.total = len(scenarios)

        # Current scenario timing
        self.current_scenario_start: float = 0.0
        self.current_scenario_path: str = ""

    def set_running(self, path: str, category: str):
        with self._lock:
            self.states[path]["status"] = "running"
            self.current_scenario_start = time.time()
            self.current_scenario_path = path
            if category not in self.cat_start_time:
                self.cat_start_time[category] = time.time()

    def set_complete(
        self,
        path: str,
        score: float,
        passed: bool,
        category: str,
        score_display: str = "",
        coverage: dict[str, Any] | None = None,
        coverage_invalid: bool = False,
    ):
        with self._lock:
            if coverage_invalid:
                self.states[path]["status"] = "invalid"
            elif passed:
                self.states[path]["status"] = "pass"
            else:
                self.states[path]["status"] = "fail"
            self.states[path]["score"] = int(score * 100)
            self.states[path]["score_display"] = score_display
            self.states[path]["coverage"] = coverage
            self.states[path]["coverage_invalid"] = coverage_invalid
            self.cat_scores[category].append(score)
            self.completed += 1

    def set_category_done(self, category: str):
        with self._lock:
            self.cat_done[category] = True
            if category in self.cat_start_time:
                self.cat_elapsed[category] = time.time() - self.cat_start_time[category]

    def _fmt_time(self, seconds: float) -> str:
        """Format seconds as M:SS."""
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"

    def __rich__(self) -> Text:
        """Render the full display. Thread-safe."""
        now = time.time()
        total_elapsed = now - self.start_time

        # Advance spinner
        self._spin_idx = (self._spin_idx + 1) % len(self.SPINNER)
        spinner = self.SPINNER[self._spin_idx]

        lines = Text()

        with self._lock:
            completed = self.completed
            all_scores = []
            for scores in self.cat_scores.values():
                all_scores.extend(scores)
            avg_score = int(sum(all_scores) / len(all_scores) * 100) if all_scores else 0

            # Scenario time (current running scenario)
            scenario_elapsed = 0.0
            if self.current_scenario_start > 0:
                scenario_elapsed = now - self.current_scenario_start

            # Find current category
            current_cat = None
            for c in self.categories:
                if c in self.cat_start_time and not self.cat_done[c]:
                    current_cat = c
                    break

            # Category time
            cat_elapsed = 0.0
            if current_cat is not None and current_cat in self.cat_start_time:
                cat_elapsed = now - self.cat_start_time[current_cat]

            # Header line: spinner, model, progress, score
            lines.append(f"{spinner} ", style="cyan")
            lines.append(f"{self.model_name}", style="bold cyan")
            lines.append(f"  {completed}/{self.total}", style="dim")
            if all_scores:
                lines.append(f"  {avg_score}%", style="bold")
            lines.append("\n")

            # Time line: scenario / category / total
            lines.append("  ", style="none")
            if scenario_elapsed > 0:
                lines.append(f"scenario:{self._fmt_time(scenario_elapsed)}", style="dim")
                lines.append("  ", style="none")
            if cat_elapsed > 0 and current_cat is not None:
                lines.append(f"{current_cat}:{self._fmt_time(cat_elapsed)}", style="dim")
                lines.append("  ", style="none")
            lines.append(f"total:{self._fmt_time(total_elapsed)}\n", style="dim")

            # Category status line
            for cat in self.categories:
                done = self.cat_done[cat]
                scores = self.cat_scores[cat]
                has_running = any(
                    self.states[s["path"]]["status"] == "running" for s in self.by_category[cat]
                )
                label = cat[:3].upper()

                if done and scores:
                    avg = int(sum(scores) / len(scores) * 100)
                    lines.append(f"{label}:", style="dim")
                    lines.append(f"{avg}%", style="green")
                    lines.append("  ", style="none")
                elif has_running:
                    lines.append(f"{label}:", style="dim")
                    lines.append("►", style="cyan bold")
                    lines.append("  ", style="none")
                else:
                    lines.append(f"{label}:○  ", style="dim")
            lines.append("\n")

            for cat in self.categories:
                cat_scenarios = self.by_category[cat]
                cat_scores_list = list(self.cat_scores[cat])
                done = self.cat_done[cat]

                # Only show categories that have started (at least one non-pending)
                has_activity = any(
                    self.states[s["path"]]["status"] != "pending"
                    for s in cat_scenarios
                )
                if not has_activity:
                    continue

                # Category header
                if done and cat_scores_list:
                    avg = int(sum(cat_scores_list) / len(cat_scores_list) * 100)
                    lines.append(f"\n{cat.capitalize()}", style="yellow")
                    lines.append(f" ({len(cat_scenarios)})  ", style="dim")
                    lines.append(f"{avg}%\n", style="bold")
                else:
                    lines.append(f"\n{cat.capitalize()}", style="yellow")
                    lines.append(f" ({len(cat_scenarios)})\n", style="dim")

                # Scenarios — only show completed + running (skip pending)
                pending_count = 0
                for s in cat_scenarios:
                    state = self.states[s["path"]].copy()
                    name = s["name"][:28]

                    # Build coverage suffix (e.g. "(35/37 checks)")
                    cov = state.get("coverage") or {}
                    cov_suffix = ""
                    if cov.get("eligible"):
                        cov_suffix = f" ({cov['resolved']}/{cov['eligible']} checks)"

                    if state["status"] == "pending":
                        pending_count += 1
                        continue
                    elif state["status"] == "running":
                        lines.append("    ► ", style="cyan bold")
                        lines.append(f"{name}\n", style="white")
                    elif state["status"] == "invalid":
                        lines.append("    ⚠ ", style="yellow bold")
                        lines.append(f"{name:<28}", style="none")
                        lines.append(f" INVALID{cov_suffix}\n", style="yellow bold")
                    elif state["status"] == "pass":
                        lines.append("    ✓ ", style="green")
                        lines.append(f"{name:<28}", style="none")
                        if state.get("score_display"):
                            lines.append(f" {state['score_display']}{cov_suffix}\n", style="bold")
                        else:
                            lines.append(f" {state['score']:>3}%{cov_suffix}\n", style="bold")
                    else:  # fail
                        lines.append("    ✗ ", style="red")
                        lines.append(f"{name:<28}", style="none")
                        if state.get("score_display"):
                            lines.append(f" {state['score_display']}{cov_suffix}\n", style="red bold")
                        else:
                            lines.append(f" FAIL{cov_suffix}\n", style="red bold")

                if pending_count > 0:
                    lines.append(f"      ({pending_count} remaining)\n", style="dim")

        return lines


def print_banner(
    console: Any,
    mode: str,
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
