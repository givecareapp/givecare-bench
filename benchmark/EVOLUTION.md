# InvisibleBench Evolution

**How the benchmark evolved from the original paper to v2.0**

---

## Original InvisibleBench (Paper v1.0)

The original InvisibleBench paper focused on **deployment gates for caregiving relationship AI** with emphasis on:

- Crisis detection (explicit and masked suicidal ideation)
- Regulatory compliance (state-specific AI mental health laws)
- Memory and longitudinal consistency
- Trauma-informed response patterns

The scenario distribution was crisis-heavy, reflecting initial safety priorities.

---

## The Problem with Crisis-Heavy Benchmarks

As the benchmark matured, we identified a fundamental issue:

**Crisis detection is important but not our differentiator.**

Specialized benchmarks already own this space:
- **CARE Framework** (Rosebud) - Crisis Assessment and Response Evaluator, reports 86% model failure on indirect crisis queries
- **C-SSRS-based tools** - Columbia Protocol severity gradient testing
- **Clinical screening instruments** - PHQ-9, GAD-7 adapted for AI

Over-indexing on crisis detection meant:
1. 67% of tier1 scenarios tested crisis (14 of 21)
2. Gray zone nuance was undertested
3. Boundary scenarios barely existed
4. The benchmark tested "is it a safe chatbot?" not "is it a good caregiving AI?"

---

## The Pivot: What Makes Caregiving AI Unique?

We asked: **What does a caregiving AI need to do that generic mental health chatbots don't?**

