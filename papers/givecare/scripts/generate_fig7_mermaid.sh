#!/bin/bash
# Generate fig11 pressure zones from Mermaid

cd "$(dirname "$0")"

echo "Generating fig11 pressure zone extraction..."

# Step 1: Generate base Mermaid PDF
echo "  - Generating base diagram..."
mmdc -i fig11_pressure_zones.mmd \
     -o ../figures/fig7_pressure_zones_base.pdf \
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
    input_pdf=figures_dir / 'fig7_pressure_zones_base.pdf',
    output_pdf=figures_dir / 'fig7_pressure_zones.pdf',
    title='Pressure Zone Extraction & Intervention Mapping Pipeline'
)
print('    ✓ Created fig7_pressure_zones.pdf')
PYTHON_SCRIPT

echo ""
echo "✓ Generated fig7_pressure_zones.pdf with title header"
