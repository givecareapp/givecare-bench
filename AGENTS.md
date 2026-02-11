Looks like write permissions aren't granted yet. Here's the summary and updated AGENTS.md:

## Review Summary

**Big day** — InvisibleBench v2 shipped via PR #7 (6 commits, 131 files, ~10K lines changed). Three specs completed: scorer cache (#001), bench diff (#002), and v2 MECE restructure (#003).

### Key Changes
1. **MECE category restructure**: Tiers replaced with categories (safety/empathy/context/continuity/confidential)
2. **3 new CLI commands**: `bench diff`, `bench stats`, `bench reliability`, `bench annotate`
3. **11 scoring bug fixes** across 5 scorers
4. **3 new regulatory scenarios**, 3 new relational empathy scenarios (29→35 standard, 32→38 total)
5. **Cleanup**: deduplicated kappa helper, fixed RNG mutation, extracted scorer helpers

### AGENTS.md Is Stale — Needs These Fixes

| Issue | Old | New |
|-------|-----|-----|
| Scenario path | `tier{1-3}/` | `{safety,empathy,context,continuity,confidential}/` |
| Filter flag | `-t 3` (tier) | `-c safety` (category) |
| GiveCare standard count | 29 | 35 |
| GiveCare confidential count | 32 | 38 |
| Branched scenarios | 5 | 4 |
| Missing commands | — | `bench diff`, `bench stats`, `bench reliability`, `bench annotate` |

### Updated AGENTS.md

The full updated file is ready to write (shown in the write attempts above). The changes:
- Fixed scenario directory structure to MECE categories
- Replaced `-t` tier flag with `-c` category flag
- Updated scenario counts (35/38)
- Added `bench diff`, `bench stats`, `bench reliability`, `bench annotate` commands
- Fixed branching count from 5 to 4
- Added category flag example for GiveCare provider

No errors, no Sentry issues, no AI conversation learnings to extract beyond what's already documented. The work was clean — all specs completed, merged to main.
