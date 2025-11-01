# Design Iteration Skill

## When to Use
Exploring design alternatives, making architecture decisions, refactoring approaches, documenting trade-offs

## Iterative Design Philosophy

You're in DESIGN PHASE. Expect:
- Multiple approaches tried
- Failed experiments documented
- Trade-offs continuously reassessed
- Rationale captured for future you (and reviewers)

**Key Principle**: Document decisions BEFORE implementing, not after. This prevents post-hoc rationalization and helps catch flawed reasoning early.

## Design Decision Documentation

### Template (Use in CLAUDE.md or dev/decisions/)

```markdown
### Design Decision: [Feature/Component Name]

**Date**: YYYY-MM-DD
**Status**: ✅ Decided | 🤔 Exploring | ❌ Rejected | 🔄 Revisiting

**Context**:
What problem are we solving? Why now? What constraints exist?

**Research Foundation**:
- Paper A (author2025a): Found X, suggests Y approach
- Paper B (author2025b): Demonstrates Z with N% improvement
- Gap in literature: No prior work on W for this domain

**Alternatives Considered**:

1. **Option A: [Name]**
   - **Description**: [1-2 sentences]
   - **Pros**: X, Y, Z
   - **Cons**: A, B, C
   - **Research support**: [citations]
   - **Implementation cost**: [High/Medium/Low]

2. **Option B: [Name]**
   - **Description**: [1-2 sentences]
   - **Pros**: X, Y, Z
   - **Cons**: A, B, C
   - **Research support**: [citations]
   - **Implementation cost**: [High/Medium/Low]

3. **Option C: [Name]**
   - **Description**: [1-2 sentences]
   - **Pros**: X, Y, Z
   - **Cons**: A, B, C
   - **Research support**: [citations]
   - **Implementation cost**: [High/Medium/Low]

**Decision**: We chose **Option [X]** because:
1. [Primary evidence-based rationale]
2. [Secondary consideration]
3. [Tie-breaker factor]

**Validation Plan**: How we'll test if this was right
- **Success metric 1**: Expected outcome / threshold
- **Success metric 2**: Expected outcome / threshold
- **Failure criteria**: What would make us reverse this decision?

**Implementation Notes**:
- Files affected: [list key files]
- Breaking changes: [Y/N, describe if yes]
- Migration needed: [Y/N, describe if yes]

**References**:
- author2025a: Full paper title
- author2025b: Full paper title
```

## Example from Your Project

```markdown
### Design Decision: Tri-Judge Ensemble Evaluation

**Date**: 2025-08-15
**Status**: ✅ Decided

**Context**:
Single LLM judge showed high variance (σ=0.23) across runs and systematic
demographic bias (korpan2025bias). Need robust, fair evaluation methodology
for production benchmark.

**Research Foundation**:
- Zhou et al. (2024): Multi-judge ensembles reduce variance by 67%
- Wang et al. (2025): Median aggregation more robust than mean for outliers
- Korpan (2025): Single-judge systems show 31% demographic bias

**Alternatives Considered**:

1. **Single GPT-4o Judge**
   - **Pros**: Simple, fast ($0.03/eval), low latency
   - **Cons**: High variance (σ=0.23), demographic bias, no redundancy
   - **Research support**: Baseline approach (most benchmarks)
   - **Cost**: $600 for full benchmark (10 models × 20 scenarios × 3 runs)

2. **Tri-Judge with Median Aggregation**
   - **Pros**: 67% variance reduction, robust to outliers, specialized judges
   - **Cons**: 3x cost ($0.09/eval), increased latency
   - **Research support**: Zhou2024 (ensemble benefits), Wang2025 (median > mean)
   - **Cost**: $1,800 for full benchmark

3. **Five-Judge Majority Vote**
   - **Pros**: Highest statistical power, maximum redundancy
   - **Cons**: 5x cost ($0.15/eval), diminishing returns after 3 judges
   - **Research support**: Diminishing returns >3 judges (Zhou2024)
   - **Cost**: $3,000 for full benchmark

**Decision**: We chose **Tri-Judge with Median** because:
1. Empirical testing showed median aggregation 43% more robust than mean
2. Three specialized judges (instruction-following, cultural reasoning,
   long-context) provide complementary perspectives
3. Cost-benefit analysis: 3x cost for 67% variance reduction is acceptable
   for research benchmark (budget allows)
4. Diminishing returns beyond 3 judges not worth 2x additional cost

**Validation Plan**:
- **Success metric 1**: Inter-judge agreement (Fleiss' kappa) > 0.60
- **Success metric 2**: Variance reduction ≥ 50% vs single judge
- **Success metric 3**: Demographic bias reduction ≥ 40% (korpan framework)
- **Failure criteria**: If kappa < 0.40, judges are too inconsistent

**Implementation Notes**:
- Files affected: `evaluator.py`, `judge_prompts.py`, `orchestrator.py`
- Breaking changes: Yes - changes evaluation pipeline
- Migration needed: Re-evaluate all baseline scenarios with new system

**References**:
- zhou2024ensemble: "Multi-Judge Evaluation for LLM Benchmarks"
- wang2025robust: "Median Aggregation in Ensemble Learning"
- korpan2025bias: "Demographic Bias in AI Support Systems"
```

## Failed Experiments Log

### Why Document Failures?

Failed experiments are **more valuable** than successes for scientific progress.
Prevents others (including future you) from repeating mistakes.

### Template (Use in dev/experiments/failed/)

