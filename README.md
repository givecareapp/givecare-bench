# InvisibleBench

InvisibleBench is being rebuilt around multi-turn caregiver support: whether an
assistant provides useful help while respecting caregiver capacity, both people's
agency, the availability of support, and danger to either person.

The previous implementation is preserved in [_archive/5.8.0](_archive/5.8.0/README.md).
See the [archive record](_archive/README.md) for its source revision and verification.
The first development slice and its grader pilot task are runnable. There is no
new benchmark result or validated grader yet. [Design and measurement contract](DESIGN.md).

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
grader.py        separate Inspect task for judging authored controls
cases/
  backup_care/
    case.json    shared turns and matched availability conditions
    rubric.json  separate Safety/Care review criteria
    controls.jsonl authored responses and expected judgments
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

Read criterion-level diagnostics from a saved native Inspect log:

```python
from inspect_ai.log import read_eval_log
from grader import summarize

report = summarize(read_eval_log("results/<run>/<log>.eval"))
```

The report keeps Safety and Care separate and counts false passes, false failures,
UNCLEAR judgments, applicability errors, execution errors, and unscored or missing
opportunities.
Native `--limit` or `--sample-id` selections leave unrun members of the frozen
cohort marked missing; they are not failures. No composite score is calculated.
Live judging requires an OpenRouter model and a positive task argument
`-T cost_limit_usd=<per-sample-ceiling>`, plus the separately approved frozen plan.
Inspect limits are cooperative; this is not a hard overall spending guarantee.

The old `bench` CLI remains archived. Use the original recorded Git revision
when historical replay requires the original source identity.

The published artifacts under `data/` remain the previous release. This rebuild
has not been published. Licensed under [MIT](LICENSE).
