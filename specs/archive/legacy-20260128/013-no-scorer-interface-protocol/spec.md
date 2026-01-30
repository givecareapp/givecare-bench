# [FEATURE] No scorer interface/protocol

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
Each scorer module (`safety.py`, `compliance.py`, `trauma.py`, `belonging.py`, `memory.py`) exposes a `score()` function with different signatures. Safety and compliance take `rules`, trauma and belonging don't. There's no `Protocol` or base class enforcing the contract. The orchestrator knows each scorer's signature via individual lambda calls (`orchestrator.py:501-578`), making it impossible to add a new scorer without modifying the orchestrator.

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
