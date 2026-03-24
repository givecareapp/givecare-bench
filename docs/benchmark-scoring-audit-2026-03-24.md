# Benchmark Scoring Audit (2026-03-24)

## Scope

This audit reviews alignment between:

1. The public scoring rubric and methodology docs.
2. The benchmark/scenario structure used by the runner.
3. The executable scoring logic in orchestrator/scorers.

## Executive Assessment

**Overall maturity:** strong architectural direction (fail-closed gate + quality) with meaningful drift in implementation details and operational docs.

**Primary risk theme:** the benchmark is now conceptually v2, but several interfaces still expose v1/tier-era or transitional behavior. This creates governance and reproducibility risk: users can run or interpret evaluations in ways that are technically valid but semantically inconsistent with the intended rubric.

## High-Priority Findings

### 1) Canonical docs/CLI drift on model catalog and harness modes

**What we observed**
- CLI help and examples still claim “All 12 models,” but model catalog currently defines **15** models.
- CLI help advertises GiveCare `integration` mode, but implementation marks only `live` and `orchestrator` as implemented.

**Evidence**
- `--full` help and epilog examples: “All 12 models”.
- `--mode` help includes `integration`.
- Harness implementation list excludes `integration` from implemented modes.
- Model config contains 15 `ModelConfig(...)` entries.

**Why this matters**
- Run planning/cost expectation can be wrong.
- Users may interpret `integration` as ready when it is not.
- This weakens benchmark trust as a deployment gate standard.

**Recommendation**
- Make CLI text dynamically reflect model count from `MODELS_FULL`.
- Keep `integration` either fully implemented or clearly marked experimental/not implemented in help + docs.
- Add a CI doc-contract check for CLI epilog and help text.

### 2) Scenario schema/validation still carries tier-era constructs as first-class

**What we observed**
- The published schema file is tier-centric (`tier_0..tier_3`) and dimension taxonomy is legacy.
- Scenario validator still allows tier values and legacy tier enums.
- Active scenario files still include `tier` fields and tier-style IDs.

**Evidence**
- Scenario schema uses tier naming and pattern.
- Validator accepts both category and tier-era enums.
- Example scenario ID: `tier1_crisis_cssrs_passive_001` with `"tier": "safety"`.
- Some active scenarios have no canonical `category` field at all.

**Why this matters**
- Structural ambiguity undermines MECE category baseline enforcement.
- Tooling can silently accept mixed-era metadata that is hard to reason about across runs.
- Makes longitudinal comparability harder (rubric updates can’t assume normalized schema).

**Recommendation**
- Define a strict v2 scenario schema for active corpus (category required; tier optional-only for migration).
- Add a migration linter that blocks new scenarios missing canonical category or using tier-era IDs in new additions.
- Maintain backward compatibility only at loader boundary with explicit normalization + warnings.

### 3) Quality-dimension fail handling is partially inconsistent with strict fail-closed semantics

**What we observed**
- Gate failures correctly zero the score.
- If gates pass but one quality scorer errors, logic reweights implicitly by giving full weight to the successful scorer.

**Evidence**
- Orchestrator computes `overall_score = regard_score` when coordination errors (and vice versa), despite nominal fixed 50/50 architecture.

**Why this matters**
- This can inflate or distort scores under partial scorer failures.
- Rubric framing suggests fixed two-dimension quality blend after gates pass.

**Recommendation**
- Decide policy explicitly:
  - **Option A (strict):** any quality scorer error => scenario status `error`, overall 0.0.
  - **Option B (lenient):** keep one-dimension fallback, but mark as degraded and exclude from publishable stats by default.
- Reflect chosen policy in rubric/methodology and run-audit rules.

### 4) Environment reproducibility gap in default test workflow

**What we observed**
- `uv run pytest -q` fails at collection due to missing `python-dotenv` in environment.

**Evidence**
- Import error in `benchmark/invisiblebench/api/client.py` (`from dotenv import load_dotenv`) causes widespread test collection failure.

**Why this matters**
- “Definition of done” requires tests pass, but current baseline can fail before executing tests.
- This blocks confidence in scoring/rubric changes.

**Recommendation**
- Add `python-dotenv` to project dependencies (or test extra if only needed in runtime path).
- Add a smoke CI job for `uv run pytest -q` in a clean env.

## Medium-Priority Findings

### 5) Rubric language vs implementation nuance around coordination scorer

**What we observed**
- Methodology text states coordination is fully deterministic.
- Coordination scorer currently supports LLM-assisted scoring (`allow_llm`) with deterministic fallback.

**Risk**
- Interpretation drift in research/public communications.

**Recommendation**
- Align docs with implementation (“primarily deterministic, optional LLM edge-case assist”) or remove LLM path if strict determinism is required.

### 6) Mixed taxonomy in scenario metadata

**What we observed**
- Scenario files include mixed labels (e.g., top-level category absent in some, or legacy dimension labels in rubrics).

**Risk**
- Weakens downstream analyses (category-level deltas, drift and fairness slices).

**Recommendation**
- Introduce a canonical metadata normalization pass during load and emit warnings/errors for non-canonical tags in active benchmark sets.

## Alignment Action Plan (Suggested)

### Phase 1 — Fast integrity fixes (1-2 days)
1. Update CLI help text/model count/mode phrasing.
2. Patch dependency gap for test collection.
3. Add CI check that compares documented model count/modes against code constants.

### Phase 2 — Schema hardening (2-5 days)
1. Publish `SCENARIO_SCHEMA_v2` with MECE categories.
2. Add validator mode: `strict_v2=True` for benchmark corpus.
3. Add migration script to auto-fill/normalize category metadata.

### Phase 3 — Scoring governance hardening (3-7 days)
1. Resolve policy for quality scorer errors (strict vs degraded).
2. Update run audit to explicitly classify and gate partial quality failures.
3. Update docs (rubric + methodology + CLI examples) in one synchronized PR.

## Suggested rubric-governance controls

- **Rubric contract versioning:** require explicit `scoring_contract_version` bump for semantics changes.
- **Golden transcript tests:** fixed transcripts with expected gate/dimension outputs for regression detection.
- **Doc-contract tests:** assert that counts, modes, and category names in CLI/docs match runtime constants.
- **Publishability guardrails:** block leaderboard publish when any run uses degraded quality fallback unless explicitly allowed.

## Closing assessment

The benchmark has the right core architecture for a caregiver safety standard, but it now needs **operational coherence** more than new scoring ideas. The highest-leverage step is to eliminate mixed-era semantics (tier/category, deterministic/optional-LLM wording, implemented/advertised modes) so that every run is unambiguous, reproducible, and explainable to labs and product teams.
