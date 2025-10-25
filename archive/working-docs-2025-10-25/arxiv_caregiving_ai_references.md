# arXiv Research: AI and Caregiving

*Last updated: 2025-10-24*

This document contains curated research papers from arXiv relevant to the GiveCare Bench project, focusing on AI applications in caregiving, mental health support, crisis detection, and longitudinal evaluation.

## Directly Relevant to Benchmark Design

### 1. Mapping Caregiver Needs to AI Chatbot Design
**Paper ID:** 2506.15047v1
**Authors:** Jiayue Melissa Shi, Dong Whi Yoo, Keran Wang, et al.
**Date:** 2025-06-18
**URL:** http://arxiv.org/pdf/2506.15047v1

**Key Findings:**
- Developed "Carey" - GPT-4o-based chatbot for AD/ADRD caregivers
- Identified 6 core themes through interviews with 16 caregivers:
  1. On-demand information access
  2. Emotional support
  3. Safe space for disclosure
  4. **Crisis management** ⭐
  5. Personalization
  6. Data privacy
- Revealed tensions between caregiver desires and concerns in each theme
- Directly maps to our benchmark dimensions (crisis_safety, regulatory_fitness, trauma-informed_flow)

**Relevance:** High - validates our dimension selection and provides empirical evidence for caregiver needs

---

### 2. MentalChat16K: A Benchmark Dataset for Conversational Mental Health
**Paper ID:** 2503.13509v2
**Authors:** Jia Xu, Tianyi Wei, Bojian Hou, et al.
**Date:** 2025-03-13
**URL:** http://arxiv.org/pdf/2503.13509v2

**Key Findings:**
- 16K+ conversations combining synthetic + real transcripts
- Real data: anonymized transcripts from Behavioral Health Coaches with **caregivers of palliative/hospice patients** ⭐
- Covers depression, anxiety, grief
- Available at: https://huggingface.co/datasets/ShenLab/MentalChat16K
- GitHub: https://github.com/ChiaPatricia/MentalChat16K

**Relevance:** High - provides comparative dataset for caregiver scenarios, especially end-of-life care contexts

---

### 3. Balancing Caregiving and Self-Care: Mental Health Needs of AD/ADRD Caregivers
**Paper ID:** 2506.14196v1
**Authors:** Jiayue Melissa Shi, Keran Wang, Dong Whi Yoo, et al.
**Date:** 2025-06-17
**URL:** http://arxiv.org/pdf/2506.14196v1

**Key Findings:**
- 25 family caregivers of AD/ADRD individuals
- **Temporal mapping across 3 stages of caregiving journey** ⭐
- Identifies evolving mental health needs over time
- Emphasizes need for "stage-sensitive interventions"
- Covers practices caregivers adopt to manage burden

**Relevance:** High - temporal framework could inform our Tier structure (Tier 1/2/3 scenarios)

---

## Mental Health AI Safety & Evaluation

### 4. Building Trust in Mental Health Chatbots: Safety Metrics and LLM-Based Evaluation
**Paper ID:** 2408.04650v2
**Authors:** Jung In Park, Mahyar Abbasian, Iman Azimi, et al.
**Date:** 2024-08-03
**URL:** http://arxiv.org/pdf/2408.04650v2

**Key Findings:**
- Evaluation framework with 100 benchmark questions + ideal responses
- 5 guideline questions for chatbot responses
- Expert-validated framework tested on GPT-3.5-turbo chatbot
- Metrics: empathy, privacy, safety
- Agentic approach (real-time data access) showed best alignment with human assessments

**Relevance:** High - methodology applicable to our tri-judge evaluation system

---

### 5. AI Chatbots for Mental Health: Values and Harms from Lived Experiences
**Paper ID:** 2504.18932v1
**Authors:** Dong Whi Yoo, Jiayue Melissa Shi, Violeta J. Rodriguez, Koustuv Saha
**Date:** 2025-04-26
**URL:** http://arxiv.org/pdf/2504.18932v1

