#!/usr/bin/env bash
# One-command public leaderboard refresh: generate -> strict QA gate -> sync.
#
# Thin shim over the PUBLISH verb (src/invisiblebench/publish.py), which owns
# the fail-closed sequencing: if the strict QA gate fails, the chain aborts
# BEFORE the web-bench target is written. Individual stage scripts remain
# callable for debugging.
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
exec uv run python -m invisiblebench.publish "$@"
