# Benchmark status memo — recent work, current gaps, and opportunities

Scope: summary of the last ~1–2 days of benchmark work across calibration,
scoring, rollout, public delivery, and the next-stage regard-quality plan.

## Executive summary

The benchmark is now in a meaningfully stronger position than it was before this
work window.

### What is now strong

- the **public hard-fail layer** (`safety`, `compliance`, public hard-fail rate)
  is calibrated on the resolved 60-trace gold set
- the **runtime scorer** is aligned with that gold set on the public layer
- the **frozen 15-model board** has been rescored with the repaired scorer and
  the public leaderboard artifacts have been refreshed
- the **delivery path** is now consistent: static JSON is canonical, not Convex
- the benchmark artifact now carries **machine-readable claim-surface metadata**
  so consumers can see what is validated and what is still in progress

### What is still weak

- `regard` remains the main blocker to stronger claims about `overall_score`
- `regard` is now **measured**, but not **validation-grade**
- the current regard scorer still over-predicts `pass`, especially on
  `grounding`, and still does not produce a trustworthy ranking signal on the
  pass-only slice

### What we did about that

We did not just write caveats. We set up the next real repair loop:

- pass-only reporting inside the regard audit
- a held-out pass-only human quality set scaffold
- a same-scenario pairwise / best-worst calibration pilot scaffold
- a Regard v2 design note
- a record of the first structured Regard v2 prototype and why it was reverted

That means the benchmark now has a much clearer path from:

- “regard is weak”

into:

- “here is the exact workflow required to make it stronger without fooling ourselves”

---

## 1. What landed in this work window

## 1.1 Resolved gold set became the benchmark’s hard-fail reference

The biggest methodological shift was finishing the human calibration loop.

### Landed

- two independent human passes over the 60-trace verifier set
- conflict resolution and adjudicated `labels/gold/`
- final gold summaries and resolution notes
- verifier validation against gold
- scorer validation against gold

### Result

The project now has a concrete, resolved reference set for the public contract.
This moved the benchmark away from “LLM draft vs scorer” and toward:

- human reference
- adjudicated gold
- measured scorer/verifier alignment

### Important implication

This is what makes the current public hard-fail story serious. The benchmark is
no longer only saying “the scorer seems sensible”; it can say “the scorer was
checked against a resolved human reference set on this contract layer.”

---

## 1.2 The current scorer was repaired to match gold on the public layer

The repaired scorer now matches resolved gold on the public hard-fail layer.

### Final current-scorer vs gold result

From `internal/evals/verifier/golden_set/current_scorer_vs_gold.md`:

- public hard-fail accuracy: `60/60 = 1.000`
- safety-gate accuracy: `60/60 = 1.000`
- compliance-gate accuracy: `60/60 = 1.000`
- exact primary-rule accuracy: `60/60 = 1.000`

### Why this matters

This is the strongest benchmark improvement in the whole window.

It means:

- public red-line outcomes are now regression-gated against human gold
- frozen-board rescoring was justified
- the benchmark can make much firmer claims about hard-fail reliability than it
  could before

---

## 1.3 The frozen 15-model board was rescored and the leaderboard refreshed

Once the scorer reached gold alignment on the public layer, the repaired scorer
was rolled through the frozen 15-model board.

### Inputs rescored

- `results/run_20260330_130332/` — 10 models / 500 rows
- `results/partial_runs/run_20260330_033649_up_to_deepseek/` — 5 models / 250 rows

### Board delta

Combined frozen board hard fails:

- `119 -> 86`

Average-score movement by root:

- main root: `0.683 -> 0.725`
- partial root: `0.706 -> 0.748`

### Biggest rank movements

- `Gemini 3.1 Pro`: `15 -> 1`
- `Grok 4.1 Fast`: `7 -> 2`
- `GPT-OSS 120B`: `6 -> 3`
- `GPT-5.4`: `1 -> 8`
- `Claude Sonnet 4.5`: `3 -> 15`

### Current top 5 after refresh

1. `Gemini 3.1 Pro` — `0.798`
2. `Grok 4.1 Fast` — `0.791`
3. `GPT-OSS 120B` — `0.774`
4. `Kimi K2.5` — `0.773`
5. `Claude Opus 4.6` — `0.750`

### Why this matters

The repaired hard-fail layer was not just theoretical. It changed the public
board in visible ways.

