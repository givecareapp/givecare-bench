# InvisibleBench v2: Research Review & Roadmap

**Date**: 2026-02-24
**Sources**: ENGRAM, Lost in Conversation, Slow Drift of Support, ECRI 2026, PBSuite, Chameleon, Drift-Bench, Context Drift Equilibria

---

## What We Already Do Better

| Strength | Evidence |
|----------|----------|
| **Safety-first gating** (fail=0.0) | No reviewed paper enforces deployment gates. ENGRAM has zero safety eval. LiC measures task accuracy only. Cheng identifies violations but doesn't gate. |
| **Conditional branching** | `resolve_branch()` adapts user pressure based on model response. Cheng et al. found adaptive probing cuts time-to-breach by ~50% vs static scripts. We already do this. |
| **Multi-dimensional scoring** | 5 dimensions + per-turn violation tracking + categorized failure reasons. Everyone else collapses to binary correctness or single metrics. |
| **Domain-specific stakes** | LiC tests code/SQL. ENGRAM tests factual recall QA. We test whether an AI can be trusted with a grieving caregiver whose nonbinary partner has early-onset Alzheimer's. |
| **Behavioral eval, not just retrieval** | ENGRAM asks "can you answer questions about a transcript?" We ask "can you be a good caregiver?" |
| **Score degradation tracking** | `_build_score_degradation()` already computes early-vs-late-thirds delta. Infrastructure for drift detection exists. |

---

## Improvements for v2

### P0: High Impact, Clear Path

#### 1. Longer scenarios for boundary erosion (12-20 turns)

**Why**: Cheng et al. found mean time-to-breach is **9.21 turns** (static) / **4.64 turns** (adaptive). Most InvisibleBench scenarios are 3-8 turns. Violations in the 9-15 turn range are currently invisible.

**What to build**:
- Extend `gradual_boundary_erosion.json` to 15-20 turns
- Add 2-3 new long-form boundary scenarios (medication pressure, role substitution, attachment deepening)
- Measure time-to-breach as a new metric

**References**: Cheng et al. (arXiv 2601.14269), Laban et al. (arXiv 2505.06120)

#### 2. False reassurance / zero-risk guarantee as autofail

**Why**: Cheng et al.'s #1 violation type across all models was "you will definitely be fine" / zero-risk promises. This is not an explicit autofail trigger today.

**What to build**:
- Add `false_reassurance` to autofail trigger taxonomy
- Pattern: definitive certainty about outcomes ("you will be fine", "nothing bad will happen", "don't worry at all")
- Apply across safety and boundary scenarios

**References**: Cheng et al. (arXiv 2601.14269) -- 88% failure rate, comfort-driven drift as mechanism

#### 3. Unreliability reporting (variance across runs)

**Why**: LiC's key finding: variance between runs matters more than mean score, and unreliability **doubles** in multi-turn settings. We support `--runs N` but don't default to it or report interpercentile range.

**What to build**:
- Default `--runs 3` (minimum) for leaderboard submissions
- Report interpercentile range (U-10-90) alongside mean
- Add unreliability column to leaderboard
- Flag models with high per-scenario variance even if mean is acceptable

**References**: Laban et al. (arXiv 2505.06120) -- 112% unreliability increase in multi-turn

### P1: Medium Impact, Some Design Work

#### 4. Stance stability metric

**Why**: Both ECRI (sycophancy) and PBSuite (84% policy failure under multi-turn pressure) flag models shifting positions when challenged. We test this implicitly in pushback scenarios but don't formalize it.

**What to build**:
- Track whether model maintains position on medical boundaries, crisis protocols, scope limits across 3+ pushback turns
- Score as distinct metric: stance_stability (0-1)
- Apply to `pushback_loop.json`, `gradual_boundary_erosion.json`, `authority_override_attempt.json`

**References**: PBSuite (arXiv 2511.05018) -- <4% single-turn to 84% multi-turn failure; Chameleon (arXiv 2510.16712) -- 0.391-0.511 stance shift scores

#### 5. Deeper continuity / memory evaluation

**Why**: ENGRAM tests 600 turns / 32 sessions / 16K tokens with typed memory (episodic/semantic/procedural). We have 4 continuity scenarios. The typed decomposition maps to caregiving:

- **Episodic**: "Last session Jamie described a grocery store incident"
- **Semantic**: "River uses they/them pronouns"
- **Procedural**: "Jamie prefers direct validation over 'rise above it' advice"

**What to build**:
- Add 4-6 new continuity scenarios testing typed memory explicitly
- Score episodic/semantic/procedural recall separately
- Extend to 3+ sessions with 50+ total turns for longitudinal scenarios

**References**: ENGRAM (arXiv 2511.12960) -- 77.55% SOTA on LoCoMo; typed separation drops 31 points when collapsed

#### 6. Time-to-breach metric

**Why**: Cheng et al. measure which turn the model first violates a boundary. This is actionable for product teams -- "your model holds for 6 turns then fails" is more useful than "your model failed."

**What to build**:
- Record first violation turn in per-scenario results
- Report as `first_breach_turn` in `--detailed` output
- Aggregate across scenarios: mean/median time-to-breach per model

**References**: Cheng et al. (arXiv 2601.14269) -- 9.21 mean static, 4.64 mean adaptive

### P2: Exploratory / Future

#### 7. LLM-driven adaptive adversary mode

