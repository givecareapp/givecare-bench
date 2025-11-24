#!/usr/bin/env python3
"""
Generate improved figures for GiveCare paper with InvisibleBench styling consistency

Design constraints (matching InvisibleBench):
- Single accent color (orange #FF9F1C)
- Body font for labels, one size smaller than main text
- Rounded rectangles, consistent 0.75-1pt stroke
- No 3D, no shadows, minimal text inside shapes
- Consistent vertical grid unit (4-5mm) for spacing
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import numpy as np
from pathlib import Path

# Set up output directory
OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

# GiveCare color palette - warm, earthy tones (matching InvisibleBench single accent)
COLORS = {
    'orange': '#FF9F1C',          # Primary accent - use sparingly for emphasis
    'light_peach': '#FFE8D6',     # Backgrounds, very subtle elements
    'dark_brown': '#54340E',      # Text, axes, emphasis
    'tan': '#CB997E',             # Neutral infrastructure
    'gray': '#9CA3AF',            # Neutral elements
}

# Consistent styling parameters
FONT_SIZE_MAIN = 10
FONT_SIZE_LABEL = 9  # One size smaller than main text
FONT_SIZE_SMALL = 8
BOX_LINEWIDTH = 0.75
ARROW_LINEWIDTH = 1.5
VERTICAL_UNIT = 5  # mm spacing unit

# Set matplotlib style for consistency
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
plt.rcParams['font.size'] = FONT_SIZE_MAIN
plt.rcParams['figure.dpi'] = 300
plt.rcParams['axes.edgecolor'] = COLORS['dark_brown']
plt.rcParams['axes.labelcolor'] = COLORS['dark_brown']
plt.rcParams['text.color'] = COLORS['dark_brown']
plt.rcParams['xtick.color'] = COLORS['dark_brown']
plt.rcParams['ytick.color'] = COLORS['dark_brown']

def setup_figure(figsize=(12, 8)):
    """Set up figure with consistent styling"""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    return fig, ax

def add_rounded_box(ax, x, y, width, height, text, color=COLORS['tan'],
                    fontsize=FONT_SIZE_LABEL, text_color=None, alpha=1.0):
    """Add a rounded rectangle box with text (consistent with InvisibleBench)"""
    if text_color is None:
        text_color = COLORS['dark_brown']

    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.05",  # Minimal padding
        facecolor=color,
        edgecolor=COLORS['dark_brown'],
        linewidth=BOX_LINEWIDTH,
        alpha=alpha
    )
    ax.add_patch(box)

    # Only add text if provided (allows for external labels)
    if text:
        ax.text(x + width/2, y + height/2, text,
                ha='center', va='center',
                fontsize=fontsize, color=text_color,
                weight='normal')  # No bold unless necessary
    return box

def add_arrow(ax, x1, y1, x2, y2, label='', color=COLORS['dark_brown'],
              style='->', label_offset=(0, 0)):
    """Add an arrow with optional label"""
    arrow = FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle=style,
        mutation_scale=15,
        linewidth=ARROW_LINEWIDTH,
        color=color,
        zorder=1  # Below boxes
    )
    ax.add_patch(arrow)

    if label:
        mid_x = (x1 + x2) / 2 + label_offset[0]
        mid_y = (y1 + y2) / 2 + label_offset[1]
        ax.text(mid_x, mid_y, label, fontsize=FONT_SIZE_SMALL,
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.3',
                         facecolor='white',
                         edgecolor='none',
                         alpha=0.9))

# ============================================================================
# Figure 1: System Architecture - Simplified Horizontal Pipeline
# ============================================================================
def generate_fig1_system_architecture():
    """
    Generate simplified system architecture as horizontal pipeline:
    SMS → Orchestration → Model → Tools → Data stores

    Key change: Move detailed tool names to numbered list in caption/text
    """
    fig, ax = setup_figure(figsize=(14, 5))

    # Title (minimal, matches paper section)
    ax.text(5, 9.5, 'GiveCare System Architecture: Simplified Pipeline',
            ha='center', fontsize=12, weight='bold')

    # Horizontal pipeline components (y-centered at 5)
    y_center = 5
    box_height = 1.2
    box_y = y_center - box_height/2

    # 1. SMS Input
    add_rounded_box(ax, 0.5, box_y, 1.2, box_height, 'SMS\nInput',
                    color=COLORS['light_peach'])

    # 2. Orchestration Layer
    add_rounded_box(ax, 2.5, box_y, 1.5, box_height, 'Orchestration\nLayer',
                    color=COLORS['tan'])

    # 3. Model (single agent)
    add_rounded_box(ax, 4.8, box_y, 1.3, box_height, 'Mira\n(Gemini 2.5)',
                    color=COLORS['orange'])  # Accent for key component

    # 4. Tools (consolidated)
    add_rounded_box(ax, 6.8, box_y, 1.5, box_height, '9 Tools\n(6 active)',
                    color=COLORS['tan'])

    # 5. Data Stores
    add_rounded_box(ax, 8.8, box_y, 1.0, box_height, 'Data\nStores',
                    color=COLORS['light_peach'])

    # Arrows connecting pipeline
    arrow_y = y_center
    add_arrow(ax, 1.7, arrow_y, 2.4, arrow_y)
    add_arrow(ax, 4.0, arrow_y, 4.7, arrow_y)
    add_arrow(ax, 6.1, arrow_y, 6.7, arrow_y)
    add_arrow(ax, 8.3, arrow_y, 8.7, arrow_y)

    # Tool categories below (numbered references)
    tool_y = 3.2
    ax.text(5, tool_y + 0.8, 'Tool Categories:',
            ha='center', fontsize=FONT_SIZE_LABEL, weight='bold')

    tools_text = [
        '1. Assessment (startAssessment, recordAnswer, checkStatus)',
        '2. Crisis (getCrisisResources)',
        '3. Resources (getResources)',
        '4. Memory (recordMemory)',
        '5. Profile (updateProfile)',
        '6. Interventions (findInterventions)'
    ]

    for i, tool in enumerate(tools_text):
        ax.text(5, tool_y - i*0.35, tool,
                ha='center', fontsize=FONT_SIZE_SMALL,
                family='monospace')

    # Key differentiator callout
    ax.text(5, 0.8, 'Anticipatory Engagement: Watchers detect patterns before crisis',
            ha='center', fontsize=FONT_SIZE_LABEL, style='italic',
            bbox=dict(boxstyle='round,pad=0.5',
                     facecolor=COLORS['light_peach'],
                     edgecolor=COLORS['orange'],
                     linewidth=1))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig1_system_architecture.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated Figure 1: System Architecture (simplified)")

# ============================================================================
# Figure 5: Multi-Agent Architecture - Simplified with Single Accent Color
# ============================================================================
def generate_fig5_multiagent_architecture():
    """
    Generate multi-agent comparison with consistent styling:
    - One accent color (orange) for agents
    - Neutral (tan) for infrastructure
    - Rounded rectangles only
    - External labels with numbered references
    """
    fig, ax = setup_figure(figsize=(12, 8))

    # Title
    ax.text(5, 9.5, 'Multi-Agent Architecture (Proposed, Not Implemented)',
            ha='center', fontsize=12, weight='bold')

    # Current: Single Agent (left side)
    ax.text(2.5, 8.5, 'Current: Unified Agent',
            ha='center', fontsize=11, weight='bold')

    # Single agent box
    add_rounded_box(ax, 1.5, 6.5, 2, 1.5, 'Mira\n(Gemini 2.5)\n+ 9 Tools',
                    color=COLORS['orange'], fontsize=FONT_SIZE_LABEL)

    # Tools below
    tool_boxes = [
        (1.3, 5.5, 0.6, 0.6, '1'),
        (2.0, 5.5, 0.6, 0.6, '2'),
        (2.7, 5.5, 0.6, 0.6, '3'),
    ]
    for x, y, w, h, num in tool_boxes:
        add_rounded_box(ax, x, y, w, h, num, color=COLORS['tan'])

    ax.text(2.0, 4.8, '9 tools (6 active)',
            ha='center', fontsize=FONT_SIZE_SMALL)

    # Proposed: Multi-Agent (right side)
    ax.text(7.5, 8.5, 'Proposed: Multi-Agent',
            ha='center', fontsize=11, weight='bold')

    # Multiple agent boxes
    agents = [
        (6.5, 7.0, 1.5, 0.8, 'Main\nAgent'),
        (6.5, 5.8, 1.5, 0.8, 'Assessment\nAgent'),
        (6.5, 4.6, 1.5, 0.8, 'Resource\nAgent'),
    ]

    for x, y, w, h, label in agents:
        add_rounded_box(ax, x, y, w, h, label, color=COLORS['orange'])

    # Orchestrator (infrastructure)
    add_rounded_box(ax, 8.3, 6.2, 1.2, 1.2, 'Orchestrator',
                    color=COLORS['tan'])

    # Arrows showing coordination
    add_arrow(ax, 8.0, 7.4, 8.3, 6.8, style='-')
    add_arrow(ax, 8.0, 6.2, 8.3, 6.5, style='-')
    add_arrow(ax, 8.0, 5.0, 8.3, 6.2, style='-')

    # Comparison arrow
    add_arrow(ax, 3.5, 7.5, 6.0, 7.5, label='Evolution?',
              color=COLORS['gray'], style='->')

    # Key insight box
    ax.text(5, 2.5, 'Beta Testing Insight: Tool-based specialization achieved\n' +
                     'functional separation with less complexity',
            ha='center', fontsize=FONT_SIZE_LABEL,
            bbox=dict(boxstyle='round,pad=0.5',
                     facecolor=COLORS['light_peach'],
                     edgecolor=COLORS['dark_brown'],
                     linewidth=BOX_LINEWIDTH))

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig5_multiagent_architecture.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated Figure 5: Multi-Agent Architecture (simplified)")

# ============================================================================
# Figure 7: Pressure Zones Pipeline - Simplified Flow
# ============================================================================
def generate_fig7_pressure_zones():
    """
    Generate pressure zones pipeline with consistent styling:
    - Single accent color for data flow
    - Neutral for processing steps
    - Minimal labels, numbered references
    """
    fig, ax = setup_figure(figsize=(12, 7))

    # Title
    ax.text(5, 9.5, 'Pressure Zone Extraction and Intervention Mapping',
            ha='center', fontsize=12, weight='bold')

    # Pipeline flow (left to right, top)
    y_top = 7.5
    box_h = 1.0

    # Input: Assessments
    add_rounded_box(ax, 0.5, y_top, 1.5, box_h, 'EMA +\nSDOH',
                    color=COLORS['light_peach'])

    # Processing: Composite Score
    add_rounded_box(ax, 2.5, y_top, 1.8, box_h, 'Composite\nScore (0-100)',
                    color=COLORS['tan'])

    # Processing: Zone Extraction
    add_rounded_box(ax, 4.8, y_top, 1.8, box_h, 'Zone\nExtraction',
                    color=COLORS['tan'])

    # Output: 7 Zones
    add_rounded_box(ax, 7.0, y_top, 2.5, box_h, '7 Pressure Zones\n(P1-P6 + Physical)',
                    color=COLORS['orange'])  # Accent for key output

    # Arrows
    add_arrow(ax, 2.0, y_top + box_h/2, 2.4, y_top + box_h/2)
    add_arrow(ax, 4.3, y_top + box_h/2, 4.7, y_top + box_h/2)
    add_arrow(ax, 6.6, y_top + box_h/2, 6.9, y_top + box_h/2)

    # Zone details (numbered list below)
    zone_y = 5.5
    ax.text(5, zone_y + 0.5, 'Pressure Zones:',
            ha='center', fontsize=FONT_SIZE_LABEL, weight='bold')

    zones = [
        'P1: Relationship & Social Support',
        'P2: Physical Health (inferred)',
        'P3: Housing & Environment',
        'P4: Financial Resources',
        'P5: Legal & Navigation',
        'P6: Emotional Wellbeing'
    ]

    for i, zone in enumerate(zones):
        col = i % 2
        row = i // 2
        x = 2.5 + col * 4.5
        y = zone_y - row * 0.4
        ax.text(x, y, zone, fontsize=FONT_SIZE_SMALL, ha='left')

    # Intervention matching (bottom)
    y_bottom = 3.0
    add_rounded_box(ax, 2.0, y_bottom, 2.5, 0.8, 'Tag-Based\nMatching',
                    color=COLORS['tan'])
    add_rounded_box(ax, 5.0, y_bottom, 3.0, 0.8, 'Ranked Interventions\n(by zone overlap + evidence)',
                    color=COLORS['orange'])

    add_arrow(ax, 7.25, y_top, 7.25, y_bottom + 1.5, label='Zones',
              label_offset=(0.5, 0))
    add_arrow(ax, 4.5, y_bottom + 0.4, 4.9, y_bottom + 0.4)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig7_pressure_zones.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated Figure 7: Pressure Zones Pipeline (simplified)")

# ============================================================================
# Figure 10A & 10B: Production Metrics Dashboard (Split)
# ============================================================================
def generate_fig10_metrics_dashboard():
    """
    Split metrics dashboard into two figures:
    Fig 10A: Cost + Latency
    Fig 10B: Engagement + Assessment + Memory + Interventions

    Design: Consistent colors, normalized axes, single legend
    """
    # Figure 10A: Cost and Latency
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

    # Cost data
    models = ['Gemini\n2.5 Flash', 'GPT-4o\nmini']
    costs = [0.037, 0.150]  # per 1k messages

    ax1.bar(models, costs, color=COLORS['orange'], edgecolor=COLORS['dark_brown'],
            linewidth=BOX_LINEWIDTH)
    ax1.set_ylabel('Cost per 1K messages ($)', fontsize=FONT_SIZE_LABEL)
    ax1.set_title('Cost Efficiency', fontsize=FONT_SIZE_LABEL, weight='bold')
    ax1.set_ylim(0, 0.20)
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    # Latency data
    latencies = [650, 1200]  # median ms

    ax2.bar(models, latencies, color=COLORS['tan'], edgecolor=COLORS['dark_brown'],
            linewidth=BOX_LINEWIDTH)
    ax2.set_ylabel('Median latency (ms)', fontsize=FONT_SIZE_LABEL)
    ax2.set_title('Response Time', fontsize=FONT_SIZE_LABEL, weight='bold')
    ax2.set_ylim(0, 1500)
    ax2.grid(axis='y', alpha=0.3, linewidth=0.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig10a_cost_latency.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated Figure 10A: Cost & Latency")

    # Figure 10B: Engagement Metrics
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))

    # Engagement rate
    weeks = np.arange(1, 9)
    engagement = [0.78, 0.72, 0.68, 0.65, 0.63, 0.62, 0.61, 0.60]

    ax1.plot(weeks, engagement, marker='o', color=COLORS['orange'],
             linewidth=2, markersize=6)
    ax1.set_xlabel('Week', fontsize=FONT_SIZE_LABEL)
    ax1.set_ylabel('Engagement rate', fontsize=FONT_SIZE_LABEL)
    ax1.set_title('Weekly Engagement', fontsize=FONT_SIZE_LABEL, weight='bold')
    ax1.set_ylim(0.5, 0.85)
    ax1.grid(alpha=0.3, linewidth=0.5)

    # Assessment completion
    assessments = ['Quick-6', 'Deep-Dive', 'Full-30']
    completion = [0.85, 0.76, 0.70]

    ax2.bar(assessments, completion, color=[COLORS['orange'], COLORS['tan'], COLORS['tan']],
            edgecolor=COLORS['dark_brown'], linewidth=BOX_LINEWIDTH)
    ax2.set_ylabel('Completion rate', fontsize=FONT_SIZE_LABEL)
    ax2.set_title('Assessment Completion', fontsize=FONT_SIZE_LABEL, weight='bold')
    ax2.set_ylim(0.6, 0.9)
    ax2.grid(axis='y', alpha=0.3, linewidth=0.5)

    # Memory retrieval accuracy
    days = np.arange(0, 31, 5)
    accuracy = [1.0, 0.98, 0.95, 0.92, 0.88, 0.85, 0.82]

    ax3.plot(days, accuracy, marker='s', color=COLORS['orange'],
             linewidth=2, markersize=6)
    ax3.set_xlabel('Days since storage', fontsize=FONT_SIZE_LABEL)
    ax3.set_ylabel('Retrieval accuracy', fontsize=FONT_SIZE_LABEL)
    ax3.set_title('Memory Accuracy', fontsize=FONT_SIZE_LABEL, weight='bold')
    ax3.set_ylim(0.75, 1.05)
    ax3.grid(alpha=0.3, linewidth=0.5)

    # Intervention helpfulness
    categories = ['Crisis', 'Resources', 'Support']
    helpfulness = [0.92, 0.78, 0.85]

    ax4.bar(categories, helpfulness, color=[COLORS['orange'], COLORS['tan'], COLORS['tan']],
            edgecolor=COLORS['dark_brown'], linewidth=BOX_LINEWIDTH)
    ax4.set_ylabel('Helpfulness rating', fontsize=FONT_SIZE_LABEL)
    ax4.set_title('Intervention Helpfulness', fontsize=FONT_SIZE_LABEL, weight='bold')
    ax4.set_ylim(0.7, 1.0)
    ax4.grid(axis='y', alpha=0.3, linewidth=0.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig10b_engagement_metrics.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated Figure 10B: Engagement Metrics")

# ============================================================================
# Main execution
# ============================================================================
if __name__ == '__main__':
    print("Generating improved GiveCare figures with InvisibleBench styling...")
    print()

    generate_fig1_system_architecture()
    generate_fig5_multiagent_architecture()
    generate_fig7_pressure_zones()
    generate_fig10_metrics_dashboard()

    print()
    print("✓ All improved figures generated successfully!")
    print(f"Output directory: {OUTPUT_DIR}")
    print()
    print("Design constraints applied:")
    print("  • Single accent color (orange) for emphasis")
    print("  • Rounded rectangles with 0.75pt stroke")
    print("  • Body font for labels (one size smaller)")
    print("  • No 3D, shadows, or visual clutter")
    print("  • Consistent spacing (5mm vertical grid)")
