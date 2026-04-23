# Binary-feature regard judge vs holdout gold

- judge model: `anthropic/claude-sonnet-4.5`
- prompt hash: `cfd67342be93de8821603f866b010932f1f5f5df9c05da13d8c9ab5946321cf4`
- traces scored: `35`
- runtime: `689.5s`

## Overall regard (derived mean)

- 4-axis (recognition/agency/grounding/scaffolding) Pearson: **+0.449** (full), **+0.231** (pass-only, n=24)
- 8-axis (all) Pearson: **+0.579** (full), **+0.472** (pass-only)

## Per-axis vs gold (derived Likert: 3/3=pass, 1/3 or 2/3=mixed, 0/3=fail)

- **recognition**: exact-match 62.9%, ordered-κ +0.192 — mixed→mixed:6, mixed→pass:6, pass→mixed:7, pass→pass:16
- **agency**: exact-match 48.6%, ordered-κ +0.113 — mixed→fail:1, mixed→mixed:13, mixed→pass:1, pass→mixed:16, pass→pass:4
- **grounding**: exact-match 51.4%, ordered-κ +0.093 — fail→mixed:1, fail→pass:2, mixed→mixed:1, mixed→pass:14, pass→pass:17
- **scaffolding**: exact-match 65.7%, ordered-κ +0.228 — fail→mixed:1, mixed→fail:1, mixed→mixed:19, mixed→pass:3, pass→mixed:7, pass→pass:4
- **resources**: exact-match 60.0%, ordered-κ +0.275 — mixed→fail:5, mixed→mixed:2, mixed→pass:4, pass→fail:3, pass→mixed:2, pass→pass:19
- **navigation**: exact-match 42.9%, ordered-κ +0.148 — mixed→fail:6, mixed→mixed:4, mixed→pass:7, pass→mixed:7, pass→pass:11
- **barriers**: exact-match 74.3%, ordered-κ +0.462 — mixed→mixed:17, mixed→pass:6, pass→mixed:3, pass→pass:9
- **engagement**: exact-match 51.4%, ordered-κ -0.051 — fail→pass:2, mixed→pass:14, pass→mixed:1, pass→pass:18

## Interpretation

- `exact-match`: fraction of traces where derived Likert == gold Likert.
- `ordered-κ`: ordered-weighted Cohen's kappa; 0 = chance, 1 = perfect.
- Gold `mixed` means either A and B disagreed OR they both rated `mixed`; derived `mixed` means 1 or 2 of the 3 features hit. These definitions differ, so exact-match rates below ~60% on `mixed`-heavy axes are expected.

_Generated 2026-04-23 00:43:49 UTC_
