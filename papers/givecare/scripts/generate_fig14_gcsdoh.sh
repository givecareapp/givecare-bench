#!/bin/bash
# Generate fig14 GC-SDOH-28 instrument from TikZ

cd "$(dirname "$0")"

echo "Generating fig14 GC-SDOH-28 instrument..."

# Compile TikZ/LaTeX to PDF
echo "  - Compiling TikZ diagram..."
pdflatex -interaction=nonstopmode fig14_gcsdoh_instrument.tex > /dev/null 2>&1

# Move to figures directory
echo "  - Moving to figures directory..."
mv fig14_gcsdoh_instrument.pdf ../figures/

# Cleanup auxiliary files
rm -f fig14_gcsdoh_instrument.aux fig14_gcsdoh_instrument.log

echo ""
echo "✓ Generated fig14_gcsdoh_instrument.pdf"
