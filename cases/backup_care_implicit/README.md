# Backup care, implicit cue: development family

**Question:** When Dad accepts a longer visit, does the model carry his two original
conditions into the message to Sam without being told to?

- Twin of [`backup_care`](../backup_care/README.md). The opening, the three variants,
  and the first followup are identical. Only the turn 3 user message changed.
- The original turn 3 asked the model to "spell out both conditions". On a real model
  the history check never fired, because that cue gives the answer away.
- This turn 3 states the same new facts and asks for the same text to Sam. It never
  mentions the conditions. The conditions appear only in the opening.
- `rubric.json` is the original with one change in kind: `coverage.update` now fails a
  message that silently drops either condition. `task.message` judges only that a usable
  draft exists. `controls.jsonl` holds the original controls plus `implicit_drop_both`
  and `implicit_carry_unprompted`. Original control labels are unchanged.

It measures unprompted carry-forward of earlier conditions over three turns. It does not
measure whether real help was obtained, caregiver relief, clinical quality, or memory
across sessions. Controls and rubric are authored development material, not validation.

**Split rule:** this family and `backup_care` are related. Keep them in the same
development or withheld split.

## Audit note, 2026-10-29

The first turn-3 text also removed two facts (that Dad's agreement was on the earlier terms and that Sam had agreed to those terms), so its results were not attributable to the cue alone. Turn 3 now states both facts as "the same terms as before" and still never lists them or asks for them to be spelled out.
