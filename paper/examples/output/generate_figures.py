#!/usr/bin/env python3
"""
GiveCare Paper Figure Generation
Generates publication-quality vector graphics for the paper using matplotlib + tikzplotlib.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
import numpy as np
import seaborn as sns
from pathlib import Path

# Configure matplotlib for LaTeX-quality output
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman', 'Computer Modern Roman'],
    'font.size': 10,
    'text.usetex': False,  # Set to True if you have LaTeX installed
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.titlesize': 12,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.format': 'pdf',
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.5,
    'grid.linewidth': 0.5,
    'lines.linewidth': 1.5,
})

# Color palette (colorblind-friendly)
COLORS = {
    'primary': '#2E86AB',      # Blue
    'secondary': '#A23B72',    # Purple
    'accent': '#F18F01',       # Orange
    'success': '#06A77D',      # Green
    'warning': '#D84315',      # Red
    'neutral': '#6C757D',      # Gray
    'light': '#E9ECEF',        # Light gray
}

OUTPUT_DIR = Path(__file__).parent


def generate_multiagent_architecture():
    """Figure 1: Multi-agent architecture with seamless handoffs"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    # User (left)
    user = Circle((1, 3), 0.4, color=COLORS['neutral'], alpha=0.3)
    ax.add_patch(user)
    ax.text(1, 3, 'User\n(SMS)', ha='center', va='center', fontsize=9, weight='bold')

    # Convex Backend (center)
    convex = FancyBboxPatch((3, 1), 4, 4, boxstyle="round,pad=0.1",
                            edgecolor=COLORS['primary'], facecolor=COLORS['light'], linewidth=2)
    ax.add_patch(convex)
    ax.text(5, 5.3, 'Convex Serverless Backend', ha='center', va='center', fontsize=10, weight='bold')

    # Three agents
    agents = [
        ('Main Agent\n(Orchestrator)', 3.5, 3, COLORS['primary']),
        ('Crisis Agent\n(Safety)', 5, 3, COLORS['warning']),
        ('Assessment Agent\n(EMA/CWBS/SDOH)', 6.5, 3, COLORS['success']),
    ]

    for name, x, y, color in agents:
        agent_box = FancyBboxPatch((x-0.6, y-0.5), 1.2, 1, boxstyle="round,pad=0.05",
                                  edgecolor=color, facecolor='white', linewidth=1.5)
        ax.add_patch(agent_box)
        ax.text(x, y, name, ha='center', va='center', fontsize=8)

    # GiveCareContext (shared state)
    context = Rectangle((3.3, 1.3), 3.4, 0.5, edgecolor=COLORS['accent'],
                       facecolor=COLORS['accent'], alpha=0.2, linewidth=1.5)
    ax.add_patch(context)
    ax.text(5, 1.55, 'GiveCareContext (23 fields: profile, burnout, messages, summaries)',
            ha='center', va='center', fontsize=7, style='italic')

    # OpenAI GPT-5 nano (right)
    llm = FancyBboxPatch((8, 2.5), 1.5, 1, boxstyle="round,pad=0.05",
                        edgecolor=COLORS['secondary'], facecolor='white', linewidth=1.5)
    ax.add_patch(llm)
    ax.text(8.75, 3, 'OpenAI\nGPT-5 nano', ha='center', va='center', fontsize=8)

    # Arrows - User to Convex
    arrow1 = FancyArrowPatch((1.4, 3), (3, 3), arrowstyle='->', mutation_scale=15,
                            linewidth=1.5, color=COLORS['neutral'])
    ax.add_patch(arrow1)
    ax.text(2.2, 3.3, 'SMS via\nTwilio', ha='center', fontsize=7)

    # Arrows - Agents to LLM
    for x in [4.1, 5.6, 7.1]:
        arrow = FancyArrowPatch((x, 3), (8, 3), arrowstyle='<->', mutation_scale=12,
                               linewidth=1, color=COLORS['secondary'], linestyle='dashed')
        ax.add_patch(arrow)

    # Handoff indicators
    ax.annotate('', xy=(5, 3.5), xytext=(4.1, 3.5),
               arrowprops=dict(arrowstyle='<->', lw=1.5, color=COLORS['accent']))
    ax.text(4.55, 3.7, 'Seamless handoffs', ha='center', fontsize=7, color=COLORS['accent'])

    ax.annotate('', xy=(6.5, 3.5), xytext=(5.6, 3.5),
               arrowprops=dict(arrowstyle='<->', lw=1.5, color=COLORS['accent']))

    # Add legend for handoff triggers
    ax.text(5, 0.5, 'Handoff triggers: Crisis keywords → Crisis Agent | startAssessment() → Assessment Agent',
            ha='center', fontsize=7, style='italic', color=COLORS['neutral'])

    plt.title('GiveCare Multi-Agent Architecture with Seamless Handoffs', fontsize=12, weight='bold', pad=10)
    plt.savefig(OUTPUT_DIR / 'fig6_multiagent_architecture.pdf')
    print("✓ Generated: fig6_multiagent_architecture.pdf")
    plt.close()


