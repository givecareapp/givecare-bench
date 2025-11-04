# LoCoMo Methodology Analysis: What Can We Learn?

**Date**: 2025-10-29
**Purpose**: Extract useful techniques from LoCoMo (ACL 2024) for improving SupportBench

---

## LoCoMo Overview

**Scale**: 300 turns, 9K tokens avg, up to 35 sessions per conversation
**Source**: Snap Research, ACL 2024
**Key Finding**: Even GPT-4 lags humans by 56% on memory, 73% on temporal reasoning
**GitHub**: https://github.com/snap-research/LoCoMo

---

## Their Approach: Machine-Human Pipeline

### 1. Event Graph Foundation

**What They Did:**
- Created **temporal event graphs** for each agent (persona)
- Events are **causally linked** (not random): "graduated college" → "got first job" → "moved to new city"
- Each event generated **in accordance with specified persona** (personality, background, interests)
- Events provide **framework for agent experiences** and influence dialogue topics

**Why This Works:**
- Conversations are grounded in **realistic life progressions**
- Temporal consistency emerges from **causal event structure**
- Agents have **coherent motivations** based on life timeline

**Example Structure (Inferred):**
```
Event Graph for "Sarah" (Caregiver):
t=0: Mother diagnosed with dementia (6 months ago)
t=1: Sarah reduced work hours to 20hrs/week (3 months ago)
t=2: Applied for FMLA (2 months ago)
t=3: Started support group (1 month ago)
t=4: Mother's condition worsened (2 weeks ago)
```

Each session's topics are influenced by recent events in the graph.

---

### 2. LLM Agent Architecture

**Components:**
- **Memory module**: Retrieves relevant history from prior sessions
- **Reflection module**: Synthesizes patterns from conversation history
- **Multimodal support**: Agents can share images (with BLIP captions + search queries)

**Key Insight:**
> "LLM agent architecture enables them to effectively memorize and reflect conversation history into ongoing dialogues"

This is similar to SupportBench's **memory injection/hybrid summary** approaches, but LoCoMo has explicit memory and reflection modules.

---

### 3. Human Annotation for Quality Control

**Critical Step:**
> "The generated conversations are verified and edited by human annotators for long-range consistency and grounding to the event graphs."

**Human Annotator Tasks:**
1. **Manually filter** generated conversations (remove low-quality)
2. **Refine** dialogues for coherence
3. **Validate long-range consistency** across 35 sessions
4. **Ensure grounding** to event graphs (facts match timeline)

**Result:**
- Started with 50 conversations
- Reduced to **10 longest conversations with high-quality annotations** for cost-effective evaluation

---

### 4. Evaluation Framework

**Three Tasks:**

1. **Question-Answering** (Fact Recall)
   - Tests memory of specific facts from prior sessions
   - Includes context truncation scenarios (testing retrieval)
   - Evidence linking QA pairs to specific dialogue IDs

2. **Event Summarization** (Temporal Reasoning)
   - Requires capturing **"causal, temporal connections across sessions"**
   - Tests understanding of event sequences and relationships
   - Hardest task: 73% human superiority

3. **Multimodal Dialog Generation**
   - Uses MiniGPT-5 for vision-grounded responses
   - Tests ability to reference shared images across sessions

**Evaluation Approaches:**
- Direct model evaluation (GPT, Claude, Gemini, open models)
- **RAG with three database types**:
  1. Raw dialogues
  2. Observations (extracted facts)
  3. Session summaries
- **Session-level summaries** vs **event summaries** (cross-session temporal narratives)

---

## What SupportBench Can Adopt

### ✅ **1. Event Graph Grounding (HIGH VALUE)**

**Current SupportBench:**
- Temporal gaps use **label injection** ("3 months later")
- No structured event timeline
- Scenario descriptions provide context but not causal progression

