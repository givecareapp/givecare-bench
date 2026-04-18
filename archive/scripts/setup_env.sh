#!/usr/bin/env bash
# Setup development environment

set -e

echo "Setting up InvisibleBench development environment..."
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -e ".[all]"

# Check for API keys
echo ""
echo "Checking API keys..."
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "⚠️  WARNING: OPENROUTER_API_KEY not set"
    echo "Set: OPENROUTER_API_KEY"
else
    echo "✓ API keys configured"
fi

echo ""
echo "Setup complete! Run tests with:"
echo "  pytest benchmark/tests/ -v"
echo ""
echo "Run scoring CLI with:"
echo "  python -m benchmark.invisiblebench.yaml_cli --help"
