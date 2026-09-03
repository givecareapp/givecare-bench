# GiveCare Bench — Harvest & Field Contract

> Governed by `~/wiki/atlas/givecare-bench.md` (intent). This file owns
> procedure only; intent found here migrates up.

## Objective

Monthly, after new results have published, harvest what the benchmark learned
for GiveCare's own use, and identify which field targets should engage with
the benchmark this month. Per the atlas Lanes line: *the standard must reach
the field, not only the leaderboard.*

Evaluation itself — Define, test, verify, calibrate, compare — is event-driven
on a model release, per the atlas capability frame's Direction and Flow. It is
never this lane. **Never run an evaluation, a scan, or any paid work to
produce something to harvest.** If nothing has published since the last
harvest, decline; do not manufacture material.

## Schedule

The dispatch lane `bench-harvest` runs this contract monthly, first Monday
09:00 America/New_York. Dispatch owns the schedule; this contract owns the
lane's read, harvest, and draft steps.

Consent is `asks`: this lane proposes, the owner decides via Docket. It never
sends, posts, publishes, deploys, or writes to another repository or system.

## Scope

This contract owns exactly two periodic verbs from the bench capability
frame: **harvest learnings** and **reach the field**. It does not own Define,
test, verify, calibrate, or compare. It does not certify GiveCare's own
product — per `VISION.md`, bench does not certify GiveCare itself until its
independence requirements are in place, and this lane makes no exception. It
never sends outreach; every field-facing output is a draft for human review.

## Read-only tooling

Use the `bench` skill's read-only CLI for every run discovery and evidence
read (`~/agents/_skills/bench/SKILL.md`):

```bash
cd /home/deploy/repos/givecare/gc-bench
uv run bench --json leaderboard status
uv run bench --json health
uv run bench --json runs --limit 25
uv run bench --json get <run-id>
uv run bench --json explain <model> <scenario> --failures
```

Do not read scan or run files ad hoc when a CLI command already covers the
read. Do not use `bench archive`, any paid-scan command, or any command not
listed above.

## State

`delivery/harvest/state.json` records
`{"last_harvest_at": "<ISO8601 UTC>", "last_leaderboard_generated_at": "<ISO8601 UTC>"}`.
Absent on the first run — treat that as no prior harvest, not as an error.

## Steps

1. Work only in `/home/deploy/repos/givecare/gc-bench`. Read `VISION.md`,
   `AGENTS.md`, `CLAUDE.md`, `docs/what-invisiblebench-owns.md`,
   `docs/publishing-audit.md`, `docs/results-experience.md`, and
   `docs/governance.md`. Do not spawn subagents.

2. Read `delivery/harvest/state.json` if present, for `last_harvest_at`. Run
   `uv run bench --json leaderboard status` and read
   `data.scan_metadata.generated_at` as the current published leaderboard's
   timestamp, and `data.scan_metadata.source_artifact` plus
   `data.scan_metadata.source_merge.sources[].artifact_id` as its run handles.

3. **Decline condition.** If `data.scan_metadata.generated_at` is not newer
   than the state file's `last_leaderboard_generated_at` (or no state file
   exists and the leaderboard's `generated_at` predates the lane's own first
   scheduled month), or the leaderboard/release artifacts are absent, nothing
   has published since the last harvest. Do no further work; report
   `NOTHING_TO_HARVEST since <last_harvest_at, or "never">` and stop.

