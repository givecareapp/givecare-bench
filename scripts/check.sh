#!/usr/bin/env bash
# Offline health check: lint, scenario/exemplar gates, tests. Also run by .githooks/pre-commit.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
uv run ruff check .
uv run python scripts/lint_turn_indices.py --strict
uv run python scripts/check_examples.py verify
uv run pytest benchmark/tests -q
