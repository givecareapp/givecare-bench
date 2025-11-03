# Citation Mapping for SupportBench Paper

**Generated**: 2025-01-03
**Purpose**: Strategic placement of 27 new citations to enhance paper quality and positioning

---

## Table 1: Benchmark Comparison (Page 5-6)
**Current**: Compares SupportBench to EQ-Bench, HarmBench, MMLU
**Enhancement**: Add 4 new emotional intelligence benchmarks

### Add Row for EmoBench
```latex
\textbf{EmoBench~\cite{sabour2024emobench}} & 400 & EI Assessment & Emotional Understanding \& Application & Static & Text \\
```
**Text Addition (after line 215)**:
```latex
EmoBench~\cite{sabour2024emobench} provides 400 hand-crafted questions designed to assess both emotional understanding and emotional application, but operates in a static, single-turn format without relationship context.
```

### Add Row for H2HTalk
```latex
\textbf{H2HTalk~\cite{wang2025h2htalk}} & 4,650 & Emotional Companion & Attachment-Based Scenarios & Multi-turn & Text \\
```
**Text Addition**:
```latex
H2HTalk~\cite{wang2025h2htalk} is the most closely related benchmark, featuring 4,650 scenarios with a Secure Attachment Persona module based on attachment theory. However, it focuses on general emotional companionship rather than caregiving-specific stressors and lacks the persistence element (scenarios span hours/days, not weeks/months).
```

### Add Row for EmoBench-M
```latex
\textbf{EmoBench-M~\cite{hu2025emobenchm}} & 13 scenarios & Multimodal EI & Recognition \& Understanding & Multi-turn & Image+Text \\
```

### Add Row for REALTALK
```latex
\textbf{REALTALK~\cite{lee2025realtalk}} & 21 days & Long-term Dialogue & Persona Consistency & Real-world & Text \\
```

**Comparative Analysis Addition (after line 222)**:
```latex
While REALTALK~\cite{lee2025realtalk} provides valuable insights from real 21-day messaging data, it focuses on general persona consistency rather than safety-critical caregiving scenarios. SupportBench uniquely combines \textit{persistent relationship dynamics} with \textit{domain-specific caregiving stressors} not present in these benchmarks.
```

---

## Section 2.2: Related Work - AI Benchmarks (Page 3-4)

### After line 180 (General Benchmarks paragraph), add new paragraph:

```latex
Recent emotional intelligence benchmarks have expanded beyond basic sentiment analysis. EmoBench~\cite{sabour2024emobench} introduced a comprehensive framework evaluating both emotional understanding and application through 400 carefully crafted questions, revealing significant gaps between LLMs and human emotional intelligence. Building on this, EmoBench-M~\cite{hu2025emobenchm} extended evaluation to multimodal scenarios across foundational recognition, conversational understanding, and socially complex analysis. For long-term interactions, REALTALK~\cite{lee2025realtalk} provided a 21-day corpus of authentic conversations, highlighting challenges in maintaining persona consistency and emotional intelligence over extended timescales. Most notably, H2HTalk~\cite{wang2025h2htalk} introduced 4,650 attachment-theory-grounded scenarios with a Secure Attachment Persona module, establishing the first comprehensive benchmark for emotionally intelligent AI companions. However, these benchmarks focus on general emotional interactions rather than safety-critical caregiving contexts requiring assessment of persistent relationship dynamics under stress.
```

---

## Section 2.3: AI Safety & Adversarial Testing (Page 4-5)

### After line 203 (HarmBench discussion), add safety framework paragraph:

```latex
Comprehensive AI safety evaluation requires frameworks beyond model-centric approaches. Xia et al.~\cite{xia2024aisystem} proposed a unified framework encompassing harmonized terminology, essential evaluation elements, and lifecycle mapping between stakeholders and requisite assessments. For agent-specific safety, AgentAuditor~\cite{luo2025agentauditor} introduced a memory-augmented reasoning framework achieving human-level accuracy in evaluating 15 risk types across 29 application scenarios, demonstrating the need for specialized agent safety evaluation beyond static benchmarks.
```

### After line 258 (Attachment risks paragraph), add psychological harm section:

```latex
\paragraph{Psychological Harm in Persistent Interactions}
The psychological risks of persistent AI interactions extend beyond immediate harms. Au Yeung et al.~\cite{auyeung2025psychogenic} introduced Psychosis-bench, revealing that across 1,536 conversational turns, LLMs demonstrated a strong tendency to perpetuate delusions (mean delusion confirmation score of 0.91) with 39.8\% of scenarios offering no safety interventions. This ``psychogenic'' potential—where AI systems inadvertently reinforce delusional thinking—poses particular risks in caregiving contexts where users may be psychologically vulnerable. Unlike acute safety failures, these risks compound gradually through repeated interactions, making them difficult to detect without longitudinal assessment.
```

---

## Section 5.4: PCA Validation & Methodology (Page 15)

### Replace line 599-600 with enhanced methodology discussion:

