#!/usr/bin/env python3
"""
Generate improved system architecture figure with precise arrow connections.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.patches import ConnectionPatch
import numpy as np

# Color palette
COLOR_PALETTE = {
    'light_peach': '#FFE8D6',
    'dark_brown': '#54340E',
    'orange': '#FF9F1C',
    'light_orange': '#FFBF68',
    'tan': '#CB997E',
}

# Set publication-quality defaults
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.linewidth'] = 1.5

def create_box(ax, x, y, width, height, title, subtitle, color, edge_color, linewidth=2):
    """Create a box with centered text."""
    box = FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color, linewidth=linewidth)
    ax.add_patch(box)

    # Center coordinates
    cx = x + width/2
    cy = y + height/2

    # Title (centered vertically with subtitle)
    title_lines = title.split('\n')
    subtitle_lines = subtitle.split('\n') if subtitle else []

    total_lines = len(title_lines) + len(subtitle_lines)
    line_height = 0.15
    start_y = cy + (total_lines - 1) * line_height / 2

    # Draw title lines
    for i, line in enumerate(title_lines):
        ax.text(cx, start_y - i * line_height, line,
               ha='center', va='center', fontsize=11, fontweight='bold',
               color='white' if color == COLOR_PALETTE['orange'] else edge_color)

    # Draw subtitle lines
    if subtitle_lines:
        subtitle_start = start_y - len(title_lines) * line_height
        for i, line in enumerate(subtitle_lines):
            ax.text(cx, subtitle_start - i * line_height, line,
                   ha='center', va='center', fontsize=9,
                   color='white' if color == COLOR_PALETTE['orange'] else edge_color)

    return cx, cy, x, y, width, height

def connect_boxes(ax, box1, box2, style='normal', offset=0):
    """Create arrow connection between boxes with proper edge detection."""
    x1, y1, bx1, by1, w1, h1 = box1
    x2, y2, bx2, by2, w2, h2 = box2

    # Determine connection points based on relative positions
    # Vertical connection
    if abs(x1 - x2) < 0.1:  # Same x coordinate (vertical stack)
        start = (x1, by1)  # Bottom of box 1
        end = (x2, by2 + h2)  # Top of box 2
    # Horizontal connection
    elif abs(y1 - y2) < 0.1:  # Same y coordinate (horizontal)
        if x1 < x2:  # Box 1 is left of box 2
            start = (bx1 + w1, y1)  # Right edge of box 1
            end = (bx2, y2)  # Left edge of box 2
        else:
            start = (bx1, y1)  # Left edge of box 1
            end = (bx2 + w2, y2)  # Right edge of box 2
    # Diagonal connection
    else:
        # Determine which edges to connect
        if y1 > y2:  # Box 1 is above box 2
            start = (x1 + offset, by1)  # Bottom of box 1
            end = (x2, by2 + h2)  # Top of box 2
        else:  # Box 1 is below box 2
            start = (x1 + offset, by1 + h1)  # Top of box 1
            end = (x2, by2)  # Bottom of box 2

    # Arrow properties
    if style == 'thick':
        arrow = FancyArrowPatch(start, end,
                              arrowstyle='->', mutation_scale=25,
                              linewidth=3.5, color=COLOR_PALETTE['orange'],
                              zorder=1)
    else:
        arrow = FancyArrowPatch(start, end,
                              arrowstyle='->', mutation_scale=25,
                              linewidth=2.5, color=COLOR_PALETTE['dark_brown'],
                              zorder=1)
    ax.add_patch(arrow)

def create_system_architecture():
    """Create system architecture figure with precise connections."""
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')

    edge_color = COLOR_PALETTE['dark_brown']

    # Title
    ax.text(7, 9.6, 'GiveCare System Architecture: 7 Integrated Components',
            ha='center', fontsize=16, fontweight='bold', color=edge_color)

    # Create all boxes and store their info
    boxes = {}

    # Row 1: Input
    boxes['sms'] = create_box(ax, 1, 8.4, 12, 0.9,
                              '1. SMS-First Interface',
                              'Zero-download, accessible via text message',
                              COLOR_PALETTE['light_peach'], edge_color)

    # Row 2: Processing Pipeline
    boxes['multi'] = create_box(ax, 1, 6.8, 3.5, 1.2,
                                '2. Multi-Agent\nOrchestration',
                                'Main • Crisis • Assessment',
                                COLOR_PALETTE['tan'], edge_color)

    boxes['sdoh'] = create_box(ax, 5.25, 6.8, 3.5, 1.2,
                              '3. GC-SDOH-28\nInstrument',
                              '28 questions • 8 domains',
                              COLOR_PALETTE['tan'], edge_color)

    boxes['burnout'] = create_box(ax, 9.5, 6.8, 3.5, 1.2,
                                  '4. Composite Burnout\nScoring',
                                  'EMA • CWBS • REACH-II • SDOH',
                                  COLOR_PALETTE['tan'], edge_color)

    # Row 3: Key Features
    boxes['antic'] = create_box(ax, 1, 4.7, 7.5, 1.7,
                               '5. ANTICIPATORY ENGAGEMENT SYSTEM  [KEY DIFFERENTIATOR]',
                               '• Wellness Trend Watcher: 4-week trajectory analysis\n• Engagement Watcher: Disengagement detection\n• Crisis Burst Detector: Escalation pattern recognition',
                               COLOR_PALETTE['orange'], edge_color, linewidth=4)

    boxes['resource'] = create_box(ax, 9.25, 4.7, 3.75, 1.7,
                                  '6. Grounded Resource\nMatching',
                                  'Gemini Maps API\nReal-time local resources\nwith contact info',
                                  COLOR_PALETTE['light_orange'], edge_color)

    # Row 4: Infrastructure
    boxes['prod'] = create_box(ax, 1, 3.0, 12, 1.2,
                              '7. Production Deployment Architecture',
                              'Convex backend • 950ms latency • 0 technical failures (N=8 pilot) • Stripe billing • RRULE triggers',
                              COLOR_PALETTE['tan'], edge_color)

    # Row 5: Outcomes
    boxes['outcomes'] = create_box(ax, 2, 0.6, 10, 1.8,
                                   'CAREGIVER OUTCOMES',
                                   'Anticipate and Reduce Burnout\nPersonalized • Locally-grounded • Adaptive engagement\nDetect escalation BEFORE crisis thresholds',
                                   COLOR_PALETTE['light_peach'], edge_color)

    # Create connections
    # SMS to processing pipeline
    connect_boxes(ax, boxes['sms'], boxes['multi'], offset=-4.25)
    connect_boxes(ax, boxes['sms'], boxes['sdoh'])
    connect_boxes(ax, boxes['sms'], boxes['burnout'], offset=4.25)

    # Processing pipeline horizontal flow
    connect_boxes(ax, boxes['multi'], boxes['sdoh'])
    connect_boxes(ax, boxes['sdoh'], boxes['burnout'])

    # Processing to features
    connect_boxes(ax, boxes['burnout'], boxes['antic'], style='thick', offset=-4.75)
    connect_boxes(ax, boxes['burnout'], boxes['resource'], offset=1.875)

    # Features to production
    connect_boxes(ax, boxes['antic'], boxes['prod'], style='thick', offset=-3.25)
    connect_boxes(ax, boxes['resource'], boxes['prod'], offset=4.125)

    # Production to outcomes
    connect_boxes(ax, boxes['prod'], boxes['outcomes'])

    plt.tight_layout()
    plt.savefig('../figures/fig1_system_architecture_improved.pdf', dpi=300, bbox_inches='tight')
    print("✓ Created fig1_system_architecture_improved.pdf")
    plt.close()

if __name__ == '__main__':
    create_system_architecture()
