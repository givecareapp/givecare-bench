#!/usr/bin/env python3
"""
Generate Figure 1: Hero end-to-end flow diagram for GiveCare paper
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-paper')
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 9
plt.rcParams['figure.dpi'] = 300


def fig1_hero_end_to_end_flow():
    """Hero Figure 1: Complete end-to-end flow diagram"""
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis('off')

    # Colors
    user_color = '#3498db'
    agent_color = '#2ecc71'
    guardrail_color = '#e74c3c'
    scoring_color = '#f39c12'
    routing_color = '#9b59b6'
    outcome_color = '#16a085'

    # Title
    ax.text(8, 9.7, 'GiveCare: End-to-End Flow for Longitudinal-Safe Caregiving AI',
            ha='center', fontsize=14, fontweight='bold')
    ax.text(8, 9.3, "Maria's Journey: From Financial Crisis to SNAP Enrollment in 48 Hours",
            ha='center', fontsize=11, style='italic')

    # Stage 1: User Input
    user_box = FancyBboxPatch((0.5, 7), 2.2, 1.5, boxstyle="round,pad=0.1",
                              facecolor=user_color, edgecolor='black', linewidth=2, alpha=0.8)
    ax.add_patch(user_box)
    ax.text(1.6, 8.2, '1. USER INPUT', ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    ax.text(1.6, 7.8, 'Maria, 52\nRetail worker\n$32k/year', ha='center', va='center', fontsize=8, color='white')
    ax.text(1.6, 7.3, '"Skipping meals\\nto buy Mom\'s meds"', ha='center', va='center',
            fontsize=7, style='italic', color='white')

    # Stage 2: Multi-Agent System
    agents_box = FancyBboxPatch((3.5, 6.5), 2.8, 2.5, boxstyle="round,pad=0.1",
                                facecolor=agent_color, edgecolor='black', linewidth=2, alpha=0.7)
    ax.add_patch(agents_box)
    ax.text(4.9, 8.6, '2. AGENTS', ha='center', va='center', fontsize=11, fontweight='bold', color='white')

    # Sub-agents
    main_agent = FancyBboxPatch((3.7, 7.8), 2.4, 0.5, boxstyle="round,pad=0.05",
                                facecolor='#27ae60', edgecolor='white', linewidth=1, alpha=0.9)
    ax.add_patch(main_agent)
    ax.text(4.9, 8.05, 'Main: Orchestration', ha='center', va='center', fontsize=8, fontweight='bold', color='white')

    crisis_agent = FancyBboxPatch((3.7, 7.2), 2.4, 0.5, boxstyle="round,pad=0.05",
                                  facecolor='#27ae60', edgecolor='white', linewidth=1, alpha=0.9)
    ax.add_patch(crisis_agent)
    ax.text(4.9, 7.45, 'Crisis: Safety Support', ha='center', va='center', fontsize=8, fontweight='bold', color='white')

    assess_agent = FancyBboxPatch((3.7, 6.6), 2.4, 0.5, boxstyle="round,pad=0.05",
                                  facecolor='#27ae60', edgecolor='white', linewidth=1, alpha=0.9)
    ax.add_patch(assess_agent)
    ax.text(4.9, 6.85, 'Assessment: GC-SDOH-28', ha='center', va='center', fontsize=8, fontweight='bold', color='white')

    # Arrow 1→2
    arrow1 = FancyArrowPatch((2.7, 7.75), (3.5, 7.75), arrowstyle='->', mutation_scale=25,
                            linewidth=3, color='gray', alpha=0.7)
    ax.add_patch(arrow1)
    ax.text(3.1, 8.1, 'SMS\nInput', ha='center', va='center', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # Stage 3: Guardrails
    guardrail_box = FancyBboxPatch((7, 6.5), 2.2, 2.5, boxstyle="round,pad=0.1",
                                   facecolor=guardrail_color, edgecolor='black', linewidth=2, alpha=0.7)
    ax.add_patch(guardrail_box)
    ax.text(8.1, 8.6, '3. GUARDRAILS', ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    ax.text(8.1, 8.2, '✓ No diagnosis', ha='left', va='center', fontsize=8, color='white')
    ax.text(8.1, 7.9, '✓ No treatment advice', ha='left', va='center', fontsize=8, color='white')
    ax.text(8.1, 7.6, '✓ No dosing', ha='left', va='center', fontsize=8, color='white')
    ax.text(8.1, 7.2, '✓ PII minimization', ha='left', va='center', fontsize=8, color='white')
    ax.text(8.1, 6.85, '20ms parallel check', ha='center', va='center', fontsize=7,
            style='italic', color='white')

    # Arrow 2→3
    arrow2 = FancyArrowPatch((6.3, 7.75), (7, 7.75), arrowstyle='->', mutation_scale=25,
                            linewidth=3, color='gray', alpha=0.7)
    ax.add_patch(arrow2)
    ax.text(6.65, 8.1, 'Response\nGeneration', ha='center', va='center', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # Stage 4: Scoring & Judge Ensemble
    scoring_box = FancyBboxPatch((9.8, 6.5), 2.5, 2.5, boxstyle="round,pad=0.1",
                                 facecolor=scoring_color, edgecolor='black', linewidth=2, alpha=0.7)
    ax.add_patch(scoring_box)
    ax.text(11.05, 8.6, '4. SCORING', ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    ax.text(11.05, 8.2, 'Composite Burnout:', ha='center', va='center', fontsize=8, color='white')
    ax.text(11.05, 7.95, 'EMA 40% • CWBS 30%', ha='center', va='center', fontsize=7, color='white')
    ax.text(11.05, 7.7, 'REACH-II 20% • SDOH 10%', ha='center', va='center', fontsize=7, color='white')
    ax.text(11.05, 7.35, 'Pressure Zones:', ha='center', va='center', fontsize=8, fontweight='bold', color='white')
    ax.text(11.05, 7.05, 'Financial strain ✓', ha='center', va='center', fontsize=7, color='white')
    ax.text(11.05, 6.8, 'Food insecurity (CRISIS)', ha='center', va='center', fontsize=7,
            color='white', fontweight='bold')

    # Arrow 3→4
    arrow3 = FancyArrowPatch((9.2, 7.75), (9.8, 7.75), arrowstyle='->', mutation_scale=25,
                            linewidth=3, color='gray', alpha=0.7)
    ax.add_patch(arrow3)
    ax.text(9.5, 8.1, 'Safety\nCheck', ha='center', va='center', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # Stage 5: Intervention Routing
    routing_box = FancyBboxPatch((7, 3.5), 2.2, 2.3, boxstyle="round,pad=0.1",
                                 facecolor=routing_color, edgecolor='black', linewidth=2, alpha=0.7)
    ax.add_patch(routing_box)
    ax.text(8.1, 5.5, '5. ROUTING', ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    ax.text(8.1, 5.1, 'RBI Algorithm:', ha='center', va='center', fontsize=8, fontweight='bold', color='white')
    ax.text(8.1, 4.85, 'Relevance × Burden', ha='center', va='center', fontsize=7, color='white')
    ax.text(8.1, 4.6, '× Impact', ha='center', va='center', fontsize=7, color='white')
    ax.text(8.1, 4.25, '→ Top 3 Interventions', ha='center', va='center', fontsize=8, color='white')
    ax.text(8.1, 3.85, 'Gemini Maps API:\n$25/1K, 20-50ms', ha='center', va='center', fontsize=6,
            style='italic', color='white')

    # Arrow 4→5
    arrow4 = FancyArrowPatch((11.05, 6.5), (8.1, 5.8), arrowstyle='->', mutation_scale=25,
                            linewidth=3, color='gray', alpha=0.7)
    ax.add_patch(arrow4)
    ax.text(9.8, 6.3, 'Prioritize\nby Zone', ha='center', va='center', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # Stage 6: Outcomes
    outcome_box = FancyBboxPatch((10, 3.5), 2.5, 2.3, boxstyle="round,pad=0.1",
                                 facecolor=outcome_color, edgecolor='black', linewidth=2, alpha=0.7)
    ax.add_patch(outcome_box)
    ax.text(11.25, 5.5, '6. OUTCOMES', ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    ax.text(11.25, 5.05, 'Maria Receives:', ha='center', va='center', fontsize=8, fontweight='bold', color='white')
    ax.text(11.25, 4.75, '1. SNAP enrollment guide', ha='left', va='center', fontsize=7, color='white')
    ax.text(11.25, 4.5, '2. Food pantry location', ha='left', va='center', fontsize=7, color='white')
    ax.text(11.25, 4.25, '3. Caregiver tax credit', ha='left', va='center', fontsize=7, color='white')
    ax.text(11.25, 3.85, '✓ Enrolled in 48h', ha='center', va='center', fontsize=7,
            fontweight='bold', color='white')
    ax.text(11.25, 3.6, '✓ Financial: 100→60', ha='center', va='center', fontsize=7,
            fontweight='bold', color='white')

    # Arrow 5→6
    arrow5 = FancyArrowPatch((9.2, 4.65), (10, 4.65), arrowstyle='->', mutation_scale=25,
                            linewidth=3, color='gray', alpha=0.7)
    ax.add_patch(arrow5)
    ax.text(9.6, 5, 'Deliver\nResources', ha='center', va='center', fontsize=7,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

    # Feedback loop arrow
    feedback_arrow = FancyArrowPatch((1.6, 7), (1.6, 4), arrowstyle='->', mutation_scale=20,
                                    linewidth=2, color='green', alpha=0.6, linestyle='--')
    ax.add_patch(feedback_arrow)
    ax.text(0.8, 5.5, 'Longitudinal\nTracking', ha='center', va='center', fontsize=7,
            rotation=90, fontweight='bold', color='green',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

    # Context passed between stages (bottom annotation)
    context_note = ('Context Passed: User profile • Burnout score • Pressure zones • '
                   'Assessment state • Recent messages • Historical summary')
    ax.text(8, 2.8, context_note, ha='center', va='center', fontsize=8,
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.7))

    # Performance metrics (bottom)
    perf_box = FancyBboxPatch((0.5, 0.5), 15, 2, boxstyle="round,pad=0.1",
                              facecolor='lightblue', edgecolor='black', linewidth=1.5, alpha=0.5)
    ax.add_patch(perf_box)

    ax.text(8, 2.2, 'System Performance Metrics', ha='center', va='center',
            fontsize=10, fontweight='bold')

    metrics = [
        ('Cost', '$1.52/user/month (10K scale)'),
        ('Latency', '950ms median response time'),
        ('Safety', '0 regulatory violations (automated eval)'),
        ('Completion', '75% GC-SDOH-28 completion (vs. ~40% traditional)'),
        ('Impact', '75% financial strain detected → SNAP enrollment')
    ]

    y_pos = 1.7
    for metric, value in metrics:
        ax.text(1.5, y_pos, f'• {metric}:', ha='left', va='center', fontsize=8, fontweight='bold')
        ax.text(4, y_pos, value, ha='left', va='center', fontsize=7)
        y_pos -= 0.3

    # Design principles annotation
    principles_text = ('Design Principles: Compliance-first gating • Attachment-resistance • '
                      'Low-cost ops • Human-grade auditability')
    ax.text(8, 0.2, principles_text, ha='center', va='center', fontsize=7, style='italic',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.6))

    plt.tight_layout()
    plt.savefig('/Users/amadad/Projects/give-care-else/givecare-bench/papers/givecare/fig1_hero_flow.pdf',
                bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Generated fig1_hero_flow.pdf")


if __name__ == '__main__':
    print("Generating Figure 1: Hero end-to-end flow diagram...\n")
    fig1_hero_end_to_end_flow()
    print("\n✅ Hero figure generated successfully!")
