# Invisible Bench

**Invisible Bench evaluates caregiver-support conversations and produces a Jury
Card for each completed scan.** One judge path evaluates each active check:
yes/no questions answered as probabilities, and a code-owned rule that
derives the verdict. Safety and Care stay separate. There is no composite
score or model rank.

Read Ali Madad's paper,
[*InvisibleBench: A Deployment Gate for Caregiving Relationship AI*](https://arxiv.org/abs/2511.20733).
It describes the original benchmark. This site documents the current method.

A **Jury Card** complements a model card with evidence from a specific run.
It shows quoted model evidence beside each verdict and its code-composed
rationale. It also records judge settings, costs, technical errors, and
attributed commentary. The card reports model judgments. It does not
establish judge accuracy or clinical outcomes. Care remains directional.

Each run keeps its `jury-card.md` and saved evidence in one private
`results/<run-id>/` directory. New runs get distinct UTC timestamps, including
runs of the same model. The saved plan, answers, and transcripts support
inspection and replay; judgments are derived from them.

The useful unit is a decision: **criterion → evidence → rationale → verdict**.
The conversation includes both the caregiver and the care recipient's needs.
A check's cue and window decide which later turns it applies to; a later good
response does not erase an earlier violation.

- [Run and inspect](quickstart.md): generate conversations, plan a scan, and read its Jury Card.
- [Method](methodology.md): understand the rules, rates, uncertainty, and limits.

Versions and counts come from the benchmark inventory. Check definitions live
in `checks/`, with their grammar in `checks/README.md`. The scan contract
lives in `src/invisiblebench/models/scan.py`, and the rule engine that derives
judgments lives in `src/invisiblebench/evaluation/rules.py`.
`src/invisiblebench/scoring.py` derives the public projection. These files are
the sources of truth in the repository.

Historical releases keep their original bytes and version labels. They are
not results from the current method. The new method needs new judge runs.
