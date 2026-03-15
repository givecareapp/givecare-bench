# AutoResearch Program: InvisibleBench Score

## Metric
Overall percentage score — higher is better.

## Eval Modes

### Offline (default) — re-score existing transcripts via Codex CLI
For targets that don't change the conversation (rubric wording, rubric weights).
Uses gpt-5.4 via ChatGPT subscription — zero API cost.

```bash
cd /home/deploy/gc-repos/givecare-bench && ./autoresearch/score_offline.sh
```
- Reads existing transcripts from a prepared GiveCare live-run transcript set
- Scores against current rubric prompts in `benchmark/configs/prompts/`
- Outputs `Overall: XX.X%`
- ~5 min per run (no live conversations)

### Online — full bench run with live Mira conversations
For targets that change conversation flow (system prompt, branch conditions, user messages).
Uses OpenAI API for scoring — ~$0.01 per run.

```bash
cd /home/deploy/gc-repos/givecare-bench && uv run bench --harness givecare --mode live -y
```
- Generates new transcripts by talking to Mira
- Scores with LLM judge (gpt-4.1-mini by default)
- ~15 min per run

Note: `--deployment prod` is unusable — prod lacks `PLAYGROUND_KEY`. Uses dev deployment (`agreeable-lion-831`) by default.

## Which eval mode per target

| Target | Eval Mode | Why |
|--------|-----------|-----|
| Rubric question wording | **Offline** | Only changes how transcripts are scored |
| Rubric weights | **Offline** | Only changes score aggregation |
| System prompt | **Online** | Changes Mira's responses |
| Branch conditions | **Online** | Changes conversation flow |
| User message clarity | **Online** | Changes what Mira receives |

## Metric Parsing (for run_experiment.sh)
- **regex**: `Overall:\s+([0-9.]+)%`
- **direction**: `higher`
- **fail_regex**: `AUTOFAIL|HARD.FAIL|gate.*fail`
- **baseline**: `81.9`

Example invocation (offline):
```bash
~/agents/skills/autoresearch/scripts/run_experiment.sh \
  --eval "cd /home/deploy/gc-repos/givecare-bench && ./autoresearch/score_offline.sh 2>&1" \
  --metric-regex 'Overall:\s+([0-9.]+)%' \
  --direction higher \
  --baseline 81.9 \
  --fail-regex 'AUTOFAIL|HARD.FAIL|gate.*fail' \
  --timeout 600 \
  --experiment-num N \
  --target "Rubric question wording" \
  --hypothesis "HYPOTHESIS" \
  --log autoresearch/experiment_log.md
```

Example invocation (online):
```bash
~/agents/skills/autoresearch/scripts/run_experiment.sh \
  --eval "cd /home/deploy/gc-repos/givecare-bench && uv run bench --harness givecare --mode live -y 2>&1" \
  --metric-regex 'Overall:\s+([0-9.]+)%' \
  --direction higher \
  --baseline 81.9 \
  --fail-regex 'AUTOFAIL|HARD.FAIL|gate.*fail' \
  --timeout 900 \
  --experiment-num N \
  --target "System prompt" \
  --hypothesis "HYPOTHESIS" \
  --log autoresearch/experiment_log.md
```

## Mutable Files
- `benchmark/configs/prompts/*.txt` — scoring rubric prompts (offline targets)
- `benchmark/scenarios/**/*.json` — scenario turn text, rubric question wording, rubric weights, autofail trigger phrases, branch conditions
- Provider system prompt block inside `benchmark/scripts/givecare_provider.py` (the `SYSTEM_PROMPT` or equivalent string — do not touch scoring logic)

## Locked Files (DO NOT MODIFY)
- `benchmark/invisiblebench/score.py`
- `benchmark/invisiblebench/__init__.py`
- `benchmark/invisiblebench/yaml_cli.py`
- `benchmark/invisiblebench/progress.py`
- `autoresearch/score_offline.sh` — the offline scorer itself
- Everything outside `benchmark/scenarios/`, `benchmark/configs/prompts/`, and the prompt section of `givecare_provider.py`

## Thresholds
- **COMMIT** if: overall score improves AND zero new autofails introduced
- **REVERT** if: overall score drops OR any new hard fail appears

## Budget
- Max experiments per target: 3
- Max experiments total: 15
- Max wall time per experiment: 10 min (offline) / 15 min (online)
- Max campaign time: 2 hours
- Branch: `main`

## Targets (priority order)
1. Rubric question wording — tighten ambiguous questions so judge scores more accurately **(offline)**
2. Rubric weights — rebalance dimension weights to better reflect safety importance **(offline)**
3. System prompt — strengthen crisis detection and trauma-informed framing **(online)**
4. Branch conditions — improve branch coverage for common model response patterns **(online)**
5. User message clarity — clarify ambiguous turns that confuse the model **(online)**

## Prerequisites
- Run `uv run bench --harness givecare --mode live -y` once to generate a baseline live-run transcript set
- Codex CLI authenticated (`codex login status` should show "Logged in using ChatGPT")
- Offline scorer reads rubric prompts from `benchmark/configs/prompts/`

## Notes
- Current baseline: 81.9% (Mira, prod deployment, March 2026)
- Each experiment: one variable only (scenario edit OR prompt edit, not both)
- Skip `archive/` and `confidential/` subdirs when selecting scenarios to edit
- Log every experiment in `autoresearch/experiment_log.md` (untracked)
- Write REPORT.md at campaign end
- Founding Engineer agent orchestrates the loop; gpt-5.4 (Codex CLI) does the judging
