#!/usr/bin/env python3
"""
Generate missing figures for InvisibleBench paper
EXACT match to hero figure 1 styling
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from pathlib import Path

# MATCH HERO FIGURE EXACTLY - use seaborn style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times', 'Times New Roman', 'DejaVu Serif']
plt.rcParams['font.size'] = 9

# Set up output directory
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

# EXACT colors from rendered hero figure PDF (warm autumn/earth tones)
COLORS = {
    # Border colors (warm earth tones from rendered hero)
    'brown': '#8B7355',        # Warm brown
    'tan': '#CD853F',          # Peru/tan
    'sienna': '#A0522D',       # Sienna/brown
    'dark_orange': '#FF8C00',  # Dark orange
    'chocolate': '#D2691E',    # Chocolate brown/orange
    'indian_red': '#CD5C5C',   # Indian red

    # Background colors (warm beige/rose/amber from rendered hero)
    'beige': '#FAEBD7',        # Warm beige/tan (AntiqueWhite)
    'cream': '#F5E6D3',        # Warm cream/tan
    'dusty_rose': '#D4A5A5',   # Dusty rose/mauve
    'warm_amber': '#FFB347',   # Warm amber/orange
    'bright_orange': '#FF8C00',# Bright orange

    # Neutral (from hero figure)
    'arrow': '#424242',
    'gray': '#8B7355',         # Warm gray/brown
    'light_bg': '#FAF8F3',     # Warm off-white
}

def add_box(ax, x, y, width, height, text, border_color, bg_color,
            fontsize=10, **kwargs):
    """Add a box - EXACT hero figure styling"""
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.1",
        facecolor=bg_color,
        edgecolor=border_color,
        linewidth=2,
        **kwargs
    )
    ax.add_patch(box)
    # Center text, bold, wrapping enabled
    ax.text(x + width/2, y + height/2, text,
            ha='center', va='center',
            fontsize=fontsize, weight='bold')
    return box

def add_arrow(ax, x1, y1, x2, y2, label='', **kwargs):
    """Add arrow - EXACT hero figure styling"""
    # Set default color if not provided
    if 'color' not in kwargs:
        kwargs['color'] = COLORS['arrow']

    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle='->',
        lw=2,
        **kwargs
    )
    ax.add_patch(arrow)
    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x, mid_y, label, fontsize=8,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

# ============================================================================
# Figure 2: Three-Tier Architecture
# ============================================================================
def generate_three_tier_architecture():
    """Generate three-tier architecture - hero figure styling"""
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Title - match hero (fontsize=12, bold)
    ax.text(5, 9.5, 'InvisibleBench Three-Tier Architecture',
            ha='center', fontsize=12, weight='bold')

    # Tier boxes - use hero color scheme
    tier_y = [7, 4.5, 2]
    tier_heights = [1.5, 1.5, 1.5]
    tier_info = [
        ('Tier 1: Smoke Tests\n3-5 turns, 5 scenarios\nSafety & Compliance',
         COLORS['sienna'], COLORS['dusty_rose']),
        ('Tier 2: Core Interactions\n8-12 turns, 9 scenarios\n+Longitudinal Consistency',
         COLORS['tan'], COLORS['cream']),
        ('Tier 3: Long-term Care\n20+ turns, 3 sessions\n+Memory Hygiene',
         COLORS['dark_orange'], COLORS['warm_amber'])
    ]

    for i, ((text, border, bg), y, h) in enumerate(zip(tier_info, tier_y, tier_heights)):
        add_box(ax, 1, y, 8, h, text, border, bg, fontsize=10)

        # Dimension badges
        dims = ["5 dimensions", "7 dimensions", "8 dimensions"][i]
        ax.text(9.2, y + h/2, dims, fontsize=9,
                bbox=dict(boxstyle='round', facecolor=COLORS['light_bg'],
                         edgecolor=border, linewidth=2))

    # Progressive complexity arrow
    add_arrow(ax, 0.5, 8, 0.5, 2.5, color=COLORS['chocolate'])
    ax.text(0.2, 5.5, 'Progressive\nComplexity', rotation=90,
            ha='center', va='center', fontsize=10, weight='bold',
            color=COLORS['chocolate'])

    # Cost indicators
    costs = ['~$2-3', '~$4-6', '~$6-9']
    for y, cost in zip(tier_y, costs):
        ax.text(9.5, y + 0.2, f'Cost:\n{cost}', fontsize=7,
                ha='left', va='bottom',
                bbox=dict(boxstyle='round', facecolor='white',
                         edgecolor=COLORS['gray'], linewidth=1))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_three_tier_architecture.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated three-tier architecture")

# ============================================================================
# Figure 3: Dimension Taxonomy
# ============================================================================
def generate_dimension_taxonomy():
    """Generate dimension taxonomy - hero figure styling"""
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Title
    ax.text(5, 9.5, 'InvisibleBench Dimension Taxonomy',
            ha='center', fontsize=12, weight='bold')

    # Top level
    ax.text(5, 8.5, '8 Analytic Dimensions', ha='center', fontsize=10,
            weight='bold', bbox=dict(boxstyle='round', facecolor=COLORS['light_bg']))

    # Analytic dimensions (left)
    analytic_dims = [
        ('Crisis Safety\n(0-3)', COLORS['chocolate']),
        ('Regulatory Fitness\n(0-3)', COLORS['sienna']),
        ('Trauma-Informed Flow\n(0-3)', COLORS['tan']),
        ('Belonging & Cultural Fitness\n(0-3)', COLORS['brown']),
        ('Relational Quality\n(0-3)', COLORS['brown']),
        ('Actionable Support\n(0-3)', COLORS['brown']),
        ('Longitudinal Consistency\n(0-2)', COLORS['tan']),
        ('Memory Hygiene\n(0-1)', COLORS['sienna'])
    ]

    y_start = 7
    for i, (name, color) in enumerate(analytic_dims):
        y = y_start - (i * 0.75)
        # Map to light background
        bg_map = {
            COLORS['chocolate']: COLORS['dusty_rose'],
            COLORS['sienna']: COLORS['dusty_rose'],
            COLORS['tan']: COLORS['cream'],
            COLORS['brown']: COLORS['beige'],
        }
        add_box(ax, 0.5, y, 3.5, 0.6, name, color, bg_map[color], fontsize=8)

    # Reported dimensions (right)
    reported = [
        ('Safety', [0], 7, COLORS['chocolate']),
        ('Compliance', [1], 6.25, COLORS['sienna']),
        ('Trauma', [2], 5.5, COLORS['tan']),
        ('Belonging', [3, 4, 5], 4.0, COLORS['brown']),
        ('Memory', [6, 7], 1.5, COLORS['tan'])
    ]

    for label, indices, y_pos, color in reported:
        bg_map = {
            COLORS['chocolate']: COLORS['dusty_rose'],
            COLORS['sienna']: COLORS['dusty_rose'],
            COLORS['tan']: COLORS['cream'],
            COLORS['brown']: COLORS['beige'],
        }
        add_box(ax, 6, y_pos, 3, 0.6, label, color, bg_map[color], fontsize=10)

        # Arrows from analytic to reported
        for idx in indices:
            y_from = y_start - (idx * 0.75) + 0.3
            add_arrow(ax, 4.1, y_from, 5.9, y_pos + 0.3, color=color, linestyle='--')

    # Notes
    ax.text(5, 0.5, 'Belonging = avg(Belonging & Cultural Fitness, Relational Quality, Actionable Support)',
            ha='center', fontsize=7, style='italic',
            bbox=dict(boxstyle='round', facecolor=COLORS['light_bg']))
    ax.text(5, 0.1, 'Memory = avg(Longitudinal Consistency, Memory Hygiene) [Tier 3 only]',
            ha='center', fontsize=7, style='italic',
            bbox=dict(boxstyle='round', facecolor=COLORS['light_bg']))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_dimension_taxonomy.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated dimension taxonomy")

# ============================================================================
# Figure 4: Judgment Distribution
# ============================================================================
def generate_judgment_distribution():
    """Generate judgment distribution - hero figure styling"""
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Title
    ax.text(5, 9.5, 'Judgment Distribution Process',
            ha='center', fontsize=12, weight='bold')

    # Input
    add_box(ax, 3.5, 8, 3, 0.8, 'Scenario + Model Response',
            COLORS['gray'], COLORS['light_bg'], fontsize=10)
    add_arrow(ax, 5, 7.9, 5, 7.3)

    # Sampling
    add_box(ax, 2, 6.5, 6, 0.6, 'Generate N=5 samples with temperature τ=0.3',
            COLORS['tan'], COLORS['cream'], fontsize=9)
    add_arrow(ax, 5, 6.4, 5, 5.8)

    # Samples
    for i in range(5):
        x = 1 + i * 1.6
        add_box(ax, x, 4.8, 1.4, 0.8, f'Sample {i+1}\nScore: s_{i+1}',
                COLORS['brown'], COLORS['beige'], fontsize=8)
        add_arrow(ax, x + 0.7, 4.7, 4, 4.0)

    # Aggregation
    add_box(ax, 2.5, 3.2, 5, 0.6, 'Aggregation Method',
            COLORS['sienna'], COLORS['dusty_rose'], fontsize=10)

    # Two paths
    add_box(ax, 1, 2.0, 3.5, 0.6, 'Categorical:\nMajority Vote',
            COLORS['tan'], COLORS['cream'], fontsize=9)
    add_box(ax, 5.5, 2.0, 3.5, 0.6, 'Numeric:\nMean Score',
            COLORS['tan'], COLORS['cream'], fontsize=9)

    add_arrow(ax, 3.5, 3.1, 2.5, 2.7)
    add_arrow(ax, 6.5, 3.1, 7, 2.7)

    # Convergence
    add_arrow(ax, 2.75, 1.9, 4, 1.5)
    add_arrow(ax, 7.25, 1.9, 6, 1.5)

    add_box(ax, 3, 0.8, 4, 0.6, 'Final Score + Confidence Interval',
            COLORS['brown'], COLORS['beige'], fontsize=10)

    # Decision
    add_arrow(ax, 5, 0.7, 5, 0.2)
    ax.text(5, 0.1, 'CI width < threshold → Accept | CI width ≥ threshold → Human Review',
            ha='center', fontsize=8,
            bbox=dict(boxstyle='round', facecolor=COLORS['dusty_rose'],
                     edgecolor=COLORS['chocolate'], linewidth=2))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_judgment_distribution.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated judgment distribution")

# ============================================================================
# Figure 5: Hybrid Cascade
# ============================================================================
def generate_hybrid_cascade():
    """Generate hybrid cascade - hero figure styling"""
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Title
    ax.text(5, 9.5, 'Hybrid Deterministic-LLM Evaluation Cascade',
            ha='center', fontsize=12, weight='bold')

    # Input
    add_box(ax, 3.5, 8, 3, 0.8, 'Response Text',
            COLORS['gray'], COLORS['light_bg'], fontsize=10)
    add_arrow(ax, 5, 7.9, 5, 7.3)

    # Stage 1: Deterministic
    add_box(ax, 2, 6.5, 6, 0.8, 'Stage 1: Deterministic Pattern Matching',
            COLORS['tan'], COLORS['cream'], fontsize=10)

    # Pattern examples
    patterns = [
        'Crisis keywords (988, suicide, harm)',
        'PII patterns (SSN, phone, email)',
        'Boundary violations ("I love you")'
    ]
    for i, pattern in enumerate(patterns):
        y = 5.2 - i * 0.6
        add_box(ax, 1.5, y, 4, 0.4, pattern,
                COLORS['brown'], COLORS['beige'], fontsize=7)

    # Decision point
    add_box(ax, 6.5, 4.6, 2.5, 1.0, 'Pattern\nMatched?',
            COLORS['sienna'], COLORS['dusty_rose'], fontsize=10)
    add_arrow(ax, 5.5, 5.0, 6.5, 5.0)

    # Yes path (autofail)
    add_arrow(ax, 8, 5.1, 9.2, 6.0, 'YES', color=COLORS['chocolate'])
    add_box(ax, 8, 6.0, 1.5, 0.8, 'AUTOFAIL\nScore = 0',
            COLORS['chocolate'], COLORS['dusty_rose'], fontsize=9)
    ax.text(8.75, 7.2, '~40% of cases\nNo LLM cost', ha='center', fontsize=7,
            bbox=dict(boxstyle='round', facecolor=COLORS['light_bg']))

    # No path (continue to LLM)
    add_arrow(ax, 7.75, 4.5, 7.75, 3.8, 'NO')

    # Stage 2: LLM Judge
    add_box(ax, 6, 2.8, 3.5, 0.8, 'Stage 2: LLM Judge (GPT-4)',
            COLORS['tan'], COLORS['cream'], fontsize=10)
    add_arrow(ax, 7.75, 2.7, 7.75, 2.0)

    # LLM evaluation
    add_box(ax, 6, 1.2, 3.5, 0.6, 'Nuanced judgment\nwith rubric',
            COLORS['brown'], COLORS['beige'], fontsize=9)
    add_arrow(ax, 7.75, 1.1, 7.75, 0.5)

    add_box(ax, 6.5, 0.0, 2.5, 0.4, 'Score (0-3)',
            COLORS['sienna'], COLORS['dusty_rose'], fontsize=9)

    # Cost note
    ax.text(1.5, 0.5, 'Cost Savings: ~$6/run → ~$3.60/run\n60% of LLM calls eliminated by deterministic stage',
            fontsize=8, bbox=dict(boxstyle='round', facecolor=COLORS['light_bg'],
                                 edgecolor=COLORS['brown'], linewidth=2))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_hybrid_cascade.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated hybrid cascade")

# ============================================================================
# Main execution
# ============================================================================
if __name__ == '__main__':
    print("Generating InvisibleBench figures with hero figure styling...")
    generate_three_tier_architecture()
    generate_dimension_taxonomy()
    generate_judgment_distribution()
    generate_hybrid_cascade()
    print("\n✓ All figures generated with consistent hero styling!")
    print(f"Output directory: {OUTPUT_DIR}")
