# [FEATURE] Excessive LLM API calls in safety scorer

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/evaluation/scorers/safety.py:190-237` — Each safety evaluation makes **6 LLM API calls**: 1 reference generation + 5 judgment distribution samples. The compliance scorer adds 3 more, trauma adds 1-4 (boundary probes), belonging adds 1. That's **11+ API calls per scenario** for scoring alone, on top of the model-under-test calls. For a 29-scenario benchmark with 10 models, that's ~3,200 scorer API calls. Consider reducing `n_samples` to 3 for safety (matching compliance) or caching the reference response.

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
