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

# Set publication-quality defaults
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.linewidth'] = 1.5

def create_system_architecture():
    """Figure 1: System Architecture showing 7 integrated components"""
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Define colors
    color_interface = '#e1f5ff'
    color_component = '#fff3e0'
    color_anticipatory = '#fce4ec'  # Highlight anticipatory engagement
    color_arrow = '#666666'

    # Title
    ax.text(5, 9.5, 'GiveCare System Architecture: 7 Integrated Components',
            ha='center', fontsize=14, fontweight='bold')

    # Component 1: SMS Interface (top)
    box1 = FancyBboxPatch((0.5, 8), 9, 0.6, boxstyle="round,pad=0.1",
                          edgecolor='#01579b', facecolor=color_interface, linewidth=2)
    ax.add_patch(box1)
    ax.text(5, 8.3, '1. SMS-First Interface\n(Zero-download, accessible)',
            ha='center', va='center', fontsize=10, fontweight='bold')

    # Component 2: Multi-Agent Orchestration
    box2 = FancyBboxPatch((0.5, 6.5), 2.5, 1.2, boxstyle="round,pad=0.1",
                          edgecolor='#e65100', facecolor=color_component, linewidth=2)
    ax.add_patch(box2)
    ax.text(1.75, 7.3, '2. Multi-Agent\nOrchestration', ha='center', va='center',
            fontsize=9, fontweight='bold')
    ax.text(1.75, 6.85, 'Main/Crisis/Assessment', ha='center', va='center', fontsize=7)

    # Component 3: GC-SDOH-28
    box3 = FancyBboxPatch((3.5, 6.5), 2.5, 1.2, boxstyle="round,pad=0.1",
                          edgecolor='#e65100', facecolor=color_component, linewidth=2)
    ax.add_patch(box3)
    ax.text(4.75, 7.3, '3. GC-SDOH-28\nInstrument', ha='center', va='center',
            fontsize=9, fontweight='bold')
    ax.text(4.75, 6.85, '28Q, 8 domains', ha='center', va='center', fontsize=7)

    # Component 4: Composite Burnout Scoring
    box4 = FancyBboxPatch((6.5, 6.5), 3, 1.2, boxstyle="round,pad=0.1",
                          edgecolor='#e65100', facecolor=color_component, linewidth=2)
    ax.add_patch(box4)
    ax.text(8, 7.3, '4. Composite Burnout\nScoring', ha='center', va='center',
            fontsize=9, fontweight='bold')
    ax.text(8, 6.85, 'EMA+CWBS+REACH-II+SDOH', ha='center', va='center', fontsize=7)

    # Component 5: ANTICIPATORY ENGAGEMENT (highlighted)
    box5 = FancyBboxPatch((0.5, 4.5), 4, 1.5, boxstyle="round,pad=0.1",
                          edgecolor='#880e4f', facecolor=color_anticipatory, linewidth=3)
    ax.add_patch(box5)
    ax.text(2.5, 5.6, '5. ANTICIPATORY ENGAGEMENT SYSTEM ★',
            ha='center', va='center', fontsize=10, fontweight='bold')
    ax.text(2.5, 5.15, '• Wellness Trend Watcher (4-week analysis)',
            ha='center', va='center', fontsize=7)
    ax.text(2.5, 4.9, '• Engagement Watcher (disengagement detection)',
            ha='center', va='center', fontsize=7)
    ax.text(2.5, 4.65, '• Crisis Burst Detector (escalation patterns)',
            ha='center', va='center', fontsize=7)

    # Component 6: Grounded Resource Matching
    box6 = FancyBboxPatch((5, 4.5), 4.5, 1.5, boxstyle="round,pad=0.1",
                          edgecolor='#e65100', facecolor=color_component, linewidth=2)
    ax.add_patch(box6)
    ax.text(7.25, 5.5, '6. Grounded Resource\nMatching', ha='center', va='center',
            fontsize=9, fontweight='bold')
    ax.text(7.25, 5.05, 'Gemini Maps API', ha='center', va='center', fontsize=7)
    ax.text(7.25, 4.8, 'Current addresses, hours, contact', ha='center', va='center', fontsize=7)

    # Component 7: Production Deployment
    box7 = FancyBboxPatch((0.5, 2.8), 9, 1.2, boxstyle="round,pad=0.1",
                          edgecolor='#e65100', facecolor=color_component, linewidth=2)
    ax.add_patch(box7)
    ax.text(5, 3.6, '7. Production Deployment Architecture',
            ha='center', va='center', fontsize=10, fontweight='bold')
    ax.text(5, 3.2, 'Convex backend • 950ms latency • 0 technical failures (N=8 pilot) • Stripe billing • RRULE triggers',
            ha='center', va='center', fontsize=7)

    # Outcomes (bottom)
    outcomes_box = FancyBboxPatch((1.5, 0.8), 7, 1.5, boxstyle="round,pad=0.1",
                                  edgecolor='#1b5e20', facecolor='#e8f5e9', linewidth=2)
    ax.add_patch(outcomes_box)
    ax.text(5, 2, 'Caregiver Outcomes', ha='center', va='center',
            fontsize=11, fontweight='bold')
    ax.text(5, 1.6, 'Anticipate and Reduce Burnout', ha='center', va='center', fontsize=9)
    ax.text(5, 1.3, 'Personalized • Locally-grounded • Adaptive engagement',
            ha='center', va='center', fontsize=8)
    ax.text(5, 1.0, 'Detect escalation BEFORE crisis thresholds',
            ha='center', va='center', fontsize=8, style='italic')

    # Add arrows showing flow
    arrow_props = dict(arrowstyle='->', lw=2, color=color_arrow)

    # SMS → Multi-Agent
    ax.annotate('', xy=(1.75, 6.5), xytext=(1.75, 8), arrowprops=arrow_props)
    # Multi-Agent → SDOH
    ax.annotate('', xy=(3.5, 7.1), xytext=(3, 7.1), arrowprops=arrow_props)
    # SDOH → Burnout Scoring
    ax.annotate('', xy=(6.5, 7.1), xytext=(6, 7.1), arrowprops=arrow_props)
    # Burnout Scoring → Anticipatory Engagement
    ax.annotate('', xy=(2.5, 6), xytext=(8, 6.5),
                arrowprops=dict(arrowstyle='->', lw=2, color='#880e4f'))
    # Burnout Scoring → Resource Matching
    ax.annotate('', xy=(7.25, 6), xytext=(8, 6.5), arrowprops=arrow_props)
    # Resource Matching → Production
    ax.annotate('', xy=(7.25, 4), xytext=(7.25, 4.5), arrowprops=arrow_props)
    # Production → Outcomes
    ax.annotate('', xy=(5, 2.3), xytext=(5, 2.8), arrowprops=arrow_props)

    plt.tight_layout()
    plt.savefig('fig1_system_architecture_7components.pdf', dpi=300, bbox_inches='tight')
    print("✓ Created fig1_system_architecture_7components.pdf")
    plt.close()


