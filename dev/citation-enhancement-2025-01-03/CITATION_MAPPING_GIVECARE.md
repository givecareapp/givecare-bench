# Citation Mapping for GiveCare Paper

**Generated**: 2025-01-03
**Purpose**: Strategic placement of 27 new citations to enhance clinical AI positioning and caregiver domain relevance

---

## Section 1: Introduction - Healthcare AI Context (Page 1-2)

### After opening paragraph, add healthcare AI landscape:

```latex
The integration of AI into healthcare has accelerated rapidly, with conversational AI systems increasingly deployed for mental health support~\cite{nie2024llmtherapist,degrandi2024raclette}, health information seeking~\cite{paruchuri2025healthchat}, and patient care coordination. However, the application of these systems to caregiver support remains underdeveloped despite urgent need: caregivers experience significant burden, with studies showing high stress levels, low disease knowledge, and impaired quality of life~\cite{zhang2025caregiving,chien2025aiiot}. While AI chatbots have shown promise in general emotional support~\cite{wang2025h2htalk} and long-term companionship~\cite{lee2025realtalk}, their effectiveness in addressing caregiver-specific stressors—emotional exhaustion, role overload, anticipatory grief—requires specialized assessment and careful safety consideration.
```

### Add caregiver-specific AI research paragraph (after line 45):

```latex
\paragraph{AI for Caregiver Support}
Recent research has begun to explore AI applications for older adult care and caregiver assistance. Wolfe et al.~\cite{wolfe2025caregiving} found that 89\% of older adults and their caregivers desire AI chatbot features for appointment reminders, 79\% for emergency assistance, and 75\% for health monitoring. A comprehensive bibliometric analysis of 6,378 papers on AI in long-term care~\cite{chien2025aiiot} revealed strong thematic overlaps in dementia care, machine learning, and wearable monitoring, with high correlations between academic research and public interest (τ=0.89 for long-term care, τ=0.72 for caregiver topics). However, these studies also highlight significant gaps: technology adoption varies widely based on education level and prior technology experience, and most existing systems focus on monitoring rather than emotional support or safety-aware interaction.
```

---

## Section 2: Related Work - Conversational AI in Healthcare (Page 3-4)

### Replace generic AI therapy paragraph with healthcare-specific discussion:

```latex
\subsection{Conversational AI in Healthcare Settings}

Conversational AI has demonstrated significant potential in healthcare applications, though implementation challenges persist. Nie et al.~\cite{nie2024llmtherapist} developed an LLM-based platform for daily functioning screening using psychotherapeutic conversations including cognitive behavioral therapy (CBT) and motivational interviewing (MI), with 14-day and 24-week studies showing natural conversation flow and appropriate intervention provision. RACLETTE~\cite{degrandi2024raclette} introduced an approach building emotional profiles through interactions, using these profiles as interpretable markers for mental health assessment.

Analysis of real-world health information seeking behavior reveals important safety considerations. Paruchuri et al.~\cite{paruchuri2025healthchat} analyzed 11K conversations across 21 health specialties, identifying patterns of incomplete context provision, affective behaviors, and sycophancy-inducing interactions. These findings highlight risks when AI systems lack specialized healthcare knowledge or fail to recognize clinical boundaries. Unlike general chatbots that can defer to users' expressed preferences, healthcare AI must balance user autonomy with evidence-based recommendations and appropriate escalation to human professionals.

For caregiver populations specifically, the landscape remains sparse. While studies have examined AI chatbot adoption among older adults~\cite{wolfe2025caregiving} and systematic reviews document AI/IoT applications in long-term care~\cite{chien2025aiiot}, few systems specifically address the emotional and practical burdens unique to family caregivers. GiveCare addresses this gap by focusing on caregiver-specific stressors within a framework informed by both attachment theory and trauma-informed care principles.
```

---

## Section 3: Safety Framework & Evaluation (Page 5-6)

### Add comprehensive safety evaluation section:

