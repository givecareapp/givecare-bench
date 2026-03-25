#!/usr/bin/env bash
set -euo pipefail

# Run the 3 probe models on a single scenario and measure differentiation.
#
# Usage:
#   ./internal/autoresearch/run_scenario.sh "Impossible Constraint"
#   ./internal/autoresearch/run_scenario.sh "Grief After Loss" --dry-run

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$REPO_ROOT/internal/autoresearch/results"
SCENARIO_FILTER="${1:?Usage: run_scenario.sh <scenario-name-or-id>}"
DRY_RUN=false

[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=true

# 3 fixed probe models: strong, weak, middle
PROBE_MODELS="opus-4.5,gemini-3-pro,gpt-5-mini"

mkdir -p "$RESULTS_DIR"

# Find next experiment number
LAST=$(ls "$RESULTS_DIR"/experiment_*.json 2>/dev/null | \
       sed 's/.*experiment_\([0-9]*\)\.json/\1/' | sort -n | tail -1 || echo "0")
NEXT=$(( ${LAST:-0} + 1 ))
OUTPUT_FILE="$RESULTS_DIR/experiment_${NEXT}.json"

echo "=== AutoResearch: experiment_${NEXT} ==="
echo "  Scenario: $SCENARIO_FILTER"
echo "  Models:   $PROBE_MODELS"
echo "  Output:   $OUTPUT_FILE"
echo ""

if $DRY_RUN; then
    echo "(dry run — would run: uv run bench -m $PROBE_MODELS -s \"$SCENARIO_FILTER\" -y)"
    exit 0
fi

cd "$REPO_ROOT"

# Run benchmark on single scenario with 3 probe models
# --update-leaderboard is NOT set — this is experimental
RUN_DIR=$(uv run bench -m "$PROBE_MODELS" -s "$SCENARIO_FILTER" -y --detailed 2>&1 | \
          grep -o 'results/run_[^ ]*' | head -1 || true)

if [[ -z "$RUN_DIR" ]]; then
    echo "ERROR: Benchmark run failed or no output directory found"
    exit 1
fi

echo ""
echo "Run directory: $RUN_DIR"

# Extract scores and compute spread for the scenario-only autoresearch campaign
uv run python internal/autoresearch/_compute_spread.py \
    --run-dir "$RUN_DIR" \
    --scenario "$SCENARIO_FILTER" \
    --output "$OUTPUT_FILE" \
    --label "experiment_${NEXT}"

echo ""
echo "=== experiment_${NEXT} complete ==="