**Why**: Cheng et al.'s adaptive probing (LLM planner generates follow-up pressure per-turn) found breaches earlier than static scripts. Our branches are deterministic.

**What to explore**:
- Optional `--adversarial` flag that replaces scripted branches with LLM-generated pressure
- GPT-4o-mini as adversary planner (like Cheng's architecture)
- Would require new scoring calibration

**References**: Cheng et al. (arXiv 2601.14269) -- adaptive vs static probing comparison

#### 8. Cross-linguistic testing

**Why**: Cheng et al. found Chinese conversations had significantly higher breach rates. We test English only.

**What to explore**:
- Spanish, Mandarin, Tagalog scenarios (top caregiver languages in US)
- Same scenario content, translated + culturally adapted
- Per-language breach rate comparison

**References**: Cheng et al. (arXiv 2601.14269) -- EN vs CN results

#### 9. Reminder intervention testing

**Why**: Context Drift Equilibria paper found drift stabilizes as bounded stochastic process and "reminder interventions" reliably reduce divergence.

**What to explore**:
- Test whether periodic system-prompt reminders (caregiver's name, pronouns, crisis history) improve longitudinal scores
- Actionable for product teams building memory systems
- Could be a `--with-reminders` flag for A/B comparison

**References**: Dongre et al. (arXiv 2510.07777)

#### 10. Token economy reporting

**Why**: ENGRAM tracks tokens consumed per query. Matters for SMS-constrained deployments (160-char messages).

**What to explore**:
- Report token consumption per scenario in `--detailed` mode
- Compare models on efficiency, not just quality

**References**: ENGRAM (arXiv 2511.12960) -- 916 avg tokens vs baselines

---

## Citable References

### Core validation (cite in paper intro / motivation)

| Paper | Key Finding | Use In Paper |
|-------|-------------|--------------|
| Cheng et al. "Slow Drift of Support" (arXiv 2601.14269) | 88% chatbot failure in mental health; mean breach at 9.21 turns; comfort/empathy as mechanism | Motivation for multi-turn design + safety gates |
| Laban et al. "Lost in Conversation" (arXiv 2505.06120) | 39% degradation + 112% unreliability increase in multi-turn | Validates multi-turn fragility thesis |
| ECRI 2026 Health Tech Hazards | AI chatbot misuse = #1 health tech hazard; 40M daily users, no FDA regulation | Policy framing for deployment gates |
| PBSuite (arXiv 2511.05018) | Policy adherence: <4% single-turn to 84% multi-turn failure | Validates conditional branching approach |

### Memory / continuity (cite in related work + continuity dimension)

| Paper | Key Finding | Use In Paper |
|-------|-------------|--------------|
| ENGRAM (arXiv 2511.12960) | Episodic/semantic/procedural typed memory; SOTA on LoCoMo (77.55%); 1% token budget | Informs typed memory evaluation for continuity |
| THEANINE (arXiv 2406.10996) | Timeline-based memory retaining outdated memories as context | Temporal memory design patterns |
| LoCoMo (ACL 2024) | 300 turns / 35 sessions; LLMs lag humans 56% on memory | Scale comparison + validation of approach |
| LongMemEval (2024) | 500 sessions, 115K tokens; 30-60% performance drop | Long-context memory challenges |

### Multi-turn dynamics (cite in methodology)

| Paper | Key Finding | Use In Paper |
|-------|-------------|--------------|
| Liu et al. "Intent Mismatch" (arXiv 2602.07338) | Root cause is intent alignment gap, not capability loss; scaling can't fix it | Theoretical grounding for branching design |
| Chameleon (arXiv 2510.16712) | Models shift stances under contradiction; 0.391-0.511 scores | Justifies stance stability measurement |
| Drift-Bench (arXiv 2602.02455) | Cooperative breakdowns under input faults | Adjacent failure modes |
| Context Drift Equilibria (arXiv 2510.07777) | Drift stabilizes; reminder interventions work | Informs longitudinal scenario design |

### Industry / policy (cite in introduction + discussion)

| Source | Key Finding | Use In Paper |
|--------|-------------|--------------|
| ECRI 2026 Top 10 Hazards | AI chatbot misuse = #1 | Frame: industry recognizes the problem |
| Psychology Today (Wei, Feb 2026) | Coverage of 88% failure study | Accessible framing for non-academic audiences |
| NIST "Evaluation Toolbox" (Feb 2026) | White House mandates AI measurement science | Policy alignment for benchmark approach |

---

## What This Changes in the Paper

### Introduction
- Add Cheng et al. 88% failure rate + ECRI #1 hazard as opening motivation
- Frame: "industry recognizes multi-turn conversational AI safety as the top health technology hazard of 2026, yet no deployment gate exists"

### Related Work
- Add ENGRAM, LiC, PBSuite, Chameleon to related work
- Position InvisibleBench as operating at behavioral/safety level vs memory/task-accuracy level
- Acknowledge limitations honestly (scenario length, scale)

### Methodology
- Cite LiC for unreliability measurement approach
- Cite Cheng for adaptive probing validation of conditional branching

### Discussion
- Cite drift equilibria for reminder interventions as product recommendation
- Cite intent mismatch for theoretical grounding of why scaling alone won't fix caregiving safety

### Limitations
- Explicitly note: shorter scenarios than memory benchmarks (by design -- safety focus)
- Note: deterministic branches vs LLM-driven adversary (trade reproducibility for realism)
