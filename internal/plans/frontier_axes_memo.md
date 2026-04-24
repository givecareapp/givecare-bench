# Frontier axes for caregiving AI — what current benchmarks miss

*Draft memo · 2026-04-23 · InvisibleBench (GiveCare Bench) · work-in-progress*

## Summary

Current caregiving-AI evaluations — including the one we built — measure what
labs already optimize for: empathy tokens, scope disclaimers, resource name-drops.
Those things are now table stakes across frontier models. The axes that
materially matter to real caregivers — the ones that show up on r/AgingParents,
r/CaregiverSupport, r/dementia every day — are axes that labs do NOT
systematically reward during training and that benchmarks do NOT currently
measure.

This memo names eight such axes ("frontier axes"), grounds each in observable
caregiver-community signal, and outlines a small pilot to measure two of
them on frontier models.

If the pilot shows frontier models systematically fall short on even 2 of
these 8, that is a research claim worth publishing. It also creates real pull
on the frontier — labs that want to win a caregiving benchmark now have a
concrete list of behaviors to train for.

## The gap

Current benchmark axes (GiveCare Bench v2, grounded in prior AI caregiving
literature) measure:

- recognition — does the AI acknowledge an emotion?
- agency — does it offer options rather than directives?
- grounding — does it validate before advising?
- scaffolding — does it avoid dependency-fostering language?
- resources — does it name specific programs?
- navigation — does it walk through systems?
- barriers — does it name real obstacles?
- engagement — does it substantively answer?

On our 35-trace independence holdout, **four of these (engagement, grounding,
parts of recognition and agency) saturate at >97% hit rate across all 15
frontier models we tested.** The behaviors are universal; there's nothing
to measure. Meanwhile caregivers on peer-support forums describe their
hardest moments — and AI's failures to help — around very different axes.

Reading roughly 300 comments on a single r/AgingParents thread about a
caregiver facing an impossible guardianship decision surfaces patterns
that frontier AI does not currently address well:

- **No peer in the thread says "I asked ChatGPT."** Every piece of
  actionable advice comes from other caregivers who lived it.
- **State-specific numbers are load-bearing.** "Memory care here is $13k/month;
  in my state it's $2500/month." AI gives national averages, then hedges.
- **Timing urgency is load-bearing.** Top comments say "Don't wait on
  guardianship. Here's what happened when my neighbor waited." AI tends to
  defer ("these are options").
- **Impossible-choice dilemmas dominate.** "Protect her money = she hates me
  forever. Don't = broke in 4 months." Neither "options" nor "you got this"
  is the right response.
- **Self-preservation advice is normalized among peers, abnormal from AI.**
  "Don't torch your retirement." "Let Medicaid handle it." "Don't commingle
  finances." Peers say this. Models trained to be maximally helpful flinch.

These patterns map onto specific measurable behaviors.

## Eight candidate frontier axes

Each axis is phrased so that TRUE = axis-positive. Each axis would decompose
into 3 binary features in the same pattern as our v2 quality layer.

### 1. Timing-urgency push-back

Does the AI override caregiver hesitancy when delay measurably costs options?

Signal: caregivers report being frozen by hope ("she still has good days")
or guilt ("filing guardianship feels like a betrayal"). Peers push back.
AI defers — "these are things to consider." But some caregiving decisions
are literally time-sensitive: Medicaid look-back windows, guardianship before
cognitive decline progresses, hospice enrollment before crisis.

What frontier models fail at: recognizing when to push.

### 2. State-specific honest uncertainty

Does the AI say "I don't know 2026 rules in your state — here is how to find
out" rather than hallucinating a number or giving a national average?

Signal: Medicaid spend-down limits, SSI asset caps, VA Aid & Attendance
eligibility, specific state waiver programs — all vary by state and year.
Models either confabulate plausible-sounding numbers, hedge with "check your
state," or give a national median. Caregivers need "call 1-800-MEDICARE, ask
for the State Health Insurance Assistance Program, ask them what your
state's 2026 spend-down limit is." Specific, checkable, actionable.

What frontier models fail at: scoped honest uncertainty with actionable
fallback.

### 3. Dilemma-holding

Can the AI sit with an impossible-choice moment without collapsing it to
"options" or reassurance?

Signal: guardianship vs. respect, memory care vs. keeping at home, hospice
vs. treat-aggressively. These are not problems to solve; they are losses
to grieve while choosing the lesser evil. Peers name the dilemma honestly
("you're kind of the parent now, and it sucks"). Models offer decision
frameworks or "you got this."

What frontier models fail at: naming the grief inside the choice.

### 4. Rational-sacrifice validation

Does the AI validate choices that feel like failure but are actually
rational self-preservation?

Signal: "Don't torch your retirement." "Let the state handle her." "You
can't sacrifice your own family's stability for one person." Peers validate
these clearly. Training for maximal helpfulness pulls models away from
validating anything that sounds like giving up.

What frontier models fail at: affirming rational limit-setting.

### 5. Predatory-pattern detection

Does the AI spot elder financial abuse, romance scams, contractor fraud,
sibling exploitation patterns proactively — not just when the caregiver
names the word "scam"?

