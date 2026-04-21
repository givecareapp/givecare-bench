# Regard quality holdout

Pass-only holdout set for validating the quality layer independently from the
existing 60-trace gold dev set.

## Purpose

This set exists so regard improvements are not tuned and judged on the exact
same calibration traces.

Use it for:

- held-out validation of Regard v2
- pass-only ranking confidence
- public-claim decisions about `overall_score`

## Shape

- target size: 35 traces
- source: frozen 15-model board
- excludes: every trace already present in `golden_set/labels/gold/`
- includes only: traces the current scorer marks as public-pass
- concentrates on pass-only scenario families that matter most for quality:
  - attachment / role drift
  - misrepresentation correction
  - therapy-boundary responses that stayed public-pass
  - minor-disclosure routing responses that stayed public-pass
  - clean crisis support traces

## Files

- `sampling_plan.md` — exact scenario-family targets and selection policy
- `candidates.jsonl` — selected holdout candidates
- `labels/template/` — one blank label template per candidate

## Build

```bash
uv run python scripts/build_regard_quality_holdout.py
```

If the original result snapshots are available locally, the script rebuilds the
holdout from those runs. In CI or fresh checkouts without those large run
artifacts, it falls back to the checked-in `candidates.jsonl` file so tests and
follow-on tooling remain reproducible.

## Annotation policy

Use the same full label schema as the main golden set so the holdout can still
catch accidental public-layer mistakes. But the primary purpose of this set is
quality validation on the pass-only slice.

Annotators should still fill:

- `verdict.*`
- `quality.*`
- `soft_issues`
- `evidence`
- `summary`

## Relationship to the main gold set

- `golden_set/` remains the dev / diagnosis set for scorer repair
- `quality_holdout/` is the held-out check before promoting a new quality layer
