# Inspect a worked measurement

Type: reference.

<!-- benchmark:identity -->

This page follows one public development exemplar through the current request
builder and rule engine. The documentation build reads the committed transcript,
check, and saved answers. It refuses stale answers or a changed expected verdict.

<!-- benchmark:example -->

## Reproduce the decision

Run `uv run python scripts/check_examples.py verify` from the checkout.
Verification reads saved answers and makes no model calls. A new judge execution
can return different probabilities.

See [Method](methodology.md) for evidence selection and [Evaluator validation](validation.md)
for the evidence required to assess accuracy.
