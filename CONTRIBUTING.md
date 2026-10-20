# Contributing

Type: how-to.

InvisibleBench is a public benchmark for caregiver-support conversations. The
public corpus, checks, and judge rules live here. Private held-out scenarios
live elsewhere and are never accepted here.

## What belongs here

- New public scenarios that test one caregiver-support behavior clearly, with
  an inventory entry and exemplar answers.
- Check definitions with their grammar and exemplars (see `checks/README.md`).
- Fixes to export, scan planning, rules, or the Jury Card.
- Documentation of the method.

## What does not belong here

- Private conversations, production traces, or identifying details.
- Scenarios that require clinical, legal, or eligibility determinations as
  ground truth.
- Composite scores or model rankings. Safety and Care stay separate.
- Any change that lets a scan spend money without a planned ceiling.

## Before you open a pull request

```bash
uv sync --extra dev
scripts/check.sh      # ruff, scenario and exemplar gates, tests
uv run bench demo     # must still produce a Jury Card with no keys
```

A scenario or check change must regenerate its exemplar answers through the
documented refresh path and include them in the same change.

## Licensing

By contributing you agree your contribution is released under the MIT License.
