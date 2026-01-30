# [FEATURE] Code smell: `ScoringConfig.validate_weights_sum` is a no-op

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/models/config.py:43-46` — The validator is decorated with `@field_validator("*")` but the body just `return v`. The weights (0.15+0.20+0.15+0.25+0.25 = 1.0) happen to sum to 1.0 today, but nothing enforces it. A `model_validator` checking `sum(weights.values()) == 1.0` would catch regressions.

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
