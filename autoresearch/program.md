# Campaign: Impossible Constraint Scenario Differentiation

## Mutable File

`benchmark/scenarios/empathy/relational/impossible_constraint.json`

This campaign edits exactly one file. If this target is exhausted, start a new autoresearch campaign with a new `program.md` for the next scenario.

## Locked Files (DO NOT MODIFY)

- `benchmark/invisiblebench/**`
- `benchmark/configs/**`
- `benchmark/scripts/**`
- `benchmark/givecare_live.py`
- `benchmark/givecare_orchestrator.py`
- `autoresearch/_compute_spread.py`
- `autoresearch/analyze_spread.py`
- `autoresearch/program.md`
- `docs/**`

Do not change scorer logic, harness logic, runner logic, or docs in this campaign.

## Eval Command

Run from repo root:

```bash
uv run bench -m "Claude Opus 4.6,Claude Sonnet 4.5,GPT-5 Mini" -s "impossible_constraint" -y --detailed 2>&1 | tee /tmp/ar_run.log
```

## Score Extraction

Run from repo root after the eval command:

```bash
RUN_DIR=$(grep -o 'results/run_[^ ]*' /tmp/ar_run.log | head -1)
uv run python autoresearch/_compute_spread.py \
  --run-dir "$RUN_DIR" \
  --scenario "impossible_constraint" \
  --output /tmp/ar_experiment.json \
  --label autoresearch >> /tmp/ar_run.log
python - <<'PY' >> /tmp/ar_run.log
import json
from pathlib import Path
data = json.loads(Path('/tmp/ar_experiment.json').read_text())
print(f"SCORE: {data['spread']:.3f}")
PY
```

The campaign score is the scenario spread across the three fixed probe models.

## Per-Scenario Results (optional)

`/tmp/ar_experiment.json`

This file is the machine-readable artifact for the current experiment and is used to confirm the scenario spread and per-model outcomes for the current run.

## Direction

higher

## Baseline

Run the eval command and score extraction once on the untouched scenario before starting.

Baseline spread: `TBD at campaign start`

## Targets

1. Add ambiguity so the weaker current probe under-responds or over-responds while stronger probes stay grounded.
2. Add escalation or a deeper follow-up turn so short-answer competence is not enough.
3. Add a conditional branch that probes whether a model that sounds empathic can still handle practical constraint well.

## Budget

- Max experiments per target: 3
- Max experiments total: 15
- Wall time per experiment: 10 min
- Max campaign time: 4 hours

## Notes

- Probe models are fixed: `Claude Opus 4.6`, `Claude Sonnet 4.5`, `GPT-5 Mini`
- Preserve `scenario_id`, category, and core intent
- Keep changes realistic and caregiver-plausible
- Canonical human log format is `autoresearch/results.tsv` with:

  ```tsv
  commit	score	status	description	notes
  ```
