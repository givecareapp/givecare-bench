# Judge Validation Manifest

> **Diátaxis: reference** — factual lookup for InvisibleBench's LLM-as-judge
> infrastructure. For the scoring architecture itself, see
> [scoring-rubric.md](scoring-rubric.md). For methodology rationale, see
> [methodology.md](methodology.md).

## Purpose

InvisibleBench evaluates models using a mix of deterministic scorers and
LLM-as-judge scorers. The judge prompt templates themselves are kept private to
prevent gaming, but the runtime emits **stable prompt-template hashes** with
every scored result so that external readers can verify that two runs used the
same judge template — even without access to the prompt text.

This document lists the judges, their template-hash slots, and the current
status of judge-validation work (TPR/TNR against human-labelled ground truth).
It is the public companion to the benchmark card's "judge validation in
progress" note: this page tracks what is and is not validated.

## Judges in the pipeline

Each scored scenario result carries per-scorer metadata. Only LLM-backed
scorers have a `judge_prompt_hash`; deterministic scorers do not.

| Scorer        | Type          | Role                                                                                 | Has `judge_prompt_hash`? |
|---------------|---------------|--------------------------------------------------------------------------------------|--------------------------|
| `safety`      | LLM judge     | Crisis-gate: binary safety fail for mental-health high-severity triggers             | yes                      |
| `compliance`  | LLM judge     | Structured extraction of diagnosis / prescribing / scope-claim violations            | yes                      |
| `regard`      | LLM judge     | Conversational quality (warmth, attunement, coordination, trauma-informed)           | yes                      |
| `coordination`| Deterministic | Regex-based proxy for coordination signals — no LLM, no hash                         | no                       |
| `memory`      | Deterministic | Probe-based recall/continuity scoring for multi-session scenarios — no LLM, no hash  | no                       |

See `benchmark/configs/prompts/README.md` for the list of required prompt
files and their template variables. The `.txt` files themselves are
gitignored.

## How template hashes are computed

`compute_prompt_template_hash(*parts)` (in
`src/invisiblebench/api/client.py`) takes the static prompt-template text —
*not* the fully rendered per-scenario prompt — and returns a SHA-256 of the
whitespace-normalized join.

This means:

- Editing a judge prompt template produces a **new hash**; old runs and new
  runs are no longer comparable on that judge.
- Changing scenario content does **not** change the hash; per-scenario
  rendering is applied after hashing.
- The hash is a stable identifier for the judge *behavior contract*, not for
  any one invocation.

Every `ScenarioResult` written by the runner includes `judge_prompt_hash` at
the top level (primary judge) and per-dimension hashes inside the individual
scorer outputs. The leaderboard artifacts under `data/leaderboard/` echo the
top-level value for each row.

## Current template hashes

Hashes below are derived from the public leaderboard artifacts
(`data/leaderboard/leaderboard.json`, contract version 2.1.0).

| Judge        | Template hash (SHA-256, first 16)          | Scope                                 | Source                                   |
|--------------|--------------------------------------------|---------------------------------------|------------------------------------------|
| `regard`     | `dc9c89876f57d179…`                        | Primary top-level `judge_prompt_hash` | `data/leaderboard/leaderboard.json`      |
| `safety`     | _pinned per-result under `scorer_details`_ | Not surfaced at leaderboard top level | `scorer_details.safety.judge_prompt_hash`|
| `compliance` | _pinned per-result under `scorer_details`_ | Not surfaced at leaderboard top level | `scorer_details.compliance.judge_prompt_hash` |

To extract per-scorer hashes from a scored run, read the per-scenario result
JSON written by `bench` into `results/<run-id>/`. The raw result payload
preserves scorer-level `judge_prompt_hash` entries that the leaderboard
summary collapses.

## Validation status

Judge validation compares judge verdicts against a human-labelled ground-truth
subset. Each judge is labelled with one of:

- **validated** — TPR and TNR reported against a labelled sample ≥ N.
- **fixed-unvalidated** — prompt template is frozen under its current hash but
  has not yet been measured against labels at the required sample size.
- **in-progress** — labelling or re-scoring work is live; numbers will move.
- **unvalidated** — no labelled comparison has been attempted.

| Judge        | Status               | TPR    | TNR    | Sample size | Hash pin     | Notes                                                                 |
|--------------|----------------------|--------|--------|-------------|--------------|-----------------------------------------------------------------------|
| `safety`     | fixed-unvalidated    | _tbd_  | _tbd_  | _tbd_       | `dc9c8987…`* | Crisis-gate judge; mental-health high-severity triggers only.         |
| `compliance` | fixed-unvalidated    | _tbd_  | _tbd_  | _tbd_       | `dc9c8987…`* | Structured extraction; dominant risk is false-reassurance classification. |
| `regard`     | fixed-unvalidated    | _tbd_  | _tbd_  | _tbd_       | `dc9c8987…`  | Quality judge; known quantization of LLM output to ~5 distinct values.|
| `coordination` | deterministic     | n/a    | n/a    | n/a         | n/a          | Known floor-effect (regex proxy); see methodology.md.                 |
| `memory`     | deterministic        | n/a    | n/a    | n/a         | n/a          | Probe-based; scored against scenario-authored expected strings.       |

`*` safety and compliance expose per-result hashes under
`scorer_details.<scorer>.judge_prompt_hash`; the leaderboard-level hash shown
is the regard/primary judge hash and is not equivalent.

**Close leaderboard deltas should be read cautiously until validation
numbers land.** Differences of a few percentage points between models are
within the plausible noise band of an unvalidated LLM judge.

### Calibration-set apparatus

The TPR/TNR numbers above are blocked on an ongoing human-adjudicated
calibration set. Infrastructure is in place internally: 60 stratified
traces across contested-false-scope, clinical-boundary, crisis, and
clean-pass buckets; per-candidate label templates; an LLM-drafted
"silver" prior; and Cohen-κ machinery for paired annotator agreement.
The set is not yet gold — two independent human adjudication passes
and a conflict-resolution pass are still outstanding before it can
back publication-grade judge validation.

## External reproducibility

A third party who cannot access private prompt text can still:

1. Re-run the benchmark with their own judge prompts and compare top-line
   deltas; absolute numbers will differ.
2. Verify that two published runs used the same judges by comparing
   `judge_prompt_hash` values per-scorer.
3. Fail the run open if any scorer's published hash does not match the
   manifest above: the judge template has shifted.

## Change policy

- Any change to a judge template that would alter `compute_prompt_template_hash`
  output is a breaking change for cross-run comparability and must be reflected
  as a new row in this manifest.
- Validation numbers must be re-measured after any hash change; prior numbers
  do not carry over.
- When validation lands, this document will be updated in the same commit as
  the TPR/TNR tables in `internal/evals/` are published externally.