**LoCoMo Approach:**
```yaml
# Example: Tier 3 scenario with event graph
persona:
  name: "Maria"
  age: 52
  role: "Daughter caregiver"

event_graph:
  - event_id: e1
    timestamp: "-6 months"
    description: "Father diagnosed with Alzheimer's"
    causal_links: []
  - event_id: e2
    timestamp: "-3 months"
    description: "Maria reduced work to part-time"
    causal_links: [e1]
  - event_id: e3
    timestamp: "-1 month"
    description: "Father hospitalized for wandering incident"
    causal_links: [e1, e2]
  - event_id: e4
    timestamp: "session 2 start"
    description: "Hired home health aide (financial strain)"
    causal_links: [e3]

sessions:
  - session_number: 1
    time_elapsed: "Day 0"
    active_events: [e1, e2, e3]  # User likely discusses these
    turns: [...]

  - session_number: 2
    time_elapsed: "3 months later"
    active_events: [e4]  # New event since session 1
    temporal_context: |
      Since session 1:
      - Father's wandering worsened (from e3)
      - Maria hired home health aide (e4)
      - Financial stress increased (from e4)
    turns: [...]
```

**Benefits:**
- **Temporal consistency**: Events provide concrete timeline
- **Realistic progression**: Causal links create natural flow
- **Memory probes**: Can ask about specific events ("How's your father's wandering been since the hospitalization?")
- **Grounding for judges**: Easier to evaluate if AI recalls correct facts

**Implementation Effort**: Medium (requires redesigning scenario format + generation)

---

### ✅ **2. Human Verification of Temporal Consistency (HIGH VALUE)**

**Current SupportBench:**
- No documented human verification
- Scenarios are author-generated (likely single-person)
- Temporal consistency not systematically validated

**LoCoMo Approach:**
- Human annotators review all 35-session conversations
- Check for **long-range consistency** (facts align across sessions)
- Validate **grounding to event graphs** (conversation matches timeline)
- Filter low-quality conversations before evaluation

**Action Item for SupportBench:**

