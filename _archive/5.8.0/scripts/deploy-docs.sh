#!/usr/bin/env bash
# Deploy docs to GitHub Pages (givecareapp.github.io/givecare-bench) WITHOUT GitHub Actions.
# Builds with the `docs` extra (mkdocs-material) and force-pushes to the gh-pages branch.
set -e
cd "$(dirname "$0")/.."
uv run --extra docs mkdocs gh-deploy --force --message "docs: local deploy (no Actions)"
