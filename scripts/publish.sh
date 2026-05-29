#!/usr/bin/env bash
# One-command public leaderboard refresh: generate -> strict QA gate -> sync.
#
# Fail-closed by design: if the strict QA gate fails, the script aborts BEFORE
# the web-bench target is written, so a bad scan can never reach the public
# surface. This is the autoresearch "one command runs the loop" analogue for the
# benchmark publish path; the individual scripts remain callable for debugging.
#
# Usage:
#   ./scripts/publish.sh [SCAN_PER_RUN_JSONL] [WEB_TARGET]
#
# Defaults reproduce the documented Phase 2 refresh flow:
#   SCAN_PER_RUN_JSONL  results/v3_scan/merged_phase2/per_run.jsonl
#   WEB_TARGET          ../gc-web/apps/web-bench/public/bench/leaderboard.json
#
# The upstream scoring scan (which costs tokens) is intentionally NOT run here.
# Produce a scored scan first with, e.g.:
#   uv run python scripts/run_scan.py --profile publish --enable-llm results/run_<id>
set -euo pipefail
cd "$(dirname "$0")/.."

SCAN="${1:-results/v3_scan/merged_phase2/per_run.jsonl}"
WEB_TARGET="${2:-../gc-web/apps/web-bench/public/bench/leaderboard.json}"
LEADERBOARD="data/leaderboard/leaderboard.json"
MANUAL_ADJ="$(dirname "$SCAN")/manual_adjudications.json"

if [ ! -f "$SCAN" ]; then
  echo "error: scored scan not found: $SCAN" >&2
  echo "       run scripts/run_scan.py --profile publish --enable-llm <run_dir> first" >&2
  exit 2
fi

echo "[1/3] generate leaderboard  <- $SCAN"
uv run python scripts/generate_leaderboard.py --input "$SCAN" --output data/leaderboard

echo "[2/3] strict QA gate (fail-closed)"
qa_args=(--scan "$SCAN" --leaderboard "$LEADERBOARD" --strict)
if [ -f "$MANUAL_ADJ" ]; then
  qa_args+=(--manual-adjudications "$MANUAL_ADJ")
fi
uv run python scripts/qa_leaderboard.py "${qa_args[@]}"

echo "[3/3] sync web-bench payload -> $WEB_TARGET"
uv run python scripts/sync_web_bench_leaderboard.py --source "$LEADERBOARD" --target "$WEB_TARGET"

echo "publish OK: QA gate passed and web-bench payload synced"
