# Method

Type: reference.

**The benchmark describes model judgments under recorded rules.** It does not
measure clinical correctness, caregiver outcomes, or expert agreement.

<!-- benchmark:identity -->

Inspect a [worked measurement](worked-example.md) and the generated
[coverage tables](coverage.md). The [validation protocol](validation.md)
separates development examples, constructed controls, and independent review.

## What is measured

The scenarios model caregiver-support conversations. Safety covers crisis,
scope, identity, and autonomy. Care covers belonging, attunement, relational
behavior, and advocacy. The distinctive concern is the relationship between
the caregiver and the care recipient across a conversation.

Inspect generates responses to scripted user turns. Some user turns branch
based on a preceding response.

- A branch condition is a yes/no question put to the judge model about the
  assistant's reply to the previous turn. Keyword rules are not allowed. They
  cannot tell endorsement from refusal or quotation.
- Every branch decision and its answered probability are recorded in the
  transcript metadata.
- Each branch probability must be finite and between 0 and 1, inclusive. An
  invalid probability stops branch selection.
- A judged branch matches at or above its `min` probability.
- Below `min`, a probability above the default scan `low` threshold is
  ambiguous. It stops branch selection with a technical error.
- Only a probability at or below `low` lets selection continue to the next
  branch.
- Projection recomputes the selected branch from the saved judge response and
  the authored condition. It also checks that response and its request hash
  against the preceding reply before it accepts the recorded path.

Session labels give time context. They do not establish that a deployed product
has working memory, tools, or persistent state.

Private scans can also evaluate committed product conversations. The public
leaderboard still requires the raw-model harness. A product result must not be
presented as a comparable raw-model result.

### Product memory

The memory check defaults to no persistent memory. A product source declares
`harness: "product"`, `mode: "committed"`, and
`transcript_policy.persistent_memory: true` in `run_manifest.json`.
Raw-model runs cannot declare this capability.

Each entry in `transcript_run.json` may supply `memory_evidence` for that
conversation. Each record contains:

- `turn`: the assistant response turn at which the evidence was available.
- `operation`: `read`, `remember`, `forget`, or `correct`.
- `status`: `succeeded` or `failed`.
- `memory_id`: the product's stable memory ID.
- `text`: the exact memory text; required for successful reads and writes.

The source exporter must capture these records from product state or operation
receipts. Assistant and caregiver statements cannot establish capability or
prove a successful operation. Proposed tool arguments and commit labels alone
do not prove which record was stored or deleted. A forget receipt with only an
ID cannot prove a fact-specific deletion without observed text for that ID.
The scan freezes the manifest and summary with
the transcripts. It supplies this data separately from conversation text, as a
`memory_context` field, only to assistant-turn requests and only when
declared, and binds it into the judge request hash. Source run IDs,
transcript paths, and conversation identities must match. Judge requests read
only the role, turn number, and content of each entry; turn metadata never
reaches the judge.

A declaration of persistent memory alone does not earn a pass. A supported
statement can pass. A claim that the recorded evidence contradicts or does not
cover is unsupported and fails; the product owns supplying its receipts. Later
evidence cannot justify an earlier claim.
The scan verifies the retained bytes and record shape; it does not independently
authenticate a product's database. Keep sensitive memory evidence private.

Check YAML holds the canonical questions, requirement basis, rule, and narrow
pass meaning. It is the only rubric. A scenario is the caregiver script; it
carries no grading notes.

## One decision per check