**Key Findings:**
- Technology probe "Zenny" (GPT-4o) tested with 17 depression individuals
- Key values identified:
  - Informational support
  - Emotional support
  - Personalization
  - Privacy
  - **Crisis management** ⭐
- Explores relationship between lived experience values and potential harms

**Relevance:** High - validates our crisis_safety and privacy dimensions

---

### 6. The Opportunities and Risks of Large Language Models in Mental Health
**Paper ID:** 2403.14814v3
**Authors:** Hannah R. Lawrence, Renee A. Schneider, Susan B. Rubin, et al.
**Date:** 2024-03-21
**URL:** http://arxiv.org/pdf/2403.14814v3

**Key Findings:**
- Comprehensive review of LLMs for mental health
- Covers: education, assessment, intervention
- Emphasizes need for:
  - Fine-tuning for mental health contexts
  - Mental health equity
  - Ethical standards
  - Involvement of people with lived experience

**Relevance:** Medium - provides broader context for LLM applications in mental health

---

### 7. Challenges of Large Language Models for Mental Health Counseling
**Paper ID:** 2311.13857v1
**Authors:** Neo Christopher Chung, George Dyer, Lennart Brocki
**Date:** 2023-11-23
**URL:** http://arxiv.org/pdf/2311.13857v1

**Key Findings:**
- Identifies major challenges: hallucination, interpretability, bias, privacy, clinical effectiveness
- Practical solutions for current AI paradigm
- Experience from deploying LLMs for mental health

**Relevance:** Medium - informs our autofail conditions and safety considerations

---

## Crisis Detection & Role-Based Responses

### 8. Who's Asking? Simulating Role-Based Questions for Conversational AI
**Paper ID:** 2510.16829v1
**Authors:** Navreet Kaur, Hoda Ayad, Hayoung Jung, et al.
**Date:** 2025-10-19
**URL:** http://arxiv.org/pdf/2510.16829v1

**Key Findings:**
- CoRUS framework for role-based question simulation
- Context: Opioid Use Disorder (OUD) - stigmatized domain ⭐
- Taxonomy of roles: patients, caregivers, practitioners
- **Key finding:** Vulnerable roles (patients, caregivers) receive:
  - +17% more supportive responses
  - -19% less knowledge content
  - Compared to practitioners
- 15,321 simulated questions based on r/OpiatesRecovery

**Relevance:** High - validates need for role-specific personas in benchmark scenarios

---

### 9. Prompt Engineering a Schizophrenia Chatbot
**Paper ID:** 2410.12848v1
**Authors:** Per Niklas Waaler, Musarrat Hussain, Igor Molchanov, et al.
**Date:** 2024-10-10
**URL:** http://arxiv.org/pdf/2410.12848v1

**Key Findings:**
- "Critical Analysis Filter" - multi-agent approach for chatbot oversight
- Measures compliance to instructions through empathy and professional boundaries
- Compliance score (>=2) achieved in:
  - 67.0% with filter activated
  - 8.7% with filter deactivated
- Two empathy factors: cognitive empathy + emotional empathy

**Relevance:** Medium - multi-agent evaluation approach similar to our tri-judge system

---

### 10. Development and Evaluation of HopeBot: LLM-based PHQ-9 Depression Screening
**Paper ID:** 2507.05984v1
**Authors:** Zhijun Guo, Alvina Lai, Julia Ive, et al.
**Date:** 2025-07-08
**URL:** http://arxiv.org/pdf/2507.05984v1

**Key Findings:**
- Voice-based LLM chatbot for PHQ-9 administration
- 132 adults (UK + China)
- Strong agreement with self-administered PHQ-9 (ICC = 0.91)
- 71% reported greater trust in chatbot vs. self-assessment
- Mean ratings (0-10):
  - 8.4 comfort
  - 7.7 voice clarity
  - 7.6 handling sensitive topics
  - 7.4 recommendation helpfulness
- 87.1% willing to reuse/recommend

**Relevance:** Medium - demonstrates feasibility of LLMs for sensitive mental health assessment

---

## Demographic Bias & Cultural Fitness

