# Quickstart

Type: how-to.

Generate transcripts with Inspect, judge them with a planned and budgeted scan,
then read the evidence. Generation and judging each have their own cost ceiling.

## Install

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
export TYPESAFE_API_KEY=...
```

A live run needs both keys and both hosts. OpenRouter serves the target models.
TypeSafe serves the judge, and it also decides branches in scenarios that branch
during generation. A key does not prove network access, so check that both hosts
answer from the machine that will run the scan:

```bash
curl --head --max-time 20 https://openrouter.ai/
curl --head --max-time 20 https://api.typesafe.ai/
```

An HTTP response proves only that the host answered. A 401, 403, or proxy error
still needs investigation. Only a small pilot run proves that inference works.
Run one first and read its saved responses before a broader run.

`uv run bench doctor` checks credentials and run storage.

## Generate transcripts

Generation runs through UK AISI Inspect (`inspect_ai`). Pick a model from
`src/invisiblebench/models/config.py`. To add a model, add it there with verified
provider prices. Loading the task registers those prices with Inspect, so
`--cost-limit` works for every roster model.

```bash
uv run inspect eval invisiblebench/safety_care --model openrouter/<catalog-model-id> \
  -M 'provider={"allow_fallbacks": true, "require_parameters": true}' \
  --cost-limit <usd-per-conversation> --log-dir results/<run-id>/inspect
