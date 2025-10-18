"""
Create system architecture diagram from mermaid specification
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.lines as mlines

# Set up the figure
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 10)
ax.set_ylim(0, 12)
ax.axis('off')

# Colors matching mermaid style
colors = {
    'user': '#e1f5ff',
    'agent': '#fff3cd',
    'score': '#d4edda',
    'match': '#f8d7da',
    'resources': '#d1ecf1'
}

# Node positions (x, y, width, height)
nodes = {
    'User': (1, 10, 1.5, 0.8, colors['user'], '👤 Caregiver'),
    'Entry': (1, 8.5, 1.5, 0.8, '#ffffff', '📱 Twilio'),
    'Agent': (4.5, 8.5, 1.8, 0.8, colors['agent'], '🤖 AI Agent'),
    
    'Assess': (2, 6.5, 2, 0.8, '#ffffff', '📋 Clinical\nAssessment'),
    'Crisis': (4.5, 6.5, 1.8, 0.8, '#ffcccc', '🚨 Crisis\nSupport'),
    'Main': (7, 6.5, 1.8, 0.8, '#ffffff', '💬 Main\nConversation'),
    
    'Score': (2, 4.5, 1.8, 0.8, colors['score'], '📊 Burnout\nScore'),
    'Band': (2, 3, 1.5, 0.8, colors['score'], '🎯 Risk Band'),
    'Zones': (4, 3, 1.5, 0.8, colors['score'], '⚡ Pressure\nZones'),
    
    'Match': (5.5, 1.5, 2, 0.8, colors['match'], '🔍 Resource\nMatching'),
    'Resources': (8, 1.5, 1.8, 0.8, colors['resources'], '📚 Resource\nDatabase'),
    
    'Response': (5.5, 10, 1.8, 0.8, '#ccffcc', '📤 SMS\nResponse'),
}

# Draw nodes
for name, (x, y, w, h, color, label) in nodes.items():
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.1",
        facecolor=color,
        edgecolor='#333333',
        linewidth=2
    )
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, label, 
            ha='center', va='center',
            fontsize=10, fontweight='bold',
            fontfamily='sans-serif')

# Arrows (from, to, label, style)
arrows = [
    ('User', 'Entry', 'SMS Message', (1.75, 9.8, 1.75, 9.3)),
    ('Entry', 'Agent', 'Webhook', (2.5, 8.9, 4.5, 8.9)),
    
    ('Agent', 'Assess', 'Needs\nAssessment?', (4.8, 8.5, 3, 7.3)),
    ('Agent', 'Crisis', 'Crisis\nDetected?', (5.4, 8.5, 5.4, 7.3)),
    ('Agent', 'Main', 'Normal Flow', (6.3, 8.5, 7.5, 7.3)),
    
    ('Assess', 'Score', 'Responses', (3, 6.5, 2.9, 5.3)),
    ('Score', 'Band', '0-100 Score', (2.9, 4.5, 2.75, 3.8)),
    ('Score', 'Zones', 'Top 2-3', (3.8, 4.5, 4.5, 3.8)),
    
    ('Band', 'Match', '', (3.5, 3.4, 5.5, 1.9)),
    ('Zones', 'Match', '', (5.5, 3.4, 6.0, 2.3)),
    
    ('Match', 'Resources', 'RBI\nAlgorithm', (7.5, 1.9, 8, 1.9)),
    ('Resources', 'Response', 'Top 3\nMatches', (8.5, 2.3, 6.8, 10)),
    
    ('Crisis', 'Response', 'Immediate\nHelp', (5.4, 7.3, 6, 10)),
    ('Main', 'Response', 'Conversation', (7.9, 7.3, 6.8, 10)),
]

# Draw arrows
for arrow_data in arrows:
    if len(arrow_data) == 4:
        from_node, to_node, label, (x1, y1, x2, y2) = arrow_data
        
        arrow = FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle='->', 
            mutation_scale=20,
            linewidth=2,
            color='#666666',
            connectionstyle="arc3,rad=0.1"
        )
        ax.add_patch(arrow)
        
        if label:
            # Add label at midpoint
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mid_x, mid_y, label,
                   ha='center', va='bottom',
                   fontsize=8, style='italic',
                   bbox=dict(boxstyle='round,pad=0.3', 
                           facecolor='white', 
                           edgecolor='none',
                           alpha=0.8))

# Add title
ax.text(5, 11.5, 'GiveCare System Architecture',
        ha='center', va='center',
        fontsize=16, fontweight='bold',
        fontfamily='sans-serif')

# Add subtitle
ax.text(5, 11.1, 'Multi-Agent Caregiving AI with SMS Integration',
        ha='center', va='center',
        fontsize=11, style='italic',
        fontfamily='sans-serif',
        color='#666666')

plt.tight_layout()
plt.savefig('output/fig1_system_architecture.pdf', 
            format='pdf', 
            bbox_inches='tight',
            dpi=300)
print("✓ Created: output/fig1_system_architecture.pdf")
plt.close()