That tells us the calibration work was scoreboard-relevant, not cosmetic.

See also:
- `internal/evals/verifier/rescore_refresh_2026-04-18.md`

---

## 1.4 Public delivery was cleaned up and made more internally consistent

A second major improvement was information-architecture and delivery-path
cleanup.

### Landed

- active Convex benchmark publish path removed from the benchmark repo
- legacy Convex-backed benchmark delivery removed from the monorepo path used by
  the public site
- static JSON confirmed as canonical for web-bench delivery
- `scripts/sync_web_bench_leaderboard.py` added for deterministic mirror / drift
  check
- `leaderboard.json` enriched with machine-readable methodology, validation,
  runtime-adjudication, and delivery metadata

### Why this matters

Before this pass, the benchmark had a split-brain problem:

- one story in docs
- one story in web-bench
- one legacy story in Convex

That is much cleaner now.

The public artifact and the website now point to the same source of truth.

---

## 1.5 Regard is no longer “unknown” — it is measured and explicitly weak

The benchmark’s biggest remaining caveat was `regard`.

This work window moved that from vague uncertainty to concrete measurement.

### Current full-set regard audit

From `internal/evals/verifier/golden_set/current_regard_vs_gold.md`:

- exact 4-axis trace match: `30/60 = 0.500`
- trace match on at least 3/4 axes: `44/60 = 0.733`
- gold-derived regard mean vs current regard base MAE: `0.136`
- gold-derived regard mean vs current regard base Pearson r: `0.052`

### Current pass-only slice

Also now reported explicitly:

- exact 4-axis trace match: `30/45 = 0.667`
- trace match on at least 3/4 axes: `43/45 = 0.956`
- pass-only base Pearson r: `-0.198`

### What that means

The scorer still tends to flatten too much of the quality layer toward `pass`.
That is especially visible in the pass-only slice, where the issue is not merely
“general mismatch,” but “weak ranking signal among already-clean traces.”

This is the key reason `overall_score` remains a secondary claim.

---

## 1.6 The regard audit itself is now more useful

The audit was upgraded from a single blended view to a more decision-useful
report.

### `scripts/audit_gold_regard.py` now does more

It now renders:

- full-set metrics
- pass-only metrics
- mismatch-family summaries by axis
- richer CSV output, including per-axis reasons / evidence fields when present

### Why this matters

This makes the next repair work less blind.

The project can now ask two separate questions:

1. Is the scorer broadly sane on the whole set?
2. Can it rank already-clean traces in a way that tracks human judgment?

That split is closer to the benchmark’s actual goal.

---

## 1.7 A first structured Regard v2 prototype was tested and intentionally reverted

A first serious attempt at Regard v2 was made.

### What it tried

- replace scalar scoring with structured axis labels
- require quote-backed evidence
- add deterministic downgrade caps for common failure families

### What happened

It fixed the original all-pass saturation problem, but it **over-corrected** and
made exact-match metrics much worse on the 60-trace dev set.

### Decision

It was **reverted** rather than shipped.

### Why that matters

This is a good methodological sign.

We did not ship a fake improvement just because it looked more principled or
increased correlation. We kept the lesson and rejected the regression.

See:
- `internal/evals/verifier/regard_v2_experiment_2026-04-17.md`

---

## 1.8 The next-stage quality-validation scaffolding is now built

Instead of continuing to tune `regard` on the same 60 traces forever, the repo
now contains the next validation scaffolding.

### Held-out pass-only quality set

Added:

- `scripts/build_regard_quality_holdout.py`
- `internal/evals/verifier/quality_holdout/README.md`
- `internal/evals/verifier/quality_holdout/sampling_plan.md`
- `internal/evals/verifier/quality_holdout/candidates.jsonl`
- `internal/evals/verifier/quality_holdout/labels/template/` (`35` label templates)

### Holdout composition

- `35` pass-only traces
- `9` targeted scenario families
- excludes the existing 60-trace gold set
- spread across `15` models

### Pairwise / best-worst pilot

Added:

- `scripts/build_regard_pairwise_pilot.py`
- `internal/evals/verifier/regard_pairwise_pilot/README.md`
- `internal/evals/verifier/regard_pairwise_pilot/groups.jsonl`
- `internal/evals/verifier/regard_pairwise_decision.md`

### Pairwise pilot composition

- `8` same-scenario groups
- `4` clean outputs per group
- intended axes: `grounding`, `agency`, `scaffolding`

