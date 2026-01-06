# Ralph Agent Instructions

## Your Task

1. Read `plans/prd.json`
2. Read `plans/progress.txt` (check Codebase Patterns first)
3. Check branch; if `branchName` is set, switch/create it
4. Pick highest priority story where `passes: false`
5. Implement that ONE story
6. Run required checks (lint/typecheck/tests) for this repo
7. Update AGENTS.md in edited directories if learnings are reusable
8. Commit: `feat: [ID] - [Title]`
9. Update prd.json: `passes: true`
10. Append learnings to progress.txt

## Progress Format

APPEND to progress.txt:

## YYYY-MM-DD - [Story ID]
- What was implemented
- Files changed
- **Learnings:**
  - Patterns discovered
  - Gotchas encountered
---

## Codebase Patterns

Add reusable patterns to the TOP of progress.txt.

## Stop Condition

If ALL stories pass, reply:
<promise>COMPLETE</promise>

Rules:
- Use trash, not rm
- git add [files] only; never git add . or -A
- No emoji in commit messages
- Ask before git push
