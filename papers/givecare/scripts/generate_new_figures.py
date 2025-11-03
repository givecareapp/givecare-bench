#!/usr/bin/env python3
"""
Generate three key figures for GiveCare paper restructuring:
1. System Architecture (7 components)
2. Value Proposition Flow (6-step loop)
3. Anticipatory Timeline (detection before crisis)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import numpy as np

# Color palette - warm, earthy tones for minimal/monochromatic design
COLOR_PALETTE = {
    'light_peach': '#FFE8D6',    # Backgrounds, very subtle elements
    'dark_brown': '#54340E',      # Text, axes, emphasis
    'orange': '#FF9F1C',          # Primary data, highlights
    'light_orange': '#FFBF68',    # Secondary elements
    'tan': '#CB997E',             # Tertiary elements, fills
}

# Set publication-quality defaults
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.linewidth'] = 1.5
plt.rcParams['axes.edgecolor'] = COLOR_PALETTE['dark_brown']
plt.rcParams['axes.labelcolor'] = COLOR_PALETTE['dark_brown']
plt.rcParams['text.color'] = COLOR_PALETTE['dark_brown']
plt.rcParams['xtick.color'] = COLOR_PALETTE['dark_brown']
plt.rcParams['ytick.color'] = COLOR_PALETTE['dark_brown']

def create_system_architecture():
    """Figure 1: System Architecture - clear vertical flow with highlighted anticipatory system"""
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Color palette
    color_input = COLOR_PALETTE['light_peach']
    color_processing = COLOR_PALETTE['tan']
    color_key_feature = COLOR_PALETTE['orange']  # Anticipatory - KEY DIFFERENTIATOR
    color_support = COLOR_PALETTE['light_orange']
    edge_color = COLOR_PALETTE['dark_brown']
    arrow_color = COLOR_PALETTE['dark_brown']

    # Title
    ax.text(7, 9.6, 'GiveCare System Architecture: 7 Integrated Components',
            ha='center', fontsize=16, fontweight='bold', color=edge_color)

    # ROW 1: INPUT - Component 1 (SMS Interface)
    box1 = FancyBboxPatch((1, 8.4), 12, 0.9, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color_input, linewidth=2)
    ax.add_patch(box1)
    ax.text(7, 8.85, '1. SMS-First Interface', ha='center', va='center',
            fontsize=12, fontweight='bold', color=edge_color)
    ax.text(7, 8.55, 'Zero-download, accessible via text message', ha='center', va='center',
            fontsize=9, color=edge_color)

    # ROW 2: PROCESSING PIPELINE - Components 2, 3, 4 (horizontal flow)
    # Component 2: Multi-Agent
    box2 = FancyBboxPatch((1, 6.8), 3.5, 1.2, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color_processing, linewidth=2)
    ax.add_patch(box2)
    ax.text(2.75, 7.65, '2. Multi-Agent\nOrchestration', ha='center', va='center',
            fontsize=10, fontweight='bold', color=edge_color)
    ax.text(2.75, 7.15, 'Main • Crisis • Assessment', ha='center', va='center',
            fontsize=8, color=edge_color)

    # Component 3: SDOH Instrument
    box3 = FancyBboxPatch((5.25, 6.8), 3.5, 1.2, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color_processing, linewidth=2)
    ax.add_patch(box3)
    ax.text(7, 7.65, '3. GC-SDOH-28\nInstrument', ha='center', va='center',
            fontsize=10, fontweight='bold', color=edge_color)
    ax.text(7, 7.15, '28 questions • 8 domains', ha='center', va='center',
            fontsize=8, color=edge_color)

    # Component 4: Composite Burnout Scoring
    box4 = FancyBboxPatch((9.5, 6.8), 3.5, 1.2, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color_processing, linewidth=2)
    ax.add_patch(box4)
    ax.text(11.25, 7.65, '4. Composite Burnout\nScoring', ha='center', va='center',
            fontsize=10, fontweight='bold', color=edge_color)
    ax.text(11.25, 7.15, 'EMA • CWBS • REACH-II • SDOH', ha='center', va='center',
            fontsize=8, color=edge_color)

    # ROW 3: KEY DIFFERENTIATOR + SUPPORT - Components 5 & 6
    # Component 5: ANTICIPATORY ENGAGEMENT (KEY FEATURE - wider and highlighted)
    box5 = FancyBboxPatch((1, 4.7), 7.5, 1.7, boxstyle="round,pad=0.15",
                          edgecolor=edge_color, facecolor=color_key_feature, linewidth=4)
    ax.add_patch(box5)
    ax.text(4.75, 6.05, '5. ANTICIPATORY ENGAGEMENT SYSTEM  [KEY DIFFERENTIATOR]',
            ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    ax.text(4.75, 5.65, '• Wellness Trend Watcher: 4-week trajectory analysis',
            ha='center', va='center', fontsize=9, color='white')
    ax.text(4.75, 5.35, '• Engagement Watcher: Disengagement detection',
            ha='center', va='center', fontsize=9, color='white')
    ax.text(4.75, 5.05, '• Crisis Burst Detector: Escalation pattern recognition',
            ha='center', va='center', fontsize=9, color='white')

    # Component 6: Resource Matching
    box6 = FancyBboxPatch((9.25, 4.7), 3.75, 1.7, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color_support, linewidth=2)
    ax.add_patch(box6)
    ax.text(11.125, 5.85, '6. Grounded Resource\nMatching', ha='center', va='center',
            fontsize=10, fontweight='bold', color=edge_color)
    ax.text(11.125, 5.4, 'Gemini Maps API', ha='center', va='center',
            fontsize=8, color=edge_color)
    ax.text(11.125, 5.1, 'Real-time local resources\nwith contact info', ha='center', va='center',
            fontsize=8, color=edge_color)

    # ROW 4: INFRASTRUCTURE - Component 7
    box7 = FancyBboxPatch((1, 3.0), 12, 1.2, boxstyle="round,pad=0.1",
                          edgecolor=edge_color, facecolor=color_processing, linewidth=2)
    ax.add_patch(box7)
    ax.text(7, 3.85, '7. Production Deployment Architecture', ha='center', va='center',
            fontsize=11, fontweight='bold', color=edge_color)
    ax.text(7, 3.45, 'Convex backend • 950ms latency • 0 technical failures (N=8 pilot) • Stripe billing • RRULE triggers',
            ha='center', va='center', fontsize=8, color=edge_color)

    # ROW 5: OUTCOMES
    outcomes_box = FancyBboxPatch((2, 0.6), 10, 1.8, boxstyle="round,pad=0.15",
                                  edgecolor=edge_color, facecolor=color_input, linewidth=2)
    ax.add_patch(outcomes_box)
    ax.text(7, 2.1, 'CAREGIVER OUTCOMES', ha='center', va='center',
            fontsize=12, fontweight='bold', color=edge_color)
    ax.text(7, 1.7, 'Anticipate and Reduce Burnout', ha='center', va='center',
            fontsize=10, color=edge_color)
    ax.text(7, 1.35, 'Personalized • Locally-grounded • Adaptive engagement',
            ha='center', va='center', fontsize=9, color=edge_color)
    ax.text(7, 1.0, 'Detect escalation BEFORE crisis thresholds',
            ha='center', va='center', fontsize=9, style='italic', color=edge_color)

    # ARROWS - Clear vertical flow
    arrow_props = dict(arrowstyle='->', lw=2.5, color=arrow_color, mutation_scale=25)
    arrow_thick = dict(arrowstyle='->', lw=3.5, color=color_key_feature, mutation_scale=25)

    # SMS → Multi-Agent (left) - from bottom of Box 1 to top of Box 2
    ax.annotate('', xy=(2.75, 8.0), xytext=(2.75, 8.4), arrowprops=arrow_props)

    # SMS → SDOH (middle) - from bottom of Box 1 to top of Box 3
    ax.annotate('', xy=(7, 8.0), xytext=(7, 8.4), arrowprops=arrow_props)

    # SMS → Burnout (right) - from bottom of Box 1 to top of Box 4
    ax.annotate('', xy=(11.25, 8.0), xytext=(11.25, 8.4), arrowprops=arrow_props)

    # Multi-Agent → SDOH
    ax.annotate('', xy=(5.25, 7.4), xytext=(4.5, 7.4), arrowprops=arrow_props)

    # SDOH → Burnout
    ax.annotate('', xy=(9.5, 7.4), xytext=(8.75, 7.4), arrowprops=arrow_props)

    # Burnout → Anticipatory (angled arrow - KEY PATH)
    # Start from bottom-left corner of Box 4, end at top of Box 5
    ax.annotate('', xy=(4.75, 6.4), xytext=(9.5, 6.8),
                arrowprops=arrow_thick)

    # Burnout → Resource Matching (slightly angled arrow)
    # Start from center-bottom of Box 4, end at center-top of Box 6
    ax.annotate('', xy=(11.125, 6.4), xytext=(11.25, 6.8), arrowprops=arrow_props)

    # Anticipatory → Production (main path)
    ax.annotate('', xy=(4.75, 4.2), xytext=(4.75, 4.7), arrowprops=arrow_thick)

    # Resource Matching → Production
    ax.annotate('', xy=(11.125, 4.2), xytext=(11.125, 4.7), arrowprops=arrow_props)

    # Production → Outcomes
    ax.annotate('', xy=(7, 2.4), xytext=(7, 3.0), arrowprops=arrow_props)

    plt.tight_layout()
    plt.savefig('../figures/fig1_system_architecture_7components.pdf', dpi=300, bbox_inches='tight')
    print("✓ Created fig1_system_architecture_7components.pdf")
    plt.close()


def create_value_proposition_flow():
    """Figure 2: Value Proposition showing 6-step loop"""
    fig, ax = plt.subplots(figsize=(10, 11))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.8, 1.8)
    ax.set_aspect('equal')  # Keep circles perfectly round
    ax.axis('off')

    # Title - larger, bolder
    ax.text(0, 1.6, 'Value Proposition: Measurement-to-Intervention-to-Maintenance Loop',
            ha='center', fontsize=14, fontweight='bold', color=COLOR_PALETTE['dark_brown'])

    # Define 6 steps in circular layout
    angles = np.linspace(90, 90 + 360, 7)[:-1]  # Start at top, 6 points
    radius = 1.0

    steps = [
        ('1. Composite\nBurnout Score', 'EMA + CWBS +\nREACH-II + SDOH'),
        ('2. Pressure\nZone Extraction', 'Emotional, physical,\nfinancial, social, time'),
        ('3. Grounded\nResource Matching', 'Gemini Maps:\nCurrent, local'),
        ('4. Multi-Factor\nScoring', 'Zone 40%, Geo 30%,\nBand 15%'),
        ('5. Longitudinal\nAdaptation', 'Track trajectory,\nadapt zones'),
        ('6. ANTICIPATORY\nEngagement', 'Detect escalation\nBEFORE crisis')
    ]

    # GiveCare color palette
    colors = [COLOR_PALETTE['light_peach'], COLOR_PALETTE['light_peach'],
              COLOR_PALETTE['light_peach'], COLOR_PALETTE['light_peach'],
              COLOR_PALETTE['light_peach'], COLOR_PALETTE['orange']]  # Step 6 highlighted
    edge_colors = [COLOR_PALETTE['dark_brown']] * 6
    edge_widths = [2, 2, 2, 2, 2, 4]  # Step 6 thicker edge

    positions = []
    for i, (angle, (title, desc), color, edge_color, edge_width) in enumerate(zip(angles, steps, colors, edge_colors, edge_widths)):
        x = radius * np.cos(np.radians(angle))
        y = radius * np.sin(np.radians(angle))
        positions.append((x, y))

        # Draw circle for step
        circle = Circle((x, y), 0.3, facecolor=color, edgecolor=edge_color, linewidth=edge_width)
        ax.add_patch(circle)

        # Add step title - larger fonts
        # White text on orange background for step 6, dark brown for others
        text_color = 'white' if i == 5 else COLOR_PALETTE['dark_brown']
        ax.text(x, y + 0.05, title, ha='center', va='center',
                fontsize=9, fontweight='bold', multialignment='center', color=text_color)
        # Add description
        ax.text(x, y - 0.09, desc, ha='center', va='center',
                fontsize=7, multialignment='center', style='italic', color=text_color)

    # Draw arrows connecting steps in a circle
    arrow_props = dict(arrowstyle='->', lw=2.5, color=COLOR_PALETTE['dark_brown'],
                      connectionstyle='arc3,rad=0.1')

    for i in range(len(positions)):
        x1, y1 = positions[i]
        x2, y2 = positions[(i + 1) % len(positions)]

        # Calculate arrow start/end on circle edge
        angle_to_next = np.arctan2(y2 - y1, x2 - x1)
        x1_edge = x1 + 0.3 * np.cos(angle_to_next)
        y1_edge = y1 + 0.3 * np.sin(angle_to_next)
        x2_edge = x2 - 0.3 * np.cos(angle_to_next)
        y2_edge = y2 - 0.3 * np.sin(angle_to_next)

        # Special thicker arrow from step 6 back to step 1 (closes loop)
        if i == 5:  # Arrow from step 6 to step 1
            arrow_props_special = dict(arrowstyle='->', lw=4, color=COLOR_PALETTE['orange'],
                                      connectionstyle='arc3,rad=0.1')
            ax.annotate('', xy=(x2_edge, y2_edge), xytext=(x1_edge, y1_edge),
                       arrowprops=arrow_props_special)
        else:
            ax.annotate('', xy=(x2_edge, y2_edge), xytext=(x1_edge, y1_edge),
                       arrowprops=arrow_props)

    # Add center text - no box, larger text, tighter spacing
    ax.text(0, 0.04, 'Anticipate', ha='center', va='center',
            fontsize=16, fontweight='bold', color=COLOR_PALETTE['dark_brown'])
    ax.text(0, -0.04, 'and Reduce', ha='center', va='center',
            fontsize=16, fontweight='bold', color=COLOR_PALETTE['dark_brown'])

    # Add Maria example annotation - MORE SPACE ABOVE
    example_text = (
        "Maria's Example:\n"
        "Financial pressure (score 45) → SNAP link → "
        "Local food pantry → 40-pt improvement → "
        "Cadence reduction → Trend watcher detects decline "
        "(70→58) BEFORE crisis → Prevents relapse"
    )
    ax.text(0, -1.55, example_text, ha='center', va='center',
            fontsize=7, bbox=dict(boxstyle='round,pad=0.5',
                                 facecolor=COLOR_PALETTE['light_peach'],
                                 edgecolor=COLOR_PALETTE['dark_brown'], linewidth=1.5),
            color=COLOR_PALETTE['dark_brown'])

    plt.tight_layout()
    plt.savefig('../figures/fig2_value_proposition_flow.pdf', dpi=300, bbox_inches='tight')
    print("✓ Created fig2_value_proposition_flow.pdf")
    plt.close()


def create_anticipatory_timeline():
    """Figure 3: Anticipatory Timeline - fixed legend placement and overlap"""
    fig, ax = plt.subplots(figsize=(10, 7))  # Increased height to prevent overlap

    # Title
    ax.set_title('Anticipatory Intelligence: Detecting Escalation Before Crisis',
                fontsize=14, fontweight='bold', pad=20, color=COLOR_PALETTE['dark_brown'])

    # Timeline data
    weeks = np.array([0, 1, 2, 3, 4])
    burnout_scores = np.array([70, 65, 60, 58, 52])

    # Crisis threshold
    crisis_threshold = 40

    # Plot burnout trajectory - orange color
    ax.plot(weeks, burnout_scores, 'o-', linewidth=3, markersize=10,
            color=COLOR_PALETTE['orange'], label='Burnout Score (declining = worsening)', zorder=3)

    # Add score labels
    for week, score in zip(weeks, burnout_scores):
        ax.text(week, score + 3, f'{int(score)}', ha='center', va='bottom',
               fontsize=10, fontweight='bold', color=COLOR_PALETTE['dark_brown'])

    # Draw crisis threshold line
    ax.axhline(y=crisis_threshold, color=COLOR_PALETTE['orange'], linestyle='--',
              linewidth=2, label='Crisis Threshold (<40)', alpha=0.7)
    ax.text(-0.3, crisis_threshold, 'Crisis', ha='right', va='center',
           fontsize=9, color=COLOR_PALETTE['orange'], fontweight='bold')

    # Highlight anticipatory intervention point
    intervention_week = 3
    intervention_score = 58

    # Draw vertical line at intervention
    ax.axvline(x=intervention_week, color=COLOR_PALETTE['tan'], linestyle=':',
              linewidth=2, alpha=0.7)

    # Add intervention annotation with arrow
    ax.annotate('ANTICIPATORY INTERVENTION\n(Week 3, before crisis)',
               xy=(intervention_week, intervention_score),
               xytext=(intervention_week + 0.7, 46),  # Adjusted position
               fontsize=10, fontweight='bold', color=COLOR_PALETTE['dark_brown'],
               bbox=dict(boxstyle='round,pad=0.5', facecolor=COLOR_PALETTE['light_peach'],
                        edgecolor=COLOR_PALETTE['dark_brown'], linewidth=2),
               arrowprops=dict(arrowstyle='->', lw=2, color=COLOR_PALETTE['orange']))

    # Add shaded region showing trend detection
    ax.fill_between([0, 3], 75, 55, alpha=0.2, color=COLOR_PALETTE['light_orange'],
                    label='4-week trend analysis window')

    # Comparison boxes - MOVED DOWN to prevent overlap
    # Snapshot AI box
    snapshot_box_text = (
        "Snapshot AI:\n"
        "Sees score 58 → \"Seems okay\"\n"
        "Misses declining trend\n"
        "No anticipation possible"
    )
    ax.text(0.3, 26, snapshot_box_text, ha='left', va='top',  # Moved down from 20 to 26
           fontsize=8, bbox=dict(boxstyle='round,pad=0.5',
                                facecolor=COLOR_PALETTE['light_peach'],
                                edgecolor=COLOR_PALETTE['tan']))

    # GiveCare box
    givecare_box_text = (
        "GiveCare Anticipatory System:\n"
        "Detects pattern: 70 → 65 → 60 → 58\n"
        "4-week decline of 12 points\n"
        "Intervenes at Week 3 BEFORE crisis (<40)\n"
        "Expected 20-30% churn reduction"
    )
    ax.text(2.2, 26, givecare_box_text, ha='left', va='top',  # Moved down from 20 to 26
           fontsize=8, bbox=dict(boxstyle='round,pad=0.5',
                                facecolor=COLOR_PALETTE['light_orange'],
                                edgecolor=COLOR_PALETTE['orange']))

    # Axes labels
    ax.set_xlabel('Week', fontsize=12, fontweight='bold')
    ax.set_ylabel('Burnout Score\n(Lower = Higher Burnout)', fontsize=12, fontweight='bold')

    # Set axis limits - increased y-axis upper limit to give more space
    ax.set_xlim(-0.5, 4.5)
    ax.set_ylim(15, 82)  # Increased from 80 to 82 for better spacing

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--', color=COLOR_PALETTE['tan'])

    # Legend - moved to upper center to avoid overlap with boxes
    ax.legend(loc='upper center', fontsize=9, framealpha=0.95, ncol=2,
             bbox_to_anchor=(0.5, 0.98))

    # Add note about 3 watchers - MOVED TO BOTTOM to avoid overlap
    watcher_note = (
        "3 Active Watchers: (1) Wellness Trend Watcher (4-week analysis), "
        "(2) Engagement Watcher (disengagement), (3) Crisis Burst Detector (language patterns)"
    )
    ax.text(2, 18, watcher_note, ha='center', va='center',  # Moved to bottom
           fontsize=7, style='italic', bbox=dict(boxstyle='round,pad=0.3',
                                                  facecolor=COLOR_PALETTE['light_peach'],
                                                  edgecolor=COLOR_PALETTE['tan'], alpha=0.9))

    plt.tight_layout()
    plt.savefig('../figures/fig3_anticipatory_timeline.pdf', dpi=300, bbox_inches='tight')
    print("✓ Created fig3_anticipatory_timeline.pdf")
    plt.close()


if __name__ == '__main__':
    print("Generating 3 key figures for GiveCare paper...")
    print()
    create_system_architecture()
    create_value_proposition_flow()
    create_anticipatory_timeline()
    print()
    print("All figures generated successfully!")
    print("Files created:")
    print("  - fig1_system_architecture_7components.pdf")
    print("  - fig2_value_proposition_flow.pdf")
    print("  - fig3_anticipatory_timeline.pdf")