4. **Harvest — findings digest for sms.** Compile a failure-taxonomy-pressure
   digest from the current leaderboard and `bench get`/`bench explain`
   evidence for the models it covers. Boundaries, enforced from
   `VISION.md`/`AGENTS.md`/`docs/governance.md`:
   - Cite every number to a run handle (a `bench get <run-id>` result or a
     `source_merge.sources[].artifact_id`). No number without a citation.
   - Never include scenario text, verifier prompts, or expected answers.
     Carry only check IDs, verdict rates/counts, and plain-English
     failure-mode names — the taxonomy pressure, not the material that
     produces it.
   - State plainly that Safety numbers are not `claim_ready` unless the read
     data marks `calibration_status: claim_ready` (none are, as of this
     contract's authoring) and that Care numbers are directional, per
     `docs/governance.md` § Conflict of interest and `docs/publishing-audit.md`
     § Claim Posture. Never composite Safety and Care into one score or rank.
   - Write to `delivery/harvest/<YYYY-MM>.md`.

5. **Harvest — verified-safety-evidence note for evidence-cycle.** Check
   whether `/home/deploy/repos/givecare/.agents/evidence-cycle.md` exists and
   defines an intake (a documented drop location or schema for incoming
   evidence). If it does, write one short pointer record there per its
   schema: the run handle(s), the publish date, and a one-line pointer to the
   step 4 digest. Carry no raw evidence, scenario text, or verifier material
   into it. If `evidence-cycle.md` does not exist, or exists but defines no
   intake, skip that write, append the same pointer as a labeled section at
   the foot of the step 4 digest file instead, and say so plainly in the
   report body.

6. **Reach the field.** From the current publish, list target audiences named
   in the atlas node's Audience field — model builders whose model is newly
   covered this cycle, labs, and policy bodies among "researchers, model
   builders, evaluators, practitioners, policymakers, journalists." For each
   candidate, look up existing relationship state read-only with
   `~/bin/crm find "<org or person>"` (see `~/agents/CLAUDE.md` § CRM).
   **Never write to CRM.** Draft one short outreach note per target: what to
   cite (the run handle and the specific finding, never raw scores or a
   rank), and why now (new model coverage, a relevant finding). Write every
   draft to `delivery/outreach/<YYYY-MM>.md`. These are drafts only — never
   send, post, or deliver any of them.

7. Update `delivery/harvest/state.json` to
   `{"last_harvest_at": "<this run's UTC timestamp>", "last_leaderboard_generated_at": "<this leaderboard's generated_at>"}`.
   This state file and the two `delivery/` files above are the lane's only
   durable writes.

## Boundaries

Binding, restated from `VISION.md`, `AGENTS.md`, and `docs/governance.md`:

- `gc-sms` receives findings and taxonomy pressure only — never scenario
  text, verifier prompts, or expected answers.
- Never state a score without a run-handle citation.
- Safety and Care are never composited into one score or rank; never publish
  a claim like "model X is better than model Y."
- Publication (scan → strict QA → deterministic Hound projection → reviewed
  Git commit → consumer sync) is out of scope for this lane. This lane only
  reads what that path has already published; it never runs any step of it.
- Drafts only. Never send, post, publish, merge, or deploy.
- Never write to CRM.
- Never run a paid scan or a model evaluation to manufacture something to
  harvest.
- Never certify GiveCare's own product ahead of bench's independence
  requirements.

## Terminal result

Classify with exactly one domain status, reported in the body: `HARVESTED`
when the harvest digest and outreach drafts were both written (with the
evidence-cycle pointer or its documented skip resolved per step 5) and state
was updated; `NOTHING_TO_HARVEST` when step 3's decline condition applied;
`HARVEST_FAILED` when a required read — the `bench` CLI, the leaderboard, or
the state file — could not be trusted.

Then end with the rack-wide token that status maps to, alone on the final
line: `HARVESTED` is `DONE`; `NOTHING_TO_HARVEST` is `DECLINED`, naming the
last harvest date on the line above; `HARVEST_FAILED` is `BROKEN`, with
`FAILED_CHECK: <exact failed check>: <bounded error>` immediately before the
token. Never invent a classification token outside this mapping for either
line.

## Atlas contract

Owner intent for this stream: `~/wiki/atlas/givecare-bench.md` — read it
before non-trivial work; it governs when this file and it disagree on intent
(this file still owns execution).
