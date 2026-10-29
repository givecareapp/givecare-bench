# InvisibleBench

InvisibleBench evaluates how an assistant handles multi-turn caregiver-support
conversations. The active project is a **0.1.4 development slice**, not a
validated InvisibleBench 6.0 release. There is no new model result or validated
grader. Safety and Care remain separate; there is no composite score or model rank.

The [benchmark card](BENCHMARK_CARD.md) contains the measurement contract,
validation status, review protocol, and interoperability limits. The first
[case family](cases/backup_care/README.md) tests respite coordination as a
helper's availability and the care recipient's consent change.

## Layout

```text
task.py                  Inspect generation task (one family per run) and solver
grader.py                Inspect control and target judging tasks; shared scorer
report.py                Offline JSON or Markdown report from judge logs
review_packet.py         Blind human-review packet from a generation log
cases/<family>/          One case family: case, rubric, authored controls, notes
                         (backup_care, fluctuating_capacity)
tests/                   Offline harness and contract tests
scripts/check.sh         Active checks, then the archived gate
BENCHMARK_CARD.md        Methods, evidence, limits, and review protocol
_archive/5.8.0/          Frozen prior public implementation
data/                    Unchanged prior public artifacts
```

`private/` is a separate ignored repository. `results/` contains historical
private run evidence. The old 5.8 implementation and its source revision are
recorded in the [archive record](_archive/README.md). It is not imported by the
active tasks. The ignored `site/` directory is generated output, not active
source.

## Run offline checks

```bash
scripts/check.sh
```

This runs active lint and mocked tests, then the unchanged archived gate. It
verifies engineering behavior, not grader accuracy or clinical validity. The
locked environment may download free dependencies. For active tests alone, run
`uv run --locked pytest tests -q`.

## Use the development tasks

Each directory under `cases/` is one family. Name the family with `-T family=<name>`.
The default is `backup_care`. An unknown name fails with the list of known families.

Generate a free mock conversation log and inspect it:

```bash
uv run --locked inspect eval task.py@conversation_family -T family=backup_care \
  --model mockllm/model --log-dir /tmp/bench-generation
uv run --locked inspect view --log-dir /tmp/bench-generation
```

Judge authored controls with a mock response:

```bash
uv run --locked inspect eval grader.py@control_judge -T family=backup_care \
  --model mockllm/model --limit 1 --log-dir /tmp/bench-controls
```

Judge a saved generation log without regenerating the target conversation.
The judge reads the family from the log:

```bash
uv run --locked inspect eval grader.py@target_judge \
  -T source_log=/tmp/bench-generation/<log>.eval \
  --model mockllm/model --log-dir /tmp/bench-judge
uv run --locked python report.py /tmp/bench-judge/<log>.eval --format markdown \
  > /tmp/bench-report.md
```

Replace `<log>.eval` with the actual filename Inspect wrote. The default mock
judge returns non-JSON text, so its answer is deliberately **unscored**. A mock
run proves the plumbing, not caregiver-support capability. The report preserves
per-check denominators, four-state verdicts, interrupted and unattempted
generation, judge errors, cited evidence, source hashes, settings, and usage.
The control report lists every disagreement with the authored labels: false
passes, false failures, and applicability. Inspect `.eval` logs are the source
of truth.

For a blind packet from a saved generation log:

```bash
uv run --locked python review_packet.py /tmp/bench-generation/<log>.eval > /tmp/bench-review.json
```

The packet omits model identity and judge answers. It can contain sensitive
conversation text; use the [review protocol](BENCHMARK_CARD.md#independent-review-protocol)
before sharing or labeling it. Authored controls are development material, not
independent validation evidence.

Paid inference requires a saved plan and explicit cost ceiling. No paid run,
publication, push, or deployment is implied by these commands. The prior
[paper](https://arxiv.org/abs/2511.20733) describes the original benchmark;
it does not validate this rebuild. Licensed under [MIT](LICENSE).