def create_value_proposition_flow():
    """Figure 2: Value Proposition showing 6-step loop"""
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.8)
    ax.axis('off')

    # Title
    ax.text(0, 1.6, 'Value Proposition: Measurement-to-Intervention-to-Maintenance Loop',
            ha='center', fontsize=12, fontweight='bold')

    # Define 6 steps in circular layout
    angles = np.linspace(90, 90 + 360, 7)[:-1]  # Start at top, 6 points
    radius = 1.0

    steps = [
        ('1. Composite\nBurnout Score', 'EMA + CWBS +\nREACH-II + SDOH'),
        ('2. Pressure\nZone Extraction', 'Emotional, physical,\nfinancial, social, time'),
        ('3. Grounded\nResource Matching', 'Gemini Maps:\nCurrent, local'),
        ('4. Multi-Factor\nScoring', 'Zone 40%, Geo 30%,\nBand 15%'),
        ('5. Longitudinal\nAdaptation', 'Track trajectory,\nadapt zones'),
        ('6. ANTICIPATORY\nEngagement ★', 'Detect escalation\nBEFORE crisis')
    ]

    colors = ['#fff3e0', '#fff3e0', '#fff3e0', '#fff3e0', '#fff3e0', '#fce4ec']
    edge_colors = ['#e65100', '#e65100', '#e65100', '#e65100', '#e65100', '#880e4f']
    edge_widths = [2, 2, 2, 2, 2, 3]

    positions = []
    for i, (angle, (title, desc), color, edge_color, edge_width) in enumerate(zip(angles, steps, colors, edge_colors, edge_widths)):
        x = radius * np.cos(np.radians(angle))
        y = radius * np.sin(np.radians(angle))
        positions.append((x, y))

        # Draw circle for step
        circle = Circle((x, y), 0.28, facecolor=color, edgecolor=edge_color, linewidth=edge_width)
        ax.add_patch(circle)

        # Add step title
        ax.text(x, y + 0.05, title, ha='center', va='center',
                fontsize=8, fontweight='bold', multialignment='center')
        # Add description
        ax.text(x, y - 0.08, desc, ha='center', va='center',
                fontsize=6, multialignment='center', style='italic')

    # Draw arrows connecting steps in a circle
    arrow_props = dict(arrowstyle='->', lw=2.5, color='#666666',
                      connectionstyle='arc3,rad=0.1')

    for i in range(len(positions)):
        x1, y1 = positions[i]
        x2, y2 = positions[(i + 1) % len(positions)]

        # Calculate arrow start/end on circle edge
        angle_to_next = np.arctan2(y2 - y1, x2 - x1)
        x1_edge = x1 + 0.28 * np.cos(angle_to_next)
        y1_edge = y1 + 0.28 * np.sin(angle_to_next)
        x2_edge = x2 - 0.28 * np.cos(angle_to_next)
        y2_edge = y2 - 0.28 * np.sin(angle_to_next)

        # Special color for arrow to step 6 (anticipatory)
        if i == 4:  # Arrow from step 5 to step 6
            arrow_props_special = dict(arrowstyle='->', lw=3, color='#880e4f',
                                      connectionstyle='arc3,rad=0.1')
            ax.annotate('', xy=(x2_edge, y2_edge), xytext=(x1_edge, y1_edge),
                       arrowprops=arrow_props_special)
        else:
            ax.annotate('', xy=(x2_edge, y2_edge), xytext=(x1_edge, y1_edge),
                       arrowprops=arrow_props)

    # Add center text showing the core value
    center_box = FancyBboxPatch((-0.35, -0.25), 0.7, 0.5, boxstyle="round,pad=0.05",
                               edgecolor='#1b5e20', facecolor='#e8f5e9', linewidth=2)
    ax.add_patch(center_box)
    ax.text(0, 0.08, 'Core Value:', ha='center', va='center',
            fontsize=9, fontweight='bold')
    ax.text(0, -0.03, 'Anticipate', ha='center', va='center',
            fontsize=10, fontweight='bold', color='#880e4f')
    ax.text(0, -0.14, 'and Reduce', ha='center', va='center',
            fontsize=10, fontweight='bold', color='#1b5e20')

    # Add Maria example annotation
    example_text = (
        "Maria's Example:\n"
        "Financial pressure (score 45) → SNAP link → "
        "Local food pantry → 40-pt improvement → "
        "Cadence reduction → Trend watcher detects decline "
        "(70→58) BEFORE crisis → Prevents relapse"
    )
    ax.text(0, -1.35, example_text, ha='center', va='center',
            fontsize=7, bbox=dict(boxstyle='round,pad=0.5',
                                 facecolor='#fffde7', edgecolor='#f57f17'))

    plt.tight_layout()
    plt.savefig('fig2_value_proposition_flow.pdf', dpi=300, bbox_inches='tight')
    print("✓ Created fig2_value_proposition_flow.pdf")
    plt.close()


