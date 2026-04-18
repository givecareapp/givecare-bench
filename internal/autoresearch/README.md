# AutoResearch

Repo-specific adaptation of `karpathy/autoresearch` for benchmark scenario work.

Reference wiki: `~/agents/wiki/givecare-bench-autoresearch-implementation.md`

## What this is

This workflow treats a single benchmark scenario as the mutable object under
research.

- mutable file: one scenario JSON
- fixed evaluator: `bench` + `internal/autoresearch/_compute_spread.py`
- search metric: scenario spread across a small fixed probe set
- keep/discard rule: automatic, logged in `results.tsv`
- promotion gate: broader model set before merge

The aim is to improve **scenario differentiation** without drifting away from
realistic caregiver interactions or gaming the scorer.

## What this is not

- not scorer tuning
- not benchmark-wide optimization in one loop
- not a permission slip to make scenarios adversarial or gimmicky
- not a substitute for transcript review before merge

## Files

- `program.md` — active campaign spec, goals, guardrails, and front matter
- `run_campaign.py` — branch/setup, baseline, experiment, and promotion runner
- `_compute_spread.py` — fixed evaluator over benchmark run artifacts
- `analyze_spread.py` — scout mode over the broader leaderboard-ready set
- `run_scenario.sh` — compatibility wrapper for quick probe-only runs
- `results/` — ignored per-run JSON artifacts
- `results.tsv` — ignored experiment ledger

## Commands

### Scout mode

Find flat scenarios worth improving:

```bash
uv run python internal/autoresearch/analyze_spread.py
```

### Set up a campaign branch

```bash
uv run python internal/autoresearch/run_campaign.py setup --tag 2026-04-17-impossible
```

### Inspect current status

```bash
uv run python internal/autoresearch/run_campaign.py status
```

### Record baseline

```bash
uv run python internal/autoresearch/run_campaign.py baseline
```

### Evaluate the current scenario edit

```bash
uv run python internal/autoresearch/run_campaign.py experiment \
  --description "tighten follow-up after blocked-resource frustration"
```

This auto-commits the candidate, runs the probes, logs the result, and either
keeps or reverts the commit.

### Promotion gate before merge

```bash
uv run python internal/autoresearch/run_campaign.py promote
```

### Ad hoc probe-only run

```bash
uv run python internal/autoresearch/run_campaign.py probe-run
```

## Benchmark-specific policy

A spread improvement is only useful if it also preserves benchmark quality.

Good changes:
- separate stronger vs weaker practical reasoning
- add realistic ambiguity or follow-up pressure
- preserve the scenario's core caregiver intent

Bad changes:
- create scorer hacks
- make all models fail
- rely on brittle lexical traps
- optimize for one vendor/model family

## Merge policy

A scenario edit should not land until:

1. it beats the current probe frontier
2. it passes the promotion gate
3. the strongest vs weakest transcripts still look benchmark-legitimate on manual review