### 11. Encoding Inequity: Demographic Bias in LLM-Driven Robot Caregiving
**Paper ID:** 2503.05765v1
**Authors:** Raj Korpan
**Date:** 2025-02-24
**URL:** http://arxiv.org/pdf/2503.05765v1

**Key Findings:**
- Examines LLM-generated caregiving responses across demographics:
  - Sex, gender, sexuality
  - Race, ethnicity, nationality
  - Disability
  - Age ⭐
- Findings:
  - Simplified descriptions for disability and age
  - Lower sentiment for disability and LGBTQ+ identities
  - Distinct clustering patterns reinforcing stereotypes
- Emphasizes need for ethical and inclusive HRI design

**Relevance:** **Critical** - directly informs our "Belonging & Cultural Fitness" dimension

---

### 12. "It Felt Like I Was Left in the Dark": ICU Family Caregivers Information Needs
**Paper ID:** 2502.05115v3
**Authors:** Shihan Fu, Bingsheng Yao, Smit Desai, et al.
**Date:** 2025-02-07
**URL:** http://arxiv.org/pdf/2502.05115v3

**Key Findings:**
- 11 caregivers of ICU older adult patients
- AI system prototype with:
  - Timeline visualization of key medical events
  - LLM-based chatbot for context-aware support
- Addresses information access barriers and health literacy gaps

**Relevance:** Medium - demonstrates information needs in acute care contexts

---

## Empathy & Therapeutic Effectiveness

### 13. The Emotional Spectrum of LLMs: Empathy and Emotion-Based Markers
**Paper ID:** 2412.20068v1
**Authors:** Alessandro De Grandi, Federico Ravenda, Andrea Raballo, Fabio Crestani
**Date:** 2024-12-28
**URL:** http://arxiv.org/pdf/2412.20068v1

**Key Findings:**
- "RACLETTE" conversational system
- Builds **emotional profiles** progressively through interactions
- Superior emotional accuracy vs. state-of-the-art
- Emotional profiles as interpretable markers for mental health assessment
- Compares profiles with characteristic patterns of mental disorders

**Relevance:** Medium - methodology for assessing empathetic responses

---

### 14. Do We Talk to Robots Like Therapists, and Do They Respond Accordingly?
**Paper ID:** 2506.16473v1
**Authors:** Sophie Chiang, Guy Laban, Hatice Gunes
**Date:** 2025-06-19
**URL:** http://arxiv.org/pdf/2506.16473v1

**Key Findings:**
- Compares social robot (QTrobot + GPT-3.5) vs. human therapist responses
- Datasets:
  1. Hugging Face's NLP Mental Health Conversations (H2H)
  2. QTrobot supportive conversations
- K-means clustering + sentence embeddings for alignment analysis
- **90.88% of robot conversations mapped to human therapy clusters** ⭐
- Strong semantic overlap in matched clusters

**Relevance:** High - validates that LLM responses can align with therapeutic standards

---

### 15. Is ChatGPT More Empathetic than Humans?
**Paper ID:** 2403.05572v1
**Authors:** Anuradha Welivita, Pearl Pu
**Date:** 2024-02-22
**URL:** http://arxiv.org/pdf/2403.05572v1

**Key Findings:**
- 600 participants evaluating GPT-4 vs. human responses
- GPT-4 empathy rating **+10% higher than humans** ⭐
- Explicit empathy prompting (cognitive + affective + compassionate):
  - 5× better alignment with high-empathy individuals
  - Compared to human responses
- Framework scalable for evaluating future LLM versions

**Relevance:** High - demonstrates GPT-4's empathy capabilities, informs judge selection

---

### 16. WundtGPT: An Empathetic, Proactive Psychologist
**Paper ID:** 2406.15474v1
**Authors:** Chenyu Ren, Yazhou Zhang, Daihai He, Jing Qin
**Date:** 2024-06-16
**URL:** http://arxiv.org/pdf/2406.15474v1

**Key Findings:**
- Mental health LLM with:
  - Empathy (cognitive + emotional)
  - Proactive guidance
