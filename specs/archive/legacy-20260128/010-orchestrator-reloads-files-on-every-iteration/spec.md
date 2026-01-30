# [FEATURE] Orchestrator reloads files on every iteration

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/evaluation/orchestrator.py:427-433` — When `_score_with_iterations` calls `self.score()` recursively for each iteration, each call re-loads the transcript, scenario, and rules from disk via the loaders. These files don't change between iterations — they should be loaded once and passed through.

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