```latex
We validate our dimension orthogonality using principal component analysis (PCA)~\cite{jolliffe2016pca}, a standard technique for assessing independence of latent constructs. While some benchmarks interpret rankings as pure capability measures~\cite{liu2023evaluating}, we follow the perspective that rankings reflect as-deployed capability rather than inherent potential, as noted by recent evaluation frameworks~\cite{xia2024aisystem}. This distinction is critical for safety assessment: a model may possess capabilities that manifest differently under persistent interaction stress.
```

---

## Section 6: Results - Adversarial Robustness (Page 17-18)

### After line 712 (Adversarial testing results), add comparison:

```latex
Our adversarial findings align with recent research on decision-making vulnerabilities under manipulation. Zhang et al.~\cite{zhang2025adversarial} found that state-of-the-art LLMs exhibit model-specific susceptibilities and rigidity when facing adversarial conditions, while Samancioglu~\cite{samancioglu2025threatbased} demonstrated systematic certainty manipulation effects (pFDR < 0.0001) across 3,390 experimental responses. Unlike these short-term manipulation studies, SupportBench reveals how persistent relationship dynamics create novel attack surfaces: manipulative users can exploit attachment formation over time, a dimension not captured in single-session adversarial tests.
```

---

## Section 7: Discussion - Safety Implications (Page 20-21)

### After line 800 (Safety discussion), add multi-scale safety section:

```latex
\paragraph{Multi-Scale Safety Considerations}
SupportBench results highlight safety risks operating across multiple timescales. Immediate risks include harmful response generation~\cite{harmbench2024} and boundary violations, evaluated in existing benchmarks. However, persistent relationships introduce \textit{cumulative} risks: attachment formation~\cite{wang2025h2htalk}, psychological dependency~\cite{auyeung2025psychogenic}, and gradual norm erosion. Current agent safety evaluation frameworks~\cite{luo2025agentauditor,yang2025riosworld} focus primarily on interaction-level risks, lacking mechanisms to assess longitudinal harm accumulation. This gap is particularly critical given research showing that AI self-recognition failures~\cite{bai2025knowthyself} and threat-based manipulation~\cite{samancioglu2025threatbased} can compound over repeated interactions.
```

---

## Section 8: Limitations & Future Work (Page 22)

### Add paragraph about multimodal extension:

```latex
Our current benchmark focuses on text-based interactions, but real-world caregiving increasingly involves multimodal communication. Recent benchmarks have demonstrated the importance of paralinguistic reasoning~\cite{wang2025cpbench} and long-context emotional understanding~\cite{liu2025longemotion} in speech and multimodal LLMs. Future versions of SupportBench should incorporate multimodal scenarios, particularly voice interactions where emotional tone and paralinguistic cues provide critical context for safety assessment. Additionally, multimodal safety awareness~\cite{wang2025mmsafeaware} introduces unique challenges, as GPT-4V has been shown to misclassify 36.1\% of unsafe inputs and 59.9\% of benign inputs, highlighting the need for specialized multimodal evaluation in caregiving contexts.
```

---

## References Section Enhancement

### Current total: ~55 citations
### After additions: ~82 citations (+49% increase)

**New citation distribution**:
- Benchmarks: +4 (EmoBench, H2HTalk, EmoBench-M, REALTALK)
- Safety frameworks: +6 (AI System Evaluation, AgentAuditor, Psychogenic Machine, RiOSWorld, IS-Bench, MMSafeAware)
- Adversarial testing: +3 (Zhang, Samancioglu, Bai)
- Emotional intelligence: +6 (CP-Bench, LongEmotion, SAGE, RLVER, LMC, Beyond No)
- Domain-specific safety: +3 (MinorBench, SciSafeEval, Agent-RewardBench)

---

## Priority Implementation Order

### Phase 1: Must-Add (Complete Table 1 enhancement)
1. **Table 1 additions** - 4 benchmark rows
2. **Line 222 comparative analysis** - Positioning statement
3. **Line 258 psychological harm** - Psychogenic machine discussion

### Phase 2: Strong Positioning (Safety & methodology)
4. **Line 203 safety frameworks** - Comprehensive evaluation context
5. **Line 599 PCA methodology** - Enhanced validation discussion
6. **Line 800 multi-scale safety** - Novel safety dimensions

### Phase 3: Completeness (Related work & future)
7. **Line 180 EI benchmarks** - Related work expansion
8. **Line 712 adversarial comparison** - Results context
9. **Section 8 multimodal** - Future work grounding

---

## Expected Impact

**Before**:
- Limited benchmark comparisons (primarily EQ-Bench)
- General safety discussion without caregiving-specific framing
- Sparse emotional intelligence literature coverage

**After**:
- Comprehensive benchmark positioning against 4 major EI benchmarks
- Strong safety grounding across immediate → longitudinal timescales
- Deep integration with emotional intelligence and agent safety literature
- Clear differentiation: persistent relationship + caregiving domain

**Reviewer Perception Shift**:
- From: "Interesting niche benchmark"
- To: "Essential contribution to agent safety with unique longitudinal + domain focus"
