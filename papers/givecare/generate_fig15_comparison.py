#!/usr/bin/env python3
"""
Generate Figure 15: AI Caregiving Systems Comparison Table
Compares GiveCare against existing AI systems across 8 key features
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# Set up the figure
fig, ax = plt.subplots(figsize=(14, 10))
ax.axis('off')

# Define systems and features
systems = [
    'GiveCare\n(This Work)',
    'Replika',
    'Pi',
    'Wysa',
    'Woebot',
    'Epic Cosmos',
    'Med-PaLM 2'
]

features = [
    'Caregiver-Specific\nSDOH Screening',
    'Multi-Agent\nArchitecture',
    'Trauma-Informed\nOptimization',
    'Regulatory\nCompliance Guards',
    'Clinical\nAssessment',
    'Burnout Tracking\n(Temporal Decay)',
    'Longitudinal\nTrajectory',
    'Grounded Local\nResources'
]

# Data: 1 = Full support (green), 0.5 = Partial (yellow), 0 = None (red)
# Rows: systems, Columns: features
data = np.array([
    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],  # GiveCare
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Replika
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Pi
    [0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 0.0, 0.0],  # Wysa (CBT techniques)
    [0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 0.0, 0.0],  # Woebot (CBT techniques)
    [0.0, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0],  # Epic Cosmos (clinician-focused)
    [0.0, 0.0, 0.0, 0.5, 0.5, 0.0, 0.0, 0.0],  # Med-PaLM 2 (clinician-focused)
])

# Define colors
color_full = '#2ecc71'      # Green
color_partial = '#f39c12'   # Orange
color_none = '#e74c3c'      # Red
color_givecare = '#3498db'  # Blue for GiveCare row

# Create table
cell_height = 0.9
cell_width = 1.2
start_x = 3.0
start_y = 8.0

# Draw title
ax.text(start_x + len(features) * cell_width / 2, start_y + 1.5,
        'AI Caregiving Systems Comparison',
        fontsize=20, fontweight='bold', ha='center', va='center')

# Draw column headers (features)
for j, feature in enumerate(features):
    x = start_x + j * cell_width
    y = start_y

    # Draw cell
    rect = FancyBboxPatch((x, y), cell_width - 0.05, cell_height - 0.05,
                          boxstyle="round,pad=0.05",
                          facecolor='#ecf0f1', edgecolor='#34495e', linewidth=1.5)
    ax.add_patch(rect)

    # Add text
    ax.text(x + cell_width/2, y + cell_height/2, feature,
            fontsize=9, ha='center', va='center', fontweight='bold',
            wrap=True)

# Draw row headers (systems) and data cells
for i, system in enumerate(systems):
    y = start_y - (i + 1) * cell_height

    # Row header (system name)
    x_label = start_x - 1.8

    # Highlight GiveCare row
    if i == 0:
        label_color = color_givecare
        label_text_color = 'white'
        label_weight = 'bold'
    else:
        label_color = '#ecf0f1'
        label_text_color = 'black'
        label_weight = 'normal'

    rect = FancyBboxPatch((x_label, y), 1.7, cell_height - 0.05,
                          boxstyle="round,pad=0.05",
                          facecolor=label_color, edgecolor='#34495e', linewidth=1.5)
    ax.add_patch(rect)

    ax.text(x_label + 0.85, y + cell_height/2, system,
            fontsize=10, ha='center', va='center',
            fontweight=label_weight, color=label_text_color)

    # Data cells
    for j in range(len(features)):
        x = start_x + j * cell_width

        # Determine color based on value
        value = data[i, j]
        if value == 1.0:
            cell_color = color_full
            symbol = '✓'
            symbol_size = 24
        elif value == 0.5:
            cell_color = color_partial
            symbol = '◐'
            symbol_size = 20
        else:
            cell_color = color_none
            symbol = '✗'
            symbol_size = 20

        # Draw cell
        rect = FancyBboxPatch((x, y), cell_width - 0.05, cell_height - 0.05,
                              boxstyle="round,pad=0.05",
                              facecolor=cell_color, edgecolor='#34495e',
                              linewidth=1, alpha=0.8)
        ax.add_patch(rect)

        # Add symbol
        ax.text(x + cell_width/2, y + cell_height/2, symbol,
                fontsize=symbol_size, ha='center', va='center',
                fontweight='bold', color='white')

# Add legend
legend_y = start_y - len(systems) * cell_height - 1.2
legend_x = start_x

# Legend patches
full_patch = mpatches.Patch(color=color_full, label='Full Support')
partial_patch = mpatches.Patch(color=color_partial, label='Partial Support')
none_patch = mpatches.Patch(color=color_none, label='Not Supported')

ax.legend(handles=[full_patch, partial_patch, none_patch],
          loc='lower left', bbox_to_anchor=(0.15, -0.05),
          fontsize=11, frameon=True, fancybox=True, shadow=True)

# Add notes
notes_text = (
    "Note: GiveCare features marked as 'Full Support' represent reference architecture design (validation pending).\n"
    "GC-SDOH-28 requires psychometric validation (N=200+, Q1-Q2 2025). Multi-agent attachment prevention\n"
    "hypothesis requires RCT validation. Comparison based on publicly documented features as of Dec 2024."
)
ax.text(start_x + len(features) * cell_width / 2, legend_y - 0.5,
        notes_text, fontsize=8, ha='center', va='top',
        style='italic', color='#7f8c8d')

# Set axis limits
ax.set_xlim(0, start_x + len(features) * cell_width + 1)
ax.set_ylim(legend_y - 1.5, start_y + 2)

plt.tight_layout()

# Save figure
output_path = 'papers/paper3-givecare-system/figures/fig15_comparison_table.pdf'
plt.savefig(output_path, format='pdf', dpi=300, bbox_inches='tight')
print(f"✓ Generated: {output_path}")

# Also save as PNG for preview
output_png = output_path.replace('.pdf', '.png')
plt.savefig(output_png, format='png', dpi=300, bbox_inches='tight')
print(f"✓ Generated preview: {output_png}")

plt.close()
