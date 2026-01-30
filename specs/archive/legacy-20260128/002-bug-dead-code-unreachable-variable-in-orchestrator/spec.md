# [FEATURE] Bug: Dead code / unreachable variable in orchestrator

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/evaluation/orchestrator.py:423` — The variable `_single_iteration_mode = True` is assigned inside `score()` but is only used later at line 671. It's always `True` in the single-iteration path, so the conditional is meaningless. More importantly, if the multi-iteration path (`iterations > 1`) returns early at line 417, this variable never exists in that scope. This isn't buggy per se since the early return skips line 671, but the flag pattern is confusing — the single-iteration wrapping at lines 671-681 always runs.

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
