#!/usr/bin/env bash
set -euo pipefail

# Compatibility wrapper for quick probe-only runs.
# Preferred interface:
#   uv run python internal/autoresearch/run_campaign.py probe-run
#   uv run python internal/autoresearch/run_campaign.py probe-run --scenario "grief"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$REPO_ROOT"

ARGS=("probe-run")
SCENARIO=""
DRY_RUN=false

for arg in "$@"; do
  if [[ "$arg" == "--dry-run" ]]; then
    DRY_RUN=true
  elif [[ -z "$SCENARIO" ]]; then
    SCENARIO="$arg"
  fi
done

if [[ -n "$SCENARIO" ]]; then
  ARGS+=("--scenario" "$SCENARIO")
fi
if $DRY_RUN; then
  ARGS+=("--dry-run")
fi

exec uv run python internal/autoresearch/run_campaign.py "${ARGS[@]}"
