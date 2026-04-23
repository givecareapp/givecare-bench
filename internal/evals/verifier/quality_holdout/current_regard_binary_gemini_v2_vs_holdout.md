# Binary-feature regard judge vs holdout gold

- judge model: `google/gemini-2.5-flash-lite`
- prompt hash: `cfd67342be93de8821603f866b010932f1f5f5df9c05da13d8c9ab5946321cf4`
- traces scored: `35`
- runtime: `143.4s`

## Overall regard (derived mean)

- 4-axis (recognition/agency/grounding/scaffolding) Pearson: **+0.197** (full), **+0.026** (pass-only, n=24)
- 8-axis (all) Pearson: **+0.236** (full), **+0.212** (pass-only)

## Per-axis vs gold (derived Likert: 3/3=pass, 1/3 or 2/3=mixed, 0/3=fail)

- **recognition**: exact-match 40.0%, ordered-κ +0.068 — mixed→fail:4, mixed→mixed:4, mixed→pass:4, pass→fail:1, pass→mixed:12, pass→pass:10
- **agency**: exact-match 60.0%, ordered-κ +0.169 — mixed→mixed:7, mixed→pass:8, pass→mixed:6, pass→pass:14
- **grounding**: exact-match 45.7%, ordered-κ -0.008 — fail→mixed:1, fail→pass:2, mixed→mixed:2, mixed→pass:13, pass→mixed:3, pass→pass:14
- **scaffolding**: exact-match 40.0%, ordered-κ +0.079 — fail→pass:1, mixed→mixed:3, mixed→pass:20, pass→pass:11
- **resources**: exact-match 54.3%, ordered-κ +0.140 — mixed→fail:4, mixed→mixed:1, mixed→pass:6, pass→fail:3, pass→mixed:3, pass→pass:18
- **navigation**: exact-match 17.1%, ordered-κ -0.066 — mixed→fail:9, mixed→mixed:3, mixed→pass:5, pass→fail:7, pass→mixed:8, pass→pass:3
- **barriers**: exact-match 82.9%, ordered-κ +0.634 — mixed→mixed:19, mixed→pass:4, pass→mixed:2, pass→pass:10
- **engagement**: exact-match 57.1%, ordered-κ +0.060 — fail→pass:2, mixed→mixed:1, mixed→pass:13, pass→pass:19

## Interpretation

- `exact-match`: fraction of traces where derived Likert == gold Likert.
- `ordered-κ`: ordered-weighted Cohen's kappa; 0 = chance, 1 = perfect.
- Gold `mixed` means either A and B disagreed OR they both rated `mixed`; derived `mixed` means 1 or 2 of the 3 features hit. These definitions differ, so exact-match rates below ~60% on `mixed`-heavy axes are expected.

_Generated 2026-04-23 02:44:24 UTC_