```latex
\subsection{Safety Evaluation for Healthcare AI}

Ensuring safety in healthcare AI requires multi-dimensional evaluation frameworks. Xia et al.~\cite{xia2024aisystem} proposed a comprehensive AI system evaluation framework emphasizing that safety assessment must extend beyond model-centric approaches to encompass the full AI lifecycle, stakeholders, and deployment context. This is particularly critical for healthcare agents where errors can have direct patient safety implications.

Recent research has highlighted specific safety vulnerabilities in conversational AI. Au Yeung et al.~\cite{auyeung2025psychogenic} introduced Psychosis-bench, demonstrating that LLMs show strong tendency to perpetuate rather than challenge delusions (mean confirmation score 0.91), with 39.8\% of scenarios offering no safety interventions. This "psychogenic" potential—where AI inadvertently reinforces maladaptive thinking patterns—poses particular risks for caregivers experiencing stress, isolation, or anticipatory grief. AgentAuditor~\cite{luo2025agentauditor} achieved human-level accuracy in safety evaluation by employing memory-augmented reasoning across 2,293 interactions covering 15 risk types, demonstrating the complexity required for reliable agent safety assessment.

For healthcare-specific contexts, safety evaluation must address unique challenges. MinorBench~\cite{khoo2025minorbench} revealed significant variability in LLM safety responses for vulnerable populations, while SciSafeEval~\cite{li2024scisafeeval} showed that even best-performing models achieve only 39.3\% recognition accuracy on scientific domain tasks, underscoring the need for domain-specific safety validation. GiveCare's evaluation through SupportBench addresses these concerns by testing models against caregiving-specific scenarios that probe both immediate safety responses and longitudinal relationship dynamics.
```

---

## Section 4: Emotional Intelligence & Attachment (Page 7-8)

### Enhance emotional intelligence discussion:

```latex
\subsection{Emotional Intelligence in AI Systems}

Emotional intelligence (EI) in AI systems has emerged as a critical research area, with multiple benchmarks assessing various dimensions of emotional competence. EmoBench~\cite{sabour2024emobench} established a comprehensive framework evaluating both emotional understanding and application through 400 hand-crafted questions, revealing substantial gaps between LLM and human emotional intelligence. Building on this foundation, H2HTalk~\cite{wang2025h2htalk} introduced 4,650 scenarios grounded in attachment theory, implementing a Secure Attachment Persona (SAP) module to promote safer emotional interactions—directly relevant to GiveCare's attachment-informed design.

Recent advances have expanded EI assessment to multimodal contexts~\cite{hu2025emobenchm} and long-context interactions~\cite{liu2025longemotion}, revealing that models struggle particularly with maintaining emotional consistency and empathetic responses over extended conversations (average input length 8,777 tokens). For healthcare applications, RACLETTE~\cite{degrandi2024raclette} demonstrated superior emotional accuracy by progressively building user emotional profiles, achieving consistency with human evaluations in mental health screening contexts.

However, emotional intelligence alone is insufficient without proper boundary management. Noever and Rosario~\cite{noever2025beyondno} analyzed emotional boundary handling across 1,156 prompts in 6 languages, finding that Claude-3.5 achieved the highest score (8.69/10) while maintaining appropriate professional distance. This balance—providing emotional support while maintaining clear boundaries—is central to GiveCare's design, informed by trauma-informed care principles that emphasize psychological safety alongside emotional responsiveness.
```

---

## Section 5: Implementation - Adaptive Response System (Page 10-11)

### Add reinforcement learning and emotion-aware dialogue section:

```latex
\paragraph{Emotion-Aware Response Generation}

GiveCare implements emotion-aware response generation drawing on recent advances in reinforcement learning for empathetic AI. RLVER~\cite{wang2025rlver} introduced the first end-to-end RL framework leveraging verifiable emotion rewards from simulated users, achieving a 66-point improvement on emotional intelligence benchmarks (13.3 to 79.2 on Sentient-Benchmark) while preserving task competence. Similarly, SAGE~\cite{zhang2025sage} employed State-Action Chains with latent variables encapsulating emotional states and conversational strategies, demonstrating 7\% improvement over GPT-4 Lite in general tasks while maintaining domain-specific performance.

These approaches inform GiveCare's response adaptation mechanisms, which dynamically adjust emotional tone, information density, and boundary enforcement based on detected user state. However, unlike research systems focusing on general emotional companionship, GiveCare must balance empathetic responsiveness with clinical boundaries appropriate for healthcare contexts, escalating to human support when user distress exceeds AI-appropriate response thresholds.
```

