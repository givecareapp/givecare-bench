# Invisible Bench

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Invisible Bench evaluates caregiver-support conversations and produces a Jury
Card for each completed scan.** Use the `bench` CLI from the `invisiblebench`
Python package.

One LLM judge checks the full conversation against each active criterion.
Safety and Care stay separate. There is no composite score or model rank.

Read the [published documentation](https://givecareapp.github.io/givecare-bench/).

## What a run produces

A **Jury Card** complements a model card with evidence from a specific run.
It shows model results and quoted evidence beside the judge's verdicts and
rationales. It also records judge settings, costs, technical errors, and
attributed commentary.

Each run has two parts in one private directory:

| Part | Contents |
| --- | --- |
| `jury-card.md` | The standard report. Replaces separate per-run reports and scorecard exports. |
| Saved evidence | `scan_plan.json`, `judgments.jsonl`, source manifests, and transcripts. Supports inspection and replay. |

Verdicts are `PASS`, `FAIL`, `UNCLEAR`, or `NOT_APPLICABLE`. Every `FAIL` needs
transcript evidence. `UNCLEAR` stays visible. Commentary can dispute a judgment
without changing the saved verdict.

The card reports model judgments. It does not establish judge accuracy or
clinical outcomes. Care remains directional. Read the
[method](docs/methodology.md) for definitions, rates, and limits.

## Quickstart

Install dependencies and set a provider key:

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
```

Generate transcripts. Review the dry-run estimate before setting a cost ceiling:

```bash
uv run bench -m your-org/your-model --dry-run
uv run bench -m your-org/your-model -y --max-cost-usd <budget>
```

Find the run ID with `uv run bench runs`. Replace `<run-id>` below with that
directory name. Create a scan plan, then review its estimate before running it:

```bash
uv run python scripts/run_scan.py plan results/<run-id> \
  --llm-model openai/gpt-5-mini
uv run python scripts/run_scan.py run \
  --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>
```

Completion writes `results/<run-id>/jury-card.md`. Inspect the run and its evidence:

```bash
uv run bench get <run-id>
uv run bench explain your-org/your-model <scenario-id> \
  --failures --scan results/<run-id>
```

Each run lives in `results/<run-id>/`, named by its UTC start time in
`YYYY-MM-DD_HH-MM-SSZ` form. Each new run gets its own directory, including runs
of the same model. The card title shows the model and a readable UTC date.
Historical runs live under `results/archive/`.

Repeat the scan command to resume unfinished judgments. Use `uv run bench jury
<run-id>` to regenerate the card from saved evidence without model calls.
See the [full quickstart](docs/quickstart.md) to judge saved responses again or
replay a scan.

## Repository map

| Path | Purpose |
| --- | --- |
| [`benchmark/`](benchmark/README.md) | Scenario corpus, inventory, and tests |
| [`checks/`](checks/) | Criteria and evidence requirements |
| [`src/invisiblebench/`](src/invisiblebench/) | Runtime, CLI, and Jury Card generation |
| [`scripts/`](scripts/) | Scan, validation, intake, and release commands |
| [`docs/`](docs/index.md) | Method and run guides |
| [`data/`](data/) | Committed projections and retained release artifacts |

Use the [inventory](benchmark/benchmark_inventory.json) for current corpus facts
and the [scan contract](src/invisiblebench/models/scan.py) for artifact fields.

## Proof

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
```

Enable the required local hook with `git config core.hooksPath .githooks`.
Public docs use
`scripts/deploy-docs.sh` when an operator chooses to deploy them.

## Repository boundaries

This repository owns the public scenarios, check definitions, judge runtime,
scan artifacts, and separate Safety/Care projection. It does not own GiveCare
product policy, model training, clinical guidance, or real-world outcome
claims.

Private transcripts, private scenarios, expected answers, judge prompts,
and credentials stay in local storage. Public releases contain aggregate
results with recorded provenance.

Committed historical releases keep their original bytes and labels. New
releases use the current contract and a new release version.
Historical web evidence remains in `data/releases/web-bench-release.tar.gz`.
Local release-watch reports stay under gitignored `delivery/watch/`.

## Contributing

See [contribution guidelines](.github/CONTRIBUTING.md) for the scenario contract,
proof commands, and pull request checks. See the [security policy](.github/SECURITY.md) for
private security reports.
