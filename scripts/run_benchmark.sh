#!/usr/bin/env bash
# Run full benchmark with default settings

set -e

echo "Running LongitudinalBench full benchmark..."
echo ""

python -m benchmarks.cli \
  --scenarios scenarios/ \
  --output data/results/runs/$(date +%Y%m%d_%H%M%S) \
  --export-html \
  --export-json

echo ""
echo "Benchmark complete! Results saved to data/results/runs/"
