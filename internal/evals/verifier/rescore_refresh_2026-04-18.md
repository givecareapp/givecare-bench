# Frozen board refresh — 2026-04-18

Operational memo for rolling the gold-aligned scorer into the frozen 15-model
benchmark board.

## Preconditions

- scorer-vs-gold audit: `internal/evals/verifier/golden_set/current_scorer_vs_gold.md`
- public hard-fail / gate / primary-rule alignment on the 60-trace gold set:
  - public hard fail: `60/60`
  - safety gate: `60/60`
  - compliance gate: `60/60`
  - primary rule: `60/60`

## Commands run

```bash
uv run bench rescore results/run_20260330_130332 --update-leaderboard
uv run bench rescore results/partial_runs/run_20260330_033649_up_to_deepseek --update-leaderboard
uv run bench --yes leaderboard rebuild
```

## Rescore inputs

The frozen board still spans two transcript roots:

- `results/run_20260330_130332/` (`10` models, `500` rows)
- `results/partial_runs/run_20260330_033649_up_to_deepseek/` (`5` models, `250` rows)

## Rescore results

| Root | Rows | Hard fails | Avg score |
|---|---:|---:|---:|
| `results/run_20260330_130332/` | 500 | `82 -> 59` | `0.683 -> 0.725` |
| `results/partial_runs/run_20260330_033649_up_to_deepseek/` | 250 | `37 -> 27` | `0.706 -> 0.748` |
| Combined frozen board | 750 | `119 -> 86` | n/a |

## Leaderboard refresh

- pre-refresh leaderboard timestamp: `2026-04-01T03:51:13.231319+00:00`
- refreshed leaderboard timestamp: `2026-04-18T23:58:22.504083+00:00`
- current leaderboard artifact: `data/leaderboard/leaderboard.json`
- health after rebuild: `15/15` models clean, `0` incomplete, `0` with errors

## Largest rank movements

| Model | Rank delta | Score delta | Pass/fail delta |
|---|---:|---:|---:|
| `Gemini 3.1 Pro` | `15 -> 1` | `+0.165` | `38/12 -> 48/2` |
| `Grok 4.1 Fast` | `7 -> 2` | `+0.116` | `39/11 -> 46/4` |
| `Gemini 2.5 Flash` | `14 -> 7` | `+0.094` | `39/11 -> 45/5` |
| `GPT-5.4` | `1 -> 8` | `-0.056` | `46/4 -> 43/7` |
| `Claude Sonnet 4.5` | `3 -> 15` | `-0.074` | `44/6 -> 39/11` |

## Current top 15 after refresh

1. `Gemini 3.1 Pro` — `0.798`
2. `Grok 4.1 Fast` — `0.791`
3. `GPT-OSS 120B` — `0.774`
4. `Kimi K2.5` — `0.773`
5. `Claude Opus 4.6` — `0.750`
6. `GLM-5` — `0.750`
7. `Gemini 2.5 Flash` — `0.746`
8. `GPT-5.4` — `0.735`
9. `GPT-5 Mini` — `0.733`
10. `Gemini 3 Flash` — `0.715`
11. `Qwen3.5 397B` — `0.711`
12. `MiniMax M2.5` — `0.701`
13. `Qwen3.5 35B` — `0.697`
14. `DeepSeek V3.2` — `0.665`
15. `Claude Sonnet 4.5` — `0.652`

## Delivery

The current public delivery path is static JSON:

- canonical artifact: `data/leaderboard/leaderboard.json`
- site mirror target: `apps/web-bench/public/bench/leaderboard.json` in the web repo

A legacy Convex publish was run during the first rollout on 2026-04-18, but it
is no longer part of the benchmark delivery path and should not be treated as
canonical.

## Remaining gaps

1. `regard` is still the main fixed-unvalidated quality judge.
2. The gold set is still only `60` traces; it is strong enough for the public
   hard-fail layer but not a universal guarantee over every edge case.
3. Keep `scripts/audit_gold_scorer.py --mode llm` as the regression gate before
   future scorer or prompt changes.
4. `detail_json` / `detail_html` artifact links are still only partially
   resolvable locally and should be repaired or de-emphasized in public-facing
   surfaces.
