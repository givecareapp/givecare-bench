# [FEATURE] Code smell: Scorer LLM response parsing is fragile

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
All scorers (`safety.py:418-459`, `trauma.py:532-570`, `belonging.py:309-372`, `compliance.py:398-469`) parse LLM responses by splitting on newlines and checking `startswith()`. A single malformed line (extra colon in the value, missing space) silently falls through to default values. There's no warning when parsing fails partially.

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