For each conversation turn, the runtime groups questions into size-bounded
requests. The [check grammar](https://github.com/givecareapp/givecare-bench/blob/main/checks/README.md#sentence-questions)
owns the grouping rule. Evidence is never truncated. An observation sees the same evidence in an exemplar, probe, or
full scan. The judge model answers each question with probabilities. Benchmark-specific
calibration is not established. Code derives the verdict, rationale, and quote.

Code applies each check's rule to the saved probabilities. `crisis.decay` uses
a Python function to compose observations bound to a reference crisis and a
numbered message. Its questions separate safety actions, reported confirmation,
and later response behavior. The [check grammar](https://github.com/givecareapp/givecare-bench/blob/main/checks/README.md#python-composition)
defines its evidence and temporal policy. A pass means that its specific
downgrade condition did not occur; it does not establish the caregiver's safety.

Bound task checks assess a produced draft against the caregiver's visible
requirements, or factual statements against a supplied excerpt. They do not
verify source authenticity, live availability, or action completion. Missing task
evidence does not earn a pass. See the [check grammar](https://github.com/givecareapp/givecare-bench/blob/main/checks/README.md#bound-task-checks).

A check's cue, window, and `applies_if` decide which turns it applies to. The
window is `reply`, `after`, or `later`. The [rule semantics](https://github.com/givecareapp/givecare-bench/blob/main/checks/README.md#rule-semantics)
define each one. A scenario tag cannot skip a check or force one. A later good
response does not erase an earlier violation, because the rule stops at the
first applicable turn that fails.

Observed dialogue is the `content` of numbered user and assistant entries.
Evidence must quote `content` at an existing positive turn number. It cannot
quote metadata.

| Verdict | Meaning |
|---|---|
| `PASS` | No applicable turn violates the rule. |
| `FAIL` | The rule fired at a cited assistant turn. Exact assistant evidence is required. |
| `UNCLEAR` | Answers inside the frozen threshold band could resolve to different verdicts. The engine resolves each unresolved answer both ways; if the verdicts differ, the judgment is `UNCLEAR`. |
| `NOT_APPLICABLE` | No turn carries the required cue, no assistant turn answers it, no turn meets `applies_if`, or the conversation is shorter than the check requires. |

Each result stores its check ID, decision rationale, evidence, and verdict.
Evidence names the role and turn. A `FAIL` cites the assistant turn the rule
fired on, plus its cue turn or the same-numbered user turn when one exists.
A `pass_if_any` failure cites the last applicable turn, where the required
behavior was still absent.

The request built for the judge carries turn content, declared memory evidence,
and task evidence selected from the caregiver's visible message. It never
carries a target-model name. Transcript content is untrusted data. The judge
model reads it literally. It is not told to resist an instruction embedded in a
reply.

Each request is saved separately. The engine combines disjoint answers for a
turn before applying the checks. A duplicate observation is an error.

The SDK client does not retry. There are no semantic retries, votes, keyword
promotions, or forced resolutions. The attempt journal owns recovery. The
[quickstart](quickstart.md#resume-a-scan) describes it.

Each dispatch reserves the cost of the pinned judge model's full input ceiling.
The ceiling is `JEV_MAX_INPUT_TOKENS` in `src/invisiblebench/api/typesafe.py`.
The reservation then settles to reported usage. The byte-based estimate is for
planning only. A budget stop raises before dispatch.

An invalid answer with reported usage is saved to `answers.jsonl` in place of
probabilities. It stops the scan for that request. A saved error does not
complete a judgment. Publication requires a derived judgment for every check. A
valid `UNCLEAR` judgment remains publishable.

## How to read the rates

An `UNCLEAR` judgment has a set of verdicts the frozen rule still permits.
Rates use that set; they never count an `UNCLEAR` as settled.

- **Rate range.** Each rate is a range. Its low end resolves every `UNCLEAR` to
  its most favorable permitted verdict, and its high end to the least favorable.
  `NOT_APPLICABLE` leaves the denominator. The range is conditional on the
  frozen rule. It is not a confidence interval and does not bound real-world
  harm.
- **Safety.** Each check reports a failure-rate range. A dimension's range is
  the mean of its checks' ranges, so each check weighs equally. A check enters
  that mean only with enough settled `PASS` or `FAIL` verdicts. The minimum is
  `MIN_CHECK_CASES` in `src/invisiblebench/scoring.py`. A check
  with fewer reports its counts (`FAIL`/settled) as case findings, and one with
  none reports no performance result. The projection also counts conversations
  with a settled `FAIL`.
- **Care.** Each quality reports a pass-rate range over all of its checks.
  Care remains directional.
- **Unresolved verdicts.** Counts separate an `UNCLEAR` that could still be a
  `FAIL` from one that can only end `PASS` or `NOT_APPLICABLE`. The second shows
  no violation, but whether the check applied is unresolved.

Both layers show the verdict counts. `NOT_APPLICABLE` stays visible but does not
enter a denominator. An empty denominator produces no rate. Dimensions are never
averaged together.

The fixed corpus does not establish population sampling error or judge accuracy.
The projection therefore reports descriptive rates and counts without confidence
intervals. Different benchmark, check, prompt, or judge versions are different
measurement conditions.

## The decision rationale and later critique

A decision rationale is composed by code from the saved probabilities and the
question names in the check's rule: which question decided the verdict, its
probability, and whether that probability read as yes, no, or unresolved. The
judge model never writes the rationale.

A reviewer can cite the scan, check ID, evidence, and rationale in a critique.
Clinician review is welcome and optional. It does not gate a scan or publication.
Keep the critique outside the ledger. Preserve the original decision.
If a critique changes a rule or judge setting,
version that change and run a new scan. Do not edit the old verdict.

The **Jury Card** is the report for an evaluated run. It opens with the model
and UTC run date, then shows Safety and Care in the same per-check table format.
Each layer reports how many checks have enough settled cases for coverage and
how many have none; this describes coverage, not accuracy. Each row gives a
plain check label and counts for PASS, FAIL, UNCLEAR, and NOT_APPLICABLE. One
expandable section per dimension gives each check’s narrow meaning and flagged
evidence. Dimension ranges follow the findings: Safety is a failure rate, Care
is a directional pass rate. They are never combined. Score details names the
checks each Safety rate averages and lists the rest with their settled counts.
For each pooled Care rate it gives every check's share of the settled cases,
so a dimension driven by one check is visible. Judge, version, execution,
source-run cost, and elapsed-time records remain available later in the card.
The card describes behavior under recorded test conditions; it does not
establish broad model quality.
When a source summary carries frozen research expectations, the card reports
expected and observed outcomes, their stated evidence basis, errors, unresolved
cases, and unlabeled coverage. These annotations never enter judge requests or
verdict rules. A rejected research attachment stays visible without blocking
completion. See the [validation protocol](validation.md) for the constructed controls.

`jury-card.md` is generated from the retained bundle without another model call.
The card's marked commentary section holds attributed observations and disputed interpretations.
The card is bound to the plan, answers, and judgments hashes; regeneration
over different evidence is refused rather than silently merged.
Commentary remains outside the ledger. The public leaderboard remains a
separate aggregate projection; the card contains private quoted evidence.

## Reproducibility and limits

Generation freezes each model's OpenRouter serving policy alongside its prompt
and settings. The [quickstart](quickstart.md#provider-routing) describes the two
routing modes. Returned provider identities are recorded separately. A missing
historical policy remains unknown and cannot support a new public release.

Each public model row includes an `evaluation_configuration`. It contains the
requested serving policy, observed provider identifiers from that model's replies,
and allowlisted generation settings. Missing observations remain explicit; the
projection never substitutes a run-wide provider list or a requested restriction.
Generation settings expose the prompt hash, not the prompt text. Private manifests,
transcripts, and memory receipts do not cross this boundary.

Generation records the owning checkout's full Git commit and clean/dirty state.
If either Git inspection fails, both fields remain unknown. Publication rejects
unknown or malformed commits and any state other than a confirmed clean tree.

Publication compares common generation settings and code across source runs.
Model-specific serving policies may differ between models, but not within one
model row. Safety and Care calculations remain separate and unchanged.

The scan plan freezes source manifests, transcripts, check definitions,
questions, thresholds, the judge model ID, and engine version in one portable
bundle. Request identity includes the conversation, role, turn, and hash of
the exact evidence and questions. `answers.jsonl` holds the saved
native typed answers, the judge's returned model ID, input tokens, and cost for
every answered request; a request that fails before the API answers records no
usage. Each record is flushed to disk before the next request. The dry-run
estimate uses request payload size. It is approximate and can understate cost.
Recorded cost uses the API's reported input tokens and the pinned judge price.
`judgments.jsonl` is derived from `answers.jsonl` by the rule engine. Replay
means deriving judgments again from the frozen plan and the saved answers.
It does not call the judge model again. Replay requires the installed engine version
to match the frozen plan. An engine change can alter request text or sentence
boundaries, so saved answers cannot be reused under that new engine. Preserve
the original bundle and plan a separate scan from its retained source runs.
Resuming a paid scan and publishing a result also require the current benchmark
contract. All input paths are relative to the bundle.

Calibration is a property of the judge model, measured across groups of
answers. It is not a guarantee about any one answer. The model reads a
question and its state literally: it does not count, compare dates, follow
double negatives, or defend itself against adversarial content in a
transcript. The checks were authored against a small set of saved
conversations. No independently reviewed real-conversation validation result is
published here, and development exemplars do not verify the vendor's calibration
claim. State these limits plainly rather than implying per-answer accuracy.

Each check also ships hand-written exemplars: short transcripts with the
verdict the rule must derive, and the judge model's saved answers for them.
The pre-commit gate derives every exemplar from those committed answers and
fails on a mismatch or a stale answer. This pins what a check means; it does
not measure accuracy on real conversations. Comparing two judge runs also
measures agreement. Constructed controls test declared boundaries and invariances;
they do not estimate accuracy on real caregiver conversations. Such accuracy claims
need unseen caregiver conversations with independent labels, including caregiver–recipient
safety cases. Those labels must not be inferred from either judge or the exemplars.
Independent review remains optional and cannot block a scan or publication.
The [validation protocol](validation.md) uses frozen expectations and the existing
scan executor. Read-only comparison reports never replace ledger judgments.

Mechanical QA checks source bytes, complete scenario and check coverage, valid
quotes, judge settings, and exact score recomputation. Public projection also
checks each transcript against the authored scenario: ordered user/reply pairs,
scripted user text or the branch recomputed from its condition and preceding
assistant reply. A branched turn must include a valid saved response bound to
that evidence by its request hash. Replies must be nonblank and have no error or
truncation markers. An opening-turn branch is invalid. Any recorded resolved
model ID must match the source model. These checks prove the
artifact contract. They do not establish the semantic correctness of a verdict.

Public cases can enter model training or retrieval. A canary does not prove that
a model has never seen a case. Private cases must remain private. No independent
held-out validation set is claimed.

## Research basis

Ali Madad introduced the benchmark in
[*InvisibleBench: A Deployment Gate for Caregiving Relationship AI*](https://arxiv.org/abs/2511.20733).
That paper describes the original design. The method above defines the current
implementation.

Per-criterion model grading and realistic conversation context have useful
precedents. HealthBench uses model grading over detailed health-conversation
rubrics. Its physician-built criteria and separate validation evidence are
properties of that benchmark; they do not transfer to Invisible Bench.
[HealthBench paper](https://arxiv.org/abs/2505.08775).

Transcripts are generated with UK AISI Inspect, which owns generation, retries,
cost limits, and evaluation logs. `bench export` turns Inspect logs into the run
directory that the judge reads. Judging stays outside Inspect so that every
verdict can be derived again from saved answers.
[Inspect](https://inspect.aisi.org.uk/),
[Inspect logs](https://inspect.aisi.org.uk/eval-logs.html).

JudgeBench shows that difficult correctness judgments can remain unreliable.
Research on position bias also shows that repeated agreement alone does not
establish validity. These findings support narrow claims and inspectable
records. They do not establish that this judge is accurate.
[JudgeBench](https://arxiv.org/abs/2410.12784),
[position-bias study](https://arxiv.org/abs/2406.07791).

Decomposing a rubric into atomic yes/no questions, with the composition rule
owned by code rather than the model, follows the System One design guidance
for this class of judge.
[How to build with System One](https://docs.typesafe.ai/concepts/how-to-build-with-system-one).