def generate_sdoh_domains():
    """Figure 2: GC-SDOH-28 domain breakdown"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: Question distribution
    domains = ['Financial\nStrain', 'Housing\nSecurity', 'Transportation', 'Social\nSupport',
               'Healthcare\nAccess', 'Food\nSecurity', 'Legal/\nAdmin', 'Technology\nAccess']
    questions = [5, 3, 3, 5, 4, 3, 3, 2]
    colors_list = [COLORS['warning'], COLORS['primary'], COLORS['accent'], COLORS['success'],
                   COLORS['secondary'], COLORS['warning'], COLORS['neutral'], COLORS['primary']]

    wedges, texts, autotexts = ax1.pie(questions, labels=domains, autopct='%d',
                                        colors=colors_list, startangle=90,
                                        textprops={'fontsize': 9})
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_weight('bold')

    ax1.set_title('GC-SDOH-28: Question Distribution\n(28 questions across 8 domains)',
                  fontsize=11, weight='bold')

    # Right: Need prevalence in beta cohort
    prevalence_domains = ['Financial\nStrain', 'Social\nIsolation', 'Legal/\nAdmin',
                         'Healthcare\nAccess', 'Transportation', 'Housing', 'Food\nSecurity',
                         'Technology\nAccess']
    prevalence = [82, 76, 67, 64, 51, 38, 29, 18]
    colors_prevalence = [COLORS['warning'], COLORS['secondary'], COLORS['neutral'],
                        COLORS['primary'], COLORS['accent'], COLORS['primary'],
                        COLORS['warning'], COLORS['neutral']]

    bars = ax2.barh(prevalence_domains, prevalence, color=colors_prevalence, alpha=0.8)
    ax2.set_xlabel('Prevalence (% of N=144 beta users)', fontsize=10)
    ax2.set_title('Need Prevalence in Beta Cohort\n(Dec 2024, N=144 caregivers)',
                  fontsize=11, weight='bold')
    ax2.set_xlim(0, 100)
    ax2.grid(axis='x', alpha=0.3, linestyle='--')
    ax2.axvline(x=47, color='red', linestyle='--', linewidth=1, alpha=0.5, label='General population (47%)')

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, prevalence)):
        ax2.text(val + 2, i, f'{val}%', va='center', fontsize=9, weight='bold')

    ax2.legend(fontsize=8, loc='lower right')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig7_gcsdoh_domains.pdf')
    print("✓ Generated: fig7_gcsdoh_domains.pdf")
    plt.close()


def generate_burnout_scoring():
    """Figure 3: Composite burnout scoring with temporal decay"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: Assessment weights
    assessments = ['EMA\n(Daily)', 'CWBS\n(Biweekly)', 'REACH-II\n(Monthly)', 'GC-SDOH-28\n(Quarterly)']
    weights = [40, 30, 20, 10]
    colors_weights = [COLORS['primary'], COLORS['secondary'], COLORS['accent'], COLORS['success']]

    bars = ax1.bar(assessments, weights, color=colors_weights, alpha=0.8, edgecolor='black', linewidth=1)
    ax1.set_ylabel('Weight (%)', fontsize=10)
    ax1.set_title('Composite Burnout Score Weights\n(Balances recency vs. comprehensiveness)',
                  fontsize=11, weight='bold')
    ax1.set_ylim(0, 50)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')

    # Add value labels
    for bar, weight in zip(bars, weights):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{weight}%', ha='center', va='bottom', fontsize=10, weight='bold')

    # Right: Temporal decay
    days = np.linspace(0, 30, 100)
    tau = 10  # 10-day half-life
    decay = np.exp(-days / tau)

    ax2.plot(days, decay * 100, color=COLORS['warning'], linewidth=2.5, label='Effective weight')
    ax2.fill_between(days, 0, decay * 100, alpha=0.2, color=COLORS['warning'])
    ax2.axhline(y=50, color=COLORS['neutral'], linestyle='--', linewidth=1, alpha=0.5)
    ax2.axhline(y=13.5, color=COLORS['neutral'], linestyle='--', linewidth=1, alpha=0.5)

    # Annotations
    ax2.annotate('τ = 10 days\n(half-life)', xy=(10, 50), xytext=(15, 60),
                arrowprops=dict(arrowstyle='->', lw=1.5, color=COLORS['neutral']),
                fontsize=9, color=COLORS['neutral'])
    ax2.annotate('20 days:\n13.5% weight', xy=(20, 13.5), xytext=(22, 25),
                arrowprops=dict(arrowstyle='->', lw=1.5, color=COLORS['neutral']),
                fontsize=9, color=COLORS['neutral'])

    ax2.set_xlabel('Days since assessment', fontsize=10)
    ax2.set_ylabel('Effective weight (%)', fontsize=10)
    ax2.set_title('Exponential Temporal Decay (τ = 10 days)\n(Recent data dominates, stale data ages out)',
                  fontsize=11, weight='bold')
    ax2.set_xlim(0, 30)
    ax2.set_ylim(0, 110)
    ax2.grid(alpha=0.3, linestyle='--')
    ax2.legend(fontsize=9)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig8_burnout_scoring.pdf')
    print("✓ Generated: fig8_burnout_scoring.pdf")
    plt.close()


