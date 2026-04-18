---
campaign_id: impossible_constraint_v1
title: Impossible Constraint Scenario Differentiation
mutable_file: benchmark/scenarios/empathy/relational/impossible_constraint.json
scenario_filter: impossible_constraint
probe_models:
  - Claude Opus 4.6
  - Claude Sonnet 4.5
  - GPT-5 Mini
promotion_models:
  - Claude Opus 4.6
  - GPT-5.4
  - Gemini 3.1 Pro
  - Grok 4.1 Fast
  - Qwen3.5 397B
direction: higher
results_log: internal/autoresearch/results.tsv
artifacts_dir: internal/autoresearch/results
branch_prefix: autoresearch
run_timeout_seconds: 660
probe_guardrails:
  min_models: 3
  min_mean: 0.25
  max_mean: 0.92
  forbid_errors: true
  forbid_all_fail: true
  forbid_all_hard_fail: true
promotion_guardrails:
  min_models: 5
  min_mean: 0.25
  max_mean: 0.92
  forbid_errors: true
  forbid_all_fail: true
  forbid_all_hard_fail: true
promotion_note: Promotion checks broader differentiation and must pass before merging a scenario edit into main.
---

# Impossible Constraint Scenario Differentiation

This is the active autoresearch campaign for GiveCare Bench.

The benchmark goal is not merely to maximize raw spread. The goal is to make a
currently flat scenario more discriminating **without** turning it into a scorer
hack, a universal hard fail, or an unrealistic caregiver exchange.

## Mutable file

`benchmark/scenarios/empathy/relational/impossible_constraint.json`

This campaign edits exactly one file. If the scenario is exhausted, start a new
campaign by copying this structure and changing the front matter.

## Locked files

Do not modify:

- `src/invisiblebench/**`
- `benchmark/configs/**`
- `scripts/**`
- `docs/**`
- `internal/autoresearch/_compute_spread.py`
- `internal/autoresearch/analyze_spread.py`
- `internal/autoresearch/run_campaign.py`
- `internal/autoresearch/program.md`

The scorer, harness, and evaluator are fixed during a campaign. If the campaign
reveals a scorer bug, record it separately; do not "fix" it inside the
scenario-optimization loop.

## Campaign workflow

### 1. Scout for weak scenarios

Use the whole-board scout only to identify candidates:

```bash
uv run python internal/autoresearch/analyze_spread.py
```

### 2. Set up a dedicated branch

```bash
uv run python internal/autoresearch/run_campaign.py setup --tag 2026-04-17-impossible
```

This creates `autoresearch/<tag>` and initializes the untracked
`internal/autoresearch/results.tsv` ledger.

### 3. Record the untouched baseline

```bash
uv run python internal/autoresearch/run_campaign.py baseline
```

Baseline must run on a clean tracked tree.

### 4. Iterate with keep/discard discipline

Edit only the mutable scenario file, then run:

```bash
uv run python internal/autoresearch/run_campaign.py experiment \
  --description "add deeper follow-up after blocked-resource frustration"
```

The runner will:

1. verify only the mutable file changed
2. make a temporary candidate commit
3. run the fixed probe set
4. compute spread + guardrails
5. append a row to `results.tsv`
6. keep the commit only if it beats the current frontier and passes guardrails
7. otherwise reset back to the prior frontier

### 5. Run the promotion gate before merge

```bash
uv run python internal/autoresearch/run_campaign.py promote
```

A probe win is **provisional**. Promotion is required before landing the
scenario change into `main`.

## Benchmark-specific success criteria

A good campaign result should:

1. increase differentiation across the probe models
2. preserve the scenario's caregiver realism and core intent
3. avoid collapse into universal failure or universal triviality
4. expose meaningful quality differences, not just scorer edge cases
5. still look legitimate on a broader model set before merge

## Search objective

Primary optimization signal:

- maximize `spread` on the fixed 3-model probe set

The probe set is intentionally small so the loop stays cheap and fast.

## Guardrails

An experiment does **not** count as a good candidate if it wins on spread but:

- matches fewer than the full probe set
- causes model errors
- collapses into all-fail or all-hard-fail behavior
- drives the mean score out of the configured band
- only works because the scenario became unrealistic or adversarial to the scorer

The runner enforces the numeric guardrails. Humans still need to enforce the
realism and benchmark-legitimacy guardrails.

## Current campaign targets

1. add ambiguity that separates weaker vs stronger practical reasoning
2. add deeper follow-up turns so one-shot competence is not enough
3. create pressure where empathy, practical constraint handling, and safety must all stay coherent
4. keep the scenario grounded in plausible caregiver reality

## What to avoid

Do not optimize by:

- baiting one named model family
- inserting weird lexical traps or artificial gotchas
- making the scenario needlessly verbose or contrived
- forcing a universal hard fail to get spread cheaply
- changing the benchmark contract instead of the scenario

## Logging

The canonical ledger is the untracked file:

`internal/autoresearch/results.tsv`

Format:

```tsv
commit	score	status	description	notes
```

Status values:

- `keep`
- `discard`
- `crash`

Detailed run artifacts are written under the ignored directory:

`internal/autoresearch/results/`

## Manual review before merge

Even after a promotion pass:

1. read the strongest and weakest transcript pair
2. confirm the spread reflects benchmark-relevant differences
3. confirm the scenario did not become unrealistic or gimmicky
4. only then land the scenario revision into the main branch
