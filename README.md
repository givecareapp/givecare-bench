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
It shows Safety and Care verdict counts by check, with flagged evidence and
code-composed rationale. Layer summaries report settled-case coverage; this is
not accuracy. The card also records judge settings, costs, technical errors,
and attributed commentary. Frozen validation expectations add case-level
agreement, errors, and untested coverage.

Each run has two parts in one private directory:

| Part | Contents |
| --- | --- |
| `jury-card.md` | The standard report for the run. |
| Saved evidence | `scan_plan.json`, `answers.jsonl`, `judgments.jsonl`, source manifests, and transcripts. Supports inspection and replay. |

Verdicts are `PASS`, `FAIL`, `UNCLEAR`, or `NOT_APPLICABLE`. Every `FAIL` needs
transcript evidence. `UNCLEAR` stays visible. Commentary can dispute a judgment
without changing the saved verdict.

The card reports model judgments. It does not establish judge accuracy or
clinical outcomes. Care remains directional. Read the
[method](docs/methodology.md) for definitions, rates, and limits.

## Try it in 30 seconds, no keys

```bash
uv sync --extra dev
uv run bench demo
```

This builds a synthetic run over the public scenarios, judges it with a stub
that answers every question "no", and prints a Jury Card. Nothing in it is a
result; it shows you the card, the evidence layout, and the `explain` path
before you spend anything.

## Quickstart

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...   # target models
export TYPESAFE_API_KEY=...     # judge

# 1. Generate transcripts with UK AISI Inspect, bounded per conversation.
uv run inspect eval invisiblebench/safety_care --model openrouter/<catalog-model-id> \
  -M 'provider={"allow_fallbacks": true, "require_parameters": true}' \
  --cost-limit <usd-per-conversation> --log-dir results/<run-id>/inspect
uv run bench export results/<run-id>/inspect/*.eval --output results/<run-id>

# 2. Plan the judge scan (no paid calls), review the estimate, then run it.
uv run bench scan plan results/<run-id>
uv run bench scan run --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>

# 3. Read the evidence.
uv run bench explain <catalog-model-id> <scenario-id> --failures --scan results/<run-id>
```

Models and their prices live in `src/invisiblebench/models/config.py`. The scan
writes `results/<run-id>/jury-card.md`. Repeat `bench scan run` to resume
judging, and use `inspect eval-retry` to resume generation. The
[full quickstart](docs/quickstart.md) covers provider routing, recovery,
rejudging, and publication.

## Validate the evaluator

`uv run python scripts/plan_validation.py --output results/<run-id>` plans
constructed controls without model calls. Run that plan with the budgeted scan
command above. The [validation guide](docs/validation.md) defines the procedure,
each tested boundary, and the limits of the evidence.

## Repository map

| Path | Contents |
| --- | --- |
| `benchmark/` | Public scenarios, inventory, benchmark card, and tests |
| `checks/` | Check definitions and exemplars; grammar in [`checks/README.md`](checks/README.md) |
| `src/invisiblebench/` | Inspect task, export, judge runtime, rules, and projection |
| `scripts/` | Checks, probes, exemplar refresh, and docs tooling |
| `data/` | Committed leaderboard projection and release archive |
| `docs/` | The [published documentation](https://givecareapp.github.io/givecare-bench/) |

Use the [inventory](benchmark/benchmark_inventory.json) for current corpus facts
and the [scan contract](src/invisiblebench/models/scan.py) for artifact fields.

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

See [contribution guidelines](CONTRIBUTING.md) for the scenario contract,
proof commands, and pull request checks. See the [security policy](SECURITY.md) for
private security reports.
