Done. Here's what I found and did:

### Critical finding: AGENTS.md is corrupted
Commit `d53e216` ("night-nurse: update AGENTS.md with learnings from 2026-02-11") replaced the entire AGENTS.md with the night-nurse's review output text instead of the actual updated guidelines. The file currently starts with "Looks like write permissions aren't granted yet. Here's the summary..." — clearly the review agent's stdout got dumped into the file when a write permission was denied and the output was captured incorrectly.

### What needs to happen
I wrote the full corrected AGENTS.md content above but was blocked by write permissions. The file needs to be restored with:
- Scenario paths updated to MECE categories (not `tier{1-3}/`)
- Filter flag `-c safety` (not `-t 3`)
- GiveCare counts 35/38 (not 29/32)
- New commands: `bench diff`, `bench stats`, `bench reliability`, `bench annotate`
- Explicit list of 5 branched scenarios
- New Learnings section documenting this corruption + other v2 gotchas

### MEMORY.md updated
- Fixed context count: 6→9
- Added v2 CLI commands reference
- Added branched scenarios list
- Added Gotchas section documenting the AGENTS.md corruption and count drift pattern
