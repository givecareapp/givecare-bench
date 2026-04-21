# Solutions log

Append-only. Newest first. Format: `## YYYY-MM-DD — title`.

---

## 2026-04-21 — GitHub Pages deploy no longer depends on the legacy branch build

GitHub Pages was still configured in legacy `gh-pages` branch mode, so every
docs deploy triggered GitHub's managed `pages-build-deployment` workflow. That
workflow emitted Node 20 deprecation warnings for its internal `checkout` and
`upload-artifact` steps, even though our repo workflows were otherwise green.

Fix:
- `.github/workflows/docs.yml` now builds the MkDocs site directly and deploys
  it with `actions/configure-pages@v6`, `actions/upload-pages-artifact@v5`,
  and `actions/deploy-pages@v5`
- the docs workflow now requests `pages: write` and `id-token: write` instead
  of pushing to `gh-pages` directly
- repo workflows were bumped to current actions that target the modern runner
  stack: `actions/checkout@v6` and `astral-sh/setup-uv@v8.1.0`
- the docs workflow path filter now includes its own workflow file so deploy
  changes are exercised on the next push
- the repository Pages setting was switched from legacy branch builds to the
  GitHub Actions workflow deploy path

This removes the repo's dependence on the legacy GitHub Pages branch build and
keeps Actions ahead of the Node 20 retirement without relying on forced runtime
compatibility flags.

## 2026-04-21 — Quality holdout builder now works in CI without local run snapshots

`build_regard_quality_holdout.py` originally assumed two local `results/run_*`
snapshots existed and always rebuilt the holdout from them. That worked on the
operator machine but failed in CI with `FileNotFoundError` before the tests even
reached the checked-in holdout candidates.

Fix:
- `scripts/build_regard_quality_holdout.py` now rebuilds from the source
  snapshots only when they exist locally
- otherwise it falls back to the checked-in
  `internal/evals/verifier/quality_holdout/candidates.jsonl`
- `benchmark/tests/unit/test_regard_workflows.py` now checks transcript-path
  existence only when the source snapshots are present and adds a regression
  test for the frozen-candidate fallback

This keeps the holdout workflow reproducible for local verifier work without
making CI depend on untracked benchmark-run artifacts.

## 2026-04-20 — Regard scorer correctness and robustness fixes

Five issues found in code review and fixed in one batch.

**Partial-parse silent-zero (`regard.py`)**
If the LLM returned a partial response (e.g. only 2 of 4 axis labels), `parsed_any` was `True` so `_score_deterministic` was not called, but unparsed axes stayed at their initialized `0.0` rather than a deterministic estimate. Fix: after the LLM parse loop, detect axes absent from `axis_labels` and call `_score_deterministic` for those axes, adding evidence entries prefixed `WARNING: LLM did not return {axis}`.

**Unguarded KeyError in audit script (`audit_gold_regard.py`)**
`_score_candidates` and `_build_rows` did bare dict lookups on `scenario_index[candidate["scenario_id"]]` and `gold_labels[trace_id]` with no guard, crashing after expensive LLM calls. Fix: upfront validation collects all missing IDs and raises a descriptive `ValueError` before the scoring loop starts.

**`msg['turn']` KeyError in deterministic checks (`regard.py`)**
`_score_grounding_deterministic` and `_detect_othering_deterministic` accessed `msg['turn']` directly. Transcripts without a `turn` field (older schema, test fixtures) would raise `KeyError`. Fix: `msg.get('turn', '?')` in evidence strings, `msg.get('turn')` in `hard_fails` dicts.

**Prompt/parser `_TURN` field mismatch (`regard_eval_v2.txt`)**
The prompt instructed the LLM to output `RECOGNITION_TURN`, `AGENCY_TURN`, etc., but the parser in `_score_with_llm` never read them — they were silently discarded, wasting tokens on every judge call. Fix: removed the four `_TURN` output lines from the prompt. Note: this changes the `judge_prompt_hash` for `regard_eval_v2.txt`.

**Bare file handles (`run_pairwise_pilot.py`)**
Three `open()` reads were not wrapped in `with` blocks. Fixed for consistency with the `with open(OUT_PATH, "a")` pattern in the same script.
