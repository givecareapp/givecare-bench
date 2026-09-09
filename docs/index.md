# Invisible Bench

**Invisible Bench evaluates caregiver-support conversations and produces a Jury
Card for each completed scan.** One LLM judge checks the full conversation
against each active criterion. Safety and Care stay separate. There is no
composite score or model rank.

A **Jury Card** complements a model card with evidence from a specific run.
It shows quoted model evidence beside the judge's verdicts and rationales.
It also records judge settings, costs, technical errors, and attributed
commentary. The card reports model judgments. It does not establish judge
accuracy or clinical outcomes. Care remains directional.

Each run keeps its `jury-card.md` and saved evidence in one private
`results/<run-id>/` directory. New runs get distinct UTC timestamps, including
runs of the same model. The saved plan, judgments, and transcripts support
inspection and replay.

The useful unit is a decision: **criterion → evidence → rationale → verdict**.
The conversation includes both the caregiver and the care recipient's needs.
Later cues, response timing, and session context remain visible to the judge.

- [Run and inspect](quickstart.md): generate conversations, plan a scan, and read its Jury Card.
- [Method](methodology.md): understand the rules, rates, uncertainty, and limits.

Versions and counts come from the benchmark inventory. Check definitions live
in `checks/`. The scan contract lives in `src/invisiblebench/models/scan.py`.
`src/invisiblebench/scoring.py` derives the public projection. These files are
the sources of truth in the repository.

Historical releases keep their original bytes and version labels. They are
not results from the current method. The new method needs new judge runs.