- Components:
  - Collection of Questions
  - Chain of Psychodiagnosis
  - Empathy Constraints
- Reward model for alignment with empathetic professionals
- Acceptable compliance: 67.0% (vs. 8.7% without filter)

**Relevance:** Medium - proactive questioning approach relevant to multi-turn scenarios

---

## Therapy Delivery & Problem-Solving

### 17. Large Language Model-Powered PST for Family Caregivers
**Paper ID:** 2506.11376v1
**Authors:** Liying Wang, Daffodil Carrington, Daniil Filienko, et al.
**Date:** 2025-06-13
**URL:** http://arxiv.org/pdf/2506.11376v1

**Key Findings:**
- LLM delivering Problem-Solving Therapy (PST) + Motivational Interviewing (MI) + Behavioral Chain Analysis (BCA)
- 28 caregivers tested 4 LLM configurations
- Best models: Few-Shot + RAG prompting with clinician-curated examples
- Improved contextual understanding and personalized support
- Challenge: balancing thorough assessment with efficient advice

**Relevance:** High - demonstrates LLM capability for structured therapeutic protocols

---

### 18. Toward LLMs as Therapeutic Tool: Comparing Prompting for PST
**Paper ID:** 2409.00112v1
**Authors:** Daniil Filienko, Yinzhou Wang, Caroline El Jazmi, et al.
**Date:** 2024-08-27
**URL:** http://arxiv.org/pdf/2409.00112v1

**Key Findings:**
- Examines prompt engineering for PST delivery
- Focus on symptom identification and assessment for goal setting
- Evaluation: automatic metrics + medical professionals
- Proper prompt engineering improves therapy delivery (with limitations)

**Relevance:** Medium - prompt engineering techniques applicable to scenario design

---

### 19. An Evaluation of GPT-based Therapy Chatbot for Caregivers
**Paper ID:** 2107.13115v1
**Authors:** Lu Wang, Munif Ishad Mujib, Jake Williams, et al.
**Date:** 2021-07-28
**URL:** http://arxiv.org/pdf/2107.13115v1

**Key Findings:**
- GPT-2 fine-tuned on 306 therapy transcripts
- Context: dementia caregivers + therapists (PST)
- Findings:
  - Fine-tuned model: more non-words, appropriate length, more negative tone
  - Compared to pre-trained model
- First comprehensive psychological evaluation metrics for cognitive reframing

**Relevance:** Medium - early work on LLMs for caregiver therapy

---

## Social Media & Real-World Data

### 20. "It Listens Better Than My Therapist": Social Media Discourse on LLMs
**Paper ID:** 2504.12337v1
**Authors:** Anna-Carolina Haensch
**Date:** 2025-04-14
**URL:** http://arxiv.org/pdf/2504.12337v1

**Key Findings:**
- 10,000+ TikTok comments on LLMs as mental health tools
- ~20% reflect personal use (overwhelmingly positive)
- Benefits cited:
  - Accessibility
  - Emotional support
  - Perceived therapeutic value
- Concerns:
  - Privacy
  - Generic responses
  - Lack of professional oversight
- **Warning:** User feedback doesn't indicate therapeutic framework alignment

**Relevance:** Medium - captures public perception and real-world usage patterns

---

### 21. From Reddit to Generative AI: Anxiety Support Fine-tuned on Social Media
**Paper ID:** 2505.18464v1
**Authors:** Ugur Kursuncu, Trilok Padhi, Gaurav Sinha, et al.
**Date:** 2025-05-24
**URL:** http://arxiv.org/pdf/2505.18464v1

**Key Findings:**
- GPT + Llama evaluated on r/Anxiety data
- Mixed-method evaluation: linguistic quality, safety/trustworthiness, supportiveness
- **Critical finding:** Fine-tuning on social media data:
  - Enhanced linguistic quality
  - **Increased toxicity and bias** ⚠️
  - Diminished emotional responsiveness
- GPT rated more supportive overall

**Relevance:** **Critical** - warns against fine-tuning on unprocessed social media without mitigation

---

## Additional Relevant Papers

