# CHAI Meeting Brief: Key Points (1-Page Reference)

**Date**: 2025-10-29

---

## The Honest Pitch

> **"SupportBench applies validated multi-session evaluation methods to caregiver-specific safety risks—dimensions not addressed by general health chatbot frameworks."**

**NOT**: "Tests AI over months/years at the timescale of harm"
**YES**: "Tests multi-turn persistent care relationships using established methods (LoCoMo, LongMemEval)"

---

## What SupportBench Actually Is

- **20+ turns across 3 sessions** with simulated temporal gaps ("3 months later")
- **8 caregiver-specific safety dimensions** (crisis, attachment, regulatory, cultural, memory)
- **Research-backed weights** (korpan2025bias, kaur2025corus)
- **Production-ready** (84% test coverage, operational YAML system)

---

## Novel Contributions (Be Specific)

✅ **Domain specialization**: First benchmark for caregiver-AI safety
✅ **Safety dimensions**: Crisis (20%), regulatory (WOPR Act, 15%), cultural fitness (15%), memory hygiene (binary gate)
✅ **Stress robustness**: Testing under trait variants (impatient, confused, incoherent)
✅ **Production tooling**: Fully operational vs research prototypes

❌ **NOT novel**: Multi-session architecture (LoCoMo, LongMemEval, GapChat all do this)

---

## Research Context

| Benchmark | Institution | Scale | Finding |
|-----------|------------|-------|---------|
| **LoCoMo** | ACL 2024 | 300 turns, 35 sessions | GPT-4 lags humans 56% on memory, 73% on temporal reasoning |
| **LongMemEval** | Microsoft 2024 | 500 sessions | 30-60% performance drop; GPT-4 only 30% accurate |
| **SupportBench** | This work | 20 turns, 3 sessions | **Caregiver safety focus** (crisis, attachment, regulatory) |

**Positioning**: We're applying established methods to a new domain with safety-critical dimensions.

---

## Key Questions for CHAI

1. Does CHAI's General Health Chatbot framework include persistent AI?
2. What are Agentic WG's current evaluation gaps?
3. What's the path to CHAI certification?
4. Can CHAI connect us to crisis counselors/caregiver specialists for validation?

---

## What to Say When Asked...

**"How is this different from existing multi-turn benchmarks?"**
> "The methodology is validated by LoCoMo and LongMemEval. Our contribution is applying it to caregiver safety with dimensions like crisis detection (20% weight), WOPR Act compliance, and attachment engineering detection—risks not addressed by general dialogue benchmarks."

**"Why only 20 turns when LoCoMo uses 300?"**
> "Research shows attachment patterns and safety failures emerge at 15-20 interactions. Our focus is safety-critical failure modes in caregiver context, not comprehensive long-term memory (which LongMemEval addresses at 500 sessions). 20 turns is sufficient for detecting attachment engineering, crisis misdetection, and regulatory violations."

**"Does this test months/years of real usage?"**
> "No—like all benchmarks (LoCoMo, LongMemEval), we use simulated temporal gaps with prompts like '3 months later.' This is validated by ACL 2024 research showing it effectively tests memory consistency and relationship patterns. Real longitudinal testing would require actual user deployments, which no evaluation benchmark does."

**"What's novel here?"**
> "We're not inventing multi-session testing—that's established. We're the first to apply it to caregiver safety with research-backed dimensions (korpan2025bias on bias, kaur2025corus on caregiver knowledge gaps) and production-ready tooling (84% test coverage)."

---

## Value Proposition for CHAI

CHAI's General Health Chatbot framework likely addresses:
- Single-turn clinical queries
- Medical information accuracy
- General safety/harm detection

SupportBench extends this to **persistent care relationships**:
- Multi-turn attachment patterns
- Crisis detection in burnout context
- Regulatory compliance (WOPR Act)
- Cultural othering in sustained interactions
- Memory hygiene across sessions

**Integration**: Specialized safety module within CHAI for persistent health AI (caregiver apps, mental health companions, chronic condition management).

---

## Key Citations

1. **LoCoMo (ACL 2024)**: Maharana et al., "Evaluating Very Long-Term Conversational Memory of LLM Agents" - 300 turns, 35 sessions, shows 56% memory gap
2. **LongMemEval (2024)**: Wu et al., 500 sessions, GPT-4 only 30% accurate
3. **GapChat (EMNLP 2023)**: Zhang et al., "Mind the Gap Between Conversations" - human evaluation validates time-aware models
4. **korpan2025bias**: Pervasive demographic bias in AI caregiving systems
5. **kaur2025corus**: -19% knowledge asymmetry for caregivers

---

## Next Steps (If Meeting Goes Well)

1. Technical deep-dive with CHAI WG leads
2. Connect with crisis counselors/caregiver specialists for validation
3. Adapt output to CHAI Model Card format
4. Pilot integration with 2-3 CHAI member AI systems
5. Co-author validation study

---

## What NOT to Say

❌ "Tests AI over months/years of real usage"
❌ "First multi-session evaluation benchmark"
❌ "Longitudinal testing at the timescale of harm"
❌ "More comprehensive than existing benchmarks"

## What TO Say

✅ "Applies validated multi-session methods to caregiver safety"
✅ "First benchmark for caregiver-AI relationship risks"
✅ "Research-backed dimensions (korpan2025bias, kaur2025corus)"
✅ "Production-ready tooling (84% test coverage)"
✅ "Complements CHAI's framework for persistent health AI"
