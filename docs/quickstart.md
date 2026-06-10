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
- Scoring is **gate-then-quality**: safety (A) and compliance (B) checks are
  hard gates — any failure zeroes the scenario. Quality dimensions are
  reported but subordinate (see [methodology](methodology.md)).

## 3. Run your model (1–2 hours, ~$1–3 for most models)

Any OpenRouter model id works — you are not limited to the published roster:

```bash
uv run bench -m "your-org/your-model" --dry-run     # cost preview, no calls
uv run bench -m "your-org/your-model" -y            # all 63 public scenarios
```

Want a smaller first taste? Run one category:

```bash
uv run bench -m "your-org/your-model" -c safety -y
```

This produces `results/run_<timestamp>/` with one transcript per scenario.

## 4. Judge the transcripts (10–30 minutes, ~$1 with the core profile)

The `dev` profile is the calibrated core: the hard-fail gates (A/B) and
boundary checks (F), judged with one-pass LLM verifiers:

```bash
uv run python scripts/run_scan.py --profile dev --dry-run --enable-llm results/run_<timestamp>
uv run python scripts/run_scan.py --profile dev --enable-llm results/run_<timestamp>
```

(`--profile publish` runs all 53 checks with full repetitions — use it when
you want the complete profile and don't mind the extra judge cost. `--profile
smoke` is free and deterministic-only.)

Output: `results/v3_scan/<timestamp>/per_run.jsonl` (one verdict ledger per
scenario), `summary.md`, and corpus-level blindspot rates.

## 5. Read the profile (the actual point)

Every number is traceable to evidence:

```bash
uv run bench explain "your-model" <scenario-id> --failures \
  --scan results/v3_scan/<timestamp>/per_run.jsonl
```

This prints each failed check with severity, judge confidence, prompt-template
hash, the quoted transcript spans that triggered the verdict, and the path to
the full transcript.

## What the results do and don't mean

- Hard-fail gate behavior is the validated claim surface (calibrated against
  human gold labels — see [verifier validation](verifier-validation.md)).
- Quality dimension scores are directional until the quality-layer judges
  clear validation-grade agreement (the caveat ships inside the leaderboard
  metadata too).
- The output is a blind-spot profile, not a rank. A model can be excellent on
  crisis recognition and still infodump a grieving caregiver — that
  jaggedness is what the benchmark exists to show. See
  [findings](findings.md) for what the current frontier looks like.

## Contributing results or scenarios

Open an issue or PR — scenario candidates go through staged probing and
human review before promotion (no fast path, including for us). See
`CONTRIBUTING.md` in the repository root.
