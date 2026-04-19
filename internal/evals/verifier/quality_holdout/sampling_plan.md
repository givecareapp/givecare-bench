# Regard quality holdout sampling plan

Version: 2026-04-17
Seed: `20260419`

## Selection policy

1. start from the frozen 15-model board (`results/run_20260330_130332` and the
   matching partial-run root)
2. exclude every trace already used in `internal/evals/verifier/golden_set/labels/gold/`
3. keep only traces the current scorer marks as public-pass
4. prioritize pass-only scenario families where regard calibration matters most
5. cap per-model exposure at 4 traces where possible

## Target family counts

| Scenario family | Target |
|---|---:|
| `tier1_boundaries_therapy_001` | 4 |
| `context_regulatory_misrepresentation_001` | 4 |
| `tier1_attachment_002` | 4 |
| `tier2_attachment_001` | 4 |
| `tier2_regulatory_001_minor_disclosure` | 4 |
| `tier1_crisis_cssrs_passive_sms_001` | 4 |
| `tier1_crisis_dual_concern_001` | 4 |
| `tier1_false_refusal_med_001` | 4 |
| `context_regulatory_therapy_function_001` | 3 |

Total target: **35** traces.

## Why these families

These families stress the pass-only quality layer in different ways:

- attachment / substitute-presence drift
- misrepresentation correction with warm but boundary-sensitive closers
- therapy-adjacent structuring that did not cross the hard-fail line
- directive medical routing that stayed public-pass
- clean crisis support traces where tone, pacing, and relational stance still matter

## Generation

```bash
uv run python scripts/build_regard_quality_holdout.py
```

Do not hand-edit `candidates.jsonl` or `labels/template/`.
