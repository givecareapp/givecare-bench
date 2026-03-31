# Verifier Pack

Authoritative transcript-adjudication layer for the current GiveCare Bench corpus.

This directory turns the benchmark from a collection of runs and scorer outputs into a
reviewable, scenario-aware evaluation system.

## What this is

The verifier pack is the adjudication layer that sits between:

- the benchmark's **normative contract** (`docs/scoring-rubric.md`)
- the benchmark's **scenario contracts** (`benchmark/scenarios/**/*.json`)
- and the benchmark's **observed transcripts** (`results/**/transcripts/*.jsonl`)

It is designed for:

- scorer validation
- transcript rescoring on a fixed corpus
- scenario-level audits across many models
- rule-level audits across many scenarios
- building a defensible public scorecard

## What this is not

- not a new generation harness
- not a replacement for the benchmark scenarios
- not a Prime Intellect environment by default
- not a promise that every quality judgment is fully objective

The verifier exists to discipline judgment, not eliminate it.

## Directory map

| Path | Purpose |
|------|---------|
| `benchmark_governance.md` | Authority model: what is public-contract vs diagnostic |
| `core_rubric.md` | Segmented adjudication rubric for transcript review |
| `taxonomy.md` | Hard-fail, soft-issue, allowed-behavior, and disagreement taxonomies |
| `output_schema.json` | JSON schema for verifier outputs |
| `prompts/` | Prompt templates for single-trace and batch adjudication |
| `scenario_contracts/` | Verifier-ready summaries of the highest-noise scenarios |
| `corpus_manifest.jsonl` | Canonical transcript manifest over the current 15-model board |
| `corpus_summary.{json,md}` | Corpus coverage, artifact health, and model-level summary |
| `retrospective_2026-03-31.md` | Established findings from the first tranche of verifier adjudication |
| `remediation_plan_2026-03-31.md` | Immediate scorer-remediation plan on the frozen corpus |
| `results/` | Claude verifier outputs by scenario tranche |

## Current corpus

The verifier pack assumes the current 15-model board is frozen and combines two transcript roots:

- `results/run_20260330_130332/transcripts/`
- `results/partial_runs/run_20260330_033649_up_to_deepseek/transcripts/`

Those two roots together provide full transcript coverage for the current board.

## Workflow

1. Read `benchmark_governance.md`
2. Apply `core_rubric.md` + `taxonomy.md`
3. Load the relevant scenario contract from `scenario_contracts/`
4. Review transcripts via one of the prompts in `prompts/`
5. Emit structured JSON matching `output_schema.json`
6. Compare against the current scorer verdict and aggregate disagreements

## Recommended batch modes

### 1. Same scenario, all models
Best for calibrating one scenario family consistently.

### 2. Same rule, many scenarios
Best for cleaning up an over-broad failure class like `false_scope_or_capability_claim`.

### 3. Rank-sensitive tranche
Best for evaluating the top of the board without reviewing every trace.

## Regeneration

The manifest and summary files are generated with:

```bash
uv run python scripts/generate_verifier_corpus.py
```

Scenario-batch adjudication can then be prepared or run with:

```bash
uv run python scripts/run_claude_verifier.py --scenario-id tier1_scope_honesty_001 --prepare-only
uv run python scripts/run_claude_verifier.py --scenario-id tier1_scope_honesty_001 --model opus
```

## Notes

- `detail_json` links resolve only partially for the current local corpus.
- `detail_html` links do not currently resolve locally.
- Some leaderboard rows are still error-contaminated; see `corpus_summary.md`.

## Current status

The first verifier tranche established that `false_scope_or_capability_claim` is not just noisy; it is a leaderboard-shaping adjudication defect in several scenario families. See:

- `retrospective_2026-03-31.md`
- `remediation_plan_2026-03-31.md`

## Remaining work

1. finish the exhaustive `false_scope_or_capability_claim` rule batch on the frozen corpus
2. split the catch-all rule into narrower public hard-fail classes plus protected allowed behaviors
3. patch the compliance scorer and add transcript-backed regression tests
4. rescore the frozen runs before any fresh model generation
5. decide whether to repair leaderboard artifact links in-place or remove them from public-facing outputs
