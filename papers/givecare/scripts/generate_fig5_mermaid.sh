#!/bin/bash
# Generate fig6 multi-agent architecture from Mermaid

cd "$(dirname "$0")"

echo "Generating fig6 multi-agent architecture..."

# Step 1: Generate base Mermaid PDF
echo "  - Generating base diagram..."
mmdc -i fig6_multiagent.mmd \
     -o ../figures/fig5_multiagent_base.pdf \
     -b transparent \
     --pdfFit

# Step 2: Add title header
echo "  - Adding title header..."
python3 << 'PYTHON_SCRIPT'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__ if '__file__' in dir() else '.').resolve().parent))

from add_title_header import add_header_to_pdf

figures_dir = Path('../figures').resolve()
add_header_to_pdf(
    input_pdf=figures_dir / 'fig5_multiagent_base.pdf',
    output_pdf=figures_dir / 'fig5_multiagent_architecture.pdf',
    title='GiveCare Multi-Agent Architecture'
)
print('    ✓ Created fig5_multiagent_architecture.pdf')
PYTHON_SCRIPT

echo ""
echo "✓ Generated fig5_multiagent_architecture.pdf with title header"
