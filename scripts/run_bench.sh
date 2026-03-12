#!/usr/bin/env bash
# run_bench.sh — Run full benchmark across 3 tmux panes (5 models each)
#
# Usage: ./scripts/run_bench.sh          # 3 panes, 5 models each
#        ./scripts/run_bench.sh --dry-run # Preview only
set -euo pipefail

SESSION="bench"
EXTRA_ARGS="${*}"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
BATCH_TS="$(date +%Y%m%d_%H%M%S)"
BATCH_DIR="$DIR/results/run_${BATCH_TS}"

mkdir -p "$BATCH_DIR"
echo "Batch output: $BATCH_DIR"

# Kill existing session if any
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Create session with first pane: Frontier (models 1-5)
tmux new-session -d -s "$SESSION" -c "$DIR" \
  "uv run bench -m 1-5 -y --output '$BATCH_DIR/frontier' $EXTRA_ARGS; echo '=== FRONTIER DONE ==='; read"

# Split right: Mid-range + cheap pt1 (models 6-10)
tmux split-window -h -t "$SESSION" -c "$DIR" \
  "uv run bench -m 6-10 -y --output '$BATCH_DIR/mid' $EXTRA_ARGS; echo '=== MID-RANGE DONE ==='; read"

# Split right again: Cheap pt2 (models 11-15)
tmux split-window -h -t "$SESSION" -c "$DIR" \
  "uv run bench -m 11-15 -y --output '$BATCH_DIR/cheap' $EXTRA_ARGS; echo '=== CHEAP DONE ==='; read"

# Even out the panes
tmux select-layout -t "$SESSION" even-horizontal

# Attach
tmux attach -t "$SESSION"
