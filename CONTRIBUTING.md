# Contributing

Thanks for your interest in GiveCare Bench. This guide covers what kinds of
contributions are welcome, how to set up the dev environment, and what a
valid PR looks like.

## What's welcome

- **Scenario additions or improvements** — new public scenarios under
  `benchmark/scenarios/`, or fixes to existing rubrics. See the
  [scenario contract](#scenario-contract) below.
- **Scorer bug fixes** — the scorers live under
  `src/invisiblebench/evaluation/scorers/`. Add a unit test in
  `benchmark/tests/unit/test_scorers/` alongside any fix.
- **Docs** — tutorials, clarifications, typos. Follow the Diátaxis types
  declared in [`CLAUDE.md`](CLAUDE.md).
- **Test coverage** — the repo has 455+ tests and appreciates more.

## What's not welcome

- Edits to private scoring prompts or jurisdiction rules. These are
  gitignored by design (see the
  [private-content segregation note in CLAUDE.md](CLAUDE.md)). Public
  verifier prompts live in `benchmark/configs/verifier_prompts/`.
- Benchmark version bumps without maintainer sign-off. The public contract
  version lives in `benchmark/benchmark_card.json`.
- Changes to archived material under `archive/` — that directory is
  frozen for provenance.

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

All three must pass. CI (`.github/workflows/ci.yml`) runs the same
commands on every PR.

## Scenario contract

Scenario JSONs live under `benchmark/scenarios/<category>/<subdir>/<id>.json`.

- `category` must be one of `safety`, `empathy`, `context`, `continuity`,
  `confidential`. The legacy `tier` field and `tier_0..tier_3` values
  are rejected by the validator.
- Required fields: `scenario_id`, `title`, `category`, `persona`,
  `scoring_dimensions`, plus `turns` or `sessions`.
- Turn contracts may use `expected_behaviors`, binary `rubric` /
  `autofail_rubric`, or ordinal `rubric_criteria`.
- Full schema: [`benchmark/scenarios/SCENARIO_SCHEMA.yaml`](benchmark/scenarios/SCENARIO_SCHEMA.yaml).

Before submitting a new scenario:

```bash
uv run python scripts/lint_turn_indices.py --strict
uv run pytest benchmark/tests/unit/test_contract_drift.py -q
```

## Running the benchmark

See [docs/install.md](docs/install.md) for the "reproduce a leaderboard
entry from scratch" walkthrough. The short version:

```bash
uv run bench --dry-run          # estimate cost only
uv run bench -m deepseek -y     # single model
uv run bench --full -y          # all public models, all 50 scenarios
```

## PR checklist

- [ ] `uv run pytest benchmark/tests -q` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run python scripts/lint_turn_indices.py --strict` passes
- [ ] New/changed behavior has a test under `benchmark/tests/unit/`
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