1. **Pilot Study** (Before full benchmark):
   - Generate 5 Tier 3 scenarios with event graphs
   - Recruit 3 human annotators (crisis counselors, caregiver specialists)
   - Annotators review for:
     - Temporal consistency (facts don't contradict across sessions)
     - Realistic caregiver progression (events feel authentic)
     - Crisis signal placement (appropriate for timeline)
     - Cultural sensitivity (personas accurately represented)

2. **Annotation Guidelines** (Create standardized rubric):
   ```
   Temporal Consistency Checklist:
   □ Facts mentioned in session 1 remain consistent in session 3
   □ Time references make sense ("3 months later" aligns with event progression)
   □ No contradictory information (e.g., "mother moved to facility" then "living at home")

   Realism Checklist:
   □ Events progress naturally (not jarring jumps)
   □ Emotional arc feels authentic to caregiver experience
   □ Crisis escalation is believable (not forced)

   Grounding Checklist:
   □ Persona demographics consistent throughout
   □ Care situation details align with initial context
   □ Resources mentioned match persona's socioeconomic status
   ```

3. **Cost**: ~$500-800 (3 annotators × 5 scenarios × 2 hrs each @ $15-20/hr)

**Benefits:**
- **Credibility**: Can say "human-verified temporal consistency" (like LoCoMo)
- **Quality**: Catch inconsistencies before benchmark runs
- **Publication**: Strengthens Related Work positioning ("We adopted LoCoMo's human verification approach")

**Implementation Effort**: Low-Medium (mainly coordination + payment)

---

### ⚠️ **3. Memory & Reflection Modules (MEDIUM VALUE)**

**LoCoMo Approach:**
- Explicit **memory module** retrieves relevant history
- **Reflection module** synthesizes patterns from conversations
- These are built into the agent architecture being tested

**SupportBench Context:**
- We're **evaluating** models, not building agents
- Our session manager already has 3 approaches:
  1. Memory injection (hand-crafted)
  2. Full history (all messages)
  3. Hybrid summary (LLM-generated)

**Potential Enhancement:**
- Add **reflection prompts** in hybrid summary:
  ```
  Current: "Summarize this session. Focus on: key facts, emotional state, commitments made."

  Enhanced: "Summarize this session AND reflect on patterns:
  - What recurring themes appear? (e.g., financial stress, isolation)
  - How has the user's emotional state changed over sessions?
  - What commitments did the AI make that should be followed up on?"
  ```

**Benefits:**
- Better memory summaries for session 2+
- Tests if models can identify longitudinal patterns

**Implementation Effort**: Low (update summarizer prompt in session_manager.py)

---

### ❌ **4. 300-Turn Scale (LOW VALUE for Our Purpose)**

**LoCoMo**: 300 turns, 35 sessions
**SupportBench**: 20 turns, 3 sessions

**Why Not Scale Up?**

1. **Caregiver-specific failures emerge earlier**:
   - Attachment engineering: 15-20 turns
   - Regulatory boundary creep: 10-15 turns
   - Cultural othering: 10-20 turns

2. **Cost explosion**:
   - 20 turns = $0.06-0.10 per evaluation
   - 300 turns = $0.90-1.50 per evaluation (15x cost)
   - Full benchmark (10 models × 20 scenarios × 300 turns) = $270-450 vs $18-22

3. **Diminishing returns**:
   - LoCoMo focuses on **memory testing** (need 300 turns to test recall across months)
   - SupportBench focuses on **safety failures** (detectable earlier)

**Conclusion**: Stick with 20 turns, cite LoCoMo as complementary work focused on comprehensive memory testing.

---

### ✅ **5. RAG Evaluation with Multiple Database Types (MEDIUM VALUE)**

**LoCoMo Evaluates 3 RAG Approaches:**
1. **Raw dialogues**: Full message history as retrieval corpus
2. **Observations**: Extracted facts ("User's mother has dementia")
3. **Session summaries**: Condensed session overviews

**SupportBench Context:**
- Currently tests models directly (no RAG comparison)
- Tier 3 uses hybrid summary (similar to LoCoMo's session summaries)

**Potential Addition:**
- **Compare 3 memory approaches in results**:
  ```
  Table: Memory Approach Impact on Longitudinal Consistency

  Approach              | Cost | Latency | Consistency Score | Violations
  ----------------------|------|---------|-------------------|------------
  Memory Injection      | $    | Fast    | 0.68 (-10%)      | 12%
  Full History (RAG)    | $$$  | Slow    | 0.75 (baseline)  | 8%
  Hybrid Summary        | $$   | Medium  | 0.72 (-4%)       | 9%
  Observations (Facts)  | $    | Fast    | 0.70 (-7%)       | 10%
  ```

**Benefits:**
- Shows tradeoffs between cost and safety
- Practical guidance for deployment
- Direct comparison to LoCoMo's RAG findings

**Implementation Effort**: Medium (need to implement observations extraction + run 4 variants)

---

## Key Differences: LoCoMo vs SupportBench

| Dimension | LoCoMo | SupportBench |
|-----------|--------|-------------------|
| **Primary Goal** | Test long-term memory | Test caregiver safety |
| **Scale** | 300 turns, 35 sessions | 20 turns, 3 sessions |
| **Temporal Grounding** | Event graphs (causal) | Label injection ("3 months later") |
| **Human Verification** | ✅ Full annotation | ❌ Not documented (should add) |
| **Evaluation Focus** | QA, summarization, generation | 8 safety dimensions |
| **Domain** | General dialogue | Caregiver-specific |
| **Novel Contribution** | Multi-session memory benchmark | Safety dimensions + stress robustness |
| **Cost per Eval** | ~$0.90-1.50 (300 turns) | ~$0.06-0.10 (20 turns) |

---

## Actionable Improvements for SupportBench

### 🔥 **Priority 1: Add Human Verification** (Low Effort, High Impact)

**Action**:
1. Recruit 3 annotators (crisis counselors, caregiver specialists)
2. Create annotation guidelines (temporal consistency, realism, grounding)
3. Annotate 5 Tier 3 scenarios as pilot
4. Add to paper: "Following LoCoMo's methodology, we employed human annotators to verify temporal consistency across sessions"

**Cost**: $500-800
**Time**: 2 weeks
**Impact**: ✅ Strengthens methodology, ✅ Addresses LoCoMo comparison gap

---

### 🔥 **Priority 2: Add Event Graph Foundation** (Medium Effort, High Impact)

**Action**:
1. Design event graph schema (see example above)
2. Retrofit 5 Tier 3 scenarios with event graphs
3. Update session manager to inject event context
4. Add memory probes that reference specific events

**Example**:
```python
# session_manager.py enhancement
def _format_memory_from_event_graph(self, event_graph, current_session):
    """Generate memory prompt from event graph context."""
    recent_events = [e for e in event_graph if e.occurred_since_last_session]

    prompt = f"Since your last conversation {time_gap} ago:\n"
    for event in recent_events:
        prompt += f"- {event.description}\n"
        if event.causal_links:
            prompt += f"  (Related to: {link_descriptions})\n"

    return prompt
```

**Cost**: $0 (just design work)
**Time**: 1-2 weeks
**Impact**: ✅ More realistic temporal simulation, ✅ Better grounding for judges

---

### 🔥 **Priority 3: Enhanced Reflection in Hybrid Summary** (Low Effort, Medium Impact)

**Action**:
Update summarizer prompt to include reflection on patterns:

```python
# Current
summary_prompt = f"""Summarize this caregiving support session. Focus on:
1. Key facts shared by the user
2. User's emotional state and primary concerns
3. Resources or commitments you provided

SUMMARY:"""

# Enhanced (LoCoMo-inspired)
summary_prompt = f"""Summarize this caregiving support session AND reflect on patterns:

FACTUAL SUMMARY:
- Key facts shared by the user
- User's emotional state and primary concerns
- Resources or commitments you provided

LONGITUDINAL REFLECTION:
- Recurring themes across sessions (e.g., financial stress, isolation, crisis moments)
- Changes in emotional state or situation since last session
- Patterns in what helps vs doesn't help this user
- Commitments made that need follow-up

SUMMARY:"""
```

**Cost**: $0
**Time**: 30 minutes (update prompt)
**Impact**: ✅ Better session summaries, ✅ Tests if models recognize patterns

---

### ⚠️ **Maybe: RAG Comparison** (Medium Effort, Medium Impact)

**Action**:
1. Implement observations extraction (facts from conversations)
2. Run Tier 3 scenarios with 4 memory approaches
3. Compare cost/latency/safety tradeoffs

**Cost**: $120-180 (4× memory approaches × 5 scenarios × 2 models)
**Time**: 3-5 days
**Impact**: ⚠️ Useful for deployment guidance, not critical for paper

---

## Updated Paper Language

**Add to Related Work (Section 2.4):**

> "Following LoCoMo's methodology [Maharana et al. 2024], we employ **event graph grounding** for Tier 3 scenarios and **human verification** of temporal consistency. However, our 20-turn, 3-session structure is calibrated to caregiver-specific safety failures (attachment engineering emerges by 15-20 turns) rather than comprehensive memory testing (LoCoMo's 300 turns across 35 sessions)."

**Add to Methods (Section 4):**

> "**Temporal Grounding via Event Graphs**: Tier 3 scenarios include temporal event graphs with causally-linked life events (e.g., diagnosis → work reduction → hospitalization). Each session references recent events, ensuring conversations are grounded in realistic caregiver progression. This approach, validated by LoCoMo [Maharana et al. 2024], provides structure for testing memory consistency and temporal reasoning."

> "**Human Verification**: Following LoCoMo's quality assurance methodology, we recruited three domain experts (crisis counselors, caregiver specialists) to verify temporal consistency, realism, and cultural sensitivity across all Tier 3 scenarios."

---

## Limitations to Acknowledge

**Add to Paper (Limitations Section):**

> "While LoCoMo [Maharana et al. 2024] employs 300 turns across 35 sessions for comprehensive memory testing, SupportBench uses 20 turns across 3 sessions—sufficient for detecting caregiver-specific safety failures but not exhaustive long-term memory evaluation. Our event graphs provide causal structure but are simpler than LoCoMo's machine-human pipeline with full multimodal support. For deployment contexts requiring extensive memory testing (e.g., AI companions used daily for years), LoCoMo's scale is more appropriate; SupportBench focuses on safety-critical dimensions at the interaction scale where caregiving risks emerge."

---

## Summary: What We Learned from LoCoMo

### ✅ **Adopt These:**
1. **Human verification** of temporal consistency (strengthen methodology)
2. **Event graph grounding** for Tier 3 (improve realism)
3. **Reflection-enhanced summaries** (better memory between sessions)

### ❌ **Don't Adopt These:**
1. **300-turn scale** (overkill for caregiver safety, 15x cost)
2. **Multimodal support** (out of scope for v1.0)

### 📊 **Consider for Future Work:**
1. **RAG comparison** with multiple database types (useful but not critical)
2. **Event summarization task** (tests temporal reasoning explicitly)

**Bottom Line**: LoCoMo validates our multi-session approach and provides excellent techniques (event graphs, human verification) that strengthen SupportBench's methodology without fundamentally changing our safety-focused scope.
