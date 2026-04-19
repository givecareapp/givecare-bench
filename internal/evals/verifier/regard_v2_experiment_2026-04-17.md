# Regard v2 experiment — 2026-04-17

Status: reverted prototype

## What was tested

A first Regard v2 prototype replaced the current scalar prompt with:

- structured `pass|mixed|fail` axis labels
- quote-backed evidence per axis
- deterministic downgrade caps for:
  - therapy structure
  - advice before validation
  - invalidation language
  - substitute-presence language
  - directive takeover

## Why it was tested

The current scorer's main failure mode is all-pass saturation, especially on
`grounding`, `agency`, and `scaffolding`. The prototype was intended to make the
quality layer more legible and more faithful to the resolved gold labels.

## Audit result

Command:

```bash
uv run python scripts/audit_gold_regard.py --mode llm
```

Observed dev-set result on the 60-trace resolved gold set:

- exact 4-axis trace match: `1/60`
- trace match on at least 3/4 axes: `29/60`
- gold-derived regard mean vs current regard base MAE: `0.244`
- gold-derived regard mean vs current regard base Pearson r: `0.532`
- pass-only exact 4-axis match: `1/45`
- pass-only base Pearson r: `0.163`

## Interpretation

The prototype fixed the original saturation problem, but it over-corrected and
started over-downgrading many clean traces. Correlation improved, but exact
agreement degraded too sharply to ship.

That makes this a useful design signal, not a releasable scorer repair.

## Decision

Revert the active scorer changes rather than shipping a worse quality layer.
Keep the design direction, holdout setup, and pairwise calibration plan.

## Next calibration targets

1. keep the current active regard scorer until a replacement beats it on the dev set
2. use the new pass-only reporting in `audit_gold_regard.py` as the ranking proxy
3. collect the new pass-only human holdout before promoting any new scorer
4. use the pairwise pilot to learn where exact axis labels and comparative judgments diverge