def generate_beta_results():
    """Figure 4: Beta performance heatmap on LongitudinalBench dimensions"""
    fig, ax = plt.subplots(figsize=(10, 6))

    dimensions = [
        'Crisis Safety',
        'Regulatory Fitness',
        'Trauma-Informed Flow',
        'Belonging & Cultural Fitness',
        'Relational Quality',
        'Actionable Support',
        'Longitudinal Consistency',
        'Memory Hygiene'
    ]

    # Scores (normalized to 0-1 scale)
    scores = np.array([
        [0.972],  # Crisis Safety: 97.2%
        [1.000],  # Regulatory Fitness: 100%
        [0.840],  # Trauma-Informed Flow: 4.2/5 = 0.84
        [0.820],  # Belonging: 82% (SDOH-informed)
        [0.860],  # Relational Quality: 4.3/5 = 0.86
        [0.760],  # Actionable Support: 3.8/5 = 0.76
        [0.000],  # Longitudinal Consistency: N/A
        [1.000],  # Memory Hygiene: 100% (P2)
    ])

    # Create heatmap
    sns.heatmap(scores, annot=True, fmt='.2f', cmap='RdYlGn', vmin=0, vmax=1,
                yticklabels=dimensions, xticklabels=['GiveCare\n(GPT-4o-mini)'],
                cbar_kws={'label': 'Score (0-1 scale)'}, linewidths=1, linecolor='white',
                ax=ax, annot_kws={'fontsize': 11, 'weight': 'bold'})

    # Highlight N/A
    ax.add_patch(Rectangle((0, 6), 1, 1, fill=True, facecolor='lightgray',
                          edgecolor='black', linewidth=2))
    ax.text(0.5, 6.5, 'N/A\n(7-day\nbeta)', ha='center', va='center', fontsize=8, style='italic')

    ax.set_title('GiveCare Beta Performance on LongitudinalBench Dimensions\n' +
                 '(N=144 caregivers, Dec 2024, preliminary evaluation)',
                 fontsize=12, weight='bold', pad=15)
    ax.set_xlabel('')
    ax.set_ylabel('LongitudinalBench Dimension', fontsize=10)

    # Add note
    fig.text(0.5, 0.02, 'Strong performance: Crisis Safety (97.2%), Regulatory Fitness (100%), Memory Hygiene (100%)\n' +
             'Moderate performance: Actionable Support (76%) - local resource grounding in progress',
             ha='center', fontsize=8, style='italic', color=COLORS['neutral'])

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(OUTPUT_DIR / 'fig9_beta_results.pdf')
    print("✓ Generated: fig9_beta_results.pdf")
    plt.close()


