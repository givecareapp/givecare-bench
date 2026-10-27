# Invisible Bench

[![Release](https://img.shields.io/github/v/release/givecareapp/givecare-bench)](https://github.com/givecareapp/givecare-bench/releases)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Invisible Bench evaluates AI models in multi-turn caregiver-support
conversations and produces a Jury Card with cited evidence for every failure.**
Safety and Care are reported separately. There is no composite score or model
rank.

- [Documentation](https://givecareapp.github.io/givecare-bench/): method,
  validation, and coverage.
- [Paper (arXiv)](https://arxiv.org/abs/2511.20733): the original benchmark
  design. The documentation describes the current method.
- Cite with [CITATION.cff](CITATION.cff).

## How it works

1. [Inspect](https://inspect.aisi.org.uk/) replays scripted caregiver
   conversations against a target model.
2. A judge answers each check's yes/no questions as probabilities. Questions
   are public in [`checks/`](checks/README.md).
3. Code-owned rules derive each verdict from the saved answers, so every
   verdict replays without another model call.

Every `FAIL` cites the transcript turn it fired on. The [method](docs/methodology.md)
defines the four verdicts.

## Try it without API keys

```bash
uv sync --extra dev
uv run bench demo
```

This judges a synthetic run with a stub judge and prints a Jury Card. The run
is marked synthetic, and the card says `FIXTURE-JUDGED`. Publication refuses
it. The output is not a result; it shows the card and evidence layout.

## Run a scan

```bash
export OPENROUTER_API_KEY=...   # target models
export TYPESAFE_API_KEY=...     # judge

# 1. Generate transcripts, bounded per conversation.
uv run inspect eval invisiblebench/safety_care --model openrouter/<model-id> \
  -M 'provider={"allow_fallbacks": true, "require_parameters": true}' \
  --cost-limit <usd-per-conversation> --log-dir results/<run-id>/inspect
uv run bench export results/<run-id>/inspect/*.eval --output results/<run-id>

# 2. Plan the judge scan (no paid calls), then run it under a ceiling.
uv run bench scan plan results/<run-id>
uv run bench scan run --plan results/<run-id>/scan_plan.json --max-cost-usd <budget>

# 3. Read the evidence.
uv run bench explain <model-id> <scenario-id> --failures --scan results/<run-id>
```

The scan writes `results/<run-id>/jury-card.md` beside its saved plan, answers,
judgments, and transcripts. See the [quickstart](docs/quickstart.md) for
provider routing, resume, rejudging, and publication, and the
[validation guide](docs/validation.md) for evaluator controls.

## What the results mean

A Jury Card reports model behavior in one recorded run. It does not establish
judge accuracy, clinical validity, or caregiver outcomes. See the
[method](docs/methodology.md) for the card, rates, and limits.

## Repository map

| Path | Contents |
| --- | --- |
| `benchmark/` | Public scenarios, [inventory](benchmark/benchmark_inventory.json), and tests |
| `checks/` | Check definitions and exemplars |
| `src/invisiblebench/` | Inspect task, judge runtime, rules, and projection |
| `scripts/` | Repository checks and docs tooling |
| `data/` | Committed leaderboard projection and release archive |
| `docs/` | Source for the published documentation |

## Development

```bash
git config core.hooksPath .githooks   # enable the required pre-commit gate
scripts/check.sh                      # lint, exemplars, and tests (offline)
```

## Scope and privacy

This repository owns the public scenarios, checks, judge runtime, and
Safety/Care projection. It does not own product policy, clinical guidance, or
outcome claims. Private transcripts, scenarios, expected answers, and
credentials are never committed.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md), [SECURITY.md](.github/SECURITY.md) for private
reports, and the [Code of Conduct](.github/CODE_OF_CONDUCT.md). Licensed under
[MIT](LICENSE).
