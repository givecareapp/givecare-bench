#!/usr/bin/env bash
set -euo pipefail

# Evaluate fine-tuned model on InvisibleBench.
#
# Starts a local MLX server, runs the benchmark against it, reports score.
#
# Usage:
#   ./autoresearch/train/eval.sh                    # Eval fused model
#   ./autoresearch/train/eval.sh --adapter-only      # Eval with adapter (no fuse)

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FUSED_MODEL="$REPO_ROOT/autoresearch/train/fused-model"
ADAPTER_DIR="$REPO_ROOT/autoresearch/train/adapters"
BASE_MODEL="mlx-community/Qwen3.5-4B-MLX-4bit"
PORT=8800
ADAPTER_ONLY=false

[[ "${1:-}" == "--adapter-only" ]] && ADAPTER_ONLY=true

cd "$REPO_ROOT"

# Determine model to serve
if $ADAPTER_ONLY; then
    echo "Serving base model with adapter..."
    MODEL_ARG="$BASE_MODEL"
    ADAPTER_ARG="--adapter-path $ADAPTER_DIR"
else
    if [[ ! -d "$FUSED_MODEL" ]]; then
        echo "No fused model found. Fusing first..."
        python -m mlx_lm.fuse \
            --model "$BASE_MODEL" \
            --adapter-path "$ADAPTER_DIR" \
            --save-path "$FUSED_MODEL"
    fi
    MODEL_ARG="$FUSED_MODEL"
    ADAPTER_ARG=""
fi

# Start MLX server in background
echo "Starting MLX server on port $PORT..."
python -m mlx_lm.server \
    --model "$MODEL_ARG" \
    $ADAPTER_ARG \
    --port "$PORT" &
SERVER_PID=$!

# Wait for server to be ready
echo "Waiting for server..."
for i in $(seq 1 30); do
    if curl -s "http://localhost:$PORT/v1/models" > /dev/null 2>&1; then
        echo "Server ready."
        break
    fi
    sleep 1
done

# Run benchmark against local server
# The MLX server exposes an OpenAI-compatible API
echo ""
echo "Running InvisibleBench evaluation..."
INVISIBLEBENCH_API_BACKEND=openai \
OPENAI_API_KEY="not-needed" \
OPENAI_BASE_URL="http://localhost:$PORT/v1" \
INVISIBLEBENCH_SCORER_MODEL="gpt-4.1-mini" \
uv run bench \
    --provider openrouter \
    -m "local/qwen3.5-4b-caregiving" \
    -y \
    --detailed 2>&1 | tee "$REPO_ROOT/autoresearch/train/eval_output.txt"

# Cleanup
echo ""
echo "Stopping server..."
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

echo "Evaluation complete. Results in autoresearch/train/eval_output.txt"
