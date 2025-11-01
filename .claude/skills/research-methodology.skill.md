# Research Methodology Skill

## When to Use
Making design decisions, grounding features in literature, writing papers, evaluating approaches

## Evidence-Based Design Principles

### Always Ground Decisions in Research
When proposing or evaluating design choices:
1. **Search for relevant research** (arXiv, HCI/AI safety literature)
2. **Cite empirical evidence** (korpan2025bias, kaur2025corus, etc.)
3. **Document trade-offs** with citations
4. **Connect to prior work**

Example from your project:
> "Belonging & Cultural Fitness upgraded to 15% weight based on korpan2025bias
> showing pervasive demographic bias and kaur2025corus demonstrating -19%
> knowledge asymmetry for caregivers."

### Research Questions Framework
Before implementing features, clarify:
- **What are we testing?** (hypothesis)
- **Why does this matter?** (motivation from literature)
- **How will we validate?** (experimental design)
- **What would falsify this?** (failure criteria)

### Citation Standards
- Use arXiv MCP when available: `mcp__arxiv-mcp-server__search_papers`
- Proper BibTeX in `papers/*/references.bib`
- Author-year in-text: `korpan2025bias`
- Track which papers informed which decisions

### Capturing Research Rationale

Document in CLAUDE.md under relevant sections:

```markdown
## Design Decision: [Feature Name]

**Research Grounding**:
- Study X found Y% of crisis signals missed in baseline systems
- Framework Z demonstrates N-fold improvement with explicit weighting

**Trade-offs Considered**:
- Higher weight → More sensitive but potential false positives
- Empirical calibration showed optimal threshold at 20%

**References**: [author2025, author2026]
```

### Using arXiv MCP for Research

When exploring design decisions:

```
# Search for relevant papers
Use mcp__arxiv-mcp-server__search_papers with:
- Specific query terms in quotes: "multi-agent systems" "AI safety"
- Categories: ["cs.AI", "cs.MA", "cs.HC"] for AI/agents/HCI
- date_from/date_to for targeted time periods
- max_results: 15-20 for comprehensive searches

# Example queries for this project:
- "AI bias" AND "demographic" with categories: ["cs.AI", "cs.CY"]
- "caregiver support" OR "mental health AI" with categories: ["cs.HC"]
- "benchmark" AND "evaluation" with categories: ["cs.AI", "cs.LG"]
```

### Design Decision Template

When making architectural or feature decisions:

```markdown
### Design Decision: [Component/Feature Name]

**Date**: YYYY-MM-DD
**Status**: ✅ Decided | 🤔 Exploring | ❌ Rejected

**Context**:
What problem are we solving? Why now?

**Research Foundation**:
- Paper A (author2025a): Found X, suggests Y
- Paper B (author2025b): Demonstrates Z approach
- Gap in literature: No prior work on W

**Alternatives Considered**:
1. **Option A**: [description]
   - Pros: X, Y
   - Cons: Z
   - Research support: [citations]

2. **Option B**: [description]
   - Pros: X, Y
   - Cons: Z
   - Research support: [citations]

**Decision**: We chose [X] because [evidence-based rationale]

**Validation Plan**:
- Metric 1: Expected outcome
- Metric 2: Expected outcome

**References**:
- author2025a: Title
- author2025b: Title
```

### Failed Experiments Log

Keep in CLAUDE.md or dev/experiments/:

```markdown
## Failed Experiments (Learn from these!)

### Experiment: [Name]
**Date**: YYYY-MM-DD
**Hypothesis**: [What we expected]
**Result**: ❌ Failed - [What actually happened]
**Why**: [Root cause analysis]
**Lesson**: [What we learned]
**Research**: [Papers that explain why this failed]
```

## Integration with This Project

### Key Research Papers Informing SupportBench

Track in `papers/*/references.bib` and cite when making decisions:
- **korpan2025bias**: Demographic bias in AI systems
- **kaur2025corus**: Knowledge asymmetry for caregivers (-19%)
- Illinois WOPR Act (HB1806/PA 104-0054): Regulatory requirements

### Areas Requiring Research Grounding

1. **Dimension Weights** (Crisis Safety 20%, Belonging 15%, etc.)
   - Must cite empirical evidence for weight choices
   - Document calibration experiments

2. **Tri-Judge Ensemble Design**
   - Cite multi-judge evaluation literature
   - Document why median > mean aggregation

3. **Autofail Conditions**
   - Ground in safety research
   - Cite crisis detection literature

4. **Tier Structure** (1/2/3 with turn counts)
   - Justify turn counts with cognitive load research
   - Cite longitudinal evaluation frameworks

### When to Search Literature

Trigger research search when:
- Proposing new evaluation dimensions
- Changing weights or scoring rubrics
- Adding autofail conditions
- Designing new scenario types
- Making claims about model behavior
- Justifying architectural choices

### Documentation Requirements

Before implementing major features:
1. Search arXiv for relevant work
2. Document 3-5 key papers
3. Add to references.bib
4. Create design decision document
5. Link papers to specific design choices

## See Also
- [Resource: Key Research Papers](resources/key-papers.md)
- [Resource: Design Decision Template](resources/design-decision-template.md)
- [Resource: arXiv Search Patterns](resources/arxiv-search-patterns.md)
