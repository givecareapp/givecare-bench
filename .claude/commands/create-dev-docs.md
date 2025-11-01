You are helping create development documentation for a large feature or task.

**Context**: The user has just approved a plan (likely from planning mode or a discussion). Your job is to create a structured dev docs directory with three files.

## Your Task

1. **Ask for the task name** if not obvious from context
   - Use kebab-case: `tri-judge-evaluation`, `dimension-weight-calibration`
   - Short but descriptive

2. **Create the directory structure**:
   ```
   dev/active/[task-name]/
   ├── [task-name]-plan.md
   ├── [task-name]-context.md
   └── [task-name]-tasks.md
   ```

3. **Generate three files**:

### File 1: [task-name]-plan.md

Structure:
```markdown
# [Task Name] - Implementation Plan

**Created**: [Today's date]
**Status**: 🚀 Active

## Executive Summary
[2-3 sentences: What are we building and why?]

## Phases

### Phase 1: [Phase Name]
**Goal**: [What this phase accomplishes]
**Tasks**:
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

### Phase 2: [Phase Name]
**Goal**: [What this phase accomplishes]
**Tasks**:
- [ ] Task 1
- [ ] Task 2

[Continue for all phases...]

## Success Criteria
1. [Measurable outcome 1]
2. [Measurable outcome 2]
3. [Measurable outcome 3]

## Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| [Risk 1] | High/Med/Low | High/Med/Low | [How to mitigate] |
| [Risk 2] | High/Med/Low | High/Med/Low | [How to mitigate] |

## Timeline Estimate
- Phase 1: [X days/hours]
- Phase 2: [Y days/hours]
- Total: [Z days/hours]

## References
- [Any relevant papers, docs, or prior discussions]
```

### File 2: [task-name]-context.md

Structure:
```markdown
# [Task Name] - Context & Decisions

**Last Updated**: [Timestamp]

## Key Files Involved

### Primary Files
- `path/to/file1.py` - Purpose/role
- `path/to/file2.py` - Purpose/role

### Secondary Files
- `path/to/file3.py` - Purpose/role

## Important Decisions

### Decision: [Decision Name]
**Date**: [Date]
**Rationale**: [Why we chose this approach]
**Alternatives**: [What we considered but didn't choose]
**Impact**: [How this affects the implementation]

## External Dependencies
- [Library/API/service we depend on]
- [Another dependency]

## Architecture Notes
[Any important architectural considerations, patterns being used, etc.]

## Known Constraints
- [Constraint 1 and why it matters]
- [Constraint 2 and why it matters]

## Next Steps
[What to work on next - updated as you progress]
```

### File 3: [task-name]-tasks.md

Structure:
```markdown
# [Task Name] - Task Checklist

**Last Updated**: [Timestamp]

## Phase 1: [Phase Name]

### [Sub-section if needed]
- [ ] Task 1: [Specific, actionable task]
- [ ] Task 2: [Specific, actionable task]
- [ ] Task 3: [Specific, actionable task]

## Phase 2: [Phase Name]

### [Sub-section if needed]
- [ ] Task 1: [Specific, actionable task]
- [ ] Task 2: [Specific, actionable task]

## Testing & Validation
- [ ] Unit tests written
- [ ] Integration tests passing
- [ ] Manual testing complete
- [ ] Documentation updated

## Completion Criteria
- [ ] All tasks above completed
- [ ] No test failures
- [ ] Code reviewed
- [ ] Merged to main branch

---

**Note**: Mark tasks with [x] as they're completed. Update this file regularly.
```

## After Creating Files

1. **Confirm completion**: List the three files created
2. **Show next steps**:
   - "Files created in `dev/active/[task-name]/`"
   - "Ready to start implementation"
   - "Remember to update context and tasks as you progress"
   - "Use `/update-dev-docs` before context compaction"

## Important Guidelines

- **DO NOT** start implementing - just create the documentation structure
- Pull details from the approved plan if available
- If information is missing, use placeholders with [TODO: ...] markers
- Keep the plan concise but comprehensive
- Make tasks specific and actionable (not vague)
- Group related tasks together

## Example Task Names (for reference)
- `tri-judge-evaluation`
- `dimension-weight-calibration`
- `memory-scoring-refactor`
- `paper-figure-generation`
- `crisis-detection-improvement`
