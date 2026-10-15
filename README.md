# Invisible Bench

Type: how-to.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Invisible Bench evaluates caregiver-support conversations and produces a Jury
Card for each completed scan.** Use the `bench` CLI from the `invisiblebench`
Python package.

One judge path evaluates each active check: yes/no questions answered as
probabilities, and a code-owned rule that derives the verdict from the saved
answers. Safety and Care stay separate. There is no composite score or model
rank.

Read the [paper on arXiv](https://arxiv.org/abs/2511.20733) and the
[published documentation](https://givecareapp.github.io/givecare-bench/).
The paper describes the original benchmark. The documentation describes the
current method. Use [CITATION.cff](CITATION.cff) to cite the paper.

## What a run produces

A **Jury Card** complements a model card with evidence from a specific run.
It shows model results and quoted evidence beside each verdict and its
code-composed rationale. It also records judge settings, costs, technical
errors, and attributed commentary. Frozen validation expectations add case-level
agreement, errors, and untested coverage. Human review remains optional.

Each run has two parts in one private directory:

| Part | Contents |
| --- | --- |
| `jury-card.md` | The standard report. Replaces separate per-run reports and scorecard exports. |
| Saved evidence | `scan_plan.json`, `answers.jsonl`, `judgments.jsonl`, source manifests, and transcripts. Supports inspection and replay. |

Verdicts are `PASS`, `FAIL`, `UNCLEAR`, or `NOT_APPLICABLE`. Every `FAIL` needs
transcript evidence. `UNCLEAR` stays visible. Commentary can dispute a judgment
without changing the saved verdict.

The card reports model judgments. It does not establish judge accuracy or
clinical outcomes. Care remains directional. Read the
[method](docs/methodology.md) for definitions, rates, and limits.

## Quickstart

Install dependencies. Set the provider key for transcripts and the TypeSafe key
for judging:

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
export TYPESAFE_API_KEY=...
```

Generate transcripts with UK AISI Inspect. Pick a catalog model from
`src/invisiblebench/models/config.py`. Inspect bounds spend with a cost limit
per conversation, so the worst case is conversations times that limit. Then
export the Inspect logs into a judge-ready run directory:

```bash
uv run inspect eval invisiblebench/safety_care --model openrouter/<catalog-model-id> \
  -M 'provider={"allow_fallbacks": true, "require_parameters": true}' \
  --cost-limit <usd-per-conversation> --log-dir results/<run-id>/inspect
uv run bench export results/<run-id>/inspect/*.eval --output results/<run-id>
```

Find the run ID with `uv run bench runs`. Replace `<run-id>` below with that
directory name. Create a scan plan, then review its estimate before running
it. `--llm-model` defaults to the pinned judge model in
`src/invisiblebench/api/typesafe.py`:

```bash
uv run bench scan plan results/<run-id> \
  --llm-model <judge>
uv run bench scan run \
  --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>
```

Completion writes `results/<run-id>/jury-card.md`. Inspect the run and its evidence:

```bash
uv run bench get <run-id>
uv run bench explain <catalog-model-id> <scenario-id> \
  --failures --scan results/<run-id>
```

Each run lives in `results/<run-id>/`, named by its UTC start time in
`YYYY-MM-DD_HH-MM-SSZ` form. Each new run gets its own directory, including runs
of the same model. The card title shows the model and a readable UTC date.
Historical runs live under `results/archive/`.

Repeat the scan command to resume unfinished judgments. A request with an
unknown outcome blocks automatic resume. Resume generation with
`inspect eval-retry`. The
[full quickstart](docs/quickstart.md) explains recovery for both generation
and judging. Use `uv run bench jury
<run-id>` to regenerate the card from saved evidence without model calls.
See the [full quickstart](docs/quickstart.md) to judge saved responses again or
replay a scan.

## Validate the evaluator

Plan constructed controls without model calls, then judge the saved plan with
the budgeted scan command above. The [validation guide](docs/validation.md)
defines the procedure, each tested boundary, and the limits of the evidence.

## Repository map

See the Layout table in [`AGENTS.md`](AGENTS.md). Use the
[inventory](benchmark/benchmark_inventory.json) for current corpus facts and the
[scan contract](src/invisiblebench/models/scan.py) for artifact fields.

## Proof

Run `scripts/check.sh`.

Enable the required local hook with `git config core.hooksPath .githooks`.

## Repository boundaries

This repository owns the public scenarios, check definitions, judge runtime,
scan artifacts, and separate Safety/Care projection. It does not own GiveCare
product policy, model training, clinical guidance, or real-world outcome
claims.

The judge questions are public in `checks/`. Private transcripts, private
scenarios, expected answers, and credentials stay in local storage. Public releases contain aggregate
results with recorded provenance.

Committed historical releases keep their original bytes and labels. New
releases use the current contract and a new release version.
Historical web evidence remains in `data/releases/web-bench-release.tar.gz`.

## Contributing

See [contribution guidelines](.github/CONTRIBUTING.md) for the scenario contract,
proof commands, and pull request checks. See the [security policy](.github/SECURITY.md) for
private security reports.
