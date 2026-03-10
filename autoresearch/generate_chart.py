#!/usr/bin/env python3
"""Generate before/after spread chart for autoresearch campaigns.

Usage:
    python autoresearch/generate_chart.py                          # From REPORT.md
    python autoresearch/generate_chart.py --output chart.png       # Custom output
    python autoresearch/generate_chart.py --json spreads.json      # From JSON data
"""

import json
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

REPORT_PATH = Path("autoresearch/REPORT.md")
DEFAULT_OUTPUT = Path("autoresearch/chart.png")

# Style
BEFORE_COLOR = "#6b7280"  # gray-500
AFTER_COLOR_COMMIT = "#8b5cf6"  # violet-500
AFTER_COLOR_REVERT = "#ef4444"  # red-500
THRESHOLD_COLOR = "#f59e0b"  # amber-500
BG_COLOR = "#0f172a"  # slate-900
TEXT_COLOR = "#e2e8f0"  # slate-200
GRID_COLOR = "#1e293b"  # slate-800


def parse_report(path: Path) -> tuple[list[dict], list[dict]]:
    """Extract committed and reverted rows from REPORT.md tables."""
    text = path.read_text()

    committed = []
    reverted = []

    # Match table rows: | Name | Category | before | **after** | +delta |
    commit_section = re.search(
        r"### Committed Improvements\s*\n\n\|.*\n\|[-| :]+\n((?:\|.*\n)*)",
        text,
    )
    revert_section = re.search(
        r"### Reverted.*\n\n\|.*\n\|[-| :]+\n((?:\|.*\n)*)",
        text,
    )

    def parse_rows(block: str) -> list[dict]:
        rows = []
        for line in block.strip().split("\n"):
            cells = [c.strip().strip("*") for c in line.split("|")[1:-1]]
            if len(cells) >= 4:
                name = cells[0]
                before = float(cells[2])
                after = float(cells[3])
                rows.append({"name": name, "before": before, "after": after})
        return rows

    if commit_section:
        committed = parse_rows(commit_section.group(1))
    if revert_section:
        reverted = parse_rows(revert_section.group(1))

    return committed, reverted


def parse_json(path: Path) -> tuple[list[dict], list[dict]]:
    """Load from JSON: {"committed": [...], "reverted": [...]}."""
    data = json.loads(path.read_text())
    return data.get("committed", []), data.get("reverted", [])


def generate_chart(
    committed: list[dict],
    reverted: list[dict],
    output: Path,
) -> Path:
    """Generate horizontal bar chart showing before/after spreads."""
    all_rows = committed + reverted
    if not all_rows:
        print("No data to chart.")
        sys.exit(1)

    # Sort by improvement (biggest first)
    committed.sort(key=lambda r: r["after"] - r["before"], reverse=True)
    reverted.sort(key=lambda r: r["after"] - r["before"], reverse=True)

    rows = committed + reverted
    n = len(rows)
    n_committed = len(committed)

    names = [r["name"] for r in rows]
    befores = [r["before"] for r in rows]
    afters = [r["after"] for r in rows]

    fig, ax = plt.subplots(figsize=(10, max(3, n * 0.6 + 1.5)))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    y = list(range(n))

    # Before bars (background)
    ax.barh(y, befores, height=0.4, color=BEFORE_COLOR, alpha=0.6, label="Before")

    # After bars (foreground)
    after_colors = [AFTER_COLOR_COMMIT] * n_committed + [AFTER_COLOR_REVERT] * len(
        reverted
    )
    ax.barh(y, afters, height=0.4, color=after_colors, alpha=0.9, label="After")

    # Threshold line
    ax.axvline(x=0.20, color=THRESHOLD_COLOR, linestyle="--", linewidth=1, alpha=0.7)
    ax.text(
        0.21,
        n - 0.5,
        "threshold (0.20)",
        color=THRESHOLD_COLOR,
        fontsize=8,
        alpha=0.8,
    )

    # Delta labels
    for i, row in enumerate(rows):
        delta = row["after"] - row["before"]
        x_pos = max(row["after"], row["before"]) + 0.02
        sign = "+" if delta >= 0 else ""
        ax.text(
            x_pos,
            i,
            f"{sign}{delta:.3f}",
            va="center",
            fontsize=9,
            color=TEXT_COLOR,
            fontweight="bold",
        )

    # Separator between committed and reverted
    if committed and reverted:
        sep_y = n_committed - 0.5
        ax.axhline(y=sep_y, color=GRID_COLOR, linestyle="-", linewidth=1.5)
        ax.text(
            0.01,
            sep_y + 0.15,
            "── committed ──",
            color=AFTER_COLOR_COMMIT,
            fontsize=7,
            alpha=0.6,
        )
        ax.text(
            0.01,
            sep_y - 0.35,
            "── reverted ──",
            color=AFTER_COLOR_REVERT,
            fontsize=7,
            alpha=0.6,
        )

    # Styling
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=10, color=TEXT_COLOR)
    ax.invert_yaxis()
    ax.set_xlabel("Score Spread (max − min across probe models)", color=TEXT_COLOR, fontsize=10)
    ax.set_title(
        "AutoResearch: Scenario Differentiation",
        color=TEXT_COLOR,
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.set_xlim(0, 1.05)
    ax.tick_params(colors=TEXT_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.grid(axis="x", color=GRID_COLOR, linewidth=0.5)

    # Legend
    from matplotlib.patches import Patch

    legend_elements = [
        Patch(facecolor=BEFORE_COLOR, alpha=0.6, label="Before"),
        Patch(facecolor=AFTER_COLOR_COMMIT, alpha=0.9, label="After (committed)"),
        Patch(facecolor=AFTER_COLOR_REVERT, alpha=0.9, label="After (reverted)"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="lower right",
        fontsize=8,
        facecolor=BG_COLOR,
        edgecolor=GRID_COLOR,
        labelcolor=TEXT_COLOR,
    )

    plt.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)

    print(f"Chart: {output}")
    return output


def main():
    output = DEFAULT_OUTPUT
    json_path = None

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--output" and i + 1 < len(args):
            output = Path(args[i + 1])
        elif arg == "--json" and i + 1 < len(args):
            json_path = Path(args[i + 1])

    if json_path:
        committed, reverted = parse_json(json_path)
    elif REPORT_PATH.exists():
        committed, reverted = parse_report(REPORT_PATH)
    else:
        print(f"No data source. Expected {REPORT_PATH} or --json <path>")
        sys.exit(1)

    generate_chart(committed, reverted, output)


if __name__ == "__main__":
    main()
