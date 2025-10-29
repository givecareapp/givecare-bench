#!/usr/bin/env bash
# Setup development environment

set -e

echo "Setting up LongitudinalBench development environment..."
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
if [ -z "$OPENROUTER_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: No API keys found in environment"
    echo "Set at least one of: OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY"
else
    echo "✓ API keys configured"
fi

echo ""
echo "Setup complete! Run tests with:"
echo "  pytest tests/ -v"
echo ""
echo "Run benchmark with:"
echo "  python -m benchmarks.cli --help"
