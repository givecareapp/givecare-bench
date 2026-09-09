# Contributing

Contributions should keep the benchmark contract small and inspectable.

## Welcome changes

- public scenarios under `benchmark/scenarios/`;
- check criteria and evidence requirements under `checks/`;
- fixes to the single LLM judge path;
- focused tests for runtime and artifact behavior;
- documentation updates that match machine-readable sources.

Do not publish confidential scenarios, private transcripts, expected answers,
judge prompts, credentials, or provider secrets.

## Setup

```bash
git clone https://github.com/givecareapp/givecare-bench
cd givecare-bench
uv sync --extra dev
cp .env.example .env
uv run bench doctor
```

## Proof

```bash
uv run ruff check .
uv run pytest benchmark/tests -q
uv run python scripts/lint_turn_indices.py --strict
```

Configure the local hook with:

```bash
git config core.hooksPath .githooks
```

## Scenario contract

Scenario JSON files live under `benchmark/scenarios/`. Use the canonical
`category` field. Retired tier fields are invalid. Use the unified `criteria`
shape for check rubrics. See
[`SCENARIO_SCHEMA.yaml`](../benchmark/scenarios/SCENARIO_SCHEMA.yaml).

Run focused checks before opening a change:

```bash
uv run python scripts/lint_turn_indices.py --strict
uv run pytest benchmark/tests/unit/test_scenario_validator.py \
  benchmark/tests/unit/test_scenario_models.py -q
```

## Running a scan

Follow the [quickstart](../docs/quickstart.md) to generate transcripts, plan a scan,
and inspect its Jury Card. Plan each paid step first. Set an explicit
`--max-cost-usd` for each live command.

The plan and live run must use the same transcript source and judge model.
Every active check uses the same LLM judge path. Optional critique cannot
change the result.

## Pull request checklist

- [ ] `uv run ruff check .` passes.
- [ ] `uv run pytest benchmark/tests -q` passes.
- [ ] `uv run python scripts/lint_turn_indices.py --strict` passes.
- [ ] The change updates machine-readable inventory or contract files when
      behavior or version changes.
- [ ] New behavior has a focused test when the test proves a required contract.
- [ ] Public docs match the current contract.
- [ ] No private data or secrets enter the change.
- [ ] The commit message uses the Conventional Commits format.

Report security issues through [`SECURITY.md`](SECURITY.md). Open other bugs
and feature requests in GitHub Issues.
