# GiveCare Bench

**GiveCare Bench reports how a model judge evaluates caregiver-support conversations.**
It measures Safety and Care separately. It produces no composite score or rank.

The useful unit is a decision: **criterion → evidence → rationale → verdict**.
The conversation includes both the caregiver and the care recipient's needs.
Later cues, response timing, and session context remain visible to the judge.

- [Run and inspect](quickstart.md): generate conversations, plan a scan, and inspect decisions.
- [Method](methodology.md): understand the rules, rates, uncertainty, and limits.
- [Owner projection](evidence-lane.md): create a checked release through Helm Evidence.

Versions and counts come from the benchmark inventory. Check definitions live
in `checks/`. The scan contract lives in `src/invisiblebench/models/scan.py`.
`src/invisiblebench/scoring.py` derives the public projection. These files are
the sources of truth in the repository.

Historical releases keep their original bytes and version labels. They are
not results from the current method. The new method needs new judge runs.