### Why this matters

This is the main opportunity unlocked by the latest work.

The benchmark now has a concrete path to:

- held-out quality validation
- same-scenario comparative calibration
- less brittle quality ranking

without pretending the current scalar judge is already good enough.

---

## 2. Current benchmark standing

## 2.1 What the benchmark can now say strongly

These are the strongest claims now supported by the repo:

### Public hard-fail layer

The benchmark is now strongest as a calibrated public-red-line benchmark.

That includes:

- safety-gate reliability
- compliance-gate reliability
- public hard-fail rate
- exact rule-family attribution on the public layer

### Operational delivery

The benchmark also has a much cleaner operational story:

- canonical artifact exists
- public site consumes static JSON
- sync path is scripted and checkable
- artifact metadata now exposes the benchmark’s claim surface directly

---

## 2.2 What the benchmark can only say cautiously

### Regard / quality ordering

`regard` is no longer unknown, but it is still not validation-grade.

That means the benchmark can say:

- quality is being measured
- `regard` is in progress
- current weaknesses are known

But it should still avoid saying:

- overall rank is fully validated as caregiving quality
- close quality differences are authoritative
- regard is solved

---

## 2.3 Best current framing

The benchmark is currently best understood as:

> a verifier-governed, gold-calibrated benchmark for caregiver-AI contract
> fidelity on the public hard-fail layer, with a still-improving quality layer
> used mainly to rank already-clean traces

That is a stronger and more honest description than “fully validated holistic
care-quality leaderboard.”

---

## 3. Current gaps

## 3.1 Main gap: regard is still not validation-grade

This is still the biggest remaining benchmark gap.

### Specific failure mode

- too much `pass` prediction
- especially weak `grounding` discrimination
- weak pass-only ranking signal

### Why it matters

This is what still blocks stronger public claims about `overall_score`.

---

## 3.2 No held-out human quality validation yet

The holdout scaffolding exists, but the human labels do not yet.

### Current state

- the repo has the holdout candidates and templates
- it does **not** yet have:
  - annotator A pass
  - annotator B pass
  - holdout gold
  - holdout validation memo

### Why it matters

Without this, any future Regard v2 repair still risks being overfit to the
existing 60-trace dev set.

---

## 3.3 No pairwise / BWS calibration data yet

The pilot is scaffolded, but not yet run.

### Why it matters

This is one of the best opportunities to reduce brittleness on the fuzzy quality
layer.

The benchmark naturally has multiple model outputs for the same scenario, which
is exactly where same-scenario pairwise or best-worst judgments can be more
stable than absolute scalar ratings.

---

## 3.4 The current 60-trace gold set is enough for the hard-fail layer, not enough for all quality claims

The existing gold set is valuable and operationally useful, but it is still a
small set.

### Strong use

- public hard-fail calibration
- scorer regression gate
- verifier validation on the decisive layer

### Weaker use

- broad claims about subtle quality ordering
- generalized trust in `overall_score`

---

## 3.5 Soft-issue and confidence fields remain weaker than the bright-line public layer

This is not the main problem right now, but it is still a secondary gap.

The public hard-fail layer is much better defined than:

- soft issues
- confidence
- subtle relational quality distinctions

That is another reason to keep the benchmark’s public claim hierarchy explicit.

---

## 3.6 Some repo / product hygiene gaps remain outside the main methodology problem

These are lower priority, but still real:

- `detail_json` / `detail_html` artifact links are only partially useful locally
- `src/invisiblebench/cli/runner.py` is still a large monolith
- broader repo cleanup opportunities remain after the archive pass

These do not block benchmark credibility as directly as `regard`, but they are
still future maintenance opportunities.

---

## 4. Main opportunities

## 4.1 Biggest immediate opportunity: validate quality on the new held-out pass-only set

This is the cleanest next step.

### Why it is high leverage

- directly addresses overfitting risk
- speaks to the actual ranking problem
- builds confidence in any future Regard v2
- creates a more serious public methodology story

### Concrete path

1. annotate the 35-trace holdout
2. adjudicate held-out gold
3. validate any repaired regard scorer on that held-out set

---

## 4.2 Biggest methodological opportunity: use comparative calibration for the fuzzy layer

The same-scenario pairwise / best-worst pilot is probably the best next method
addition for the hard quality cases.

### Why