def create_anticipatory_timeline():
    """Figure 3: Anticipatory Timeline showing detection before crisis"""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Title
    ax.set_title('Anticipatory Intelligence: Detecting Escalation Before Crisis',
                fontsize=14, fontweight='bold', pad=20)

    # Timeline data
    weeks = np.array([0, 1, 2, 3, 4])
    burnout_scores = np.array([70, 65, 60, 58, 52])

    # Crisis threshold
    crisis_threshold = 40

    # Plot burnout trajectory
    ax.plot(weeks, burnout_scores, 'o-', linewidth=3, markersize=10,
            color='#d32f2f', label='Burnout Score (declining = worsening)', zorder=3)

    # Add score labels
    for week, score in zip(weeks, burnout_scores):
        ax.text(week, score + 3, f'{int(score)}', ha='center', va='bottom',
               fontsize=10, fontweight='bold')

    # Draw crisis threshold line
    ax.axhline(y=crisis_threshold, color='#d32f2f', linestyle='--',
              linewidth=2, label='Crisis Threshold (<40)', alpha=0.7)
    ax.text(-0.3, crisis_threshold, 'Crisis', ha='right', va='center',
           fontsize=9, color='#d32f2f', fontweight='bold')

    # Highlight anticipatory intervention point
    intervention_week = 3
    intervention_score = 58

    # Draw vertical line at intervention
    ax.axvline(x=intervention_week, color='#880e4f', linestyle=':',
              linewidth=2, alpha=0.5)

    # Add intervention annotation with arrow
    ax.annotate('ANTICIPATORY INTERVENTION\n(Week 3, before crisis)',
               xy=(intervention_week, intervention_score),
               xytext=(intervention_week + 0.8, 48),
               fontsize=10, fontweight='bold', color='#880e4f',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#fce4ec',
                        edgecolor='#880e4f', linewidth=2),
               arrowprops=dict(arrowstyle='->', lw=2, color='#880e4f'))

    # Add shaded region showing trend detection
    ax.fill_between([0, 3], 75, 55, alpha=0.2, color='#fce4ec',
                    label='4-week trend analysis window')

    # Comparison boxes
    # Snapshot AI box
    snapshot_box_text = (
        "Snapshot AI:\n"
        "Sees score 58 → \"Seems okay\"\n"
        "Misses declining trend\n"
        "No anticipation possible"
    )
    ax.text(0.5, 20, snapshot_box_text, ha='left', va='top',
           fontsize=8, bbox=dict(boxstyle='round,pad=0.5',
                                facecolor='#ffebee', edgecolor='#c62828'))

    # GiveCare box
    givecare_box_text = (
        "GiveCare Anticipatory System:\n"
        "Detects pattern: 70 → 65 → 60 → 58\n"
        "4-week decline of 12 points\n"
        "Intervenes at Week 3 BEFORE crisis (<40)\n"
        "Expected 20-30% churn reduction"
    )
    ax.text(2.3, 20, givecare_box_text, ha='left', va='top',
           fontsize=8, bbox=dict(boxstyle='round,pad=0.5',
                                facecolor='#e8f5e9', edgecolor='#1b5e20'))

    # Axes labels
    ax.set_xlabel('Week', fontsize=12, fontweight='bold')
    ax.set_ylabel('Burnout Score\n(Lower = Higher Burnout)', fontsize=12, fontweight='bold')

    # Set axis limits
    ax.set_xlim(-0.5, 4.5)
    ax.set_ylim(15, 80)

    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Legend
    ax.legend(loc='upper right', fontsize=9, framealpha=0.9)

    # Add note about 3 watchers
    watcher_note = (
        "3 Active Watchers: (1) Wellness Trend Watcher (4-week analysis), "
        "(2) Engagement Watcher (disengagement), (3) Crisis Burst Detector (language patterns)"
    )
    ax.text(2, 78, watcher_note, ha='center', va='top',
           fontsize=7, style='italic', bbox=dict(boxstyle='round,pad=0.3',
                                                  facecolor='#fff9c4', alpha=0.8))

    plt.tight_layout()
    plt.savefig('fig3_anticipatory_timeline.pdf', dpi=300, bbox_inches='tight')
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
