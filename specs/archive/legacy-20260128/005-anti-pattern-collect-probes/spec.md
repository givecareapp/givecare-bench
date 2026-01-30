# [FEATURE] Anti-pattern: `_collect_probes

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/evaluation/scorers/memory.py:16-25` and `benchmark/invisiblebench/evaluation/scorers/trauma.py:24-33` have identical `_collect_probes()` implementations. This should be a shared utility.

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
