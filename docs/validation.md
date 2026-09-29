# Validate the evaluator

Type: how-to.

Use a frozen evaluator and expectations established before inspecting its answers.
Keep this research outside runtime judging. A label cannot replace a saved verdict
or block an ordinary scan.

## Separate the data by purpose

| Data | Permitted claim |
| --- | --- |
| Development exemplars | The saved answers still produce the authored rule outcomes. |
| Frozen validation cases | Agreement with the independently justified expectations on these cases. |
| Target-model conversations | Observed model behavior under the recorded evaluation conditions. |

A controlled fixture can establish a literal task requirement or a fact supplied
in an excerpt. Interpretive safety claims need independently justified labels
from people with relevant expertise. Record who supplied each expectation and
why. A label from a second model does not establish independent correctness.

## Freeze the study

1. Name the check and the narrow claim being tested.
2. Record its requirement basis and the meaning of PASS from the check definition.
3. Select cases without using the evaluator's answers to choose favorable cases.
4. Include a prohibited behavior and a legitimate-behavior control for each boundary.
5. Specify each expectation from source evidence, known operations, or independent review.
6. Record ambiguities without forcing them into PASS or FAIL.
7. Freeze transcript bytes, check definitions, judge settings, and expectations before inference.
8. Keep this set out of prompt tuning. After inspecting errors, use fresh cases for a later validation claim.

Useful paired controls include current versus resolved risk, caregiver versus
recipient, an unavailable option versus a feasible alternative, a supported
claim versus an invented detail, and a completed task versus a promise.
A refusal can avoid a prohibited statement while failing the requested task.
Report both checks separately.

Start with a small controlled battery. Its results describe those constructed
boundaries. They do not establish accuracy on unseen real caregiver conversations
or certify caregiver safety. No independently reviewed real-conversation validation
result is published by this protocol.

## Use the existing execution path

Prepare a source run with its manifest, summary, and transcripts. Label authored
fixtures as `harness: "fixture"` and `mode: "authored"`; never label them as a
raw target-model run. Use the ordinary scan planner to freeze them:

```bash
uv run bench scan plan <source-run> --output results/<new-run-id>
```

For a single check, use `scripts/probe_check.py plan <check-id> <transcripts...>
--output results/<new-run-id>`. Probes use the same evidence selection and rule
engine as full scans.

Review the saved estimate. Obtain an explicit cost ceiling before running a plan.
Keep all returned answers, including disagreements and UNCLEAR outcomes. Do not
reroll a case, weaken a threshold, or relabel an expectation to make it pass.

## Record expectations

The read-only `bench compare --expectations <file.jsonl>` report accepts one JSON
object per independently specified judgment. Required fields are:

| Field | Content |
| --- | --- |
| `model_id`, `scenario_id`, `check_id` | Exact identities in the frozen scan. |
| `transcript_sha256` | Digest from that transcript's frozen `TranscriptSource`. |
| `check_sha256` | `sha256(json_bytes(check.model_dump(mode="json")))`, using `invisiblebench.judge`. |
| `expected` | PASS, FAIL, UNCLEAR, or NOT_APPLICABLE. |
| `basis` | `controlled_fixture`, `source_evidence`, or `independent_review`. |
| `source` | Source identity and the evidence supporting the expectation. |
| `author`, `reason` | Who supplied the expectation and the specific justification. |

Store private expectations in the existing `internal/calibration/labels/` location.
Do not move them into public projections. Duplicate expectations are rejected.
Each label must bind to exact transcript and check bytes in at least one compared
scan. Labels for a changed definition are excluded from the other scan and listed
explicitly. The report retains provenance; it cannot authenticate independence.

To inspect one scan against its expectations, pass that bundle as both inputs:

```bash
uv run bench compare --old <scan> --new <scan> --expectations <file.jsonl>
```

## Compare decisions, applicability, and cost

Plan new judging from retained transcripts into a new directory. Preserve the
old plan and answers. `bench scan rejudge` freezes the old checks with a new judge;
`bench scan plan <retained-source> --output <new>` uses the current checks.

```bash
uv run bench compare --old <old-scan> --new <new-scan> --expectations <file.jsonl>
uv run bench --json questions <new-scan>
```

The comparison reports four-verdict transitions, applicability, uncertainty,
coverage, saved request cost, and source execution settings. It refuses a judge
comparison when shared conversation identities have different transcript bytes.
Expectations add a confusion table, false passes, false failures, and unresolved
counts. Keep unlabeled cases visible. Report counts and denominators for each
check; small constructed sets do not support population accuracy estimates.

`bench questions` separates raw probability uncertainty from observations whose
resolution can narrow a judgment's possible verdicts. Each effect names the
conversation, role, turn, and exact observation key, including bound references.
NOT_APPLICABLE-or-PASS differs from PASS-or-FAIL. The report resolves one answer
at a time. Some judgments need several answers to resolve together, so zero reported
effects does not prove that an unresolved answer is irrelevant. On partial scans,
judgment-level analysis is unavailable; saved probabilities remain inspectable.

Replay historical scans with their recorded engine's checkout. The current CLI
rejects retired engine formats. For a cross-engine study, validate each bundle
with its native engine, then compare the retained judgment identities and transcript
hashes in the research analysis. Do not migrate old answers into the new engine.

A lower UNCLEAR rate alone does not show improvement. Keep changed definitions,
applicability transitions, independently checked errors, and cost beside it.
