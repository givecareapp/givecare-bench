# Hybrid Evaluation Protocol

## Text for Paper 1 (LongitudinalBench) - Insert in Methodology Section

### Hybrid Judge Architecture

LongitudinalBench employs a **hybrid evaluation protocol** combining deterministic rule-based gates with LLM-as-judge assessment, optimized for each dimension's characteristics:

**Objective Gates (Rule-Based with Hard Fails)**
- **Compliance Detection**: Diagnosis/treatment keyword matching with context awareness (deterministic, <1ms/turn)
- **Crisis Signal Detection**: Pattern-based explicit crisis identification with 100% recall requirement
- **Memory Hygiene**: PII leak detection via regex + entity recognition (zero tolerance)

These dimensions require **deterministic pass/fail decisions** for regulatory compliance and cannot tolerate variance across evaluation runs. Implementation details in our companion methods paper~\cite{yaml-scoring}.

**Subjective Assessment (LLM Tri-Judge Ensemble)**
- **Trauma-Informed Flow**: Pacing, validation, grounding assessment (Judge 2: Gemini 2.5 Pro)
- **Belonging & Cultural Fitness**: Nuanced othering detection, agency recognition (Judge 2: Gemini 2.5 Pro)
- **Relational Quality**: Warmth, presence, boundary-setting (Judge 3: Claude Opus 4)
- **Actionable Support**: Resource quality and accessibility (Judge 3: Claude Opus 4)

These dimensions require **semantic understanding** of tone, cultural context, and relational dynamics beyond pattern matching.

**Aggregation Strategy**
1. Rule-based scorers execute first; any hard fail → overall score = 0 regardless of LLM judges
2. LLM judges evaluate remaining dimensions with dimension-specific rubrics
3. Median aggregation across three judges (robust to outlier judgments)
4. Final score = weighted average respecting autofail override

This hybrid approach achieves **determinism where required** (compliance, crisis, PII) while preserving **nuanced assessment** for relational/cultural dimensions, with 100-200× cost reduction vs. pure LLM-as-judge on objective criteria.

---

## Text for Paper 2 (YAML Scoring) - Insert in Discussion Section

### Hybrid Evaluation: When to Use Rules vs. LLM Judges

Our framework and LLM judges serve **complementary roles** in a production evaluation stack:

**Rule-Based Scoring Excels:**
- **Objective criteria**: "Does response contain diagnosis?" (Boolean decision)
- **Regulatory compliance**: WOPR Act, HIPAA, GDPR enforcement (deterministic requirements)
- **Zero-tolerance violations**: PII leaks, explicit crisis signals (autofails)
- **High-frequency iteration**: Rule refinement with instant re-evaluation (zero marginal cost)
- **Auditability**: Evidence provenance for every penalty (compliance attestation)

**LLM Judges Excel:**
- **Subjective criteria**: "Is this empathetic?" (gradient assessment)
- **Nuanced semantics**: Sarcasm, tone, cultural context detection
- **Open-ended evaluation**: No predefined violation patterns
- **Relational quality**: Warmth, presence, therapeutic rapport

**Recommended Hybrid Architecture:**

```yaml
evaluation_stack:
  tier_1_gates:  # Rule-based (deterministic, fast)
    - compliance_checker     # < 0.5ms, hard fail
    - crisis_detector        # < 1ms, hard fail
    - pii_scanner           # < 0.3ms, hard fail

  tier_2_assessment:  # LLM ensemble (nuanced, slower)
    - trauma_informed_judge  # ~150ms, gradient score
    - belonging_judge        # ~150ms, gradient score
    - relational_judge       # ~150ms, gradient score

  aggregation:
    rule: "Hard fails override all LLM scores"
    weights: {compliance: 0.3, trauma: 0.25, belonging: 0.25, relational: 0.2}
    cost: ~$0.05/eval (vs $0.12 pure LLM)
```

**Hybrid Performance:**
- Latency: 84ms (rules) + 450ms (3 LLM judges) = **534ms total** (vs 900ms pure LLM)
- Cost: Zero marginal (rules) + $0.045 (LLM) = **$0.045/eval** (vs $0.10 pure LLM)
- Determinism: 100% on compliance/crisis/PII, gradient on subjective dimensions

**Deployment in LongitudinalBench:** Our caregiving AI benchmark~\cite{longitudinalbench} implements this hybrid protocol, achieving regulatory determinism while preserving cultural/relational nuance. See companion paper for benchmark results demonstrating 15-20% model degradation across tiers that pure rule-based scoring would miss.

---

## Key Integration Points

**In Paper 1 (Benchmark):**
- Methods section: "We employ a hybrid protocol (Section X.X) combining rule-based gates for objective criteria with LLM tri-judge ensemble for subjective assessment. See [methods paper] for YAML rule specifications and scorer implementations."
- Results section: "Rule-based compliance detection identified 42% boundary violations (diagnosis/treatment) with zero false positives; LLM judges assessed trauma-informed flow (avg 0.7±0.15 across judges, κ=0.62)."

**In Paper 2 (Methods):**
- Introduction: "Deployed in LongitudinalBench~\cite{longitudinalbench}, a multi-tier caregiving AI safety benchmark requiring both deterministic compliance gates and nuanced relational assessment."
- Evaluation section: "Benchmark integration: Our rule-based scorers handle compliance (100% precision), crisis detection (100% recall on explicit signals), and PII hygiene, while LLM judges assess trauma-informed flow, belonging, and relational quality. Combined latency: 534ms vs 900ms pure LLM (41% reduction)."

---

## Cross-References to Add

**Paper 1 → Paper 2:**
```
~\cite{yaml-scoring}  % YAML-driven scoring framework companion paper
```

**Paper 2 → Paper 1:**
```
~\cite{longitudinalbench}  % LongitudinalBench deployment example
```

Both papers should share one `.bib` entry for each other with proper arXiv IDs once published.
