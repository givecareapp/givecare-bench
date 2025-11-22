"""
Global style configuration for InvisibleBench paper figures
Ensures consistency across all diagrams, charts, and tables
"""

import matplotlib.pyplot as plt

# Base matplotlib configuration
def configure_matplotlib():
    """Apply base matplotlib settings for all figures"""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams['pdf.fonttype'] = 42
    plt.rcParams['ps.fonttype'] = 42
    plt.rcParams['figure.dpi'] = 300
    plt.rcParams['font.family'] = 'serif'
    plt.rcParams['font.serif'] = ['Times', 'Times New Roman', 'DejaVu Serif']
    plt.rcParams['font.size'] = 9

# EXACT colors from rendered hero figure PDF (warm autumn/earth tones)
HERO_COLORS = {
    # Box backgrounds (warm beige/tan/rose from rendered hero)
    'user_bg': '#FAEBD7',      # Warm beige/tan (AntiqueWhite)
    'agent_bg': '#F5E6D3',     # Warm cream/tan
    'guardrail_bg': '#D4A5A5', # Dusty rose/mauve
    'judge_bg': '#D4A5A5',     # Dusty rose/mauve
    'routing_bg': '#FFB347',   # Warm amber/orange
    'outcome_bg': '#FAEBD7',   # Warm beige

    # Box borders (darker earth tones from rendered hero)
    'user_border': '#8B7355',    # Warm brown
    'agent_border': '#CD853F',   # Peru/tan
    'guardrail_border': '#A0522D', # Sienna/brown
    'judge_border': '#A0522D',   # Sienna/brown
    'routing_border': '#FF8C00',  # Dark orange
    'fail_border': '#D2691E',    # Chocolate brown/orange
    'pass_border': '#CD853F',    # Peru/tan
    'review_border': '#CD5C5C',  # Indian red
    'tier_border': '#FF8C00',    # Dark orange

    # Outcome box backgrounds (warm tones)
    'pass_bg': '#F5E6D3',      # Light warm beige
    'fail_bg': '#FF8C00',      # Bright orange
    'review_bg': '#D4A5A5',    # Dusty rose
    'tier_bg': '#FFB347',      # Warm amber/orange

    # Other elements
    'arrow': '#424242',        # Dark gray for arrows
    'neutral_border': '#8B7355', # Warm gray/brown
    'neutral_bg': '#FAF8F3',   # Warm off-white background
}

# Standard box styling from hero
BOX_STYLE = {
    'boxstyle': 'round,pad=0.1',
    'linewidth': 2,
}

# Standard arrow styling from hero
ARROW_STYLE = {
    'arrowstyle': '->',
    'lw': 2,
    'color': HERO_COLORS['arrow'],
}

# Standard font sizes from hero
FONT_SIZES = {
    'title': 12,
    'box_title': 10,
    'box_detail': 7,
    'label': 8,
    'annotation': 7,
}
