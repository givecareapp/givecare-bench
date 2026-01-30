# [FEATURE] Missing edge case tests for scorer parsing

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
The LLM response parsers in each scorer have no dedicated tests. Edge cases like:
- LLM returns `RESPONSE_QUALITY: 0.8 (good response)` (extra text after number)
- LLM returns `CRISIS_DETECTED: Yes` (capitalized) vs `yes`
- LLM omits a required field entirely
- LLM returns scores outside 0.0-1.0 range

None of these are tested.

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
