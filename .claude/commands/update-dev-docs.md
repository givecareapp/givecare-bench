You are updating development documentation before context compaction or at the end of a work session.

**Context**: The user has been working on a feature and needs to capture progress before the conversation ends or context gets compacted.

## Your Task

1. **Identify the active task**
   - Check `dev/active/` for existing task directories
   - If multiple tasks, ask which one to update
   - If not obvious, ask the user

2. **Read current documentation**:
   - `dev/active/[task-name]/[task-name]-plan.md` (for reference)
   - `dev/active/[task-name]/[task-name]-context.md` (to update)
   - `dev/active/[task-name]/[task-name]-tasks.md` (to update)

3. **Update context.md**:
   - Add any NEW decisions made during this session
   - Note files that were modified
   - Record any discoveries or important findings
   - Update "Last Updated" timestamp
   - Add "Next Steps" section with specific actions

Example additions:
```markdown
## Important Decisions

### Decision: Switch to Median Aggregation
**Date**: 2025-10-30
**Rationale**: Empirical testing showed median is 43% more robust than mean
for handling outlier judge responses. Tested on 20 sample scenarios.
**Impact**: Changes evaluator.py aggregation logic, requires re-running baseline

## Next Steps
- Complete median aggregation implementation in evaluator.py
- Update tests to validate median calculation
- Re-run baseline scenarios to establish new ground truth
- Update paper Section 4.2 with aggregation method justification
```

4. **Update tasks.md**:
   - Mark completed tasks with [x]
   - Add any newly discovered tasks
   - Reorder tasks if priorities changed
   - Update "Last Updated" timestamp
   - DO NOT remove completed tasks (keep them for history)

Example updates:
```markdown
## Phase 1: Implementation

- [x] Task 1: Create evaluator.py skeleton
- [x] Task 2: Implement judge prompt templates
- [ ] Task 3: Add median aggregation logic (IN PROGRESS)
- [ ] Task 4: Add variance calculation
- [ ] Task 5: Update tests (NEW - discovered during implementation)

## Phase 2: Validation

- [ ] Task 1: Run on tier 1 scenarios
- [ ] Task 2: Analyze variance reduction
- [ ] Task 3: Compare median vs mean results
```

5. **Summarize progress**:
   - What was accomplished this session
   - What's next
   - Any blockers or issues

## Output Format

Provide a summary like:

```markdown
## Dev Docs Updated: [task-name]

### Completed This Session
- ✅ [Task 1 completed]
- ✅ [Task 2 completed]
- 🔄 [Task in progress]

### Context Captured
- Recorded decision about [X]
- Noted files modified: [file1, file2]
- Added discovery: [important finding]

### Next Steps
1. [Specific next action]
2. [Another specific action]
3. [Final action before milestone]

### Blockers (if any)
- [Blocker 1 and potential solution]

---

**Files Updated**:
- `dev/active/[task-name]/[task-name]-context.md`
- `dev/active/[task-name]/[task-name]-tasks.md`

**Ready for**: Context compaction or end of session
```

## Important Guidelines

- **DO NOT** continue implementation after updating docs
- Be specific in "Next Steps" (not vague)
- Capture WHY decisions were made, not just WHAT
- Note any failed approaches (important for learning)
- If no progress made, say so honestly and update blockers
- Update timestamps to current date/time

## When to Use This Command

Use `/update-dev-docs` when:
- Context is running low (< 20% remaining)
- End of work session
- Before switching to different task
- After completing major milestone
- When you realize you haven't documented recent work

## Example Scenarios

### Scenario 1: Mid-implementation, context low
User: "Context is at 15%, update dev docs"
You:
1. Read current docs
2. Mark 3 tasks completed
3. Add 2 new tasks discovered
4. Note decision about error handling approach
5. Write specific next steps
6. Summarize progress

### Scenario 2: End of day
User: "End of day, save progress"
You:
1. Read current docs
2. Update all completed tasks
3. Add context about where implementation currently stands
4. Note any blockers encountered
5. Write detailed next steps for tomorrow
6. Summarize session

### Scenario 3: Stuck on problem
User: "I'm stuck on this approach, document it"
You:
1. Read current docs
2. Add failed approach to context with explanation
3. Note why it didn't work
4. Suggest alternative approach in next steps
5. Keep task as incomplete but note attempt

## DO NOT

- Don't start new implementation
- Don't delete completed tasks (keep for history)
- Don't be vague in next steps
- Don't skip updating timestamps
- Don't forget to capture WHY behind decisions
