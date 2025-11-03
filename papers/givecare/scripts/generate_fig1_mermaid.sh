#!/bin/bash
# Generate fig1 system architecture from Mermaid

cd "$(dirname "$0")"

echo "Generating fig1 system architecture..."

# Step 1: Generate base Mermaid PDF
echo "  - Generating base diagram..."
mmdc -i system_architecture_horizontal.mmd \
     -o ../figures/fig1_system_architecture_base.pdf \
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
    input_pdf=figures_dir / 'fig1_system_architecture_base.pdf',
    output_pdf=figures_dir / 'fig1_system_architecture.pdf',
    title='GiveCare System Architecture'
)
print('    ✓ Created fig1_system_architecture.pdf')
PYTHON_SCRIPT

echo ""
echo "✓ Generated fig1_system_architecture.pdf with title header"
