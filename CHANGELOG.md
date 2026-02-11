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

### Added
- **MECE category rename**: Scenarios reorganized from `tier1/tier2/tier3/` into capability categories (`safety/`, `empathy/`, `context/`, `continuity/`)
  - CLI flag `--tier/-t` replaced by `--category/-c`
  - `CategoryLevel` enum replaces `TierLevel` (backward-compat alias retained)
  - All loaders, exporters, and result models updated
- **3 new regulatory scenarios** (context category):
  - `misrepresentation_correction.json` — NV AB 406 (correcting "AI counselor" framing)
  - `therapeutic_function_boundary.json` — IL WOPR Act (declining CBT, diagnosis, treatment plans)
  - `data_privacy_inquiry.json` — UT HB 452 / WA MHMD (data handling, deletion requests)
- **3 new relational scenarios** (empathy category):
  - `pushback_loop.json`, `impossible_constraint.json`, `no_right_answer.json`
- **Conditional branching**: Adaptive multi-turn conversations where user messages depend on model behavior
  - 4 scenarios annotated with branch points (medical boundary, venting calibration, attachment formation, longitudinal memory)
  - 4 deterministic condition types: `contains_any`, `contains_all`, `not_contains`, `regex`
  - Branch resolution in both model eval and system eval (GiveCare provider)
  - Branch IDs recorded in transcript JSONL for audit
  - New module: `evaluation/branching.py` with 20 unit tests
- **Scorer LRU cache**: Thread-safe LRU cache for temperature=0 scorer LLM calls (~40% API cost reduction)
  - SHA256 hash of normalized payload as cache key
  - Returns deepcopy to prevent mutation of cached results
  - Configurable via `INVISIBLEBENCH_SCORER_CACHE_SIZE` env var (default: 256, set to 0 to disable)

### Changed
- **35 standard scenarios** (was 29): safety (12), empathy (10), context (9), continuity (4)
- **38 with confidential** (was 32)
- **Prior results invalidated**: Category rename + new scenarios require rerun

### Fixed
- 11 scoring bugs across attunement, belonging, compliance, false_refusal, and safety scorers
- California rules (`ca.yaml`): Added missing `mental_health_specifics` section
- California and New York rules: Added missing `notes` sections
- Base rules (`base.yaml`): Reordered disclosure phrases for consistency
- All 172 tests now passing

---

## [2.0.0] - 2026-02-03

### Changed - MAJOR BENCHMARK EVOLUTION

This release significantly rebalances the benchmark from crisis-heavy to gray zone and boundary focused. See [EVOLUTION.md](./benchmark/EVOLUTION.md) for full rationale.

**Scores from v2.0 are NOT directly comparable to v1.x** - the scenario mix and focus have fundamentally changed.

### Added
- **Gray zone scenarios** (4 new):
  - `exhaustion_venting_vs_depression.json` - tiredness ≠ depression
  - `care_recipient_frustration.json` - frustration ≠ abuse indicator
  - `compassion_fatigue_expression.json` - numbness as fatigue, not depression
  - Updated `dark_humor_coping.json` - gallows humor as valid coping
- **Boundary scenarios** (3 new):
  - `ai_dependency_formation.json` - preferring AI to human connection
  - `medical_advice_boundary.json` - information vs prescription limits
  - `therapist_replacement.json` - complement vs replacement positioning
- **Crisis evolution scenarios** (2 new):
  - `crisis_recovery_test.json` - tests course-correction after initial miss (extends CARE)
  - `dual_concern_crisis.json` - caregiver self-preservation vs care duties (unique)
- **Scoring modules**:
  - `authenticity.py` - formulaic response detection
  - `consistency.py` - intra-conversation contradiction detection
  - Turn-by-turn degradation tracking
- **Documentation**:
  - `EVOLUTION.md` - comprehensive evolution documentation
  - Updated README with v2.0 focus

### Changed
- **Tier 1 rebalanced**:
  - Gray zone: 4 → 8 scenarios
  - Boundaries: 2 → 5 scenarios
  - Crisis: 14 → 5 scenarios (9 archived)
- Crisis scenarios archived to `benchmark/scenarios/archive/crisis/` (still available via `--include-archive`)
- Updated all documentation to reflect new benchmark shape

### Rationale
Crisis detection is important but not our differentiator. Specialized benchmarks (CARE, C-SSRS tools) own comprehensive crisis testing. InvisibleBench's unique value is testing gray zone calibration and boundary navigation specific to caregiving AI.

Research basis:
- [Mapping Caregiver Needs to AI Chatbot Design](https://arxiv.org/html/2506.15047)
- CARE Framework (86% model failure on indirect crisis queries)
- MT-Eval (score degradation over conversation length)

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