uv run bench export results/<run-id>/inspect/*.eval --output results/<run-id>
```

- Task options use `-T`: `category=`, `scenario=`, and `confidential=true`.
- Concurrency uses Inspect's `--max-samples` and `--max-connections`.
- `inspect view` browses runs.
- `--cost-limit` is a per-conversation ceiling checked against reported usage.
  A target-model call can cross it once before Inspect stops that sample. A
  scenario with judged branches requires this limit; each branch request is
  checked against its maximum input cost before dispatch, and reported branch
  usage is included in the exported generation cost. If usage is unknown, the
  sample records that uncertainty and Inspect reserves the request maximum.
- To resume a failed generation, run `inspect eval-retry <log>`, then repeat
  `bench export`. Inspect owns retries, timeouts, and transport.

`bench export` writes `results/<run-id>/`. The run ID is a UTC timestamp in
`YYYY-MM-DD_HH-MM-SSZ` form, and each run gets its own directory. Model identity
lives in the manifest and the Jury Card, not in the directory name.

### Provider routing

A model can set an optional `endpoint`: an exact OpenRouter provider slug.

- With fallbacks allowed, the run measures the **routed service**.
- To pin one provider, pass `"only": ["<slug>"], "allow_fallbacks": false` in the
  `-M provider=` object.

Both modes require providers that support the supplied generation parameters.
`bench export` checks the generation settings against the roster policy and
records the policy per model under `transcript_policy.serving`. The providers
that actually served each reply stay in the transcript metadata.

Verify an endpoint's availability and prices before you pin it. A base slug can
match several variants or regions, so an endpoint-specific study needs the full
slug. Never infer a single-provider comparison from a model name.

## Judge the transcripts

Plan the scan first. Planning makes no paid calls and prints an estimate. Then
run the plan with an explicit ceiling. `--llm-model` defaults to the judge model
pinned in `src/invisiblebench/api/typesafe.py`.

```bash
uv run bench scan plan results/<run-id> --llm-model <judge>
uv run bench scan run --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>
```

### Add product development checks

Keep owner-local checks outside the public `checks/` registry. Add them to the
same scan with their directory:

```bash
uv run bench scan plan results/<run-id> --output results/<new-run-id> \
  --supplemental-checks <owner-check-directory>
```

The planner retains every canonical check and freezes the added YAML files in
the existing input bundle. Duplicate IDs are rejected. Execution verifies those
files and the current canonical checks before making calls. Rejudging retains
the same frozen definitions. Supplemental checks make the scan ineligible for
public projection; they do not change the public standard.

The scan format is `invisiblebench-scan/v4`. Keep historical bundles unchanged
and use their recorded engine for replay. A new engine needs a new plan.

### Scan artifacts

The run directory then holds everything needed to replay the scan:

```text
results/<run-id>/
├── jury-card.md         # standard report, written when judging completes
├── scan_plan.json       # frozen checks, questions, thresholds, and input hashes
├── attempts.jsonl       # each judge request, recorded before dispatch
├── answers.jsonl        # one saved record per judge request (probabilities, cost)
├── judgments.jsonl      # one verdict per conversation and check, derived from answers.jsonl
├── run_manifest.json
├── transcript_run.json
└── transcripts/
```

The Jury Card and this evidence bundle are the two outputs of a run. The public
leaderboard is a separate projection across runs.

Planning groups questions that share identical evidence and splits groups to fit
the judge's context limit. Each request is checked again before dispatch. Evidence
is never truncated or summarized, so an observation too long for the limit is
rejected.

### Resume a scan

Each request is written to `attempts.jsonl` before dispatch, and its answer is
written to `answers.jsonl` before the next request. To resume, repeat the same
`bench scan run` command. Completed requests are kept.

Resume retries a request only when its outcome and cost are known: a budget
refusal before dispatch, or an invalid answer with reported usage. Any other
error after dispatch leaves the outcome unknown, because a missing answer does
not prove there was no charge. That includes interruptions, timeouts, dropped
connections, HTTP errors, and answers without reported usage. It stops automatic
resume. Keep the blocked bundle for inspection, and plan a new scan from the same
transcripts:

```bash
uv run bench scan plan results/<run-id> --output results/<new-run-id>
```

`UNCLEAR` verdicts are complete results, not failures to resume.

### Judge again or compare

To judge the same frozen evidence with a different judge:

```bash
uv run bench scan rejudge results/<run-id> --output results/<new-run-id> \
  --llm-model <judge>
```

Review the estimate, then run it with `bench scan run`. The new bundle keeps its
source files under `inputs/<source-hash>/`. Keep those relative paths intact,
because the frozen plan refers to them.

- `bench compare --old results/<old-run> --new results/<new-run>` reports verdict changes,
  applicability, coverage, uncertainty, and cost on unchanged transcripts. Add
  `--expectations <file.jsonl>` to report agreement with frozen expectations.
  Read [Evaluator validation](validation.md) before treating that agreement as
  accuracy.
- `bench questions <run-id>` ranks observation families by how many unresolved
  verdicts they affect. `bench --json questions <run-id>` gives exact
  conversation, turn, and observation references.

To replay a historical scan, use a source checkout at the engine version
recorded in its plan, and keep its bundle unchanged. New judging needs a new
plan; old plans are not migrated.

## Read the evidence

```bash
uv run bench explain <model-id> <scenario-id> --failures --scan results/<run-id>
uv run bench runs
uv run bench get <run-id>
uv run bench jury <run-id>
```

`bench jury` regenerates the Jury Card without model calls. It keeps the card's
marked commentary section when the plan and ledger hashes still match. Put the
author, date, observation, and check or turn references there. Commentary never
changes a verdict. The card quotes conversations, so keep it private.

To archive a run, move its whole directory into `results/archive/` with `mv`.

## Publish a projection

Publication is one step from a complete, current scan. The projection script
recomputes the scorecard, runs strict publication checks, and writes
`data/leaderboard/leaderboard.json` and `data/releases/web-bench-release.tar.gz`.
It needs no provider key. Preview first:

```bash
uv run python -m invisiblebench.projection --bundle results/<run-id> --dry-run
```

The preview prints the scan's plan and judgments SHA-256 values and, for each
output, its SHA-256 before and after. A reviewer uses these values to tie the
Git change to the scan. Check `expected_effects`, then drop `--dry-run` to write.

The script rejects a scan that is incomplete, was planned under a different
benchmark, check, or judge version, or has a dirty or missing `git_sha`.

- Separate model runs can share a publication when their code and common
  generation settings match.
- Each model needs one consistent serving policy. Conflicting policies for one
  model are rejected, not merged.
- Missing scenario coverage is an error.

The write is atomic and digest-verified. The archive holds only the aggregate
leaderboard and its manifest, never conversations, judge answers, or private
intake. Review and commit the outputs. The script does not push or deploy.

The current schemas are `safety-care/v6` and `gc-bench.web-benchmark-release/v5`.
A consumer must check both before it reads a release. Results from an older
method stay results under that method.

## Verify

Run `scripts/check.sh` before you share an artifact.

After a refactor, replay a frozen current-format scan without API calls:

```bash
uv run python scripts/rescore_diff.py --frozen <scan-dir>
```

Replay re-derives verdicts from the frozen plan and the saved answers. It does
not call the judge again. A scan from a retired format needs a new run.
