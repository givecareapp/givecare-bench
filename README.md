# InvisibleBench

InvisibleBench is being rebuilt around multi-turn caregiver support: whether an
assistant provides useful help while respecting caregiver capacity, both people's
agency, the availability of support, and danger to either person.

The previous implementation is preserved in [_archive/5.8.0](_archive/5.8.0/README.md).
See the [archive record](_archive/README.md) for its source revision and verification.
The first development slice and its grader pilot task are runnable. There is no
new benchmark result or validated grader yet. [Design and measurement contract](DESIGN.md).
The [development benchmark card](BENCHMARK_CARD.md) records methods, coverage,
limits, validation status, and interoperability.
The [independent review protocol](REVIEW_PROTOCOL.md) defines the label and
calibration work still needed before measurement claims.
The package is versioned `0.1.0` as a development slice; this is not a validated
InvisibleBench 6.0 release. Native logs also record exact source hashes.

The visual walkthrough is available locally at
`/home/deploy/wiki/pages/givecare/visuals/invisiblebench-walkthrough.html`.
It embeds the case, rubric, and authored controls as a source-bound design
snapshot. It is an explanation, not a live model evaluation.

## Rebuild boundary

- Design new cases from caregiver evidence. Capacity, agency, access, and safety
  are proposed coverage domains, not validated scales.
- Keep multi-turn evaluation. Use matched conditions to test whether relevant
  history and changed facts alter the response appropriately.
- Report Safety and Care separately. A lack of violations does not establish
  useful help, clinical validity, or caregiver benefit.
- Start with one matched family and an independently assessed comparison.
  Development cases are not independent validation evidence.
- Bring archived engineering into the active project only when a concrete need
  and verification justify it. Do not import the old corpus or rubric by default.
- Reuse Inspect before building execution machinery. Paid inference requires a
  saved plan and an explicitly approved ceiling.

## Working tree

```text
task.py          Inspect task; actual multi-turn generation, no scorer
grader.py        separate Inspect tasks for controls and saved target logs
report.py        offline audit from native Inspect judge logs
review_packet.py blind human-review packet from a saved generation log
BENCHMARK_CARD.md benchmark-level methods and limits
REVIEW_PROTOCOL.md independent labeling and calibration contract
cases/
  backup_care/
    case.json    shared turns and matched availability conditions
    rubric.json  separate Safety/Care review criteria
    controls.jsonl authored responses and expected judgments
    README.md   family contract, contrasts, and validation status
tests/           offline harness and case-contract checks
DESIGN.md        claim, falsifiers, evidence limits, comparison design
_archive/5.8.0/   frozen previous public project
scripts/check.sh active checks followed by the historical gate
data/            unchanged published artifacts for existing consumers
private/         separate, ignored private repository
results/         ignored historical run evidence
```

Repository history, local credentials, and private evidence remain in place.
Archiving does not remove prior exposure to benchmark content. New independent
validation requires separately authored, withheld case families.

## Verify locally

```bash
scripts/check.sh
```

This checks the active slice and then runs the archive's unchanged gate. Setup
uses the locked dependencies and may download them. Tests use mocked responses,
with no paid inference. These checks establish engineering behavior, not semantic
grader accuracy. Run only the active checks with `uv run --locked pytest tests -q`.

Generate a free mock log and open it in Inspect:

```bash
uv run --locked inspect eval task.py@backup_care --model mockllm/model --log-dir results/rebuild-smoke
uv run --locked inspect view --log-dir results/rebuild-smoke
```

Mock output proves no caregiving capability. Paid runs require the frozen plan
and explicit budget described in [DESIGN.md](DESIGN.md#comparison-before-claims).
The grader pilot is separate from target generation. It submits one criterion
and the conversation through one response to the judge. Expected labels and
future turns stay out of the judge request. It validates the JSON verdict and
exact evidence quotes; those mechanical checks cannot establish judgment accuracy.

Run a free protocol smoke check with Inspect's default mock output:

```bash
uv run --locked inspect eval grader.py@control_judge --model mockllm/model --limit 1 --log-dir results/grader-smoke
```

The default mock returns non-JSON text, so this deliberately produces an unscored
judge answer, not a passing verdict. Tests cover valid and invalid responses,
all authored controls, repeated samples, and diagnostic reporting without inference.

To judge a saved target-generation log with the same criterion prompt and parser,
use the separate Inspect task. This reads the native `.eval` log; it does not
regenerate target replies or expose the rubric during generation:

```bash
uv run --locked inspect eval grader.py@target_judge \
  -T source_log=results/<generation>/<log>.eval \
  --model mockllm/model --log-dir results/target-judge-smoke
uv run --locked python report.py results/<target-judge-smoke>/<log>.eval \
  > /tmp/bench-target-audit.json
```

The mock judge's default text is deliberately unscored. The target audit counts
Safety and Care verdicts, UNCLEAR, NOT_APPLICABLE, execution errors, and
unscored opportunities per check. Missing opportunities are split between source
generation gaps and unrun judge samples, using the full frozen family denominator.
It identifies the source generation log by
hash and carries its model usage alongside judge usage. It is a development
instrument, not a validated measurement of target-model quality. Live judging
requires the separately approved frozen plan and cost ceiling below.

Read criterion-level diagnostics from a saved native Inspect log:

```python
from inspect_ai.log import read_eval_log
from grader import summarize

report = summarize(read_eval_log("results/<run>/<log>.eval"))
```

The report keeps Safety and Care separate and counts false passes, false failures,
UNCLEAR judgments, applicability errors, execution errors, and unscored or missing
opportunities.
For an offline JSON audit report with run settings, model usage and reported cost,
source hashes, per-check counts, and each recorded trial's verdict and cited
evidence, run:

```bash
uv run --locked python report.py results/<run>/<log>.eval > /tmp/bench-audit.json
uv run --locked python report.py results/<run>/<log>.eval --format markdown \
  > /tmp/bench-audit.md
```

The report reads only the saved Inspect log. Its trial list contains recorded
samples; the per-check summary counts missing members of the frozen cohort.
The Markdown view is a readable run report with per-check denominators, source
binding, settings, and cited FAIL or UNCLEAR evidence keyed to Inspect sample IDs.
Open the `.eval` log in Inspect to review full transcripts. The local report is
not an independently validated score card.
Control reports describe grader behavior on authored controls. Target reports
describe unvalidated judge verdicts on saved conversations. Neither establishes
grader accuracy on independent labels or target-model quality. Review the output before sharing it:
Inspect logs and reports may contain private conversations.
Native `--limit` or `--sample-id` selections leave unrun members of the frozen
cohort marked missing; they are not failures. No composite score is calculated.
For a blind human-review packet from a saved generation log, run
`uv run --locked python review_packet.py <generation.eval> > <packet.json>`.
The packet is for a separately frozen review set, not the authored development
controls; see [the protocol](REVIEW_PROTOCOL.md). It may contain sensitive text.
Live judging requires an OpenRouter model and a positive task argument
`-T cost_limit_usd=<per-sample-ceiling>`, plus the separately approved frozen plan.
Inspect limits are cooperative; this is not a hard overall spending guarantee.

The old `bench` CLI remains archived. Use the original recorded Git revision
when historical replay requires the original source identity.

Every Eval Ever is an interoperability candidate. The tested converter does not
preserve this slice's four-state evidence and failed on the offline mock log.
See [the benchmark card](BENCHMARK_CARD.md#interoperability) for the export gate.

The published artifacts under `data/` remain the previous release. This rebuild
has not been published. Licensed under [MIT](LICENSE).
