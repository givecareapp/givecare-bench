# Binary-feature regard judge vs holdout gold

- judge model: `google/gemini-2.5-flash-lite`
- prompt hash: `0e77009ca98a14c5649648cc5fad6667e5bb1003ee809d34576ea14a397d1950`
- traces scored: `35`
- runtime: `140.0s`

## Overall regard (derived mean)

- 4-axis (recognition/agency/grounding/scaffolding) Pearson: **-0.126** (full), **-0.115** (pass-only, n=24)
- 8-axis (all) Pearson: **+0.168** (full), **+0.083** (pass-only)

## Per-axis vs gold (derived Likert: 3/3=pass, 1/3 or 2/3=mixed, 0/3=fail)

- **recognition**: exact-match 65.7%, ordered-κ +0.000 — mixed→pass:12, pass→pass:23
- **agency**: exact-match 57.1%, ordered-κ +0.000 — mixed→pass:15, pass→pass:20
- **grounding**: exact-match 48.6%, ordered-κ +0.000 — fail→pass:3, mixed→pass:15, pass→pass:17
- **scaffolding**: exact-match 42.9%, ordered-κ +0.107 — fail→pass:1, mixed→mixed:4, mixed→pass:19, pass→pass:11
- **resources**: exact-match 60.0%, ordered-κ +0.164 — mixed→fail:3, mixed→mixed:2, mixed→pass:6, pass→fail:5, pass→pass:19
- **navigation**: exact-match 22.9%, ordered-κ +0.020 — mixed→fail:10, mixed→mixed:2, mixed→pass:5, pass→fail:7, pass→mixed:5, pass→pass:6
- **barriers**: exact-match 74.3%, ordered-κ +0.481 — mixed→mixed:16, mixed→pass:7, pass→mixed:2, pass→pass:10
- **engagement**: exact-match 57.1%, ordered-κ +0.060 — fail→pass:2, mixed→mixed:1, mixed→pass:13, pass→pass:19

## Interpretation

- `exact-match`: fraction of traces where derived Likert == gold Likert.
- `ordered-κ`: ordered-weighted Cohen's kappa; 0 = chance, 1 = perfect.
- Gold `mixed` means either A and B disagreed OR they both rated `mixed`; derived `mixed` means 1 or 2 of the 3 features hit. These definitions differ, so exact-match rates below ~60% on `mixed`-heavy axes are expected.

_Generated 2026-04-23 02:42:00 UTC_