def generate_dspy_optimization():
    """Figure 5: DSPy optimization results (P1-P6 breakdown)"""
    fig, ax = plt.subplots(figsize=(10, 6))

    principles = ['P1: Acknowledge\n>Answer\n>Advance', 'P2: Never\nRepeat',
                  'P3: Respect\nBoundaries', 'P4: Soft\nConfirmations',
                  'P5: Always\nOffer Skip', 'P6: Deliver\nValue']
    baseline = [0.76, 0.95, 0.89, 0.92, 0.65, 0.84]
    optimized = [0.86, 1.00, 0.94, 0.95, 0.79, 0.91]

    x = np.arange(len(principles))
    width = 0.35

    bars1 = ax.bar(x - width/2, baseline, width, label='Baseline (81.8%)',
                   color=COLORS['neutral'], alpha=0.7, edgecolor='black', linewidth=1)
    bars2 = ax.bar(x + width/2, optimized, width, label='Optimized (89.2%)',
                   color=COLORS['success'], alpha=0.8, edgecolor='black', linewidth=1)

    ax.set_ylabel('Score (0-1 scale)', fontsize=10)
    ax.set_title('DSPy DIY Meta-Prompting Optimization Results\n' +
                 '(50 examples, 5 iterations, +9.0% improvement, 11 minutes, $10-15 cost)',
                 fontsize=12, weight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(principles, fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.818, color=COLORS['neutral'], linestyle='--', linewidth=1, alpha=0.5, label='Baseline avg')
    ax.axhline(y=0.892, color=COLORS['success'], linestyle='--', linewidth=1, alpha=0.5, label='Optimized avg')
    ax.legend(fontsize=9, loc='lower right')
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    # Add improvement percentages
    for i, (b, o) in enumerate(zip(baseline, optimized)):
        improvement = ((o - b) / b) * 100
        ax.text(i, max(b, o) + 0.03, f'+{improvement:.0f}%', ha='center',
               fontsize=8, weight='bold', color=COLORS['success'])

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fig10_dspy_optimization.pdf')
    print("✓ Generated: fig10_dspy_optimization.pdf")
    plt.close()


def main():
    """Generate all figures for the paper"""
    print("Generating GiveCare paper figures...")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    generate_multiagent_architecture()
    generate_sdoh_domains()
    generate_burnout_scoring()
    generate_beta_results()
    generate_dspy_optimization()

    print()
    print("✓ All figures generated successfully!")
    print("Note: Figures are saved as PDF (vector graphics) for LaTeX compilation")


if __name__ == '__main__':
    main()
