Diátaxis: reference

# Baseline metrics — 2026-03-31 remediation start

## Frozen corpus availability

Confirmed local run assets:

- `results/run_20260330_021307/`
- `results/partial_runs/run_20260330_033649_up_to_deepseek/`
- `results/run_20260330_130332/`
- `results/leaderboard_ready/`

## Baseline counts

- `false_scope`-involved rows: `172/255` compliance-fail rows
- `false_scope`-only hard-fail rows: `154/261` hard-fail rows
- scope-majority `false_scope`-only rows: `135/750` total rows
- contract inversion rows: `115/261` hard-fail rows
- strictest `0/3` inversion rows: `95/172` false-scope-involved rows

## Current classifier split across false-scope hard-fail items

- allowed honest-limitation / anti-dependency items: `264`
- soft boundary / drift items: `122`
- remaining explicit hard-fail items: `4`

## Contaminated models to rerun or flag

- `Qwen3.5 35B`
- `Qwen3.5 397B`
- `GPT-5 Mini`
- `Kimi K2.5`

## Generated artifacts

- `internal/evals/false_scope_inventory_2026-03-31.csv`
- `internal/evals/false_scope_examples_2026-03-31.md`
- `internal/evals/false_scope_contract_inversion_2026-03-31.md`