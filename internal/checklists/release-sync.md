# Release Sync Checklist

When something changes in the benchmark, follow this flow: change the canonical, verify MkDocs, ripple to consumers. Do not update consumers directly — they reflect the canonical, not the other way around.

---

## 1. Change the canonical

All source-of-truth artifacts live in givecare-bench:

| What | Where |
|------|-------|
| Check definitions | `benchmark/configs/failure_modes.yaml` |
| Verifier routing | `benchmark/configs/scorer_routing.yaml` |
| Scoring contract | `benchmark/configs/scoring_v3.yaml` |
| Benchmark card | `benchmark/benchmark_card.json` |
| Scenario inventory | `benchmark/benchmark_inventory.json` |
| Package version | `pyproject.toml` + `src/invisiblebench/__init__.py` |
| Implementation | `src/invisiblebench/` |
| Public docs | `docs/` (MkDocs) |

Make the change here first. Everything else follows.

---

## 2. Verify MkDocs reflects the change

Check each page. Only update pages affected by the change — not every page on every release.

- [ ] `docs/checks.md` — check added, removed, rerouted, or recalibrated
- [ ] `docs/taxonomy.md` — dimension added/removed, MECE claim changed, grounding changed
- [ ] `docs/findings.md` — new fleet data, new calibration results, new key finding
- [ ] `docs/methodology.md` — scoring formula, claim surface, grounding layers changed
- [ ] `docs/architecture.md` — verifier types, engine, event-window scoping changed
- [ ] `docs/scoring-rubric.md` — rubric questions, dimension descriptions changed
- [ ] `docs/judge-validation.md` — new kappa results, new gold sets
- [ ] `docs/index.md` — version, dimension names, hero stats changed
- [ ] `mkdocs.yml` — new pages added to nav
- [ ] `uv run mkdocs build --strict` passes

---

## 3. Ripple to consumers

These are downstream of the canonical. Update them to reflect what changed, don't add new content here.

### Same repo (givecare-bench)

- [ ] `benchmark/benchmark_card.json` — version, methodology, metrics, validation
- [ ] `benchmark/benchmark_inventory.json` — version
- [ ] `data/leaderboard/leaderboard.json` — metadata block (run `scripts/generate_leaderboard.py` or edit metadata directly)
- [ ] `README.md` — one-line architecture summary matches current
- [ ] `benchmark/README.md` — same
- [ ] `CLAUDE.md` — contract section (version, scoring one-liner, calibration one-liner)
- [ ] `AGENTS.md` — version, dimension names, script paths
- [ ] `pyproject.toml` + `src/invisiblebench/__init__.py` — package version
- [ ] Tests — update assertions on version, claim_surface, dimension names
- [ ] `uv run ruff check .` + `uv run pytest benchmark/tests -q` pass

### Cross-repo (give-care-mono)

- [ ] `apps/web-bench/public/bench/leaderboard.json` — sync from `data/leaderboard/leaderboard.json`:
  ```bash
  uv run python scripts/sync_web_bench_leaderboard.py --target /path/to/give-care-mono/apps/web-bench/public/bench/leaderboard.json
  ```
- [ ] `apps/web-bench/src/routes/_site/` — update index/about/leaderboard if methodology text changed
- [ ] `apps/web-bench/src/components/bench/types.ts` — update metric names/labels if dimensions changed
- [ ] `apps/web-wiki/docs/bench/` — verify canonical-source notes still point correctly
- [ ] Blog post — only for major releases, not every change

### Cross-repo (agents)

- [ ] `~/agents/wiki/givecare-bench-verifier-implementation.md` — update if architecture changed
- [ ] `~/agents/wiki/givecare-bench-diagram.html` — update if scoring pipeline changed

---

## 4. Do not update

These are historical records or auto-deployed:

- Previous blog posts (historical, not updated retroactively)
- `internal/` working notes (add canonical headers pointing to docs/, don't rewrite)
- `archive/` (frozen historical material)

---

## Version checklist

When bumping the version number, all of these must match:

- [ ] `pyproject.toml` version
- [ ] `src/invisiblebench/__init__.py` `__version__`
- [ ] `benchmark/benchmark_card.json` version
- [ ] `benchmark/benchmark_inventory.json` benchmark_version
- [ ] `data/leaderboard/leaderboard.json` metadata.benchmark_version + metadata.code_version
- [ ] `CLAUDE.md` contract section
- [ ] `scripts/generate_leaderboard.py` REQUIRED_BENCHMARK_VERSION
- [ ] Test fixtures in `benchmark/tests/unit/test_leaderboard.py`
