# Binary-feature regard judge vs holdout gold

- judge model: `anthropic/claude-sonnet-4.5`
- prompt hash: `0e77009ca98a14c5649648cc5fad6667e5bb1003ee809d34576ea14a397d1950`
- traces scored: `35`
- runtime: `583.4s`

## Overall regard (derived mean)

- 4-axis (recognition/agency/grounding/scaffolding) Pearson: **+0.119** (full), **+0.030** (pass-only, n=24)
- 8-axis (all) Pearson: **+0.328** (full), **+0.172** (pass-only)

## Per-axis vs gold (derived Likert: 3/3=pass, 1/3 or 2/3=mixed, 0/3=fail)

- **recognition**: exact-match 65.7%, ordered-κ +0.000 — mixed→pass:12, pass→pass:23
- **agency**: exact-match 57.1%, ordered-κ +0.000 — mixed→pass:15, pass→pass:20
- **grounding**: exact-match 48.6%, ordered-κ +0.046 — fail→mixed:1, fail→pass:2, mixed→pass:15, pass→pass:17
- **scaffolding**: exact-match 60.0%, ordered-κ +0.099 — fail→mixed:1, mixed→fail:1, mixed→mixed:18, mixed→pass:4, pass→mixed:8, pass→pass:3
- **resources**: exact-match 62.9%, ordered-κ +0.288 — mixed→fail:4, mixed→mixed:3, mixed→pass:4, pass→fail:3, pass→mixed:2, pass→pass:19
- **navigation**: exact-match 48.6%, ordered-κ +0.196 — mixed→fail:5, mixed→mixed:4, mixed→pass:8, pass→mixed:5, pass→pass:13
- **barriers**: exact-match 60.0%, ordered-κ +0.260 — mixed→mixed:11, mixed→pass:12, pass→mixed:2, pass→pass:10
- **engagement**: exact-match 54.3%, ordered-κ +0.000 — fail→pass:2, mixed→pass:14, pass→pass:19

## Interpretation

- `exact-match`: fraction of traces where derived Likert == gold Likert.
- `ordered-κ`: ordered-weighted Cohen's kappa; 0 = chance, 1 = perfect.
- Gold `mixed` means either A and B disagreed OR they both rated `mixed`; derived `mixed` means 1 or 2 of the 3 features hit. These definitions differ, so exact-match rates below ~60% on `mixed`-heavy axes are expected.

_Generated 2026-04-23 00:14:05 UTC_
