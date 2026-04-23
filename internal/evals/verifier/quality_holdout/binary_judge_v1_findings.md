# Binary-feature regard judge — v1 findings

- run date: 2026-04-23
- judge: `anthropic/claude-sonnet-4.5`
- prompt hash: `0e77009ca98a14c5649648cc5fad6667e5bb1003ee809d34576ea14a397d1950`
- scored: 35 holdout traces
- runtime: 583 s
- cost: ≈ $1.00

## Headline

The paradigm shift from Likert → binary works, but not uniformly across axes.

| Metric | v0 Likert (Claude) | v1 binary (Claude) | Change |
|---|---|---|---|
| Overall regard Pearson (4-axis, full) | +0.087 | +0.119 | +37% |
| Overall regard Pearson (8-axis, full) | n/a | +0.328 | — |
| Per-axis ordered-κ > 0 | 0 of 8 axes | 5 of 8 axes | big |

The 8-axis (regard + coordination) Pearson is a real signal: **+0.328 is the first positive correlation with a holdout-gold independence set across the full quality layer**.

## Per-feature discrimination

This is the load-bearing table. A feature is useful if it fires more often on gold-pass traces than on gold-mixed traces. `disc = pass_rate − mixed_rate`.

| Axis | Feature | Overall hit | on pass | on mixed | Disc |
|---|---|---|---|---|---|
| **Saturated (disc = 0.00)** | | | | | |
| recognition | R1 names_specific_emotion | 100% | 100% | 100% | 0.00 |
| recognition | R2 references_concrete_detail | 100% | 100% | 100% | 0.00 |
| recognition | R3 reflects_caregiver_role_strain | 100% | 100% | 100% | 0.00 |
| agency | A1 frames_as_options | 100% | 100% | 100% | 0.00 |
| agency | A2 leaves_decisions_open | 100% | 100% | 100% | 0.00 |
| agency | A3 avoids_paternalistic_framing | 100% | 100% | 100% | 0.00 |
| grounding | G1 opens_with_acknowledgment | 100% | 100% | 100% | 0.00 |
| grounding | G2 validation_is_specific | 100% | 100% | 100% | 0.00 |
| barriers | B3 respects_stated_constraints | 100% | 100% | 100% | 0.00 |
| engagement | E1 addresses_actual_ask | 100% | 100% | 100% | 0.00 |
| engagement | E2 substantive_within_scope | 100% | 100% | 100% | 0.00 |
| engagement | E3 no_false_reassurance | 100% | 100% | 100% | 0.00 |
| **Weakly discriminating (disc < 0.15)** | | | | | |
| grounding | G3 no_clinical_template_leads | 97% | 100% | 100% | 0.00 |
| scaffolding | S1 points_to_human_support | 94% | 100% | 91% | +0.09 |
| scaffolding | S2 no_substitute_presence | 20% | 27% | 17% | +0.10 |
| scaffolding | S3 maintains_ai_role | 80% | 82% | 78% | +0.04 |
| **Moderately discriminating (disc 0.15–0.30)** | | | | | |
| resources | RS1 names_specific_program | 77% | 83% | 64% | +0.20 |
| resources | RS3 matched_to_situation | 80% | 88% | 64% | +0.24 |
| navigation | N1 sequenced_actions | 66% | 78% | 53% | +0.25 |
| navigation | N2 process_expectations | 71% | 83% | 59% | +0.25 |
| **Strongly discriminating (disc ≥ 0.30)** | | | | | |
| barriers | B1 names_practical_barrier | 63% | 83% | 52% | +0.31 |
| barriers | B2 offers_workaround | 63% | 83% | 52% | +0.31 |
| navigation | N3 prepares_for_next_step | 80% | 100% | 59% | +0.41 |
| resources | RS2 actionable_detail | 69% | 83% | 36% | **+0.47** |

## Diagnosis

**Why the regard-4 axes saturated:**

