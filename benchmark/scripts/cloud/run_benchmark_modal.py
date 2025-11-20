#!/usr/bin/env python3
"""
Modal deployment script for GiveCare benchmark.

Runs full core benchmark (5 models × 17 scenarios = 85 evaluations) on Modal cloud.
Estimated cost: $50-60, Expected time: 2-3 hours

Usage:
    # First time setup
    pip install modal
    modal setup  # Will prompt for login/API key

    # Set up secrets
    modal secret create openrouter-api-key OPENROUTER_API_KEY=<your-key>
    modal secret create anthropic-api-key ANTHROPIC_API_KEY=<your-key>

    # Run benchmark
    modal run benchmark/scripts/cloud/run_benchmark_modal.py

    # Or deploy as app
    modal deploy benchmark/scripts/cloud/run_benchmark_modal.py
"""

import modal
import os
from pathlib import Path

# Get the absolute path to the benchmark directory
BENCHMARK_DIR = Path(__file__).parent.parent.parent.resolve()

# Create Modal app
app = modal.App("givecare-benchmark")

# Create image with all dependencies and benchmark code
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Core API clients
        "anthropic>=0.23.0",
        "openai>=1.12.0",
        # Data handling
        "jsonlines>=4.0.0",
        "pyyaml>=6.0.0",
        "pydantic>=2.0.0",
        # Progress and utilities
        "tqdm>=4.66.0",
        "requests>=2.0.0",
        # Analytics and visualization
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
    )
    # Add benchmark code into the image
    .add_local_dir(
        str(BENCHMARK_DIR),
        remote_path="/root/benchmark"
    )
)

# Create a persistent volume for results
volume = modal.Volume.from_name("givecare-results", create_if_missing=True)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("openrouter-api-key"),
        modal.Secret.from_name("anthropic-api-key")
    ],
    volumes={"/results": volume},
    timeout=10800,  # 3 hours
    cpu=2,
    memory=4096,
)
def run_full_benchmark():
    """Run the full core benchmark (5 models × 17 scenarios)."""
    import sys
    sys.path.insert(0, "/root/benchmark")

    # Set environment variables for full benchmark mode
    os.environ["FULL_BENCHMARK"] = "true"
    os.environ["OUTPUT_DIR"] = "/results/full_benchmark"

    # Import and run the validation script
    from scripts.validation.run_minimal import main

    print("="*60)
    print("GIVECARE FULL BENCHMARK - MODAL CLOUD EXECUTION")
    print("="*60)
    print("Configuration:")
    print("  - 5 models (Claude 4.5, Gemini 2.5 Flash, GPT-4o Mini, DeepSeek V3, Qwen 3 235B)")
    print("  - 17 scenarios (Tier 1-3)")
    print("  - 85 total evaluations")
    print("  - Expected cost: $50-60")
    print("  - Expected time: 2-3 hours")
    print("="*60 + "\n")

    return main()


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("openrouter-api-key"),
        modal.Secret.from_name("anthropic-api-key")
    ],
    volumes={"/results": volume},
    timeout=3600,  # 1 hour
    cpu=2,
    memory=4096,
)
def run_minimal_benchmark():
    """Run minimal benchmark (1 model × 3 scenarios) for testing."""
    import sys
    sys.path.insert(0, "/root/benchmark")

    # Use default minimal configuration
    os.environ["OUTPUT_DIR"] = "/results/minimal_benchmark"

    from scripts.validation.run_minimal import main

    print("="*60)
    print("GIVECARE MINIMAL BENCHMARK - MODAL CLOUD EXECUTION")
    print("="*60)
    print("Configuration:")
    print("  - 1 model (Claude 4.5)")
    print("  - 3 scenarios (one from each tier)")
    print("  - 3 total evaluations")
    print("  - Expected cost: ~$5-10")
    print("  - Expected time: ~15 minutes")
    print("="*60 + "\n")

    return main()


@app.local_entrypoint()
def main(mode: str = "full"):
    """
    Main entrypoint for running benchmark on Modal.

    Args:
        mode: Either "full" (5 models × 17 scenarios) or "minimal" (1 model × 3 scenarios)
    """
    print("\n" + "="*60)
    print("DEPLOYING GIVECARE BENCHMARK TO MODAL")
    print("="*60)

    if mode == "full":
        print("Mode: FULL BENCHMARK")
        print("  - 5 models × 17 scenarios = 85 evaluations")
        print("  - Estimated cost: $50-60")
        print("  - Estimated time: 2-3 hours")
        print("="*60 + "\n")

        result = run_full_benchmark.remote()

    elif mode == "minimal":
        print("Mode: MINIMAL BENCHMARK (TEST)")
        print("  - 1 model × 3 scenarios = 3 evaluations")
        print("  - Estimated cost: $5-10")
        print("  - Estimated time: ~15 minutes")
        print("="*60 + "\n")

        result = run_minimal_benchmark.remote()

    else:
        print(f"ERROR: Unknown mode '{mode}'. Use 'full' or 'minimal'")
        return 1

    print("\n" + "="*60)
    print("BENCHMARK COMPLETE!")
    print("="*60)
    print("\nTo download results:")
    print("  modal volume get givecare-results /local/path/to/save")
    print("\nTo view files in volume:")
    print("  modal volume ls givecare-results")
    print("="*60 + "\n")

    return result


if __name__ == "__main__":
    # Can be run locally for testing imports
    print("Modal deployment script loaded successfully")
    print("Run with: modal run benchmark/scripts/cloud/run_benchmark_modal.py")
