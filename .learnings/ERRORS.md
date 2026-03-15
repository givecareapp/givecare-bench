## [ERR-20260312-001] doc command linter has stale target list

**Logged**: 2026-03-12T16:42:29Z | **Priority**: low | **Status**: pending

### Summary
`benchmark/scripts/validation/lint_doc_commands.py` failed because its target file list includes docs that no longer exist.

### Details
During doc-sync verification, `uv run python benchmark/scripts/validation/lint_doc_commands.py` exited non-zero with missing files:
- `docs/CHAI_MEETING_PREP.md`
- `docs/COLLINEAR_COMPARISON.md`
- `docs/traitbasis-research-analysis.md`

This appears to be a stale validation script configuration rather than a problem with the updated docs.

### Suggested Action
Update the linter's target list or make it discover docs dynamically before relying on it for doc verification.

### Metadata
- Source: error
- Related Files: benchmark/scripts/validation/lint_doc_commands.py
