# LongitudinalBench Scenarios

This directory contains test scenarios organized by tier and category.

## Structure

```
scenarios/
├── tier1/          # 3-5 turn scenarios (basic safety)
│   ├── crisis/         # Crisis detection scenarios
│   ├── boundaries/     # Boundary violation scenarios
│   └── cultural/       # Cultural sensitivity scenarios
│
├── tier2/          # 8-12 turn scenarios (longitudinal patterns)
│   ├── longitudinal/   # Attachment and relationship patterns
│   ├── cultural/       # Cultural and identity scenarios
│   └── burnout/        # Caregiver burnout scenarios
│
├── tier3/          # 20+ turn scenarios (multi-session)
│   └── *.json          # Long-term relationship scenarios
│
└── confidential/   # Security testing scenarios (not for public leaderboard)
    └── *.json          # Adversarial and edge case scenarios
```

## Tiers

### Tier 1: Basic Safety (3-5 turns)
Tests foundational safety requirements:
- Crisis detection and response
- Regulatory boundary adherence
- Basic cultural sensitivity
- Immediate harm prevention

**Cost per eval**: ~$0.03-0.05

### Tier 2: Longitudinal Patterns (8-12 turns)
Tests emerging patterns over longer conversations:
- Attachment formation/engineering
- Performance degradation
- Cultural othering patterns
- Burnout trajectory recognition

**Cost per eval**: ~$0.05-0.08

### Tier 3: Multi-Session (20+ turns across sessions)
Tests long-term relationship dynamics:
- Memory consistency across temporal gaps
- Trust escalation patterns
- Dependency formation
- Memory hygiene (PII handling)

**Cost per eval**: ~$0.06-0.10 (with hybrid summary approach)

## Creating New Scenarios

See `docs/scenarios.md` for detailed scenario design guidelines.

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
  "turns": [],
  "scoring_dimensions": {}
}
```

## Confidential Scenarios

Scenarios in `confidential/` are used for security testing and adversarial evaluation. They should NOT be included in public leaderboards or shared externally.
