# Governance

> **Diátaxis: reference** — how InvisibleBench governs its conflict of interest,
> versioning and stability, third-party model submission, and human annotation.
> Voice and evidence standard match
> [verifier-validation.md](verifier-validation.md): precise, underclaiming, no
> marketing.

## Conflict of interest and self-measurement

GiveCare builds Mira (its caregiver-support product) and also runs the benchmark
that scores it. That is a conflict of interest, stated plainly. Self-measurement
is credible only under explicit rules, enforced in code where possible:

- **No teaching to the test.** The product (`gc-sms`) never ingests scenario
  text, verifier prompts, or expected behaviors. Pressure transfers only through
  the public taxonomy and findings — a scenario script never becomes a product
  prompt.
- **Same contract for the home team.** The GiveCare/Mira product is evaluated
  through the same V2 HTTP harness (`bench --harness givecare --mode v2`), the
  same scenario contract, and the same verifier path as any other model. There
  is no special path for the home team.
- **Product runs are excluded from the public comparative leaderboard.** Per the
  public release policy, GiveCare/Mira V2 runs use `--harness givecare --mode v2`
  and are not part of the public comparative leaderboard; publicly comparable
  runs use the raw `llm` surface.
- **Public scenarios are burnable.** Assume every published scenario enters
  training corpora. Staging (the gitignored `intake/`) is the standing refresh
  source, and a private slice is held back as a contamination probe before large
  promotions. Every scenario file also embeds the contamination canary GUID
  (`benchmark/scenarios/CANARY.txt`); a model that can reproduce the GUID has
  trained on benchmark data.

The load-bearing guardrail is the claim posture itself: **no check currently
carries a public claim.** 0 of 50 checks are `claim_ready`, so the benchmark
makes no published Safety claim about any model — including Mira. Self-measurement
cannot flatter the home team while the published claim surface is empty.

## Versioning and stability

Version constants live in `src/invisiblebench/version.py`.

- **`BENCHMARK_VERSION`** (currently `4.0.0`) — the public corpus/checks version.
  It must match `benchmark/benchmark_inventory.json` and the generated
  leaderboard metadata. Comparability holds **within** a `BENCHMARK_VERSION`;
  cross-version comparisons are not claims.
- **Result-row schemas** (`RESULT_CONTRACT_VERSION`, `SCANNED_ROW_CONTRACT_VERSION`)
  version the JSONL row shapes independently of the corpus. They evolve on their
  own cadence and are not the public comparability surface.

What changes a version, and what they mean:

- **A verifier template change is a breaking change.** Any edit to a verifier
  prompt that alters its `compute_prompt_template_hash` output breaks cross-run
  comparability on that check. Per the verifier-validation change policy, such a
  change must be recorded as a new row in the verifier manifest, and any
  validation numbers must be re-measured — prior numbers do not carry over. See
  the "Change policy" section of
  [verifier-validation.md](verifier-validation.md).
- **Retiring a check is a major (4.0) event.** Difficulty ratchets through
  staged scenario promotion and contrast sets, never by quietly redefining or
  dropping checks. Removing a check from the taxonomy changes what the benchmark
  measures, so it is treated as a major-version event, not a silent edit.
- **Scenario and roster refreshes** regenerate the leaderboard within the
  current `BENCHMARK_VERSION`; adding scenarios or models does not by itself bump
  it.

## Third-party model submission

Any OpenRouter-served model can be run against the public benchmark without
GiveCare's involvement — the same self-serve path documented in
[quickstart.md](quickstart.md):

```bash
uv sync --extra dev && export OPENROUTER_API_KEY=...
uv run bench -m "your-org/your-model" --dry-run                       # plan transcripts
uv run bench -m "your-org/your-model" -y --max-cost-usd 25            # run transcripts
uv run python scripts/run_scan.py --profile publish --enable-llm --max-cost-usd 34 results/run_<id>   # one-model conservative judge ceiling
```

Live scans checkpoint every completed model/scenario row. If the explicit
ceiling or the process stops the scan, repeat the same command with
`--resume <incomplete-scan-dir>`; the runner verifies the original sources and
options, skips completed rows, and applies the new ceiling to cumulative cost.
Dry runs print the maximum accepted ceiling. The runtime rejects values above
the larger of 1.5× the conservative plan or the plan plus $1, so the required
hard ceiling cannot be replaced with a meaningless unbounded approval.

That produces the same scored surface the maintainers see. Reaching the
**public** leaderboard is a separate, fail-closed step — there is no side door:

```bash
./scripts/publish.sh <scan>/per_run.jsonl <web-target>
```

`publish.sh` runs `generate → strict QA → sync` and aborts before writing the
public target if the strict QA gate (`scripts/qa_leaderboard.py --strict`) fails.
Strict QA also requires the artifact benchmark version, current check-template
hash map, and hashes observed in the source scan to agree exactly.
The web-bench copy is a projection of `data/leaderboard/leaderboard.json`, never
hand-edited; `delivery/sync_web_bench.py` refuses to write unless the source
bytes were just strict-QA'd. Promoting a submitted row into the public artifact
stays a maintainer action, but the QA gate — not maintainer discretion — decides
what is publishable at all.

Third-party verifier or scenario contributions follow the same discipline as
internal work: every candidate lands in staging, is probed, and is promoted only
by human review; verifier contributions carry the calibration bar. There is no
fast path. See `CONTRIBUTING.md` in the repository root.

## Annotation and ethics

**Scenarios are synthetic; no human subjects.** Every scenario is
researcher-generated fiction grounded in aggregated caregiving statistics (AARP,
the National Alliance for Caregiving, and published research). No real caregiver
conversations, transcripts, or personally identifiable information are used, and
the evaluation itself involves no human subjects. Scenarios include masked and
explicit crisis signals and medical-boundary probes, released with
sensitive-content warnings to enable community safety research.

**Human-labeled calibration data now exists.** The paper's original ethics
statement anticipated *future* human-rater validation; the benchmark has since
received 241 human-graded natural cards across 19 checks (224 remain after N/A
and demoted-check exclusions) and built a 60-trace layer-level set with two
human passes. The natural files retain final verdicts but not both independent
labels; the layer-level set used AI-assisted resolution and a prior judge.
Balanced authored sets across the 19 hard-fail checks use AI reference-panel
labels. All are **development evidence, not validation** —
[verifier-validation.md](verifier-validation.md) documents what each set does
and does not support.

**Annotator of record.** The current annotator of record is the project owner.
The `claim_ready` bar (see the "Defining claim_ready" section of
[verifier-validation.md](verifier-validation.md)) requires **≥ 2 independent
human annotators, blinded to model identity and to the expected verdict, with no
AI model as the final adjudicator**, and pre-resolution inter-annotator
agreement reported. No current per-check set preserves that complete claim-grade
record. It is the primary reason 0 of 50 checks are `claim_ready` and the
published claim surface is empty.

**No claims beyond the evidence.** The benchmark makes no ROI, clinical, or
efficacy claims. Production traces, where used, are harvested only after
anonymization and review; confidential scenarios never return to the public
repo. Future validation studies with external human raters will require IRB
approval.
