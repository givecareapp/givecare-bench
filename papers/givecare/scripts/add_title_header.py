#!/usr/bin/env python3
"""
Add title header above Mermaid diagram PDFs to match the style of other figures.
Uses pdftoppm (from poppler-utils) to convert PDF to image.
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from PIL import Image
import numpy as np
from pathlib import Path
import subprocess
import tempfile
import os

# Color palette
COLOR_PALETTE = {
    'dark_brown': '#54340E',
}

# Set publication-quality defaults
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10

def add_header_to_pdf(input_pdf: Path, output_pdf: Path, title: str):
    """Add a header title above a PDF diagram."""

    # Convert PDF to PNG using pdftoppm
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        output_prefix = tmpdir_path / "page"

        # Run pdftoppm to convert first page to PNG at 300 DPI
        subprocess.run([
            'pdftoppm',
            '-png',
            '-f', '1',  # first page
            '-l', '1',  # last page
            '-r', '300',  # 300 DPI
            str(input_pdf),
            str(output_prefix)
        ], check=True, capture_output=True)

        # Load the generated PNG
        png_file = tmpdir_path / "page-1.png"
        img = Image.open(png_file)
        img_array = np.array(img)

    # Get image dimensions
    img_height, img_width = img_array.shape[:2]

    # Calculate figure size (in inches, 300 DPI)
    dpi = 300
    fig_width = img_width / dpi

    # Add extra height for title (0.5 inches)
    title_height = 0.5
    fig_height = (img_height / dpi) + title_height

    # Create figure
    fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, img_height / (img_height + title_height * dpi)])
    ax.axis('off')

    # Display the diagram
    ax.imshow(img_array)

    # Add title above the diagram
    title_y = 1.0 + (title_height * dpi / img_height) * 0.45
    fig.text(0.5, title_y, title,
             ha='center', va='center',
             fontsize=12, fontweight='bold',
             color=COLOR_PALETTE['dark_brown'],
             transform=ax.transAxes)

    # Save to PDF
    with PdfPages(output_pdf) as pdf:
        pdf.savefig(fig, bbox_inches='tight', dpi=dpi)
        plt.close()

def main():
    """Process both architecture diagrams."""
    figures_dir = Path(__file__).parent.parent / 'figures'

    # Process compact vertical layout
    print("  - Adding header to compact layout...")
    add_header_to_pdf(
        input_pdf=figures_dir / 'fig1_architecture_compact.pdf',
        output_pdf=figures_dir / 'fig1_architecture_compact_titled.pdf',
        title='GiveCare System Architecture: 7 Integrated Components'
    )
    print("    ✓ Created fig1_architecture_compact_titled.pdf")

    # Process horizontal layout
    print("  - Adding header to horizontal layout...")
    add_header_to_pdf(
        input_pdf=figures_dir / 'fig1_architecture_horizontal.pdf',
        output_pdf=figures_dir / 'fig1_architecture_horizontal_titled.pdf',
        title='GiveCare System Architecture: 7 Integrated Components'
    )
    print("    ✓ Created fig1_architecture_horizontal_titled.pdf")

if __name__ == '__main__':
    main()
