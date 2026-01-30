# [FEATURE] No test fixtures for LLM-enabled code paths

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`conftest.py:8` sets `INVISIBLEBENCH_DISABLE_LLM=1` globally. All tests run in offline/deterministic mode. The LLM-based scoring paths (which are the primary production paths with the judgment distribution, reference generation, and multi-sample voting) are completely untested. There are no mocked API client tests verifying that LLM response parsing produces correct scores.

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
