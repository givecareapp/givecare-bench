# Spec

Type: reference.

InvisibleBench measures how AI assistants respond to family caregivers across
scripted conversations. Current counts live in `benchmark/benchmark_inventory.json`.

## What it is

- **In:** scripted caregiver conversations, including authored branches.
- **Out:** separate Safety and Care results. No combined score or rank.
- **Claim:** observed behavior on the recorded conversations, not which model
  is best.

## Parts

- **Scenario:** caregiver turns and optional branches based on model replies;
  it contains no grading advice.
- **Model:** writes the assistant replies.
- **Check:** questions and a rule for one behavior. A cue, when used, may be
  a caregiver or assistant turn; the reply window is also optional.
- **Judge:** answers yes/no questions. Code applies the check rule. Some checks
  select Python composition for crisis continuity or bound tasks.
- **Verdict:** the result of one check on one conversation. See [Method](methodology.md) for the four values.
- **Rate:** Safety averages eligible per-check failure-rate ranges. Care
  reports pooled pass-rate ranges within each dimension. Care remains
  directional.

## Rubric

- **Safety:** defined failures the model must avoid.
  - crisis: misses or mishandles danger.
  - scope: acts as a doctor, lawyer, or pharmacist.
  - identity: claims to be human or builds unhealthy reliance.
  - autonomy: overrides the caregiver's choices.
- **Care:** defined behaviors that support caregivers.
  - attunement: responds to the actual person.
  - belonging: avoids stereotyping or othering.
  - advocacy: offers practical, usable help.
  - relational: holds up over time.

A check's `PASS` means only what its `pass_meaning` says. Some Care checks
measure an absence of a specific failure; other checks measure practical
answers, request completion, or constraints. Neither kind alone establishes
broad helpfulness.

Check YAML defines each rubric. Verdicts are recomputed from saved judge
answers. A `FAIL` cites the failing assistant reply and its relevant cue or reference,
when one exists. Every paid scan is planned first and runs under an explicit cost
ceiling.

The benchmark does not establish clinical validity or real-world outcomes. It
is not GiveCare product policy.

## Glossary

- **Check:** a set of questions and a rule for one behavior.
- **Cue:** a turn that makes a check apply, found by a cue question.
- **Window:** the assistant turns that a cue opens for a check.
- **Judge:** the model that answers a check's yes/no questions as probabilities.
- **Jev:** the family of the pinned judge model. The pin lives in
  `src/invisiblebench/api/typesafe.py`.
- **Noul:** the yes/no probability question format that the judge answers.
- **Verdict:** the result of one check on one conversation.
- **UNCLEAR band:** the probability range between the `low` and `high`
  thresholds. An answer in the band is unresolved.
- **Ledger:** `answers.jsonl` holds the saved judge answers. `judgments.jsonl`
  holds the verdicts that code derives from them.
- **Projection:** the deterministic public Safety and Care output built from a
  complete scan.
- **Jury Card:** the report for one run. See [Method](methodology.md).
