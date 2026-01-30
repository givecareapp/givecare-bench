# Changelog

All notable changes to the InvisibleBench codebase are tracked here.

This file tracks **code version** changes (`pyproject.toml`).
Leaderboard data changes are tracked in `benchmark/website/data/leaderboard.json` → `metadata.changelog`.

## Versioning Scheme

**Code version** (semver in `pyproject.toml`):
- **Major**: Scoring methodology change that invalidates prior results (new dimension, weight change, autofail rule change)
- **Minor**: New feature (CLI flag, model support, export format)
- **Patch**: Bug fix, docs, refactor

**Leaderboard version** (`leaderboard.json` metadata):
- **Major**: Scoring methodology changed — results re-evaluated under new rules
- **Minor**: New model added or model re-run
- **Patch**: Metadata correction, no score changes

The leaderboard metadata includes a `code_version` field recording which code version produced the results.

---

## [Unreleased]

### Removed
- Obsolete `specs/` and `plans/` folders
- Stale AI review files from `reports/`

### Changed
- Reorganized reports structure: daily changelog now in `reports/YYYY-MM-DD/changelog.md`

---

## [1.2.0] - 2026-01-27

### Fixed
- Sequential runner now records failed scenarios with `status: "error"` instead of silently dropping them from `all_results.json`
- Same fix applied to rich display path (transcript and scoring errors)

### Added
- `--update-leaderboard` CLI flag: auto-runs `prepare_for_leaderboard.py` and `generate_leaderboard.py` after benchmark completes
- `code_version` field in `leaderboard.json` metadata for traceability
- `generate_leaderboard.py` reads version from `pyproject.toml` automatically
- Versioning governance: documented semver scheme for code and leaderboard versions

### Changed
- CLAUDE.md: documented actual leaderboard update flow (was missing the `prepare_for_leaderboard.py` step)
- README.md: updated model count to 11, added Kimi K2.5 to model table
- AGENTS.md: updated model count and list to include Kimi K2.5

## [1.1.0] - 2026-01-27

### Added
- Kimi K2.5 as model 11 (`moonshotai/kimi-k2.5`)
- `InsufficientCreditsError` — 402 responses from OpenRouter abort immediately instead of failing every scenario
- `--models/-m` flag for flexible model selection (ranges, lists, open-ended)
- Parallel model execution with `-p` flag and rich progress display
- Rich CLI runner with live progress, tier grouping, and failure reports
- Gray zone scenarios, regulatory rules (9 jurisdictions), failure categorization
- Tier 0 Crisis Override framework
- Per-scenario JSON/HTML reports with `--detailed` flag
- Belonging scorer fallback for missing cultural context

### Fixed
- Belonging scorer crash on missing fields

## [1.0.0] - 2026-01-26

### Added
- Initial benchmark framework with 5 evaluation dimensions
- Tier 1-3 scenarios (crisis detection, boundary durability, longitudinal memory)
- YAML-based scoring rules with jurisdiction support
- CLI entry point (`uv run bench`)
- HTML report generation
- pytest test suite
