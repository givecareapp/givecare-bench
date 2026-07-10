#!/usr/bin/env bash
# One-command public leaderboard refresh: generate -> strict QA gate -> sync.
#
# Thin shim over the PUBLISH verb (src/invisiblebench/publish.py), which owns
# the fail-closed sequencing: if the strict QA gate fails, the chain aborts
# BEFORE the web-bench target is written. Individual stage scripts remain
# callable for debugging.
#
# Usage:
#   ./scripts/publish.sh SCAN_PER_RUN_JSONL WEB_TARGET
#
# Both arguments are required so publication cannot silently fall back to a
# historical Phase 2 scan or an unintended web target.
#
# The upstream scoring scan (which costs tokens) is intentionally NOT run here.
# Produce a scored scan first with, e.g.:
#   uv run python scripts/run_scan.py --profile publish --enable-llm \
#     --max-cost-usd 31 results/run_<id>
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python -m invisiblebench.publish "$@"
