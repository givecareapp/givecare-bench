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

---

## [1.3.0] - 2026-02-03

### Added
- **`--provider` flag**: Unified CLI for model eval (`openrouter`) and system eval (`givecare`)
- **`--diagnose` flag**: Generate actionable diagnostic reports after any eval run
- **`diagnose` subcommand**: Generate diagnostic reports from existing results
- **Diagnostic reports** include:
  - Failure priority (hard fails first, sorted by score)
  - Quoted responses from transcripts showing what triggered failures
  - Suggested fixes for each violation type
  - Pattern analysis (common issues across scenarios)
  - Comparison with previous run (regressions, improvements)
- **`--confidential` flag**: Include 3 confidential scenarios (32 total vs 29 standard)
- Expanded disclosure detection phrases in base.yaml
- Fixed .env loading in api/client.py for various entry points

### Changed
- System eval now uses `uv run bench --provider givecare -y` (was separate script)
- Updated all documentation to reflect unified CLI
- README.md: Added "Two Evaluation Modes" section with comparison table
- benchmark/README.md: Complete rewrite for current architecture
- benchmark/ARCHITECTURE.md: Added diagnostic reports section
- benchmark/scenarios/README.md: Updated scenario counts (29+3)
- benchmark/scripts/README.md: Updated for new CLI commands
- benchmark/scripts/validation/QUICKSTART.md: Complete rewrite

### Removed
- Obsolete `specs/` and `plans/` folders
- Stale AI review files from `reports/`

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
