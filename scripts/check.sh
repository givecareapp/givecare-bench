#!/usr/bin/env bash
# Retain the historical gate while the replacement benchmark is designed.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../_archive/5.8.0"
exec uv run --locked --extra dev bash ./scripts/check.sh