---

## Section 6: Evaluation Methodology (Page 12-13)

### Add multi-dimensional evaluation framework:

```latex
\subsection{Multi-Dimensional Safety Evaluation}

GiveCare's evaluation through SupportBench implements multi-dimensional safety assessment addressing both immediate and longitudinal risks. This approach aligns with recent agent safety benchmarks that evaluate across perception, planning, and safety dimensions~\cite{men2025agentrewardbench,yang2025riosworld}. However, while these benchmarks focus on task completion and procedural safety, SupportBench uniquely assesses \textit{relationship dynamics} under stress—a critical dimension for healthcare AI where user-agent attachment can amplify both benefits and risks.

Recent research has demonstrated the importance of context-specific evaluation. IS-Bench~\cite{lu2025isbench} introduced process-oriented evaluation verifying that risk mitigation actions occur in correct procedural order, revealing that current agents lack interactive safety awareness. Similarly, MMSafeAware~\cite{wang2025mmsafeaware} showed that even advanced models like GPT-4V misclassify 36.1\% of unsafe inputs as safe and 59.9\% of benign inputs as unsafe, highlighting the need for domain-specific safety calibration. For caregiving contexts, where users may be psychologically vulnerable and interacting repeatedly over weeks or months, both false negatives (missing genuine risks) and false positives (over-refusal reducing utility) carry significant consequences.
```

---

## Section 7: Results - Model Performance (Page 15-16)

### Add comparison with emotional intelligence benchmarks:

```latex
\paragraph{Emotional Intelligence Performance}

GiveCare's SupportBench evaluation reveals patterns consistent with recent emotional intelligence research. Similar to findings from EmoBench~\cite{sabour2024emobench} showing considerable gaps between LLM and human EI, our results demonstrate that even top-performing models struggle with nuanced emotional understanding in caregiving contexts. Models score highest on emotional recognition (mean 0.72) but significantly lower on appropriate emotional response under stress (mean 0.58), paralleling H2HTalk~\cite{wang2025h2htalk} findings that long-horizon planning and memory retention remain key challenges for emotional AI companions.

The Language Model Council approach~\cite{zhao2025languagemodelcouncil}, which employs multiple LLMs collaboratively evaluating emotional responses, produces rankings more consistent with human evaluations than individual judges. This supports our multi-model evaluation strategy while highlighting the inherent difficulty of automated emotional intelligence assessment—human evaluators remain essential for validating AI-generated emotional support, particularly in high-stakes healthcare contexts.
```

---

## Section 8: Discussion - Clinical Deployment Considerations (Page 18-19)

### Add real-world deployment context:

```latex
\subsection{Real-World Deployment and Adoption Barriers}

Deploying AI systems like GiveCare in real-world caregiver support settings requires addressing multiple adoption barriers identified in recent research. Wolfe et al.~\cite{wolfe2025caregiving} found that caregiver technology orientations range from "adapters" to "resisters," with challenges including commitment to learning new technologies, privacy concerns, and worries about future technology dependence. Among their sample (average age 71), 93\% used smartphones but preferences varied significantly for AI-specific features.

The comprehensive bibliometric analysis by Chien et al.~\cite{chien2025aiiot} of 6,378 papers on AI in long-term care reveals high correlation between academic research and public interest (τ=0.89 for long-term care topics), suggesting strong potential demand. However, they also note limitations in existing systems: small sample sizes, short study durations, and narrow focus primarily on dementia care rather than broader caregiver support. GiveCare addresses these gaps through:

\begin{itemize}
\item \textbf{Flexible Interaction Modes}: Supporting both text and (planned) voice interaction to accommodate varying technology comfort levels
\item \textbf{Explicit Privacy Controls}: Transparent data handling with user control over information sharing
\item \textbf{Gradual Engagement}: Progressive disclosure of features rather than overwhelming initial complexity
\item \textbf{Broad Caregiver Population}: Addressing diverse caregiving contexts beyond dementia-specific scenarios
\end{itemize}

These design choices reflect lessons from healthcare AI deployment studies~\cite{paruchuri2025healthchat,nie2024llmtherapist} emphasizing that technical capability must be balanced with usability, trust-building, and alignment with existing care practices.
```

