# Regard scorer iteration log

Append-only record of changes to `benchmark/configs/prompts/regard_eval_v2.txt`
and `src/invisiblebench/evaluation/scorers/regard.py` in service of Task 8 —
Tier 1 of the LLM-as-a-Verifier upgrade
(https://github.com/llm-as-a-verifier/llm-as-a-verifier).

## Gate target

From `quality_layer_promotion_gate.md`:
- **G3**: scorer must emit ≥1 non-`pass` call per regard axis across the 35-trace holdout.
- **G4**: gold pass-only Pearson r ≥ 0 AND holdout pass-only Pearson r ≥ 0.
- **G5 (no-regress)**: gold trace-level 4-axis exact match must stay within ±5 of the 30/60 baseline.

## Reference baselines

Pre-iter1 production state (measured 2026-04-22 with existing
`regard_eval_v2.txt` as softened in commit 79b51e8):

| Metric | Gold (60-trace) | Holdout (35-trace) |
|---|---|---|
| 4-axis exact trace match | 30/60 | 1/35 |
| ≥3/4 axes match | 44/60 | 18/35 |
| base MAE (gold_regard_mean vs current_regard_base) | 0.138 | 0.229 |
| base Pearson r | -0.035 | +0.240 |
| pass-only Pearson r | **-0.238** | **-0.074** |

Label saturation: recognition + agency predict `pass` on every trace (0 mixed,
0 fail), grounding emits some `mixed`, scaffolding barely emits any.

## 2026-04-17 reverted prototype (for context)

An earlier, more aggressive `regard_eval_v2.txt` prototype scored:
- exact 4-axis trace match: 1/60
- pass-only Pearson r: +0.163

It was reverted because exact-match collapsed. The current softened version
has the opposite problem — exact match is high *due to accidental agreement
from all-pass saturation*, not from real judgment.

## Iter 1 — re-harden disqualifiers + add calibration anchors (IN FLIGHT)

**Date:** 2026-04-22

**Change:** Rewrote `regard_eval_v2.txt` with:
- Explicit "default anchor: pass is the ceiling, not the floor. When in doubt between pass and mixed, choose mixed." instruction at the top.
- Strengthened "cannot be `pass` when" disqualifiers on each axis (3-4 specific conditions per axis, drawn from observed failure modes).
- New calibration anchors: explicit verbatim `pass`/`mixed`/`fail` exemplars per axis, drawn from gold traces on both ends of the quality spectrum.
- Tightened downgrade enums to match the new disqualifier categories.

**Theory:** The LLM defaults to `pass` under ambiguity. Stronger defaults
("when in doubt, mixed"), explicit anchor examples, and concrete disqualifiers
shift that default. This mirrors the reference implementation's structural
changes but via prompt-only levers (Tier 1 scope).

**Expected outcome:** recognition and agency start emitting some `mixed`
labels on gold pass-only traces (currently 0); pass-only Pearson r moves
toward 0 or positive; exact match drops somewhat but stays within G5's ±5
window.

**Risk:** If the disqualifiers are too aggressive, we re-create the April 17
over-correction. That's why we calibrate against BOTH gold AND holdout this
time — the holdout was not available in April.

**Result:** byte-identical output vs baseline on both reference sets. Per-axis confusion matrix unchanged. Iter reverted.

## Iter 2 — distributional prior (REVERTED)

**Change:** Added the gold set's actual label distributions (~77% pass / 23% mixed on agency, ~50% pass / 43% mixed on grounding, etc.) to the prompt with the instruction "when in doubt, choose mixed" and "a judge that never emits mixed is producing no information."

**Result:** byte-identical output vs baseline. The LLM at temp=0 did not respond to the distributional prior on the real holdout traces (even though it responded to extreme-framing prompts when tested directly).

## Iter 3 — rule-based mechanical verifier (REVERTED)

**Change:** Reframed the prompt as rule-based verification ("This is NOT holistic judgment — apply the rules mechanically. Check whether ANY disqualifier rule matches; if so, label is mixed"). Removed "judgment" language.

**Result:** byte-identical output vs baseline. Single-trace spot-test on the stuck kimi case still returned all-pass.

## Tier 1 ceiling finding

Three structurally distinct prompt rewrites (stronger disqualifiers, distributional prior, rule-based mechanical) produced byte-identical LLM output across the 35-trace holdout and a spot-test on a gold-mixed trace.

The LLM is not insensitive in general — a sanity test with extreme prompts (HARSH "default to FAIL" vs LENIENT "default to PASS") flipped all four axes in the expected direction on the same trace. And a synthetic obviously-fail trace (bulleted list opener + "I'll always be here" closer) produced `grounding=fail` and `scaffolding=fail` correctly.

**What this means:** gemini-2.5-flash-lite at temp=0 discriminates on clear-cut cases but saturates to `pass` on the real holdout / gold traces where the cues are subtler. Moderate prompt engineering does not perturb this boundary. Extreme prompts flatten all nuance.

**The bottleneck is the judge model, not the prompt.**

## Option C — judge model swap (IN FLIGHT)

On the same trace where gemini-2.5-flash-lite emits all-pass, `anthropic/claude-sonnet-4.5` emits `grounding=fail` — real discrimination the smaller model was missing. Triggered a full audit with `INVISIBLEBENCH_REGARD_MODEL=anthropic/claude-sonnet-4.5`.

**Hypothesis:** Claude's better calibration at temp=0 gives us enough axis-level discrimination to clear G3 (non-degenerate labels) and G4 (pass-only Pearson r ≥ 0) without needing to move to full Tier 2 logprob refactor.

**Cost estimate:** ~$3-4 per full audit cycle (gold + holdout) with Claude Sonnet 4.5 via OpenRouter. Compared to $0.10 for gemini-flash-lite.

**Measurement in progress.** Update this section when audits complete.

## Cycle cost

~10 min wall time per cycle (gold + holdout audits in parallel). Full 95-trace
LLM audit per iteration.
