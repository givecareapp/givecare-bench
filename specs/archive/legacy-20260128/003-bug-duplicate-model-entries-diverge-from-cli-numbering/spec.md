# [FEATURE] Bug: Duplicate model entries diverge from CLI numbering

## Source
- Type: feature
- Requested: 2026-01-27T13:57:02Z
- Priority: P2

## Goal
From AI review (ai-review-2026-01-27). Effort: unknown

## Review Details
`benchmark/invisiblebench/models/config.py:102-173` vs `benchmark/invisiblebench/cli/runner.py:64-65` — The `MODELS_FULL` list and the CLI's `MODELS_FULL` (derived via `model_dump()`) contain 10 entries, but the `DEFAULT_TEST_MODELS` list in `api/client.py:285-296` has completely different model IDs (e.g., `openai/gpt-5` vs `openai/gpt-5.2-20251211`, `meta-llama/llama-3.1-70b-instruct` vs `qwen/qwen3-235b-a22b`). These two model lists will drift silently. `DEFAULT_TEST_MODELS` appears unused — it should be removed or reconciled.

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
