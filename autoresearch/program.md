# AutoResearch Program: InvisibleBench Score

## Metric
Overall percentage score — higher is better.

## Eval Command
```bash
cd /home/deploy/gc-repos/givecare-bench && .venv/bin/python benchmark/scripts/givecare_provider.py --all --deployment prod
```
Parse: look for overall percentage in stdout (e.g. `Overall: 81.9%`).

## Mutable Files
- `benchmark/scenarios/**/*.json` — scenario turn text, rubric question wording, rubric weights, autofail trigger phrases, branch conditions
- Provider system prompt block inside `benchmark/scripts/givecare_provider.py` (the `SYSTEM_PROMPT` or equivalent string — do not touch scoring logic)

## Locked Files (DO NOT MODIFY)
- `benchmark/invisiblebench/score.py`
- `benchmark/invisiblebench/__init__.py`
- `benchmark/invisiblebench/yaml_cli.py`
- `benchmark/invisiblebench/progress.py`
- Everything outside `benchmark/scenarios/` and the prompt section of `givecare_provider.py`

## Thresholds
- **COMMIT** if: overall score improves AND zero new autofails introduced
- **REVERT** if: overall score drops OR any new hard fail appears

## Budget
- Max experiments per target: 3
- Max wall time per experiment: 15 min (full bench run)
- Branch: `autoresearch/mira-ib-mar11`

## Targets (priority order)
1. Rubric question wording — tighten ambiguous questions so judge scores more accurately
2. Rubric weights — rebalance dimension weights to better reflect safety importance
3. System prompt — strengthen crisis detection and trauma-informed framing
4. Branch conditions — improve branch coverage for common model response patterns
5. User message clarity — clarify ambiguous turns that confuse the model

## Notes
- Current baseline: 81.9% (Mira, prod deployment, March 2026)
- Each experiment: one variable only (scenario edit OR prompt edit, not both)
- Skip `archive/` and `confidential/` subdirs when selecting scenarios to edit
- Log every experiment in `autoresearch/experiment_log.md` (untracked)
- Write REPORT.md at campaign end
