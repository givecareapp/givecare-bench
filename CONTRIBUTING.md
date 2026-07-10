# Contributing

Thanks for your interest in GiveCare Bench. This guide covers what kinds of
contributions are welcome, how to set up the dev environment, and what a
valid PR looks like.

## What's welcome

- **Scenario additions or improvements** — new public scenarios under
  `benchmark/scenarios/`, or fixes to existing rubrics. See the
  [scenario contract](#scenario-contract) below.
- **Verifier bug fixes** — the executable checks live in `checks/`, with
  verifier code under `src/invisiblebench/evaluation/verifiers/`. Add or
  update focused unit tests under `benchmark/tests/unit/` alongside any fix.
- **Docs** — tutorials, clarifications, typos. Follow the Diátaxis types
  declared in [`CLAUDE.md`](CLAUDE.md).
- **Test coverage** — focused regressions for benchmark contracts and runtime behavior.

## What's not welcome

- Publication of confidential holdout scenarios, private transcripts, or
  credentials. Public judge prompts are embedded in
  `checks/<layer>/<dimension>/<ID>.yaml` as `prompt:` blocks.
- Benchmark version bumps without maintainer sign-off. The public contract
  version lives in `benchmark/benchmark_card.json`.

## Dev setup

```bash
git clone https://github.com/givecareapp/givecare-bench
cd givecare-bench
uv sync --extra dev --extra analytics
cp .env.example .env   # then fill in at least one LLM provider key
uv run bench doctor    # verifies env + runs_dir
```

Full install guidance (including how to put `bench` on PATH from any
folder): [docs/install.md](docs/install.md).

## Running tests and lint

```bash
uv run pytest benchmark/tests -q
uv run ruff check .
uv run python scripts/lint_turn_indices.py --strict
```

All three must pass. Checks run via a local pre-commit hook — one-time setup:

```bash
git config core.hooksPath .githooks
```

The hook runs ruff, lint_turn_indices, and pytest automatically on commit. Docs deploy locally via `scripts/deploy-docs.sh` (mkdocs gh-deploy — no GitHub Actions).

## Scenario contract

Scenario JSONs live under `benchmark/scenarios/<category>/<subdir>/<id>.json`.

- `category` must be one of `safety`, `empathy`, `context`, `continuity`,
  `confidential`. The retired `tier` field and `tier_0..tier_3` values
  are rejected by the validator.
- Required fields: `scenario_id`, `title`, `category`, `persona`,
  `scoring_dimensions`, plus `turns` or `sessions`.
- Turn contracts use `expected_behaviors` and/or one unified `rubric` list
  (criteria with `kind: binary|ordinal|autofail`); the retired
  `autofail_rubric` / `rubric_criteria` dialects are rejected.
- Full schema: [`benchmark/scenarios/SCENARIO_SCHEMA.yaml`](benchmark/scenarios/SCENARIO_SCHEMA.yaml).

Before submitting a new scenario:

```bash
uv run python scripts/lint_turn_indices.py --strict
uv run pytest benchmark/tests/unit/test_scenario_validator.py benchmark/tests/unit/test_scenario_models.py -q
```

## Running the benchmark

See [docs/install.md](docs/install.md) for the "reproduce a leaderboard
entry from scratch" walkthrough. The short version:

`bench` generates target transcripts only; judge them in a separate step with
`scripts/run_scan.py`:

```bash
uv run bench --dry-run          # estimate cost only
uv run bench -m deepseek -y --max-cost-usd 1   # single model, transcripts only
uv run bench --full -y --max-cost-usd 50       # all public models, transcripts only
uv run python scripts/run_scan.py --profile dev --enable-llm \
  --max-cost-usd 2 --llm-model openai/gpt-5-mini results/run_<id>   # judge one model
```

## PR checklist

- [ ] `uv run pytest benchmark/tests -q` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run python scripts/lint_turn_indices.py --strict` passes
- [ ] Pre-commit hook is configured (`git config core.hooksPath .githooks`) and passes locally
- [ ] New/changed behavior has a test under `benchmark/tests/unit/`
- [ ] A new or retired check updates `check_count` in
      `benchmark/benchmark_inventory.json`; a new claim-carrying check
      (`hard_fail` or S5/S4_GATE severity) declares a `calibration:` block
      with its evidence status (QA rejects hard-fail claims without one)
- [ ] If public behavior changed, docs are updated (README, CLAUDE.md,
      or the appropriate `docs/*.md` page)
- [ ] Commit message follows Conventional Commits
      (`feat(scorer): ...`, `fix(cli): ...`, `docs: ...`)
- [ ] PR description explains the *why*, not just the *what*

## Reporting issues

- Bugs / feature requests: [GitHub Issues](https://github.com/givecareapp/givecare-bench/issues).
- Security issues: see [SECURITY.md](SECURITY.md).
- Scorer disagreements (you think a verifier scored a scenario incorrectly):
  open an issue with the scenario id, model, run id, and what you'd expect.

## Code of conduct

By participating, you agree to the [Contributor Covenant](CODE_OF_CONDUCT.md).
