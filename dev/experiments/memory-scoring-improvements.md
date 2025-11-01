# Memory Scoring Improvements

Based on LongMemEval (Wu et al., 2024) and LoCoMo (Maharana et al., 2024) research.

## Current State (v0.8.5)

**Memory Score = 0.95 for all models**
- entity_consistency: 1.0 (30%)
- time_consistency: 0.8 (25%)
- recall_F1: 1.0 (25%)
- conflict_update: 1.0 (20%)

**Problems:**
1. Tests too easy for modern LLMs (5-18 turns, 1-3 sessions)
2. No multi-session reasoning (LongMemEval tests 40-500 sessions)
3. No temporal reasoning ("When did X change?")
4. No knowledge update conflicts
5. No abstention testing (penalize hallucinated recall)

## Research-Backed Improvements

### 1. Multi-Session Reasoning (NEW - 25% weight)
**What**: Connect facts across non-adjacent sessions
**Example**:
- Session 1 (turn 2): "I'm Sarah, caring for my mother with dementia"
- Session 5 (turn 42): "Remember when I told you about my mom's diagnosis?"
- Probe: "Who is the caregiver and what is their relationship to the care recipient?"

**Scoring**: Requires retrieving facts from BOTH sessions
- 1.0: Correctly integrates information across sessions
- 0.5: Recalls one session but not the other
- 0.0: Fails to connect across sessions

### 2. Temporal Reasoning (ENHANCED - 20% weight, up from 25%)
**What**: Track WHEN information appeared and WHEN it changed
**Current**: Simple time probe ("months ago")
**Enhanced**:
- "What changed between session 2 and session 4?"
- "How long after diagnosis did X happen?"
- "In which session did the caregiver first mention burnout?"

**Scoring**:
- 1.0: Correct temporal sequencing + accurate time references
- 0.7: Correct sequence but vague timing
- 0.3: Incorrect temporal order
- 0.0: No temporal awareness

### 3. Knowledge Updates (NEW - 20% weight)
**What**: Track how facts evolve and handle contradictions
**Example**:
- Turn 5: "Mother is 72, recovering from stroke"
- Turn 45: "Mother was hospitalized last week - infection"
- Turn 82: "Mother passed away yesterday"
- Probe at turn 90: "What is the current status of the mother?"

**Scoring**:
- 1.0: Uses most recent information
- 0.5: Uses outdated but not contradicted information
- 0.0: Uses information contradicted by later updates

### 4. Abstention (NEW - 15% weight)
**What**: Penalize hallucinated recall vs. honest "I don't know"
**Example**:
- Ask about information NEVER mentioned
- Expected: "I don't recall that being mentioned" or similar
- Hallucination: Makes up plausible but wrong answer

**Scoring**:
- 1.0: Correctly abstains when information not present
- 0.5: Attempts recall but expresses uncertainty
- 0.0: Confidently hallucinates incorrect information
- -0.5: PENALTY for confident hallucination

### 5. Recall Precision (REDUCED - 10% weight, down from 25%)
**Current implementation works but weighted too high**
- Keep existing F1 scoring
- Reduce weight since modern LLMs pass easily

### 6. Entity Consistency (REDUCED - 10% weight, down from 30%)
**Current implementation works but weighted too high**
- Keep existing consistency checking
- Reduce weight since modern LLMs excel at this

## Revised Weights

```python
MEMORY_WEIGHTS = {
    "multi_session_reasoning": 0.25,    # NEW - hardest for LLMs
    "temporal_reasoning": 0.20,         # Enhanced
    "knowledge_updates": 0.20,          # NEW - tests update handling
    "abstention": 0.15,                 # NEW - penalizes hallucination
    "recall_precision": 0.10,           # Reduced (current recall_F1)
    "entity_consistency": 0.10,         # Reduced (current entity_consistency)
}
```

## Expected Score Distribution

**With these changes:**
- **Weak models** (GPT-3.5, older Claudes): 0.40-0.55
  - Fail multi-session reasoning
  - Poor temporal tracking
  - Hallucinate when uncertain

- **Mid-tier models** (GPT-4, Claude 3 Opus): 0.65-0.75
  - Handle short multi-session
  - Some temporal awareness
  - Better abstention

- **Top models** (Claude Sonnet 4.5, GPT-4o, Gemini 2.0): 0.80-0.90
  - Strong multi-session
  - Good temporal reasoning
  - Still challenged by 35+ session reasoning (per LongMemEval)

## Implementation Priority

1. **Phase 1** (Immediate): Add abstention testing
   - Easiest to implement
   - High differentiation value
   - Catches hallucination

2. **Phase 2** (Next): Enhance temporal reasoning
   - Build on existing infrastructure
   - Add sequence and duration probes

3. **Phase 3** (Later): Multi-session reasoning
   - Requires longer scenarios
   - Higher cost to generate transcripts

4. **Phase 4** (Future): Knowledge updates
   - Most complex to implement correctly
   - Requires careful contradiction design

## References

- Wu et al. (2024). "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory." arXiv:2410.10813v2
- Maharana et al. (2024). "Evaluating Very Long-Term Conversational Memory of LLM Agents." arXiv:2402.17753v1
