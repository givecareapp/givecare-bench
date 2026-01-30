# [FEATURE] Mixed data representations: dicts vs. Pydantic models

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
The codebase has two parallel model systems:
- Pydantic models in `models/config.py`, `models/results.py`, `models/scenario.py`
- Legacy dataclasses in `models/__init__.py` (lines 66-241)
- Raw dicts throughout the scorers and orchestrator

The orchestrator, all scorers, and the CLI operate entirely on raw dicts (`Dict[str, Any]`). The Pydantic models (`ScenarioResult`, `EvalResult`, `BatchResult`) are defined but never instantiated in the actual benchmark pipeline. This means you get zero runtime validation from Pydantic in production.

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