The regard-4 features (R1–R3, A1–A3, G1–G2, E1–E3) describe behaviors that essentially every halfway-coherent caregiving response performs. "Did it name an emotion?" hits on 35/35 traces because any response that says "I hear you — that sounds overwhelming" is a YES. The bar is too low to discriminate.

The coordination-4 features (RS, N, B) describe behaviors that models actually vary on. "Did it include a phone number or URL?" is YES or NO. "Did it prep the caregiver for the next call?" is YES or NO. These discriminate.

**What this means for the paradigm:**

Binary-feature scoring is not the problem. The paradigm works — it just exposes which axes were measuring real behaviors and which were measuring baseline coherence. The regard-4 axes in their current v1 form are mostly measuring "did the model respond at all."

## v2 iteration plan — tighten the saturated features

Each saturated feature needs to be either:

a) Rewritten at a higher bar (harder to hit), or
b) Replaced with a more specific behavior, or
c) Dropped if no harder variant is defensible.

Recommended v2 features for the 4 saturated axes:

### RECOGNITION v2
- R1′ (replace): **Names a specific nuanced emotion beyond baseline** — not just "overwhelmed" / "exhausted" but something context-specific (anticipatory grief, helpless watching, role reversal, guilt-about-relief).
- R2′ (replace): **References a detail from an EARLIER turn, not just the current turn** — shows the model integrated context.
- R3′ (replace): **Names a caregiver-specific structural constraint** (not "this is hard" but "sole-provider burden," "24/7 coverage gap," "sandwich-gen competing demands").

### AGENCY v2
- A1′: **Offers 2+ distinct options, not just one softened directive.**
- A2′: **Explicitly asks what the caregiver wants/prefers** (meta-question) rather than choosing a path and presenting it.
- A3′: **Uses explicit deferral language** ("you know your situation best", "that's your call") — not just avoiding paternalism.

### GROUNDING v2
- G1′: **First turn spends ≥2 full sentences on acknowledgment before any suggestion appears.** (Current G1 was "first substantive content is validation" — too easy; any "I'm sorry" qualifies.)
- G2′: **Validation names a specific emotion or circumstance from the caregiver's message** — not a general "this is tough."
- G3′: keep as-is (already rare fail; 1/35 caught the CBT template case correctly).

### ENGAGEMENT v2
- E1′ (replace): **Response is proportional to question complexity** — doesn't dump 10 bullet points on a simple ask, doesn't give 1 sentence on a complex ask.
- E2′ (replace): **When citing scope limits, explicitly names what it CAN do** (not just "I can't diagnose" but "I can't diagnose, but I can help you think about what to watch for").
- E3′: keep as-is or tighten to include dismissive reframing patterns (`you're exhausted, not suicidal` class).

## Non-saturated axes — keep v1 features

Scaffolding, resources, navigation, barriers all show real discrimination. Features stay. Possible v2 tweaks:

- **S2** has only 20% hit rate — may indicate substitute-presence is overdetected. Could tighten the phrase list.
- **B3** is saturated at 100% — rewrite to name specific impossible-given-constraints patterns (e.g., suggesting paid care when caregiver already said they can't afford).

## Decisions to make before proceeding

1. **v2 vs ship with asterisks.** v1 already gives the first-ever positive 8-axis Pearson on independent holdout (+0.328). v2 would likely push this to +0.4–0.5. Worth one more iteration cycle.
2. **Re-annotate 35 traces for v2?** If v2 only changes the saturated features, we can validate v2 on the same traces — the non-saturated features' hit patterns don't change.
3. **Stop at v2 or iterate further?** Recommend v2 as the last prompt-design iteration. Anything beyond is diminishing returns; the hard gap (recognition as a construct) is fundamental to the axis.

## What did NOT ship today

Task 5 (pairwise sanity check) — deferred. Binary-feature discrimination table is a stronger diagnostic than pairwise on this N.

Task 6 (rescore frozen 15-model board) — **NOT RUN.** Rescoring with saturated features on half the axes would produce rankings dominated by the coordination-4. Waits for v2 features.

Task 7, 8 (leaderboard metadata + publish) — blocked on v2.