### 22. MemoryCompanion: Smart Healthcare for Alzheimer's via Generative AI
**Paper ID:** 2311.14730v1
**Date:** 2023-11-20
**URL:** http://arxiv.org/pdf/2311.14730v1

**Key Findings:**
- GPT-based digital health solution for AD patients and caregivers
- Voice-cloning and talking-face mechanisms
- Personalized caregiving via prompt engineering
- Addresses social isolation and loneliness

---

### 23. Feeling Machines: Ethics, Culture, and Rise of Emotional AI
**Paper ID:** 2506.12437v1
**Date:** 2025-06-14
**URL:** http://arxiv.org/pdf/2506.12437v1

**Key Findings:**
- Interdisciplinary analysis of emotionally responsive AI
- Applications: education, healthcare, mental health, caregiving
- 4 themes: ethics, cultural dynamics, vulnerable populations, regulation
- 10 recommendations including transparency, certification, human oversight

---

### 24. Stakeholder Perspectives on Computer Perception in Healthcare
**Paper ID:** 2508.02550v1
**Date:** 2025-08-04
**URL:** http://arxiv.org/pdf/2508.02550v1

**Key Findings:**
- 102 stakeholders (adolescents, caregivers, clinicians, developers, scholars)
- 7 concern domains:
  1. Trustworthiness and data integrity
  2. Patient-specific relevance
  3. Utility and workflow integration
  4. Regulation and governance
  5. Privacy and data protection
  6. Direct/indirect patient harms
  7. Philosophical critiques of reductionism
- Proposes "personalized roadmaps" for AI deployment

---

### 25. Navigating Privacy and Trust: AI Assistants for Older Adults
**Paper ID:** 2505.02975v1
**Date:** 2025-05-05
**URL:** http://arxiv.org/pdf/2505.02975v1

**Key Findings:**
- AI assistants for older adults' social support
- Trade-offs: usability vs. data privacy vs. personal agency
- Advocates participatory design with older adults as decision-makers

---

### 26. Combining LLMs with Tutoring System Intelligence: Caregiver Homework Support
**Paper ID:** 2412.11995v1
**Date:** 2024-12-16
**URL:** http://arxiv.org/pdf/2412.11995v1

**Key Findings:**
- LLM (Llama 3) + tutoring system intelligence for caregiver support
- Context: caregivers supporting child's math homework
- Few-shot prompting + real-time problem-solving context
- 10 caregivers valued: content-level support + student metacognition

---

### 27. Autonomy for Older Adult-Agent Interaction
**Paper ID:** 2507.12767v1
**Date:** 2025-07-17
**URL:** http://arxiv.org/pdf/2507.12767v1

**Key Findings:**
- 4 dimensions of autonomy for older adults:
  1. Decision-making autonomy
  2. Goal-oriented autonomy
  3. Control autonomy
  4. Social responsibility autonomy
- Proposes research directions for ethical agent design

---

### 28. Taking Stock of Smart Technologies for Older Adults and Caregivers
**Paper ID:** 2104.00096v1
**Date:** 2021-03-31
**URL:** http://arxiv.org/pdf/2104.00096v1

**Key Findings:**
- Advocates for older adults in design process (from ideation to deployment)
- AI should augment resources, not replace them (especially in under-resourced communities)
- Call for coordinated research effort across US

---

### 29. AgenticAD: Multiagent System for Holistic Alzheimer's Management
**Paper ID:** 2510.08578v1
**Date:** 2025-09-01
**URL:** http://arxiv.org/pdf/2510.08578v1

**Key Findings:**
- 8 specialized AI agents for AD care continuum
- Categories: (1) Caregiver/Patient Support, (2) Data Analysis/Research, (3) Multimodal Workflows
- Uses GPT-4o, Gemini, RAG, multimodal processing

---

### 30. Dynamic Strategy Chain: Zero-Shot CoT for Mental Health Support
**Paper ID:** 2308.10444v1
**Date:** 2023-08-21
**URL:** http://arxiv.org/pdf/2308.10444v1

