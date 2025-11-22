#!/usr/bin/env python3
"""
Generate missing figures for GiveCare paper
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle, Wedge
import numpy as np
from pathlib import Path

# Set up output directory
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

# GiveCare color palette
COLORS = {
    'primary': '#2563eb',      # Blue
    'secondary': '#7c3aed',    # Purple
    'accent': '#059669',       # Green
    'warning': '#dc2626',      # Red
    'neutral': '#64748b',      # Gray
    'light': '#f1f5f9',        # Light gray
    'orange': '#ea580c',       # Orange
}

def setup_figure(figsize=(14, 10)):
    """Set up figure with consistent styling"""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    return fig, ax

def add_box(ax, x, y, width, height, text, color=COLORS['primary'],
            fontsize=10, text_color='white', **kwargs):
    """Add a colored box with text"""
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.1",
        facecolor=color,
        edgecolor='black',
        linewidth=1.5,
        **kwargs
    )
    ax.add_patch(box)
    ax.text(x + width/2, y + height/2, text,
            ha='center', va='center',
            fontsize=fontsize, color=text_color,
            weight='bold', wrap=True)
    return box

def add_arrow(ax, x1, y1, x2, y2, label='', **kwargs):
    """Add an arrow with optional label"""
    defaults = {'arrowstyle': '->', 'mutation_scale': 20, 'linewidth': 2, 'color': 'black'}
    defaults.update(kwargs)

    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        **defaults
    )
    ax.add_patch(arrow)
    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x, mid_y, label, fontsize=8,
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

# ============================================================================
# Figure 1: GC-SDOH-28 Conversational Flow
# ============================================================================
def generate_sdoh_conversational_flow():
    """Generate GC-SDOH-28 conversational delivery flow"""
    fig, ax = setup_figure(figsize=(14, 11))

    # Title
    ax.text(5, 9.8, 'GC-SDOH-28 Conversational Delivery Flow',
            ha='center', fontsize=16, weight='bold')

    # Day timeline
    days = ['Day 1', 'Day 2', 'Day 3']
    day_x = [1, 4, 7]
    for i, (day, x) in enumerate(zip(days, day_x)):
        ax.text(x + 1, 9.2, day, ha='center', fontsize=11, weight='bold',
                bbox=dict(boxstyle='round', facecolor=COLORS['neutral'],
                         edgecolor='black', linewidth=2))

    # Turns
    turns = [
        ('Turn 1-2\nFinancial\nStability', 1, 7.5, COLORS['warning']),
        ('Turn 3-4\nHousing &\nTransport', 1, 6.0, COLORS['orange']),
        ('Turn 5-6\nFood &\nUtilities', 4, 7.5, COLORS['accent']),
        ('Turn 7\nSafety &\nCommunity', 4, 6.0, COLORS['primary']),
        ('Turn 8\nResults &\nResources', 7, 7.5, COLORS['secondary'])
    ]

    for text, x, y, color in turns:
        add_box(ax, x, y, 2, 1.2, text, color=color, fontsize=9)

    # Progress indicators
    progress_labels = ['2 of 28', '7 of 28', '15 of 28', '22 of 28', '28 of 28']
    for i, (label, x, y, color) in enumerate(zip(progress_labels,
                                                   [1, 1, 4, 4, 7],
                                                   [7.5, 6.0, 7.5, 6.0, 7.5],
                                                   [c for _, _, _, c in turns])):
        ax.text(x + 2.2, y + 0.2, label, fontsize=7,
                bbox=dict(boxstyle='round', facecolor='white',
                         edgecolor=color, linewidth=1.5))

    # Skip options
    add_box(ax, 0.2, 4.5, 2.6, 0.6, 'Skip Option\nAvailable',
            color=COLORS['neutral'], fontsize=8)
    ax.text(1.5, 3.9, '"Skip this for now" →\nReturns in 24h',
            ha='center', fontsize=7, style='italic')

    # Resource matching
    add_box(ax, 7, 4.5, 2.6, 0.6, 'Resource\nMatching',
            color=COLORS['accent'], fontsize=9)
    add_arrow(ax, 8.3, 6.9, 8.3, 5.2, color=COLORS['accent'])

    # Flow arrows
    add_arrow(ax, 2, 8.1, 3.9, 8.1)
    add_arrow(ax, 2, 6.6, 3.9, 6.6)
    add_arrow(ax, 5, 8.1, 6.9, 8.1)
    add_arrow(ax, 5, 6.6, 6.9, 7.3)

    # Bottom: Key features
    features = [
        ('Conversational\nNot Survey', COLORS['primary']),
        ('8 turns\n2-3 days', COLORS['secondary']),
        ('28 questions\n7 domains', COLORS['accent']),
        ('Skip-friendly\nLow burden', COLORS['orange'])
    ]
    for i, (text, color) in enumerate(features):
        x = 0.5 + i * 2.4
        add_box(ax, x, 0.5, 2.2, 0.8, text, color=color, fontsize=8)

    # Comparison note
    ax.text(5, 2.5, 'Traditional SDOH: Single 28-question form (15-20 min, 40% completion)\n' +
                     'GC-SDOH-28: 8 conversational turns (2-3 min each, 78% preliminary completion)',
            ha='center', fontsize=9, style='italic',
            bbox=dict(boxstyle='round', facecolor=COLORS['light'],
                     edgecolor=COLORS['primary'], linewidth=2))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_sdoh_conversational_flow.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated GC-SDOH-28 conversational flow")

# ============================================================================
# Figure 2: Anticipatory Watcher Architecture
# ============================================================================
def generate_watcher_architecture():
    """Generate anticipatory watcher architecture diagram"""
    fig, ax = setup_figure(figsize=(14, 11))

    # Title
    ax.text(5, 9.8, 'Anticipatory Watcher Architecture',
            ha='center', fontsize=16, weight='bold')

    # Working Memory (center)
    add_box(ax, 3.5, 6.5, 3, 1.5, 'Working Memory\n(Vector Store)',
            color=COLORS['primary'], fontsize=11)

    # Memory categories
    categories = [
        'Care Routine', 'Preference',
        'Intervention Result', 'Crisis Trigger'
    ]
    for i, cat in enumerate(categories):
        x = 3.7 + (i % 2) * 1.3
        y = 7.3 - (i // 2) * 0.4
        ax.text(x, y, cat, fontsize=7,
                bbox=dict(boxstyle='round', facecolor='white',
                         edgecolor=COLORS['accent'], linewidth=1))

    # Three watchers
    watchers = [
        ('Trend Watcher\n(53 tests)', 0.5, 4.5, COLORS['accent'],
         'Detects patterns:\n• Declining engagement\n• Escalating burden\n• Improving trends'),
        ('Engagement Watcher\n(37 tests)', 3.5, 4.5, COLORS['secondary'],
         'Monitors:\n• Response frequency\n• Message length\n• Time of day patterns'),
        ('Burst Watcher\n(45 tests)', 6.5, 4.5, COLORS['orange'],
         'Identifies:\n• Sudden high activity\n• Crisis indicators\n• Distress signals')
    ]

    for name, x, y, color, details in watchers:
        # Watcher box
        add_box(ax, x, y, 2.8, 0.9, name, color=color, fontsize=9)

        # Details
        ax.text(x + 1.4, y - 0.9, details, ha='center', va='top',
                fontsize=7, bbox=dict(boxstyle='round',
                                     facecolor=COLORS['light']))

        # Arrow to working memory
        add_arrow(ax, x + 1.4, y + 1.0, x + 1.4 if x < 3.5 else 5,
                 6.4 if x < 3.5 else 6.4, color=color, linestyle='--')

    # Vector embedding search
    add_box(ax, 1.5, 8.5, 3, 0.8, 'Vector Embedding Search',
            color=COLORS['neutral'], fontsize=10)
    add_arrow(ax, 5, 8.9, 6, 7.5, linestyle=':')

    # Importance scoring
    add_box(ax, 5.5, 8.5, 3, 0.8, 'Importance Scoring\n(1-10 scale)',
            color=COLORS['neutral'], fontsize=10)

    # Output: Anticipatory suggestions
    add_box(ax, 2, 1.5, 6, 0.8, 'Anticipatory Suggestions\n(Proactive interventions)',
            color=COLORS['accent'], fontsize=11)

    # Arrows from watchers to output
    for x in [1.9, 4.9, 7.9]:
        add_arrow(ax, x, 3.0 if x < 5 else 3.2, 5, 2.4, color=COLORS['accent'])

    # Test coverage note
    ax.text(5, 0.5, 'Total Test Coverage: 135 tests (53 + 37 + 45)',
            ha='center', fontsize=9,
            bbox=dict(boxstyle='round', facecolor=COLORS['light'],
                     edgecolor=COLORS['primary'], linewidth=2))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_watcher_architecture.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated anticipatory watcher architecture")

# ============================================================================
# Figure 3: Resource Discovery Progressive Enhancement
# ============================================================================
def generate_resource_discovery():
    """Generate resource discovery progressive enhancement flowchart"""
    fig, ax = setup_figure(figsize=(14, 11))

    # Title
    ax.text(5, 9.8, 'Resource Discovery: Progressive Enhancement',
            ha='center', fontsize=16, weight='bold')

    # Initial state
    add_box(ax, 3.5, 8.5, 3, 0.8, 'User Request\n(e.g., "Need food help")',
            color=COLORS['neutral'], fontsize=10)
    add_arrow(ax, 5, 8.4, 5, 7.8)

    # Tier 1: No data
    add_box(ax, 1, 7, 3, 1.2, 'Tier 1: Day 1 (No Data)\n\n' +
            'National Resources\n' +
            '• 988 Crisis Hotline\n' +
            '• 211 Referral\n' +
            '• National helplines',
            color=COLORS['warning'], fontsize=8)

    # Tier 2: Has ZIP
    add_box(ax, 4, 7, 2.5, 1.2, 'Tier 2: Has ZIP\n\n' +
            'Local Grounding\n' +
            '• Google Maps API\n' +
            '• Local orgs\n' +
            '• Community resources',
            color=COLORS['primary'], fontsize=8)

    # Tier 3: Has score
    add_box(ax, 6.8, 7, 2.5, 1.2, 'Tier 3: Has Score\n\n' +
            'Targeted Matching\n' +
            '• Worst pressure zone\n' +
            '• Evidence-based\n' +
            '• Personalized',
            color=COLORS['accent'], fontsize=8)

    # Progressive arrow
    add_arrow(ax, 2.5, 7.6, 4, 7.6, label='→', color=COLORS['secondary'])
    add_arrow(ax, 6.5, 7.6, 6.8, 7.6, label='→', color=COLORS['secondary'])

    # Intent interpretation layer
    add_box(ax, 2, 5.5, 6, 0.8, 'Intent Interpretation (LLM)\n' +
            'Extract: need type, urgency, location preference',
            color=COLORS['secondary'], fontsize=9)

    # Arrows from tiers to intent
    add_arrow(ax, 2.5, 6.9, 3.5, 6.4)
    add_arrow(ax, 5.25, 6.9, 5, 6.4)
    add_arrow(ax, 8, 6.9, 6.5, 6.4)

    # Search grounding
    add_box(ax, 1, 4, 4, 0.8, 'Search Grounding\n' +
            '(Google Search API for national/local)',
            color=COLORS['primary'], fontsize=9)

    # Maps grounding
    add_box(ax, 5.5, 4, 4, 0.8, 'Maps Grounding\n' +
            '(Google Maps API for local)',
            color=COLORS['accent'], fontsize=9)

    add_arrow(ax, 4, 5.4, 3, 4.9)
    add_arrow(ax, 6, 5.4, 7.5, 4.9)

    # Fallback mechanism
    add_box(ax, 2.5, 2.5, 5, 0.7, 'Tiered Fallback: T3 → T2 → T1',
            color=COLORS['orange'], fontsize=10)

    add_arrow(ax, 3, 3.9, 4, 3.3)
    add_arrow(ax, 7.5, 3.9, 6, 3.3)

    # Final output
    add_box(ax, 2, 1, 6, 0.8, 'Actionable Resources\n' +
            '(Contact info, hours, eligibility)',
            color=COLORS['accent'], fontsize=10)
    add_arrow(ax, 5, 2.4, 5, 1.9)

    # Key innovation note
    ax.text(5, 0.2, 'Zero Hardcoded Resources • AI-Native Discovery • Progressive Enhancement',
            ha='center', fontsize=9, weight='bold',
            bbox=dict(boxstyle='round', facecolor=COLORS['light'],
                     edgecolor=COLORS['primary'], linewidth=2))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig_resource_discovery.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated resource discovery progressive enhancement")

# ============================================================================
# Main execution
# ============================================================================
if __name__ == '__main__':
    print("Generating GiveCare figures...")
    generate_sdoh_conversational_flow()
    generate_watcher_architecture()
    generate_resource_discovery()
    print("\n✓ All GiveCare figures generated successfully!")
    print(f"Output directory: {OUTPUT_DIR}")
