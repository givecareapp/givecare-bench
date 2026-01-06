#!/usr/bin/env bash
# Run full benchmark with default settings

set -e

echo "Running InvisibleBench full benchmark..."
echo ""

python -m invisiblebench.cli \
  --scenarios benchmark/scenarios \
  --output results/runs/$(date +%Y%m%d_%H%M%S) \
  --export-html

echo ""
echo "Benchmark complete! Results saved to results/runs/"