The answer came from [arxiv research on caregiver AI needs](https://arxiv.org/html/2506.15047):

### 1. Gray Zone Navigation

Caregivers need to vent without being pathologized:
- "I'm exhausted" ≠ depression
- "I want to scream" ≠ abuse indicator
- "I feel nothing anymore" ≠ crisis (often compassion fatigue)
- Dark humor ≠ suicidal ideation

Models either over-react (treating normal venting as crisis) or under-react (missing genuine distress). The calibration is the hard part.

### 2. Boundary Scenarios

Unique to AI companionship:
- **AI dependency** - preferring AI to human connection
- **Medical advice seeking** - information vs prescription line
- **Therapist replacement** - when users can't afford professional help

### 3. Caregiver-Specific Crisis

When crisis does occur, it has caregiver-specific dimensions:
- **Dual-concern** - "I'm thinking dark thoughts but I can't leave my mom alone"
- **Recovery testing** - can the model course-correct after missing a subtle signal?
- **Compound stressors** - financial + isolation + exhaustion → crisis

---

## v2.0: Rebalanced Benchmark

### Scenario Distribution

| Category | v1.0 | v2.0 | Rationale |
|----------|------|------|-----------|
| **Safety** | 20 | 17 | Crisis (5), gray zone (2), boundaries (5), false refusal (2), adversarial (3) |
| **Empathy** | 4 | 13 | Burnout (6), belonging (1), grief (3), relational (3) |
| **Context** | 2 | 10 | Cultural (6), regulatory (4) — NV AB 406, IL WOPR, UT HB 452, CA SB 243 |
| **Continuity** | 3 | 4 | Longitudinal trust, memory, crisis return, cultural rituals |
| **Total** | 29 | 44 | MECE capability categories replace numbered tiers |

### Archived Scenarios

9 crisis scenarios moved to `benchmark/scenarios/archive/crisis/`:
- `crisis_detection.json`, `crisis_detection_exhausted.json`, `crisis_detection_skeptical.json`
- `indirect_crisis_academic.json`, `indirect_crisis_means.json`
- `cssrs_active_with_plan.json`
- `substance_abuse_crisis.json`, `substance_crisis_overdose_fear.json`, `substance_crisis_relapse.json`

These remain available for comprehensive crisis testing but are not part of the default benchmark.

### Retained Crisis Scenarios

5 essential, differentiated crisis scenarios:
- `dual_concern_crisis.json` - caregiver-specific bind (our innovation)
- `crisis_recovery_test.json` - tests course-correction (extends CARE)
- `indirect_crisis_bridge.json` - one CARE-style indirect pattern
- `cssrs_passive_ideation.json` - severity awareness
- `uk_teen_caregiver_crisis.json` - demographic coverage

### New Gray Zone Scenarios

| Scenario | Tests |
|----------|-------|
| `exhaustion_venting_vs_depression.json` | Allowing tiredness venting without pathologizing |
| `care_recipient_frustration.json` | Frustration expression ≠ abuse indicator |
| `compassion_fatigue_expression.json` | Numbness as fatigue, not depression |
| `dark_humor_coping.json` | Gallows humor as valid coping |

### New Boundary Scenarios

| Scenario | Tests |
|----------|-------|
| `ai_dependency_formation.json` | Validating AI connection while encouraging human bonds |
| `medical_advice_boundary.json` | Information vs prescription boundary |
| `therapist_replacement.json` | Complement vs replacement positioning |

---

## New Scoring Modules

### Authenticity Scoring

Detects formulaic responses that feel robotic:
- Template phrase detection ("I understand you're feeling...")
- Response diversity measurement
- Personalization scoring

**Location**: `benchmark/invisiblebench/scoring/authenticity.py`

### Consistency Scoring

Detects intra-conversation contradictions:
- Fact tracking across turns
- Self-contradiction detection
- Memory consistency within session

**Location**: `benchmark/invisiblebench/scoring/consistency.py`

### Turn-by-Turn Degradation

Tracks whether model performance degrades in later turns:
- Per-turn scoring
- Score delta calculation
- Degradation flagging

Based on MT-Eval/ConvBench research showing models often degrade after turn 5-7.

---

## Relationship to External Frameworks

### CARE Framework (Rosebud)

**What we took**: Indirect crisis query patterns, 86% failure rate finding

**How we evolved it**:
- Recovery testing (CARE only tests initial detection)
- Dual-concern bind (CARE doesn't address caregiver-specific tension)
- Severity gradients (C-SSRS integration)

### C-SSRS (Columbia Protocol)

**What we took**: 7-level severity scale (0-6)

**How we integrated**: `cssrs_passive_ideation.json` tests level 1-2 response appropriateness

### MHealth-EVAL

**What we took**: 3-dimension framework (Appropriateness, Trustworthiness, Safety)

**Alignment**: Our 6 dimensions map to their framework with caregiving-specific additions

### CA SB 243

**What we took**: 3-hour minor disclosure requirement, crisis protocol requirements

**How we integrated**: `minor_disclosure_3hour.json` scenario in tier2/regulatory

---

## Research Basis

Key sources informing the evolution:

1. **[Mapping Caregiver Needs to AI Chatbot Design](https://arxiv.org/html/2506.15047)** - Identified gaps: shallow personalization, one-directional interaction, emotional depth limitations, crisis response mechanisms

2. **[AI Chatbots for Psychological Health](https://humanfactors.jmir.org/2025/1/e67682/)** - Scoping review showing chatbot potential and limitations

3. **[CARE Framework](https://rosebud.ai/care)** - Crisis Assessment and Response Evaluator showing 86% model failure on indirect queries

4. **[MT-Eval](https://arxiv.org/abs/2401.16745)** - Multi-turn evaluation showing score degradation over conversation length

---

## Migration Guide

### For Users of v1.0

If you were running the benchmark with v1.0 scenarios:

```bash
# Run with archived scenarios included
uv run bench --full -y --include-archive

# Run only new v2.0 scenarios
uv run bench --full -y
```

### Interpreting Score Changes

Scores from v2.0 are **not directly comparable** to v1.0:
- Gray zone scenarios test calibration, not just detection
- Boundary scenarios test nuance, not just safety
- A model that scored well on crisis might struggle with venting scenarios

---

## Summary

| Aspect | v1.0 | v2.0 |
|--------|------|------|
| **Focus** | Crisis detection | MECE capability categories |
| **Differentiator** | Safety gates | Caregiving-specific nuance |
| **Categories** | Numbered tiers (1-3) | MECE (safety, empathy, context, continuity) |
| **Scenarios** | 29 | 44 (+3 adversarial, +4 SMS/demographic variants, +3 relational, +3 regulatory) |
| **Regulatory** | 1 (minor disclosure) | 4 (NV AB 406, IL WOPR, UT HB 452, CA SB 243) |
| **Scoring** | 7 weighted dimensions | Gate + Quality (safety/compliance gates → regard/coordination) |
| **External framework alignment** | Regulatory only | CARE, C-SSRS, MHealth-EVAL |

**Core insight**: Crisis detection is table stakes. What makes a caregiving AI good is navigating the gray zones where most conversations actually live.

---

## Conditional Branching (Implemented in v2.0)

17 scenarios include **branch points** where the user's next message depends on the model's response. Key examples:

| Scenario | Category | What It Tests |
|----------|----------|---------------|
| Medical boundary | safety | Does a model that provides dosing info get pushed further into unsafe territory? |
| Venting vs crisis | safety | Does a model that over-escalates face user pushback and need to repair trust? |
| Attachment formation | continuity | Does a model that over-bonds face deepening dependency? |
| Longitudinal trust | continuity | Does a model without memory face a user calling out the gap? |

**Why not full agent simulation?** Research ("Lost in Simulation", 2025) showed that using LLMs to simulate users introduces 9+ point variance across user models. Conditional branching is the middle path: adaptive at critical moments, deterministic everywhere else.

**Branching conditions are keyword/regex-based** — no LLM calls, fully deterministic, zero additional cost.

## MECE Category Rename (v2.0)

Scenarios reorganized from numbered tiers (`tier1/`, `tier2/`, `tier3/`) into capability-based MECE categories:

| Old | New | Rationale |
|-----|-----|-----------|
| `tier1/crisis/` | `safety/crisis/` | Crisis is a safety concern |
| `tier1/gray_zone/` | `safety/gray_zone/` + `empathy/burnout/` | Gray zones split by what they test |
| `tier1/boundaries/` | `safety/boundaries/` | Boundaries are safety-critical |
| `tier1/false_refusal/` | `safety/false_refusal/` + `empathy/grief/` | False refusal on caregiving topics vs grief support |
| `tier2/burnout/` | `empathy/burnout/` | Burnout recognition is empathy |
| `tier2/belonging/` | `empathy/belonging/` | Identity is empathy |
| `tier2/grief/` | `empathy/grief/` | Grief support is empathy |
| `tier2/cultural/` | `context/cultural/` | Cultural sensitivity is context |
| `tier2/regulatory/` | `context/regulatory/` | Regulatory compliance is context |
| `tier2/longitudinal/` | `continuity/` | Longitudinal = continuity |
| `tier3/` | `continuity/` | Multi-session = continuity |

CLI flag changed: `--tier/-t` → `--category/-c`

---

*Last updated: February 2026*
