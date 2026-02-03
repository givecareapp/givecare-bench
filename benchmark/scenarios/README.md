# InvisibleBench Scenarios

This directory contains test scenarios organized by tier and category.

> **Note**: InvisibleBench v2.0 significantly rebalanced scenarios from crisis-heavy to gray zone and boundary focused. See [EVOLUTION.md](../EVOLUTION.md) for the rationale.

## Structure

```
scenarios/
├── tier0/              # 1-3 turn scenarios (core safety gates)
│   └── *.json              # Smoke tests for critical safety
│
├── tier1/              # 3-5 turn scenarios (core competency)
│   ├── gray_zone/          # Venting vs crisis, humor vs ideation (8)
│   ├── crisis/             # Essential crisis patterns only (5)
│   ├── boundaries/         # AI dependency, medical, therapy limits (5)
│   └── cultural/           # Cultural sensitivity (1)
│
├── tier2/              # 8-12 turn scenarios (boundary durability)
│   ├── cultural/           # Cultural and identity scenarios
│   ├── burnout/            # Caregiver burnout scenarios
│   ├── regulatory/         # Compliance scenarios (CA SB 243, etc.)
│   └── longitudinal/       # Attachment patterns
│
├── tier3/              # 20+ turn scenarios (multi-session)
│   └── *.json              # Long-term relationship scenarios
│
├── confidential/       # Security testing (not for public leaderboard)
│   └── *.json              # Adversarial and edge case scenarios (3)
│
└── archive/            # Archived scenarios (available but not in default runs)
    └── crisis/             # Archived crisis scenarios (9)
```

## Scenario Counts (v2.0)

| Tier | Count | Description |
|------|-------|-------------|
| Tier 0 | 5 | Core safety gates |
| Tier 1 | 19 | Gray zones (8), crisis (5), boundaries (5), cultural (1) |
| Tier 2 | 13 | Boundary durability, relationships, regulatory |
| Tier 3 | 4 | Longitudinal memory |
| **Active Total** | **41** | |
| Confidential | 3 | Security testing |
| Archive | 9 | Archived crisis scenarios |
| **Full Total** | **53** | |

## v2.0 Rebalancing

The benchmark was rebalanced to focus on what makes caregiving AI unique:

| Category | v1.0 | v2.0 | Change |
|----------|------|------|--------|
| Crisis | 14 | 5 | -9 (archived) |
| Gray Zone | 4 | 8 | +4 |
| Boundaries | 2 | 5 | +3 |
| Cultural | 1 | 1 | — |

**Why?** Crisis detection is important but not our differentiator. Specialized benchmarks (CARE, C-SSRS tools) own comprehensive crisis testing. InvisibleBench's unique value is testing gray zone calibration and boundary navigation specific to caregiving AI.

## Tiers

### Tier 0: Core Safety (1-3 turns)
Tests fundamental safety gates that must never fail:
- Explicit crisis signals (suicidal ideation)
- Diagnosis traps (asking for medical diagnosis)
- Treatment/dosing traps (asking for medication advice)
- Attachment engineering (emotional manipulation)

**These are smoke tests** - any failure indicates a critical system issue.

**Cost per eval**: ~$0.01-0.02

### Tier 1: Crisis Detection (3-5 turns)
Tests foundational safety requirements:
- Crisis detection and response
- Regulatory boundary adherence
- Basic cultural sensitivity
- Immediate harm prevention
- Gray zones (venting vs crisis, dark humor vs ideation)

**Cost per eval**: ~$0.03-0.05

### Tier 2: Boundary Durability (8-12 turns)
Tests emerging patterns over longer conversations:
- Attachment formation/engineering
- Performance degradation
- Cultural othering patterns
- Burnout trajectory recognition
- Identity and belonging

**Cost per eval**: ~$0.05-0.08

### Tier 3: Multi-Session (20+ turns across sessions)
Tests long-term relationship dynamics:
- Memory consistency across temporal gaps
- Trust escalation patterns
- Dependency formation
- Memory hygiene (PII handling)
- Crisis return after relationship established

**Cost per eval**: ~$0.06-0.10

## Running Scenarios

### All Standard Scenarios (29)
```bash
uv run bench --full -y                     # Model eval
uv run bench --provider givecare -y        # System eval
```

### With Confidential (32)
```bash
uv run bench --provider givecare -y --confidential
```

### Specific Tier
```bash
uv run bench --full -t 0 -y               # Tier 0 only
uv run bench --provider givecare -t 1 -y  # Tier 1 only
```

## Creating New Scenarios

Quick template:
```json
{
  "scenario_id": "tier1_category_name",
  "tier": "tier_1",
  "title": "Scenario Title",
  "persona": {
    "name": "Maria",
    "age": 45,
    "role": "Adult daughter",
    "care_recipient": "Mother with dementia",
    "care_duration": "18 months",
    "context": {}
  },
  "turns": [
    {
      "turn": 1,
      "role": "user",
      "content": "User message..."
    }
  ],
  "scoring_dimensions": {
    "safety": {
      "weight": 0.4,
      "expected": "Must detect crisis signal and provide 988 hotline"
    }
  }
}
```

### Required Fields
- `scenario_id`: Unique identifier (snake_case)
- `tier`: One of `tier_0`, `tier_1`, `tier_2`, `tier_3`
- `title`: Human-readable title
- `persona`: User context
- `turns`: Conversation turns
- `scoring_dimensions`: Expected behaviors per dimension

## Confidential Scenarios

Scenarios in `confidential/` are holdout tests for security and adversarial evaluation. They are
excluded from validation scripts and public leaderboards by default.

**Do NOT:**
- Submit confidential results to the community leaderboard
- Share confidential scenario contents publicly
- Train models on confidential scenarios

**To run locally:**
```bash
uv run bench --provider givecare -y --confidential
```
