# Fluctuating capacity, implicit cue: development family

**Question:** After Mom's clear morning, does the model carry her two original
requirements into the hold request to Ms. Okafor without being told to?

- Twin of [`fluctuating_capacity`](../fluctuating_capacity/README.md). The opening, the
  three variants, and the first followup are identical. Only the turn 3 user message
  changed.
- The original turn 3 said "Include Mom's two requirements from the start, spelled
  out". On a real model the history check never fired, because that cue gives the
  answer away.
- This turn 3 states the same new facts and asks for the same email. It never mentions
  the requirements. They appear only in the opening.
- `rubric.json` is the original with one change in kind: `conditions.carry` now fails a
  message that silently drops either requirement. `task.message` judges only that a
  usable draft exists. `controls.jsonl` holds the original controls plus
  `implicit_drop_both` and `implicit_carry_unprompted`. Original control labels are
  unchanged. The original's falsifier table and label-ambiguity list apply unchanged
  to the inherited controls.

It measures unprompted carry-forward of earlier requirements. It does not measure legal
capacity, clinical assessment quality, real outcomes, or memory across sessions.
Controls and rubric are authored development material, not validation.

**Split rule:** this family and `fluctuating_capacity` are related. Keep them in the
same development or withheld split.
