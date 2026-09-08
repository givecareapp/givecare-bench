# GiveCare Bench

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

InvisibleBench evaluates caregiver-support conversations. It checks Safety and
Care behavior across multi-turn scenarios and keeps the two layers separate.

The active contract is defined by [`benchmark/configs/scoring.yaml`](benchmark/configs/scoring.yaml):

- one LLM judge evaluates every active check against the full conversation;
- every active check gets one `mode_results` entry;
- results use `PASS`, `FAIL`, `UNCLEAR`, or `NOT_APPLICABLE`;
- a `FAIL` includes transcript evidence;
- the public projection uses `safety-care/v2`;
- the projection has no composite score and no model rank.

An optional critique can annotate a completed result. It cannot change a
verdict or block a scan or projection. `UNCLEAR` stays visible.

Use machine-readable files for changing facts:

- [`benchmark/benchmark_inventory.json`](benchmark/benchmark_inventory.json)
  defines the corpus version and inventory.
- [`checks/`](checks/) defines checks, criteria, and evidence requirements.
- [`benchmark/scenarios/`](benchmark/scenarios/) contains the public scenarios.
- [`src/invisiblebench/`](src/invisiblebench/) contains the runtime.

Read the [public documentation](docs/index.md) for the model, method, and
evidence contract.

## Quickstart

Install dependencies and set a provider key:

```bash
uv sync --extra dev
export OPENROUTER_API_KEY=...
```

Generate transcripts. Plan paid work first:

```bash
uv run bench -m your-org/your-model --dry-run
uv run bench -m your-org/your-model -y --max-cost-usd <budget>
```

Create a scan plan, then run the same scan with that plan:

```bash
uv run python scripts/run_scan.py results/run_<id> \
  --dry-run --llm-model openai/gpt-5-mini
uv run python scripts/run_scan.py results/run_<id> \
  --plan <scan-dir>/scan_plan.json \
  --max-cost-usd <budget> --llm-model openai/gpt-5-mini
```

Inspect evidence in a completed scan:

```bash
uv run bench explain your-org/your-model <scenario-id> \
  --failures --scan <scan-dir>/per_run.jsonl
```

## Proof

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
helm evidence driver check --driver evidence-driver.json
```

The local hook runs the repository checks. Public docs use
`scripts/deploy-docs.sh` when an operator chooses to deploy them.

## Repository boundaries

This repository owns the public scenarios, check definitions, judge runtime,
scan artifacts, and separate Safety/Care projection. It does not own GiveCare
product policy, model training, clinical guidance, or real-world outcome
claims.

Private transcripts, scenario text, expected answers, judge prompts,
and credentials stay in protected local or Evidence paths.
The repository does not write into a consumer repository.

Candidate scenario content can move through the human-gated
`evidence-driver.json#corpus.apply` operation. That gate protects content
provenance. It does not approve or change a model verdict. The deterministic
`corpus.project` operation creates the owner projection from a checked score candidate and retained scan.

Committed historical releases keep their original bytes and labels. New
releases use the current contract and a new release version.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the scenario contract, proof
commands, and pull request checks. See [`SECURITY.md`](SECURITY.md) for
private security reports.
