# [FEATURE] Anti-pattern: Massive code duplication in `runner.py`

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/cli/runner.py` — The transcript generation + scoring + result-building logic is copy-pasted across 4 code paths:
- `generate_transcript()` (sync, lines 348-404)
- `evaluate_scenario_async()` (async, lines 435-591)
- Rich live display path (lines 859-960)
- Non-rich fallback path (lines 961-1043)

Each duplicates the same `conversation_history` building, error result construction, and result summary dict. A single `evaluate_scenario()` function with sync/async dispatch would eliminate ~300 lines.

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
