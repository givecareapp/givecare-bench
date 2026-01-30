# [FEATURE] `httpx.AsyncClient` created per-call in async path

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/api/client.py:192-195` — Each `call_model_async()` invocation creates a new `AsyncClient` with its own connection pool. When running 29 scenarios per model, this means 29+ TLS handshakes. The client should be created once and reused (e.g., stored on `ModelAPIClient` and closed explicitly).

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
