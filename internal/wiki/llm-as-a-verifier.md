# LLM-as-a-Verifier — upstream reference and GiveCare Bench adaptation

## Why this page exists

This page records how GiveCare Bench uses ideas from the upstream
**LLM-as-a-Verifier** repo, what we copied conceptually, and what we changed for
our benchmark.

## Upstream source

Primary reference used during implementation:

- upstream repo: `llm-as-a-verifier`
- local reference snapshot used during development: `/tmp/llm-as-a-verifier.3r9Zkz/`
- key upstream files:
  - `/tmp/llm-as-a-verifier.3r9Zkz/README.md`
  - `/tmp/llm-as-a-verifier.3r9Zkz/scripts/verifier_core.py`

## What the upstream repo is built for

The upstream framework is designed for **trajectory selection** on coding-agent
benchmarks like Terminal-Bench and SWE-bench.

Core upstream pattern:

1. compare multiple candidate trajectories for the same task
2. judge them with an LLM verifier instead of a single scalar judge call
3. decompose evaluation across multiple criteria
4. repeat verification multiple times
5. use a finer-grained score scale instead of a one-shot binary or coarse score
6. aggregate those pairwise comparisons into a tournament winner

In short: upstream is a **pairwise, multi-trajectory reward model**.

## What GiveCare Bench needs instead

GiveCare Bench does **not** need trajectory tournaments.

We need:

- adjudication of **one transcript at a time**
- explicit detection of public hard-fail rules
- scenario-aware interpretation of the transcript contract
- repeated verification for stability
- human-calibrated reference labels for validation

So our adaptation keeps the verifier principles, but changes the task shape.

## The key conceptual carry-overs

From upstream, we intentionally kept these ideas:

### 1. Finer scoring granularity than one-shot judging
We do not rely on a single monolithic "is this good" judgment.
Instead we break the transcript into rule-level and quality-level checks.

### 2. Repeated verification
We run repeated verifier passes and aggregate them, instead of trusting one
verifier completion.

### 3. Criteria decomposition
We separate bright-line public hard fails from softer quality signals.
Within hard fails, we decompose further into individual rule checks.

### 4. Structured outputs
Verifier outputs are schema-shaped and meant to be inspectable, not just prose.

## What we intentionally did **not** copy

### 1. Pairwise trajectory tournaments
Upstream chooses the best candidate among multiple traces for the same task.
GiveCare Bench usually evaluates a single observed transcript, so we do not run
round-robin tournaments.

### 2. Logprob-weighted A–T score extraction
Upstream uses Gemini logprobs over a letter scale. Our verifier work does not use
that exact scoring mechanism.

### 3. Coding-agent task framing
Our unit of analysis is a caregiver-support conversation transcript, not a code
execution trajectory.

## Our local implementation

### Core verifier pack
- `internal/evals/verifier/README.md`
- `internal/evals/verifier/benchmark_governance.md`
- `internal/evals/verifier/core_rubric.md`
- `internal/evals/verifier/taxonomy.md`
- `internal/evals/verifier/output_schema.json`

### Prompting
- `internal/evals/verifier/prompts/single_trace.md`
- `internal/evals/verifier/prompts/decomposed_single_trace.md`
- `internal/evals/verifier/prompts/scenario_batch.md`
- `internal/evals/verifier/prompts/rule_batch.md`

### Scenario-aware reference material
- `internal/evals/verifier/scenario_contracts/`

### Corpus / batch tooling
- `scripts/generate_verifier_corpus.py`
- `scripts/run_claude_verifier.py`
- `src/invisiblebench/utils/verifier_batches.py`

### Repeated decomposed verifier
- `scripts/run_golden_verifier.py`
- `src/invisiblebench/utils/golden_verifier.py`

### Human calibration / gold-set workflow
- `internal/evals/verifier/golden_set/README.md`
- `internal/evals/verifier/golden_set/annotator_walkthrough.md`
- `scripts/golden_set_kappa.py`

## Current GiveCare Bench verifier shape

The current verifier stack has two related but distinct modes.

### A. Scenario-batch verifier mode
Used for auditing slices of the frozen corpus.

Typical flow:

1. generate corpus manifest
2. select a scenario family or tranche
3. build prompt payloads from transcripts + scorer outputs
4. run an LLM verifier over the batch
5. compare verifier outputs against current scorer verdicts

Representative command:

```bash
uv run python scripts/run_claude_verifier.py --scenario-id tier1_scope_honesty_001 --prepare-only
```

### B. Golden-set repeated verifier mode
Used for calibration against human annotation.

Typical flow:

1. use the 60-trace golden set
2. run repeated decomposed single-trace verification
3. aggregate deterministic rule-level outputs
4. compare against `annotator_a` now, then resolved gold later

Representative command:

```bash
uv run python scripts/run_golden_verifier.py --model sonnet --repeat 2 --label-name ai_verifier_v2 --score-against annotator_a
```

## The central local adaptation

The core GiveCare Bench move is:

> upstream verifier ideas, but applied to **single-trace transcript adjudication**
> instead of **pairwise trajectory ranking**.

That means our verifier answers questions like:

- did this transcript hard-fail a public rule?
- if yes, which rule?
- what quote supports that rule?
- how did quality dimensions look if no public hard fail occurred?

—not:

- which of five candidate trajectories is best?

## How the decomposed verifier is structured locally

In the current repeated verifier path, the verifier focuses heavily on:

- explicit `rule_checks`
- repeated passes
- deterministic aggregation
- evidence-carrying rationales

This is why the local implementation lives partly in prompts and partly in code:

- prompt decomposition supplies semantic structure
- aggregation code turns repeated outputs into a stable verdict

## Calibration source of truth

Current hierarchy:

- `labels/ai_silver/` — draft only, not authoritative
- `labels/annotator_a/` — first human pass
- `labels/annotator_b/` — second independent human pass, when available
- `labels/gold/` — final resolved labels after disagreement resolution

Until resolved gold exists, the verifier is calibrated primarily against
`annotator_a`, not formal gold.

## Important local assumptions

Safe assumptions:

- the verifier is an **internal adjudication layer**, not the benchmark harness
- repeated decomposition is the preferred verifier pattern in this repo
- human calibration is required before strong verifier claims
- public hard-fail detection is the most mature verifier surface today

Unsafe assumptions:

- that we copied the upstream verifier literally
- that our verifier is pairwise or tournament-based
- that current `ai_silver` labels are gold
- that soft issues are as reliable as public hard-fail labels

## Current limitations / open gaps

- one remaining medication-language ambiguity still exists in the dev set
- soft issues are noisier than public hard fails
- resolved `labels/gold/` still depend on a second human annotation pass
- broader calibration coverage is still thinner than the core public hard-fail set

## If you need to re-orient quickly

Start here, in order:

1. `internal/evals/verifier/README.md`
2. `internal/evals/verifier/benchmark_governance.md`
3. `internal/evals/verifier/core_rubric.md`
4. `internal/evals/verifier/taxonomy.md`
5. `internal/evals/verifier/golden_set/README.md`
6. `src/invisiblebench/utils/golden_verifier.py`
7. `scripts/run_golden_verifier.py`

That path gets you from upstream-inspired concept to actual GiveCare Bench
implementation.
