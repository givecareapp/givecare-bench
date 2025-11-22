# Installation Guide

InvisibleBench uses `uv` for fast, reliable dependency management.

## Prerequisites

- Python 3.9 or higher
- `uv` package manager

## Install uv (if needed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# With pip (fallback)
pip install uv
```

## Installation Options

### Option 1: Basic Installation (Recommended)

```bash
# Clone repository
git clone https://github.com/givecareapp/givecare-bench.git
cd givecare-bench

# Install with uv
uv pip install -e .
```

This installs core dependencies:
- `pydantic` - Data validation
- `pyyaml` - YAML parsing
- `tqdm` - Progress bars
- `anthropic` - Anthropic API
- `openai` - OpenAI API
- `huggingface-hub` - HuggingFace integration
- `datasets` - Dataset loading

### Option 2: With Visualization

```bash
# Install with visualization tools (matplotlib, seaborn)
uv pip install -e ".[visualization]"
```

### Option 3: With Analytics

```bash
# Install with analytics tools (numpy, pandas)
uv pip install -e ".[analytics]"
```

### Option 4: Development Setup

```bash
# Install with dev tools (pytest, black, mypy, ruff)
uv pip install -e ".[dev]"
```

### Option 5: Full Installation

```bash
# Install everything (all optional dependencies)
uv pip install -e ".[all]"
```

## Environment Configuration

### API Keys

Create a `.env` file in the project root:

```bash
# Copy example
cp .env.example .env

# Edit with your keys
nano .env
```

Add your API keys:

```env
# Required for model evaluation
OPENROUTER_API_KEY=sk-or-v1-...

# Optional: Direct API access
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional: HuggingFace uploads
HF_TOKEN=hf_...
```

## Verify Installation

```bash
# Check package installed
uv pip show invisiblebench

# Run tests
uv run pytest tests/ -q

# Check CLI works
uv run invisiblebench --help

# Validate structure
uv run python huggingface/validate_structure.py
```

## Common Issues

### Issue: `uv` command not found

**Solution:**
```bash
# Ensure uv is in PATH
export PATH="$HOME/.cargo/bin:$PATH"

# Or install with pip
pip install uv
```

### Issue: Import errors after installation

**Solution:**
```bash
# Reinstall in editable mode
uv pip install -e . --force-reinstall
```

### Issue: API key not recognized

**Solution:**
```bash
# Verify .env file exists
ls -la .env

# Check environment variables loaded
python -c "import os; print(os.getenv('OPENROUTER_API_KEY'))"
```

### Issue: Missing optional dependencies

**Solution:**
```bash
# Install specific optional dependencies
uv pip install -e ".[visualization,analytics]"

# Or install all
uv pip install -e ".[all]"
```

## For HuggingFace Dataset Users

If you just want to load the dataset without installing the full package:

```bash
pip install datasets

# Load dataset
python -c "from datasets import load_dataset; ds = load_dataset('givecareapp/invisiblebench')"
```

## Uninstallation

```bash
uv pip uninstall invisiblebench
```

## Updating

```bash
# Pull latest changes
git pull origin main

# Reinstall
uv pip install -e . --force-reinstall
```

## Docker (Optional)

For isolated environment:

```dockerfile
FROM python:3.11-slim

# Install uv
RUN pip install uv

# Copy project
COPY . /app
WORKDIR /app

# Install
RUN uv pip install -e ".[all]"

# Run
CMD ["uv", "run", "invisiblebench", "--help"]
```

Build and run:
```bash
docker build -t invisiblebench .
docker run -v $(pwd)/results:/app/results invisiblebench
```

## Next Steps

- Read `README.md` for usage examples
- See `docs/VALIDATION_GUIDE.md` for running evaluations
- Check `docs/CLAUDE.md` for development guidance