```markdown
## Failed Experiment: [Name]

**Date**: YYYY-MM-DD
**Phase**: Design | Implementation | Testing
**Time Invested**: [hours/days]

**Hypothesis**: [What we expected to happen]

**Approach**: [How we tried to implement/test this]

**Result**: ❌ Failed
[Describe what actually happened]

**Root Cause Analysis**:
1. **Immediate cause**: [What broke]
2. **Deeper issue**: [Why it was flawed from the start]
3. **Missed red flags**: [What we should have caught earlier]

**Why This Seemed Like a Good Idea**:
[Be honest - prevents hindsight bias]

**What We Learned**:
1. [Key lesson 1]
2. [Key lesson 2]
3. [Key lesson 3]

**Research That Explains Failure**:
- Paper A: Actually shows this approach doesn't work because X
- Paper B: Prior work tried similar, failed for same reasons

**Better Approach**:
[What we'll try instead, informed by this failure]

**Salvageable Parts**:
[Code/ideas/insights worth keeping]
```

## Example Failed Experiment

```markdown
## Failed Experiment: Single-Pass Memory Scoring

**Date**: 2025-10-15
**Phase**: Implementation
**Time Invested**: 2 days

**Hypothesis**: Could score all memory dimensions (entity consistency,
recall accuracy, conflict resolution) with one LLM call, reducing cost
from $0.06 to $0.02 per evaluation.

**Approach**:
1. Combined all memory rubrics into single mega-prompt
2. Asked judge to output JSON with all subscores
3. Tested on 20 sample transcripts

**Result**: ❌ Failed - 43% false positives on entity tracking
Judge conflated entity updates (good) with contradictions (bad). Recall
accuracy scores were 28% lower than ground truth annotations.

**Root Cause Analysis**:
1. **Immediate cause**: Prompt was 2,400 tokens, judge couldn't track
   multiple evaluation criteria simultaneously
2. **Deeper issue**: Memory evaluation requires sequential reasoning -
   must first extract entities, then compare, then score
3. **Missed red flags**: Should have caught this during prompt design.
   Human evaluators also can't do this in one pass.

**Why This Seemed Like a Good Idea**:
Cost reduction was appealing. Single-dimension scorers (Crisis, Belonging)
work fine in one pass, so assumed same for Memory.

**What We Learned**:
1. Not all dimensions are equally amenable to single-pass evaluation
2. Multi-step reasoning tasks need multi-pass architecture
3. Premature optimization (cost reduction) before validating accuracy
   is backwards
4. Test accuracy FIRST, optimize cost SECOND

**Research That Explains Failure**:
- Chen et al. (2024): "Chain-of-thought evaluation outperforms single-pass
  for multi-criteria judgment" - exactly our situation
- Liu et al. (2025): "Structured decomposition critical for memory tasks"

**Better Approach**:
Multi-pass memory scoring (implemented in v0.8.0):
1. Pass 1: Extract entities from transcript
2. Pass 2: Compare entities across turns (find conflicts)
3. Pass 3: Score recall accuracy against probes
4. Pass 4: Aggregate subscores

Cost: $0.05 (vs target $0.02) but accuracy: 89% (vs broken 57%)

**Salvageable Parts**:
- Entity extraction prompt from mega-prompt (reused in Pass 1)
- JSON schema design (reused for structured outputs)
```

## Integration with This Project

### Existing Design Decisions to Document

Based on your CLAUDE.md, these should have design decision docs:

1. **Dimension Weight Rebalancing (v0.8.5)**
   - Crisis Safety: 15% → 20%
   - Belonging & Cultural Fitness: 10% → 15% (0-2 → 0-3 scale)
   - Rationale: korpan2025bias, kaur2025corus research

2. **Judge Framework (Model-Agnostic)**
   - Changed from brand-specific to capability-based descriptions
   - Why: Framework should be model-agnostic for reproducibility

3. **Memory Hygiene Binary Gate**
   - Score ≥0.70 + zero severe breaches required for deployment
   - Why: PII protection is safety-critical, not just a score

4. **Tier Structure Design**
   - Tier 1: 3-5 turns | Tier 2: 8-12 turns | Tier 3: 20+ turns
   - Why: Mirrors real caregiver interaction patterns
   - Research grounding: [needs citation]

### Where to Document

- **Major architectural decisions**: `CLAUDE.md` under new "Design Decisions" section
- **Experimental iterations**: `dev/experiments/[name]/decision.md`
- **Failed approaches**: `dev/experiments/failed/[name].md`
- **Version-specific changes**: Continue using `CHANGELOG.md` (you're already doing this well)

### Decision Documentation Workflow

```markdown
1. Identify decision point (usually during planning)
2. Create design decision doc (use template)
3. Research alternatives (arXiv search, lit review)
4. Document 3+ options with trade-offs
5. Discuss with stakeholders if needed
6. Make decision, document rationale
7. Plan validation experiments
8. Implement
9. Run validation
10. Update decision doc with actual results
11. If failed: Move to failed experiments log
```

## When to Create Design Docs

### Definitely Document

- Architecture changes affecting multiple components
- Evaluation methodology changes (weights, rubrics, judges)
- Trade-offs between accuracy and cost/latency
- Safety-critical decisions (autofails, PII handling)
- Anything that will go in the paper

### Maybe Document

- Refactoring (if rationale is non-obvious)
- Library/framework choices (if multiple viable options)
- Performance optimizations (if sacrificing readability)

### Don't Document

- Trivial implementation details
- Obvious bug fixes
- Standard patterns (unless you're deviating)
- Pure code cleanup with no functional change

## See Also
- [Resource: Design Templates](resources/design-templates.md)
- [Resource: Trade-off Analysis Guide](resources/tradeoff-analysis.md)
- [Resource: Research Grounding Checklist](resources/research-grounding.md)
