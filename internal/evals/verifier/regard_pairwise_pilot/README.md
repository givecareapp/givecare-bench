# Regard pairwise pilot

Same-scenario comparative quality set for best-worst / pairwise calibration.

## Purpose

The absolute axis labels (`pass|mixed|fail`) remain the primary scorer target.
This pilot exists to check whether comparative judgments are more stable for the
hardest quality distinctions among already-clean traces.

## Shape

- 8 scenario groups
- 4 clean outputs per scenario
- source: pass-only quality holdout candidates
- focus axes:
  - `grounding`
  - `agency`
  - `scaffolding`

## Build

```bash
uv run python scripts/build_regard_pairwise_pilot.py
```

## Run

```bash
uv run python scripts/run_pairwise_pilot.py [--model MODEL] [--limit N] [--overwrite]
```

The committed `groups.jsonl` scaffold is reproducible in fresh checkouts, but
actual pilot annotation still requires the transcript files referenced in each
row under `results/`.

## Output

- `groups.jsonl` — one same-scenario comparison group per line
- `pilot_results.jsonl` — one LLM best-worst judgment record per completed group

Each group contains:

- scenario id
- four clean outputs
- transcript paths
- instructions for comparative annotation

## Intended annotation mode

For each group and each target axis, ask annotators to mark:

- best
- worst

Do not ask them to produce a numeric score in this pilot.

## Decision status

This is a calibration workflow, not a production ranking method yet. See
`../regard_pairwise_decision.md` for the current decision policy.