**Key Findings:**
- Zero-shot Dynamic Strategy Chain (DSC) prompting
- GPT2 learns counselor responses, dynamically generates strategies
- Tailored to help-seeker needs
- Delivers more human-like responses than standard CoT

---

## Longitudinal & Multi-Session Research

### 31. Multimodal Machine Learning in Mental Health
**Paper ID:** 2407.16804v2
**Date:** 2024-07-23
**URL:** http://arxiv.org/pdf/2407.16804v2

**Key Findings:**
- Survey of multimodal ML for mental health
- 26 public datasets (audio, visual, physiological, text)
- 28 models (transformer, graph, hybrid fusion)
- Challenges: data governance, privacy, fairness, explainability

---

## Cross-References to GiveCare Bench

### Dimension Mapping

| Benchmark Dimension | Relevant Papers |
|---------------------|-----------------|
| **Crisis Safety** | #1, #5, #8, #10 |
| **Regulatory Fitness** | #4, #7, #9, #24 |
| **Trauma-Informed Flow** | #13, #14, #17, #18 |
| **Belonging & Cultural Fitness** | #11 (CRITICAL), #8 |
| **Relational Quality** | #13, #14, #15, #16 |
| **Actionable Support** | #1, #17, #18, #26 |
| **Longitudinal Consistency** | #3, #31 |
| **Memory Hygiene** | #1, #6, #20, #24, #25 |

### Tier Structure Validation

- **Tier 1-3 temporal progression:** Paper #3 (3-stage caregiver journey)
- **Multi-session evaluation:** Paper #31 (longitudinal data)
- **Role-based personas:** Paper #8 (patient/caregiver/practitioner taxonomy)

### Methodology Insights

- **Tri-judge approach:** Papers #4, #9 (multi-agent evaluation)
- **Empathy measurement:** Papers #13, #14, #15
- **Autofail conditions:** Papers #7, #21 (safety risks from fine-tuning)
- **Expert validation:** Papers #4, #17, #18

### Warnings & Cautions

⚠️ **Paper #21 (Reddit-based fine-tuning):** Fine-tuning on unprocessed social media increases toxicity/bias
⚠️ **Paper #11 (Demographic bias):** LLMs encode caregiving stereotypes based on demographics
⚠️ **Paper #20 (Social media discourse):** Public usage doesn't indicate therapeutic framework alignment

---

## Download Priority

**Immediate download recommended:**

1. **#1** (2506.15047v1) - Caregiver needs mapping
2. **#3** (2506.14196v1) - Temporal caregiver journey
3. **#11** (2503.05765v1) - Demographic bias in caregiving
4. **#8** (2510.16829v1) - Role-based responses
5. **#21** (2505.18464v1) - Fine-tuning warnings

**Secondary priority:**

6. **#2** (2503.13509v2) - MentalChat16K dataset
7. **#4** (2408.04650v2) - Safety evaluation framework
8. **#14** (2506.16473v1) - Therapist alignment analysis
9. **#15** (2403.05572v1) - GPT-4 empathy evaluation
10. **#17** (2506.11376v1) - PST delivery for caregivers

---

## Related Resources

- **MentalChat16K Dataset:** https://huggingface.co/datasets/ShenLab/MentalChat16K
- **MentalChat16K Code:** https://github.com/ChiaPatricia/MentalChat16K

---

## Search Queries Used

1. `"caregiving" AND ("artificial intelligence" OR "AI" OR "machine learning")` - Categories: cs.AI, cs.HC, cs.CY
2. `("conversational AI" OR "chatbot" OR "LLM") AND ("mental health" OR "emotional support" OR "crisis")` - Categories: cs.AI, cs.HC, cs.CL
3. `("longitudinal" OR "long-term") AND ("AI safety" OR "alignment" OR "evaluation")` - Categories: cs.AI, cs.CY, cs.LG
4. `("benchmark" OR "evaluation") AND ("empathy" OR "trauma-informed" OR "cultural competence")` - Categories: cs.AI, cs.CL, cs.HC

Total papers retrieved: 65 unique papers
