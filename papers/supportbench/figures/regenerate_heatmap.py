"""
Regenerate heatmap with GiveCare color palette
"""
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# GiveCare color palette
GIVECARE_COLORS = {
    'orange': '#FF9F1C',        # Orange - critical/low scores
    'light_orange': '#FFBF68',  # Light Orange - medium scores
    'tan': '#CB997E',           # Tan - good scores
    'light_peach': '#FFE8D6',   # Light Peach - excellent scores
    'dark_brown': '#54340E'     # Dark Brown - text/borders
}

# Set publication style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42
plt.rcParams['figure.dpi'] = 300
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 11
plt.rcParams['axes.grid'] = False  # Disable default grid

# Data from validation testing
models = [
    'Gemini 2.5 Flash',
    'Qwen 3 235B',
    'GPT-4o Mini',
    'Claude Sonnet 4.5',
    'DeepSeek Chat V3'
]

dimensions = ['Memory', 'Trauma', 'Belonging', 'Compliance', 'Safety']

# Scores (0-100 scale)
scores = np.array([
    [96, 87, 93, 100, 80],
    [96, 75, 95, 67, 80],
    [94, 60, 88, 100, 47],
    [96, 75, 94, 33, 97],
    [96, 78, 98, 33, 80]
])

# Create custom GiveCare colormap
# Map scores: 0-30 (orange), 30-60 (light_orange), 60-80 (tan), 80-100 (light_peach)
colors_list = [
    GIVECARE_COLORS['orange'],        # 0% - critical
    GIVECARE_COLORS['light_orange'],  # 50% - medium
    GIVECARE_COLORS['tan'],           # 75% - good
    GIVECARE_COLORS['light_peach']    # 100% - excellent
]
n_bins = 100
cmap = mcolors.LinearSegmentedColormap.from_list('givecare', colors_list, N=n_bins)

# Create figure
fig, ax = plt.subplots(figsize=(10, 6))

# Disable all default grids
ax.grid(False)

# Create heatmap
im = ax.imshow(scores, cmap=cmap, aspect='auto', vmin=0, vmax=100)

# Set ticks
ax.set_xticks(np.arange(len(dimensions)))
ax.set_yticks(np.arange(len(models)))
ax.set_xticklabels(dimensions, fontsize=12)
ax.set_yticklabels(models, fontsize=12)

# Labels
ax.set_xlabel('Evaluation Dimensions', fontsize=13, fontweight='bold')
ax.set_ylabel('Models', fontsize=13, fontweight='bold')
ax.set_title('SupportBench: Model Performance by Dimension\n(5 Models × 3 Scenarios)',
             fontsize=14, fontweight='bold', pad=20)

# Add text annotations
for i in range(len(models)):
    for j in range(len(dimensions)):
        text = ax.text(j, i, int(scores[i, j]),
                      ha="center", va="center",
                      color="white" if scores[i, j] < 50 else GIVECARE_COLORS['dark_brown'],
                      fontsize=11, fontweight='bold')

# Colorbar with GiveCare styling
cbar = plt.colorbar(im, ax=ax)
cbar.set_label('Score (%)', rotation=270, labelpad=20, fontsize=12, fontweight='bold')

# Grid - only draw borders between cells
ax.set_xticks(np.arange(len(dimensions))-0.5, minor=True)
ax.set_yticks(np.arange(len(models))-0.5, minor=True)
ax.grid(which="minor", color=GIVECARE_COLORS['dark_brown'], linestyle='-', linewidth=2)
ax.tick_params(which="minor", size=0)  # Hide minor tick marks
ax.spines['top'].set_color(GIVECARE_COLORS['dark_brown'])
ax.spines['bottom'].set_color(GIVECARE_COLORS['dark_brown'])
ax.spines['left'].set_color(GIVECARE_COLORS['dark_brown'])
ax.spines['right'].set_color(GIVECARE_COLORS['dark_brown'])
ax.spines['top'].set_linewidth(2)
ax.spines['bottom'].set_linewidth(2)
ax.spines['left'].set_linewidth(2)
ax.spines['right'].set_linewidth(2)

plt.tight_layout()

# Save
output_path = '/Users/amadad/Projects/give-care-else/givecare-bench/papers/supportbench/figures/heatmap.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
print(f"✓ Generated heatmap with GiveCare colors: {output_path}")

plt.close()
