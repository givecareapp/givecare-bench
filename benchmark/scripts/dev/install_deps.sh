#!/bin/bash
# Install dependencies for validation scripts

set -e

echo "Installing validation script dependencies..."

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: No virtual environment detected."
    echo "Consider activating a virtual environment first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install core dependencies if needed
echo "Checking core dependencies..."
python3 -c "import yaml" 2>/dev/null || {
    echo "Installing core dependencies from requirements.txt..."
    pip install -r requirements.txt
}

# Install validation-specific dependencies
echo "Installing validation dependencies..."
pip install jsonlines tqdm pandas matplotlib seaborn

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "
import jsonlines
import tqdm
import pandas as pd
import matplotlib
import seaborn as sns
print('✓ All validation dependencies installed successfully')
" || {
    echo "ERROR: Installation verification failed"
    exit 1
}

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Set API keys:"
echo "   export OPENROUTER_API_KEY='your-key'"
echo "2. Run validation:"
echo "   python scripts/run_minimal_validation.py --dry-run"