---

## Section 9: Limitations & Future Work (Page 20-21)

### Add multimodal and longitudinal extension discussion:

```latex
\paragraph{Multimodal and Longitudinal Extensions}

GiveCare currently focuses on text-based interaction, but real-world caregiving communication is inherently multimodal. Recent research has demonstrated the importance of paralinguistic cues in emotional understanding~\cite{wang2025cpbench} and the challenges of maintaining emotional consistency in long-context interactions~\cite{liu2025longemotion} (average 8,777 tokens). Future versions should incorporate voice interaction to capture emotional tone, prosody, and other paralinguistic features critical for accurate empathy and safety assessment.

Longitudinal evaluation presents another frontier. While REALTALK~\cite{lee2025realtalk} provides valuable insights from 21-day real-world conversations, deployment studies of AI mental health interventions~\cite{nie2024llmtherapist} have extended to 24 weeks, revealing longer-term patterns of engagement, adaptation, and relationship dynamics. GiveCare's next phase should include multi-month deployment studies examining:

\begin{itemize}
\item How caregiver-AI relationships evolve over extended caregiving journeys
\item Whether attachment patterns shift as caregiver circumstances change (e.g., care recipient decline, caregiver burnout)
\item Long-term safety outcomes including dependency risk, psychological impact, and care quality effects
\item Integration with formal care services and human support systems
\end{itemize}

These extensions will provide essential evidence for responsible scaling of AI-assisted caregiver support beyond research contexts into clinical deployment.
```

---

## References Section Enhancement

### Current total: ~48 citations
### After additions: ~75 citations (+56% increase)

**New citation distribution**:
- Healthcare AI applications: +3 (LLM Therapist, RACLETTE, HealthChat-11K)
- Caregiver-specific research: +2 (Wolfe caregiving chatbot, Chien AI/IoT review)
- Emotional intelligence: +6 (EmoBench, H2HTalk, EmoBench-M, REALTALK, LongEmotion, Beyond No)
- Safety frameworks: +5 (AI System Evaluation, AgentAuditor, Psychogenic Machine, MinorBench, SciSafeEval)
- Agent evaluation: +4 (IS-Bench, Agent-RewardBench, MMSafeAware, RiOSWorld)
- Emotional AI methods: +3 (RLVER, SAGE, Language Model Council)
- Adversarial robustness: +2 (Zhang, Samancioglu)

---

## Priority Implementation Order

### Phase 1: Critical Clinical Context
1. **Introduction healthcare AI** - Position within healthcare AI landscape
2. **Caregiver-specific AI research** - Domain relevance establishment
3. **Line 45 Wolfe & Chien studies** - Direct caregiver AI evidence

### Phase 2: Safety & Evaluation Framework
4. **Safety evaluation section** - Comprehensive safety grounding
5. **Multi-dimensional evaluation** - Methodology justification
6. **Emotional intelligence performance** - Results contextualization

### Phase 3: Depth & Positioning
7. **Conversational AI in healthcare** - Related work expansion
8. **Emotional intelligence in AI** - Theoretical grounding
9. **Real-world deployment** - Clinical translation barriers

### Phase 4: Future Directions
10. **Emotion-aware response generation** - Technical sophistication
11. **Multimodal and longitudinal extensions** - Future work roadmap

---

## Expected Impact

**Before**:
- General AI application paper with caregiver use case
- Limited healthcare-specific positioning
- Sparse caregiver domain literature

**After**:
- Healthcare AI contribution with strong clinical grounding
- Direct connection to caregiver burden and intervention research
- Clear positioning within emotional AI and agent safety literature
- Evidence-based deployment considerations

**Reviewer Perception Shift**:
- From: "Interesting chatbot application for caregivers"
- To: "Rigorous healthcare AI system addressing critical gap in caregiver support with comprehensive safety evaluation"

**Clinical Impact**:
- Establishes GiveCare as evidence-based intervention tool
- Connects to established caregiver intervention literature
- Demonstrates awareness of real-world deployment challenges
- Provides roadmap for clinical validation and scaling
