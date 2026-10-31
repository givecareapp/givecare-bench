# Changelog

Type: reference.

Notable changes to the InvisibleBench rebuild, newest first, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. The version is
the one in `pyproject.toml`, which every Inspect log records as
`benchmark_version`. Commits are the detailed record. The 5.8.0 archive under
`_archive/5.8.0/` does not change and has no entries here.

## [Unreleased]

Development version 0.1.4, working tree on top of commit `f21730b`, not
committed. An end-to-end audit on 2026-10-30 found the deterministic layer sound
and every semantic claim unvalidated: no blind human label set has been scored
against any judge, and the judge almost never answers UNCLEAR. Nothing here is
a validated model result.

### Added

- `run.py`: one command judges the authored controls, generates each target's
  conversations, judges them, and writes offline reports and `run.json` into one
  new directory. `run.json` is read back from the Inspect logs, never typed. The
  command refuses before any evaluation when a family is unknown, its case files
  are uncommitted, a paid model lacks `--judge-cost-limit-usd` or
  `--ceiling-usd`, a paid model has no registered price, or `--out` is not empty.
  A failure mid-run still writes `run.json` from the finished logs, then
  re-raises.
- `task.py`: `OPENROUTER_PRICES` and `register_prices()` give Inspect a USD
  price per million tokens for each paid model, so logs record cost and the
  ceiling can count it.
- `grader.py`: `Verdict` enum. The `criterion_verdict` scorer reports native
  `categorical()` verdict frequencies in each judge log.
- `tests/test_run.py`: refusal gates, ceiling stop, record and report writing,
  and the failure path, all on mock models.

### Changed

- Summaries, reports, and `report.py --diff` identity carry Inspect's native
  `EvalRevision` (origin, commit, dirty) in a `revision` field. The Markdown
  report header shows it.
- `judged_revision` still refuses uncommitted `cases/<family>/` files and now
  records only the uncommitted paths.
- `README.md` and `BENCHMARK_CARD.md` describe the six families, the
  development and withheld split, `run.py` as the one runner, and
  pre-registration of paid runs through `--purpose`. Both state that no
  validated model result exists.
- `scripts/check.sh` lints `run.py`.

### Removed

- The `git rev-parse` call in `task.py` `revision()`; Inspect records the
  commit.
- The `git_commit` field of `summarize` and `summarize_target`; `revision`
  replaces it.
