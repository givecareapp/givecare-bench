#!/bin/bash
# Generate fig1 hero flow diagram from Mermaid

cd "$(dirname "$0")"

echo "Generating fig1 SupportBench hero flow diagram..."

# Step 1: Generate base Mermaid PDF
echo "  - Generating base diagram..."
mmdc -i fig1_hero_flow.mmd \
     -o ../figures/fig1_hero_flow_base.pdf \
     -b transparent \
     --pdfFit

# Step 2: Add title header using the givecare script
echo "  - Adding title header..."
python3 << 'PYTHON_SCRIPT'
import sys
from pathlib import Path

# Import add_title_header from givecare scripts
givecare_scripts = Path(__file__ if '__file__' in dir() else '.').resolve().parent.parent.parent / 'givecare' / 'scripts'
sys.path.insert(0, str(givecare_scripts))

from add_title_header import add_header_to_pdf

figures_dir = Path('../figures').resolve()
add_header_to_pdf(
    input_pdf=figures_dir / 'fig1_hero_flow_base.pdf',
    output_pdf=figures_dir / 'fig1_hero_flow_diagram.pdf',
    title='SupportBench End-to-End Evaluation Flow'
)
print('    ✓ Created fig1_hero_flow_diagram.pdf')
PYTHON_SCRIPT

echo ""
echo "✓ Generated fig1_hero_flow_diagram.pdf with title header"