For subjective conversational quality, comparative judgments are often more
stable than absolute ratings.

### Best use here

Use pairwise / best-worst as:

- a calibration layer
- a ranking sanity check
- a way to learn which pass-only traces actually differ in grounding / agency /
  scaffolding

Do **not** treat it as public production logic until it is validated.

---

## 4.3 Biggest product opportunity: reframe the quality layer as “ranking among clean traces”

The pass-only split now makes this much more explicit.

The benchmark should continue leaning toward:

- **primary layer:** contract fidelity / hard-fail reliability
- **secondary layer:** quality among clean traces

That framing is more idiomatic for the benchmark’s actual strength.

---

## 4.4 Biggest repair opportunity inside regard: targeted grounding work

The pass-only slice shows the most systematic weakness is still `grounding`.

That suggests the highest-value scorer work is not generic “make regard better,”
but:

- reduce over-credit on pass-only grounding
- especially in boundary / attachment / misrepresentation / false-refusal families

That is the most plausible route to improving quality ranking without overhauling
all four axes at once.

---

## 4.5 Bigger future opportunity: expand quality gold beyond the current 60 dev traces

Once holdout validation exists, the next level would be a broader quality set.

That would support stronger claims about:

- robustness across more families
- stability of pass-only ranking
- consistency of human comparative judgments

This is not the immediate next step, but it is the clearest long-term path to a
more authoritative quality layer.

---

## 5. Recommended next sequence

## Phase 1 — use the new scaffolding

1. run annotator A on `internal/evals/verifier/quality_holdout/`
2. run annotator B on the same holdout
3. compute agreement and resolve holdout gold

## Phase 2 — run comparative calibration

4. run the pairwise / best-worst pilot in `internal/evals/verifier/regard_pairwise_pilot/`
5. compare comparative judgments to absolute quality labels on the same families

## Phase 3 — attempt Regard v2 again, but under a stricter rule

6. repair `regard` only if the new scorer:
   - improves on the current gold dev set
   - holds on the held-out pass-only set
   - improves pass-only ranking signal
   - does not regress exact agreement catastrophically

## Phase 4 — only then revisit public claim strength

7. update machine-readable leaderboard metadata and public copy only if the new
   quality layer genuinely clears validation thresholds

---

## 6. What we should avoid doing next

These are the wrong next moves:

- more vague caveats without new evidence
- more prompt-only tuning on the same 60 traces
- shipping another principled-looking but regressing regard scorer
- strengthening `overall_score` language before holdout validation

---

## 7. Artifact map from this work window

## Calibration / scoring / rollout

- `internal/evals/verifier/golden_set/current_scorer_vs_gold.md`
- `internal/evals/verifier/golden_set/current_scorer_vs_gold.csv`
- `internal/evals/verifier/rescore_refresh_2026-04-18.md`
- `data/leaderboard/leaderboard.json`

## Regard measurement

- `internal/evals/verifier/golden_set/current_regard_vs_gold.md`
- `internal/evals/verifier/golden_set/current_regard_vs_gold.csv`
- `scripts/audit_gold_regard.py`

## Regard next-step design / scaffolding

- `internal/evals/verifier/regard_v2_design.md`
- `internal/evals/verifier/regard_v2_experiment_2026-04-17.md`
- `internal/evals/verifier/quality_holdout/README.md`
- `internal/evals/verifier/quality_holdout/sampling_plan.md`
- `internal/evals/verifier/quality_holdout/candidates.jsonl`
- `internal/evals/verifier/quality_holdout/labels/template/`
- `internal/evals/verifier/regard_pairwise_pilot/README.md`
- `internal/evals/verifier/regard_pairwise_pilot/groups.jsonl`
- `internal/evals/verifier/regard_pairwise_decision.md`
- `scripts/build_regard_quality_holdout.py`
- `scripts/build_regard_pairwise_pilot.py`

---

## Bottom line

Over the last ~1–2 days, the benchmark got much stronger where it matters most
right now:

- public hard-fail governance
- scorer alignment
- board rollout
- artifact / delivery consistency
- explicit claim-surface clarity

The remaining weakness is now much better defined and much better instrumented:

- `regard` is still not validation-grade
- but it is no longer vague
- and the repo now contains the right next scaffolding to improve it without
  pretending it is already solved

That is the current state: **materially stronger benchmark, clearer limits,
and a real path for the next methodological upgrade.**
