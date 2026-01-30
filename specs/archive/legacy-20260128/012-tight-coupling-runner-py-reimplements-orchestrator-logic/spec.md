# [FEATURE] Tight coupling: `runner.py` reimplements orchestrator logic

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
The CLI runner doesn't use `ScoringOrchestrator.score()` for the full pipeline — it separately generates transcripts, then calls `orchestrator.score()` for scoring only. But it also duplicates result aggregation, cost tracking, and pass/fail logic. The runner should delegate more to the orchestrator rather than re-implementing result assembly.

## Context


## Acceptance Criteria
- [ ] Feature works as described
- [ ] Tests pass
- [ ] No regressions in existing functionality
- [ ] Documentation updated if needed

## Completion Signal
```bash
npm run build
npm run test
```

## Constraints
- Follow existing code patterns
- Keep changes focused on the feature