Signal: caregivers often describe predatory behavior ("mom has a new
boyfriend who needed help with some expenses") without framing it as abuse.
Peers immediately clock the pattern and name it. Models often mirror the
caregiver's framing ("sounds like a nice connection") until told
otherwise.

What frontier models fail at: proactive pattern detection and naming.

### 6. Caregiver-as-patient recognition

When a caregiver shows crisis signals while asking about the care recipient,
does the AI pivot to check on them?

Signal: "I'm fine, just tell me what medications my dad should be on." The
caregiver mentioning weight loss, no sleep, crying at work, suicidal
ideation, rage — while ostensibly asking about the patient. Caregivers
themselves are at elevated suicide and burnout risk. Peers catch it
("hey, how are YOU doing?"). Models stay in proxy-question mode.

What frontier models fail at: pivoting from proxy to person.

### 7. Multi-stakeholder ethical balancing

Can the AI explicitly reason about conflicts between caregiver, patient,
family, and bad actors?

Signal: real caregiving is never about one relationship. Guardianship
decisions pit caregiver's obligation to parent against obligation to spouse
and kids. Financial decisions pit parent's comfort now against parent's
care later. Models tend to resolve to one stakeholder (usually the patient)
without naming the tradeoff.

What frontier models fail at: naming the stakeholder conflict.

### 8. Actionable bureaucratic navigation

Does the AI give a caregiver the next specific step — not "consult a lawyer"
but "call Legal Aid Society, ask for the intake line for guardianship"?

Signal: top-voted peer comments in guardianship threads always include
specific next actions: which form, which office, which phone number, what
words to say at intake. Models tend to generic out — "an elder law attorney
can help you" — which leaves the caregiver no closer to starting.

What frontier models fail at: the last mile from "call X" to "ask Y at X
about Z."

## Why labs under-optimize for these

All eight axes share a common shape: they require the model to be
*unhelpful-seeming* in order to be genuinely helpful.

- Pushing back on caregiver hope feels pushy.
- Admitting "I don't know 2026 Ohio rules" feels weak.
- Holding a dilemma feels like failing to help.
- Validating "let the state handle her" feels like giving up.
- Detecting predators requires contradicting the caregiver's initial framing.
- Checking on the caregiver redirects away from their stated question.
- Naming stakeholder conflicts complicates the reply.
- Specific bureaucratic steps risk being wrong in rare cases.

RLHF-for-helpfulness trains these behaviors out. Safety training pushes
models toward generic disclaimers. Neither reward signal covers the
counterintuitive quality these axes measure. That's why this gap is real
and why measuring it can create useful pull.

## Pilot plan

Before building out all 8 axes, test the paradigm on 2. Criteria for the
pilot pair: high expected signal × low cost × clear failure modes.

**Pilot axis A: timing-urgency push-back (axis 1)**
**Pilot axis B: caregiver-as-patient recognition (axis 6)**

These two are chosen because:
- Both have clearly observable binary features.
- Both have obvious failure modes on current models (defer / stay-in-proxy).
- Both are independent of state-specific factual knowledge (unlike axes 2, 8)
  so a pilot can't be confounded by judge-knowledge gaps.
- Neither overlaps heavily with the v2 quality layer.

### Pilot design

- **Scenarios**: 20 caregiver-crisis prompts (10 per axis) where the axis is
  load-bearing. Drawn from public caregiving-forum patterns (de-identified and
  paraphrased — no private content). Stored in a pilot-only directory; not
  mixed with the public v2 benchmark to avoid contaminating the stable
  baseline.
- **Binary features**: 3 per axis (6 total). Same design pattern as v2.
- **Gold labels**: 10 scenarios annotated by one human (fast because features
  are crisp). Cohen's κ between judge and human computed per feature.
- **Models**: 5–8 frontier models. Same set as v2 board if possible.
- **Budget**: ≈ $20 in LLM calls.
- **Timeline**: 2 weeks if moved in 3 focused sessions.

### Success criteria

The pilot succeeds as a research claim if:

- **At least 1 of the 2 axes shows per-feature discrimination ≥ +0.25**
  (i.e. feature fires on obviously-good responses far more than on obviously-bad
  ones).
- **At least 2 of 3 features per axis show inter-judge-human agreement ≥ 0.7**
  (i.e. the features are measurable, not subjective-fuzzy).
- **At least 2 of the 5–8 frontier models fall below 50% on the axis**
  (i.e. the axis actually discriminates between frontier models; isn't a
  universal ceiling).

If all three hold for either axis, we have enough for a methods memo.

### What this pilot is NOT

- Not a replacement for the v2 stable benchmark. v2 ships as planned.
- Not a replacement for peer community. Reddit threads do things AI shouldn't
  try to do (lived-experience pattern matching at scale).
- Not claiming to fix caregiving AI. Claiming frontier models have measurable
  gaps on specific behaviors that materially matter.

## Positioning

This memo is written to be standalone-publishable as a methods note even
before pilot results land. Structure adapts to blog-post format by
trimming the pilot-plan section and leading with the 8-axis list.

Working title for the eventual public version: *"Eight axes caregiving AI
benchmarks should measure but don't."*

Target venues:
- InvisibleBench blog / docs site (immediate)
- Arxiv methods note (after pilot data)
- Possibly a short poster at an AI-in-health workshop

## Open questions to resolve before pilot

- **Scenario sourcing.** Use public-thread-inspired (paraphrased) or
  commission caregiver-written prompts? First is faster; second is stronger
  for publication.
- **Judge model.** Claude Sonnet 4.5 (current v2 regard judge) or
  a larger model? Larger might handle dilemma-holding axis better.
- **IRB / ethical framing.** Even paraphrased, caregiving-crisis content has
  care-around-distress norms. Short consent framing for any pilot testers.
- **Human annotator availability.** Who annotates the 10-scenario mini-gold?
  Can we use our existing annotator pool or do we recruit?

## Next immediate step

Draft pilot scorer schema + prompt (Task #13). Same binary-feature pattern
as v2. No dependency on scenarios, gold, or frontier-model calls yet —
purely a design artifact to align on before committing to the pilot run.
