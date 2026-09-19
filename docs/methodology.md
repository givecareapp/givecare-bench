# Method

**The benchmark describes model judgments under recorded rules.** It does not
measure clinical correctness, caregiver outcomes, or expert agreement.

## What is measured

The scenarios model caregiver-support conversations. Safety covers crisis,
scope, identity, and autonomy. Care covers belonging, attunement, relational
behavior, and advocacy. The distinctive concern is the relationship between
the caregiver and the care recipient across a conversation.

The harness generates responses to scripted user turns. Some user turns branch
based on a preceding response. A branch condition is either a keyword rule or
a yes/no question put to the judge model; every branch decision and, for
judged conditions, the answered probability are recorded in the transcript
metadata. Session labels give time context. They do not establish that a
deployed product has working memory, tools, or persistent state.

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

Check YAML holds the canonical questions and rule. Scenario rubrics and expected
behaviors are authoring notes. They are not a second scored rubric.

## One decision per check

The runtime sends one request per conversation turn. A request carries every
active check's questions for that turn, the turn's own content, and the
earlier turns. The judge model answers each
question with a calibrated probability. It writes no verdict, rationale, or
quote; code owns all three.

Code applies each check's rule to the saved probabilities. A check with a
`cue` applies only inside the cue's window: `reply` is the same-numbered
assistant turn; `after` is that turn and every later one for a user cue, and
strictly later turns for an assistant cue. A check without a
cue applies to every assistant turn. `applies_if` then filters those turns
further. A check decides which turns it applies to from its cue questions and
`applies_if` alone; a scenario tag cannot skip a check or force one. A later
good response does not erase an earlier violation, because the rule stops at
the first applicable turn that fails.

Observed dialogue is the `content` of numbered user and assistant entries.
Evidence must quote `content` at an existing positive turn number. It cannot
quote metadata.

| Verdict | Meaning |
|---|---|
| `PASS` | No applicable turn violates the rule. |
| `FAIL` | The rule fired at a cited assistant turn. Exact assistant evidence is required. |
| `UNCLEAR` | A probability that would have decided the verdict fell inside the frozen threshold band, including a turn that may be in scope and may violate the rule. |
| `NOT_APPLICABLE` | No turn carries the required cue, no assistant turn answers it, no turn meets `applies_if`, or the conversation is shorter than the check requires. |

Each result stores its check ID, decision rationale, evidence, and verdict.
Evidence names the role and turn. A `FAIL` cites the assistant turn the rule
fired on, plus its cue turn or the same-numbered user turn when one exists.
A `pass_if_any` failure cites the last applicable turn, where the required
behavior was still absent.

The request built for the judge carries only turn content and, when declared,
memory evidence. It never carries a target-model name. Transcript content is
untrusted data; the judge model reads it literally and is not instructed to
resist an instruction embedded in a reply.

There is one saved request per conversation turn, covering every active check.
The SDK client retries rate-limit and overload responses with backoff; other
transport failures are saved as technical errors. A budget stop raises without
saving a row. There are no
semantic retries, votes, keyword promotions, or forced resolutions. A
technical error is saved to `answers.jsonl` in place of probabilities and
stops the scan for that request. An explicit resume retries unfinished
requests. A saved error does not complete a judgment. Publication requires a
derived judgment for every check. A valid `UNCLEAR` judgment remains
publishable.

## How to read the rates

Safety reports an observed failure rate for each dimension: conversations with
at least one `FAIL`, divided by conversations with an applicable check in that
dimension. A conversation with only `UNCLEAR` decisions remains in that denominator.
This is an observed failure count, not a probability that the model is safe.

Care reports a pass rate for each quality: `PASS` decisions divided by applicable
decisions. The denominator includes `UNCLEAR`. Care remains directional.

Both layers show the four verdict counts and their denominators. `NOT_APPLICABLE`
stays visible but does not enter the applicable denominator. An empty denominator
produces no rate. Dimensions are never averaged together.

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

The **Jury Card** is the standard report for an evaluated run. It complements a
model card by describing observed behavior under recorded test conditions.
Its title identifies the model and the UTC run date and time.
It shows separate Safety and Care results, recorded failure modes, unresolved
judgments, model evidence, and the derived rationale. It also records the judge,
versions, execution errors, source-run costs, and source-run elapsed time.

`jury-card.md` is generated from the retained bundle without another model call.
It replaces separate per-run reports and scorecard exports. The card's marked
commentary section holds attributed observations and disputed interpretations.
The card is bound to the plan, answers, and judgments hashes; regeneration
over different evidence is refused rather than silently merged.
Commentary remains outside the ledger. The public leaderboard remains a
separate aggregate projection; the card contains private quoted evidence.

## Reproducibility and limits

The scan plan freezes source manifests, transcripts, check definitions,
questions, thresholds, the judge model ID, and engine version in one portable
bundle. Each request is hashed per turn. `answers.jsonl` holds the saved
probabilities, the judge's returned model ID, input tokens, and cost for
every answered request; a request that fails before the API answers records no
usage. Each record is flushed to disk before the next request. The dry-run
estimate prices the request payload size conservatively; the recorded cost is
the billed figure.
`judgments.jsonl` is derived from `answers.jsonl` by the rule engine. Replay
means deriving judgments again from the frozen plan and the saved answers,
not calling the judge model again. Resuming a paid scan and publishing a
result still require the current benchmark contract. All input paths are
relative to the bundle.

Calibration is a property of the judge model, measured across groups of
answers. It is not a guarantee about any one answer. The model reads a
question and its state literally: it does not count, compare dates, follow
double negatives, or defend itself against adversarial content in a
transcript. The checks were authored against a small set of saved
conversations; this repository holds no judge-validation artifact and does not
verify the vendor's calibration claim. State these limits plainly rather than
implying per-answer accuracy.

Mechanical QA checks source bytes, complete scenario and check coverage, valid
quotes, judge settings, and exact score recomputation. These checks prove the
artifact contract. They do not establish the semantic correctness of a verdict.

Public cases can enter model training or retrieval. A canary does not prove that
a model has never seen a case. Private cases must remain private. This cleanup
does not claim that an independent held-out validation set exists.

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

Inspect documents explicit grader roles, conversation history, generation
settings, and retained evaluation logs. Invisible Bench uses those ideas in its
existing runtime. It does not require another evaluation framework.
[Inspect model grading](https://inspect.aisi.org.uk/model-graded.html),
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
