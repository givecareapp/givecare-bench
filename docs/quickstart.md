# Quickstart: benchmark your model in an afternoon

This page assumes nothing about GiveCare. You need: a machine with
[uv](https://docs.astral.sh/uv/), an [OpenRouter](https://openrouter.ai) API
key, and roughly an afternoon. You will end with a jagged safety profile of
your model — which caregiving-safety checks it passes, which it fails, with
quoted transcript evidence for every failure.

## 1. Setup (5 minutes)

```bash
git clone https://github.com/givecareapp/givecare-bench
cd givecare-bench
uv sync --extra dev
export OPENROUTER_API_KEY=sk-or-...
uv run bench doctor          # verifies env + directories
```

## 2. Know what you're running (5 minutes)

- `checks/` — the taxonomy. One YAML file per check: definition, severity,
  routing, and the judge prompt. `ls checks/` is the whole inventory.
- `benchmark/scenarios/` — multi-turn caregiver conversations with one
  contract (`SCENARIO_SCHEMA.yaml`).
- Scoring uses a **Safety + Care** model — no composite. Safety checks (Crisis,
  Scope, Identity, Autonomy) produce per-line violation rates; a calibrated
  Safety violation blocks publication. Care checks (Belonging, Attunement,
  Trauma-awareness, Relational, Advocacy) produce directional distributions.
  The two layers are reported side by side (see [methodology](methodology.md)).

## 3. Run your model (1–2 hours; cost depends strongly on the model)

Any OpenRouter model id works — you are not limited to the published roster:

```bash
uv run bench -m "your-org/your-model" --dry-run  # cost preview, no calls
uv run bench -m "your-org/your-model" -y --max-cost-usd 25  # all 63 public scenarios
```

Want a smaller first taste? Run one category:

```bash
uv run bench -m "your-org/your-model" -c safety --dry-run
uv run bench -m "your-org/your-model" -c safety -y --max-cost-usd 10
```

For a cheap live canary before a larger run, use one low-cost target model and
one scenario. The GPT-5 Mini judge runs in the scan step, not in `bench`:

```bash
env INVISIBLEBENCH_API_TIMEOUT_SECONDS=10 INVISIBLEBENCH_API_MAX_RETRIES=1 \
  uv run bench -m "flash lite" --scenario context_regulatory_data_privacy_001 \
  -y
```

This produces `results/run_<timestamp>/` with one transcript per scenario.

## 4. Judge the transcripts (10–30 minutes, ~$1 with the core profile)

The `dev` profile is the calibrated core: the Safety-line checks (Crisis, Scope,
Identity) judged with one-pass LLM verifiers:

```bash
uv run python scripts/run_scan.py --profile dev --dry-run --enable-llm \
  --llm-model openai/gpt-5-mini results/run_<timestamp>
uv run python scripts/run_scan.py --profile dev --enable-llm \
  --max-cost-usd 2 --llm-model openai/gpt-5-mini results/run_<timestamp>
```

(`--profile publish` runs all 50 checks with full repetitions. Dry-run it
first, then set `--max-cost-usd` at or above the printed conservative budget.
`--profile smoke` is free and deterministic-only.)

Output: `results/safety_care_scan/<timestamp>/per_run.jsonl` (one verdict
ledger per scenario), `summary.md`, and corpus-level blindspot rates.

## 5. Read the profile (the actual point)

Every number is traceable to evidence:

```bash
uv run bench explain "your-model" <scenario-id> --failures \
  --scan results/safety_care_scan/<timestamp>/per_run.jsonl
```

This prints each failed check with severity, judge confidence, prompt-template
hash, the quoted transcript spans that triggered the verdict, and the path to
the full transcript. Any `overall_score` / `hard_fail` fields shown here are
raw/internal diagnostic fields, not the public Safety/Care score model.

## What the results do and don't mean

- Hard-fail gate behavior is diagnostic until a check is `claim_ready`; the
  current public claim surface is empty (0 `claim_ready`) — see
  [verifier validation](verifier-validation.md).
- Quality dimension scores are directional until the quality-layer judges
  clear validation-grade agreement (the caveat ships inside the leaderboard
  metadata too).
- The output is a blind-spot profile, not a rank. A model can be excellent on
  crisis recognition and still infodump a grieving caregiver — that
  jaggedness is what the benchmark exists to show.

## Contributing results or scenarios

Open an issue or PR — scenario candidates go through staged probing and
human review before promotion (no fast path, including for us). See
`CONTRIBUTING.md` in the repository root.
