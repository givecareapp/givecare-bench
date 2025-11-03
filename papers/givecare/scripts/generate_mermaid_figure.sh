#!/bin/bash
# Generate PDF from Mermaid diagram

cd "$(dirname "$0")"

# Check if mmdc (mermaid-cli) is installed
if ! command -v mmdc &> /dev/null; then
    echo "Installing mermaid-cli..."
    npm install -g @mermaid-js/mermaid-cli
fi

# Generate PDF from Mermaid
echo "Generating figure from Mermaid..."
mmdc -i system_architecture.mmd -o ../figures/fig1_system_architecture_mermaid.pdf -b transparent

echo "✓ Created fig1_system_architecture_mermaid.pdf"
