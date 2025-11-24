#!/usr/bin/env python3
"""
Generate ALL figures for InvisibleBench paper with a consistent, publication-ready style.

Figures:
- Figure 1: End-to-end InvisibleBench flow diagram (pipeline with autofail branch)
- Figure 2: Three-tier architecture (depth/complexity with examples)
- Figure 3: Dimension taxonomy (Sankey-style flow with weights)
- Figure 4: Judgment distribution (Chevron process with sample sizes)
- Figure 5: Hybrid cascade (deterministic + LLM gate with cost note)
- Figure 6: Results Heatmap (annotated, color-blind-safe)

Design constraints:
- Color-blind-safe palette with clear contrast
- Consistent typography and stroke weights
- Dual export (PDF + PNG) for every figure
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, PathPatch, Polygon
from matplotlib.path import Path
import seaborn as sns
import pandas as pd

# GiveCare brand palette + neutrals
COLORS = {
    'primary': '#FF9F1C',       # orange
    'accent': '#CB997E',        # tan
    'accent2': '#FFBF68',       # light orange
    'muted': '#7A6A58',         # muted brown
    'gray': '#6E6E6E',
    'bg': '#FFF7EF',
    'panel': '#FFE8D6',
    'stroke': '#54340E',        # dark brown
    'white': '#FFFFFF',
    'light_gray': '#E0E0E0',
    'danger': '#C62828',
    'warning': '#F6A14D',
    'safe': '#2E7D32',
}

# Shared typography/layout constants
STYLE = {
    'font.family': 'DejaVu Sans',
    'font.size': 10,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'legend.fontsize': 9,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'text.color': COLORS['stroke'],
    'axes.labelcolor': COLORS['stroke'],
    'xtick.color': COLORS['muted'],
    'ytick.color': COLORS['muted'],
    'figure.dpi': 300,
}

def setup_plot_style():
    """Apply consistent styling to all plots."""
    plt.rcParams.update({
        **STYLE,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.spines.left': False,
        'axes.spines.bottom': False,
        'axes.grid': False,
        'axes.linewidth': 0.0,
        'lines.linewidth': 1.2,
        'pdf.fonttype': 42,
        'ps.fonttype': 42,
    })


def save_figure(fig, name: str):
    fig.savefig(f'{name}.pdf', bbox_inches='tight')
    fig.savefig(f'{name}.png', bbox_inches='tight', dpi=300)


# Shared data used across figures
TIER_INFO = [
    {"name": "Tier 1", "turns": "3–5 turns", "focus": "Foundational safety"},
    {"name": "Tier 2", "turns": "8–12 turns", "focus": "Memory & attachment"},
    {"name": "Tier 3", "turns": "20+ turns", "focus": "Consistency & hygiene"},
]

DIM_WEIGHTS = [
    ("Crisis Safety", "Safety", 20),
    ("Regulatory Fitness", "Compliance", 15),
    ("Trauma-Informed", "Trauma", 15),
    ("Cultural Fitness", "Belonging", 15),
    ("Relational Quality", "Belonging", 10),
    ("Actionable Support", "Belonging", 10),
    ("Longitudinal Consistency", "Memory", 10),
    ("Memory Hygiene", "Memory", 5),
]

JUDGE_PIPELINE = [
    ("Judge Prompt", "Rubric + context"),
    ("Sampling", "3 judges / T≈0.7"),
    ("Aggregation", "Median / majority"),
    ("Autofail", "Severe → fail"),
    ("Review", "<0.6 conf → human"),
]

def draw_box(ax, x, y, w, h, color, edgecolor=None, label=None, sublabel=None, style='round,pad=0.1'):
    """Helper to draw a styled box."""
    if edgecolor is None:
        edgecolor = color
    box = FancyBboxPatch((x, y), w, h, boxstyle=style,
                         facecolor=color, edgecolor=edgecolor, linewidth=1.0)
    ax.add_patch(box)
    
    if label:
        ax.text(x + w/2, y + h*0.6, label, ha='center', va='center',
                fontweight='bold', fontsize=10, color=COLORS['stroke'])
    if sublabel:
        ax.text(x + w/2, y + h*0.3, sublabel, ha='center', va='center',
                fontsize=9, color=COLORS['muted'])
    return box

def draw_arrow(ax, x1, y1, x2, y2, color=COLORS['gray'], style='->', curvature=0.0):
    """Helper to draw a styled arrow."""
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                           arrowstyle=style, connectionstyle=f"arc3,rad={curvature}",
                           mutation_scale=15, linewidth=1.5, color=color)
    ax.add_patch(arrow)

# =============================================================================
# Figure 1: Hero Flow Diagram
# =============================================================================
def fig1_hero_flow_diagram():
    """Clean left-to-right InvisibleBench deployment gate diagram."""
    setup_plot_style()
    fig, ax = plt.subplots(figsize=(12.0, 4.0))
    ax.set_xlim(0, 14.0)
    ax.set_ylim(0, 4.5)
    ax.axis('off')

    # Main flow at center height
    flow_y = 1.8
    box_h = 0.85
    box_w = 1.8

    # --- 1. User input -------------------------------------------------------
    draw_box(ax, 0.3, flow_y, box_w, box_h,
             COLORS['panel'], COLORS['stroke'],
             "User input", "Transcript")

    # Arrow to scenarios
    draw_arrow(ax, 2.1, flow_y + box_h/2, 2.5, flow_y + box_h/2, COLORS['stroke'])

    # --- 2. Scenarios block (tiers stacked vertically, compact) --------------
    scenario_x = 2.5
    tier_w = 2.4
    tier_h = 0.65
    tier_gap = 0.08

    # Draw tiers from bottom to top (Tier 1 at bottom)
    for i, info in enumerate(TIER_INFO):
        y_pos = flow_y - 0.3 + i * (tier_h + tier_gap)
        edge_color = COLORS['primary'] if info["name"] == "Tier 3" else COLORS['stroke']
        draw_box(ax, scenario_x, y_pos, tier_w, tier_h,
                 COLORS['white'], edge_color,
                 info['name'], info['turns'])

    # Label above tiers
    ax.text(scenario_x + tier_w/2, flow_y + 2.1,
            "Scenarios", ha='center', va='bottom',
            fontweight='bold', fontsize=10, color=COLORS['stroke'])

    # Arrow from scenarios to guardrails (connect from tier stack to pipe)
    draw_arrow(ax, scenario_x + tier_w + 0.05, flow_y + box_h/2,
               scenario_x + tier_w + 0.35, flow_y + box_h/2, COLORS['stroke'])

    # --- 3. Processing pipeline (horizontal boxes) ---------------------------
    pipe_x = scenario_x + tier_w + 0.35
    pipe_gap = 0.15

    # Guardrails
    draw_box(ax, pipe_x, flow_y, box_w, box_h,
             COLORS['white'], COLORS['accent'],
             "Guardrails", "Autofail checks")

    draw_arrow(ax, pipe_x + box_w, flow_y + box_h/2,
               pipe_x + box_w + pipe_gap, flow_y + box_h/2, COLORS['stroke'])

    # LLM Judges
    judge_x = pipe_x + box_w + pipe_gap
    draw_box(ax, judge_x, flow_y, box_w, box_h,
             COLORS['white'], COLORS['accent2'],
             "LLM judges", "3× per dimension")

    draw_arrow(ax, judge_x + box_w, flow_y + box_h/2,
               judge_x + box_w + pipe_gap, flow_y + box_h/2, COLORS['stroke'])

    # Aggregator
    agg_x = judge_x + box_w + pipe_gap
    draw_box(ax, agg_x, flow_y, box_w, box_h,
             COLORS['white'], COLORS['stroke'],
             "Aggregator", "Median score")

    # Arrow to decision
    draw_arrow(ax, agg_x + box_w, flow_y + box_h/2,
               agg_x + box_w + 0.3, flow_y + box_h/2, COLORS['stroke'])

    # --- 4. Decision diamond -------------------------------------------------
    decision_x = agg_x + box_w + 0.5
    decision_cy = flow_y + box_h/2
    diamond_size = 0.5

    diamond_pts = [
        (decision_x, decision_cy),
        (decision_x + diamond_size, decision_cy + diamond_size),
        (decision_x + 2*diamond_size, decision_cy),
        (decision_x + diamond_size, decision_cy - diamond_size),
    ]
    diamond = Polygon(diamond_pts, closed=True,
                      facecolor=COLORS['white'], edgecolor=COLORS['stroke'], linewidth=1.2)
    ax.add_patch(diamond)
    ax.text(decision_x + diamond_size, decision_cy, "Gate",
            ha='center', va='center', fontweight='bold', fontsize=9)

    # --- 5. Outcomes (fan-out from diamond) ----------------------------------
    outcome_x = decision_x + 2*diamond_size + 0.8
    outcome_w = 1.3
    outcome_h = 0.55

    # PASS (top)
    draw_arrow(ax, decision_x + 2*diamond_size, decision_cy,
               outcome_x, decision_cy + 1.0, COLORS['safe'])
    draw_box(ax, outcome_x, decision_cy + 0.7, outcome_w, outcome_h,
             "#E8F5E9", COLORS['safe'], "PASS", "≥70%")

    # REVIEW (middle)
    draw_arrow(ax, decision_x + 2*diamond_size, decision_cy,
               outcome_x, decision_cy, COLORS['warning'])
    draw_box(ax, outcome_x, decision_cy - outcome_h/2, outcome_w, outcome_h,
             "#FFF2E0", COLORS['warning'], "REVIEW", "50–70%")

    # FAIL (bottom)
    draw_arrow(ax, decision_x + 2*diamond_size, decision_cy,
               outcome_x, decision_cy - 1.0, COLORS['danger'])
    draw_box(ax, outcome_x, decision_cy - 1.25, outcome_w, outcome_h,
             "#FDECEC", COLORS['danger'], "FAIL", "Autofail")

    save_figure(fig, "fig1_hero_flow_diagram_v4")
    plt.close(fig)
    print("Generated: fig1_hero_flow_diagram_v4 (pdf/png)")

# =============================================================================
# Figure 2: Three Tier Architecture
# =============================================================================
def fig2_three_tier_architecture():
    """Three-tier architecture depth chart with examples (brand)."""
    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 5.0)
    ax.axis('off')

    ax.plot([1, 9.6], [1.0, 1.0], color=COLORS['stroke'], linewidth=1.1)
    ax.text(9.7, 1.0, "Complexity →", va='center', fontsize=10, color=COLORS['muted'])

    heights = [1.4, 2.3, 3.2]
    colors = [COLORS['panel'], COLORS['accent2'], COLORS['primary']]
    for i, info in enumerate(TIER_INFO):
        draw_box(
            ax,
            1.4 + i*2.7,
            1.0,
            2.2,
            heights[i],
            colors[i],
            COLORS['stroke'],
            info['name'],
            f"{info['turns']} • {info['focus']}"
        )

    ax.text(1.0, 4.4, "Tier coverage with example turn spans", fontweight='bold', fontsize=12)
    save_figure(fig, 'fig2_three_tier_clean_v4')
    plt.close()
    print("Generated: fig2_three_tier_clean_v4 (pdf/png)")

# =============================================================================
# Figure 3: Dimension Taxonomy (Sankey Style)
# =============================================================================
def fig3_dimension_taxonomy():
    """Non-overlapping bar chart of dimension weights grouped by reported score."""
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    ax.axis('off')

    dims = [name for name, _, _ in DIM_WEIGHTS]
    weights = [w for _, _, w in DIM_WEIGHTS]
    groups = [score for _, score, _ in DIM_WEIGHTS]

    y_positions = list(range(len(dims)))

    # Color by reported score group
    group_colors = {
        "Safety": COLORS['accent'],
        "Compliance": COLORS['primary'],
        "Trauma": COLORS['accent2'],
        "Belonging": "#9467BD",
        "Memory": "#0072B2",
    }
    colors = [group_colors[g] for g in groups]

    ax.barh(
        y_positions,
        weights,
        height=0.6,
        color=colors,
        edgecolor=COLORS['stroke'],
        linewidth=0.8,
    )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(dims)
    ax.invert_yaxis()  # top = first item
    ax.set_xlabel("Weight (%)")
    ax.set_xlim(0, 25)

    # Annotate group labels to the right of each bar
    for y, (w, g) in enumerate(zip(weights, groups)):
        ax.text(
            w + 0.6, y,
            g,
            va='center',
            fontsize=9,
        )

    ax.text(
        0.0, len(dims) + 0.5,
        "Eight analytic dimensions grouped into five reported scores",
        ha='left',
        fontweight='bold',
        fontsize=11,
    )

    fig.tight_layout()
    save_figure(fig, 'fig3_dimension_taxonomy_clean_v4')
    plt.close(fig)

# =============================================================================
# Figure 4: Judgment Pipeline (Chevron Process)
# =============================================================================
def fig4_judgment_pipeline():
    """Judgment distribution pipeline with sample sizes."""
    fig, ax = plt.subplots(figsize=(10, 3.3)) # Widen figure
    ax.set_xlim(0, 11.5) # Widen x-axis
    ax.set_ylim(0, 4.0)
    ax.axis('off')

    colors = [COLORS['panel'], COLORS['primary'], COLORS['accent2'], COLORS['accent'], COLORS['warning']]

    # Draw Chevrons
    for i, (title, sub) in enumerate(JUDGE_PIPELINE):
        x_start = 0.5 + i*2.2 # Increase spacing
        width = 2.0
        height = 1.2
        y_mid = 2.0
        d = 0.3

        if i == 0: # First one flat start
            pts = [
                (x_start, y_mid - height/2),
                (x_start + width - d, y_mid - height/2),
                (x_start + width, y_mid),
                (x_start + width - d, y_mid + height/2),
                (x_start, y_mid + height/2)
            ]
        else:
            pts = [
                (x_start, y_mid - height/2),
                (x_start + width - d, y_mid - height/2),
                (x_start + width, y_mid),
                (x_start + width - d, y_mid + height/2),
                (x_start, y_mid + height/2),
                (x_start + d, y_mid)
            ]
            
        poly = Polygon(pts, closed=True, facecolor=colors[i], edgecolor=COLORS['white'], lw=2)
        ax.add_patch(poly)
        
        # Text
        text_x = x_start + width/2
        if i > 0: text_x += d/2
        
        ax.text(text_x, y_mid + 0.2, title, ha='center', va='center', fontweight='bold', fontsize=9)
        ax.text(text_x, y_mid - 0.25, sub, ha='center', va='center', fontsize=8)

    ax.text(5.5, 4.0, "Judgment distribution pipeline", ha='center', fontweight='bold', fontsize=11)
    save_figure(fig, 'fig4_judgment_distribution_clean_v3')
    plt.close()
    print("Generated: fig4_judgment_distribution_clean_v3 (pdf/png)")

# =============================================================================
# Figure 5: Hybrid Cascade (Filter/Gate Flow)
# =============================================================================
def fig5_hybrid_cascade():
    """Hybrid deterministic + LLM cascade."""
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 10.5)
    ax.axis('off')

    # 1. Input
    draw_box(ax, 3.8, 8.7, 3.0, 1.0, COLORS['panel'], COLORS['stroke'], "Turn Input")
    draw_arrow(ax, 5.3, 8.7, 5.3, 7.7, COLORS['stroke'])

    # 2. Deterministic Filter
    draw_box(ax, 2.8, 6.2, 5.0, 1.5, COLORS['panel'], COLORS['primary'], "Deterministic Filter", "Pattern match (autofail, zero cost)")
    draw_arrow(ax, 5.3, 6.2, 5.3, 5.0, COLORS['stroke']) # Arrow goes lower

    # 3. Decision Diamond (Moved lower)
    diamond_pts = [(5.3, 5.0), (6.8, 4.0), (5.3, 3.0), (3.8, 4.0)]
    diamond = Polygon(diamond_pts, closed=True, facecolor=COLORS['white'], edgecolor=COLORS['accent'])
    ax.add_patch(diamond)
    ax.text(5.3, 4.0, "Violation?", ha='center', va='center', fontweight='bold')

    # Path A: Yes (Fail) - Fast Exit
    draw_arrow(ax, 6.8, 4.0, 8.3, 4.0, COLORS['danger'])
    draw_box(ax, 8.3, 3.4, 1.7, 1.0, "#FDECEC", COLORS['danger'], "FAIL", "Immediate stop")

    # Path B: No/Ambiguous (LLM)
    draw_arrow(ax, 5.3, 3.0, 5.3, 2.2, COLORS['stroke'])
    ax.text(5.5, 2.6, "Ambiguous", fontsize=9, color=COLORS['muted'])

    # 4. LLM Judge
    draw_box(ax, 3.8, 1.2, 3.0, 1.0, COLORS['white'], COLORS['accent2'], "LLM Judge", "Semantic analysis")

    # Annotation (Simplified and moved)
    ax.text(1.8, 6.9, "~40% cost\nreduction", ha='center', va='center', color=COLORS['safe'], fontweight='bold', fontsize=10)
    draw_arrow(ax, 2.6, 6.9, 3.0, 6.9, COLORS['safe'], style='->') # Point to filter

    ax.text(5.3, 0.5, "Hybrid deterministic + LLM judgment cascade", ha='center', fontweight='bold')
    save_figure(fig, 'fig5_hybrid_cascade_clean_v3')
    plt.close()
    print("Generated: fig5_hybrid_cascade_clean_v3 (pdf/png)")

# =============================================================================
# Figure 6: Heatmap
# =============================================================================
def fig6_results_heatmap():
    """Heatmap with simpler annotations and less visual noise."""
    data = {
        'Model': ['DeepSeek v3', 'Gemini 2.5', 'GPT-4o Mini', 'Claude 4.5'],
        'Overall': [75.9, 73.6, 73.0, 65.4],
        'Memory': [92.3, 90.9, 91.8, 85.1],
        'Trauma': [82.2, 85.0, 73.5, 84.1],
        'Belonging': [91.7, 80.4, 64.1, 75.5],
        'Compliance': [56.3, 58.8, 88.2, 17.6],
        'Safety': [27.3, 17.6, 11.8, 44.8],
    }

    df = pd.DataFrame(data).set_index('Model')

    plt.figure(figsize=(8.5, 4.5))  # a bit wider, less tall
    cmap = sns.light_palette(COLORS['primary'], as_cmap=True)

    ax = sns.heatmap(
        df,
        annot=True,
        fmt=".0f",  # integers only
        cmap=cmap,
        linewidths=0.8,
        linecolor=COLORS['white'],
        cbar_kws={'label': 'Score (%)', 'shrink': 0.8},
        vmin=0,
        vmax=100,
    )

    for t in ax.texts:
        val = float(t.get_text())
        t.set_fontsize(9)
        if val < 50:
            t.set_color(COLORS['danger'])
            t.set_fontweight('bold')
        elif val > 90:
            t.set_fontweight('bold')

    plt.title(
        "InvisibleBench results: performance by dimension",
        pad=16,
        fontsize=12,
        fontweight='bold',
        color=COLORS['stroke'],
    )
    plt.xlabel("")
    plt.ylabel("")
    plt.tight_layout()
    save_figure(plt.gcf(), 'heatmap_v3')
    plt.close()


def generate_all_figures():
    """Generate all InvisibleBench paper figures."""
    setup_plot_style()

    print("=" * 60)
    print("Generating ALL figures for InvisibleBench paper (GiveCare Brand)")
    print("=" * 60)

    fig1_hero_flow_diagram()
    fig2_three_tier_architecture()
    fig3_dimension_taxonomy()
    fig4_judgment_pipeline()
    fig5_hybrid_cascade()
    fig6_results_heatmap()

    print("\n" + "=" * 60)
    print("✅ All figures generated successfully!")
    print("=" * 60)

if __name__ == "__main__":
    generate_all_figures()
