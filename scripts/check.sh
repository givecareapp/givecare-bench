#!/usr/bin/env bash
# Check the active development slice, then the unchanged historical project.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
uv run --locked ruff check task.py grader.py report.py review_packet.py tests
uv run --locked pytest tests -q
cd _archive/5.8.0
exec uv run --locked --extra dev bash ./scripts/check.sh
