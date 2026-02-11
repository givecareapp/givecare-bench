# InvisibleBench Scenarios

This directory contains test scenarios organized by capability category (MECE).

## Structure

```
scenarios/
├── safety/             # 12 scenarios — crisis, boundaries, gray zones, false refusal
│   ├── crisis/             # Crisis detection patterns (4)
│   ├── gray_zone/          # Venting vs crisis, humor vs ideation (2)
│   ├── boundaries/         # Medical, therapy, attachment, abuse (4)
│   └── false_refusal/      # Inappropriate refusal of caregiving topics (2)
│
├── empathy/            # 10 scenarios — emotional attunement, belonging, relational
│   ├── burnout/            # Caregiver burnout and compassion fatigue (3)
│   ├── belonging/          # Identity and belonging (1)
│   ├── grief/              # Grief, loss, end-of-life (3)
│   └── relational/         # Pushback, impossible constraints, ambiguity (3)
│
├── context/            # 9 scenarios — cultural awareness, regulatory compliance
│   ├── cultural/           # Cultural sensitivity and identity (5)
│   └── regulatory/         # Compliance scenarios (4)
│
├── continuity/         # 4 scenarios — longitudinal trust, memory, consistency
│   └── *.json              # Multi-session relationship scenarios
│
├── confidential/       # 3 holdout scenarios (not in standard runs)
│   └── *.json              # Adversarial and edge case scenarios
│
└── archive/            # Archived scenarios (available but not in default runs)
    ├── tier0/              # Archived smoke tests (5)
    ├── tier1/              # Archived tier 1 scenarios (7)
    ├── tier2/              # Archived tier 2 scenarios (3)
    ├── tier3/              # Archived tier 3 scenarios (1)
    └── crisis/             # Archived crisis scenarios (9)
```

## Scenario Counts

| Category | Count | Subcategories |
|----------|-------|---------------|
| Safety | 12 | Crisis (4), gray zone (2), boundaries (4), false refusal (2) |
| Empathy | 10 | Burnout (3), belonging (1), grief (3), relational (3) |
| Context | 9 | Cultural (5), regulatory (4) |
| Continuity | 4 | Longitudinal scenarios |
| **Active Total** | **35** | |
| Confidential | 3 | Holdout set |
| Archive | 25 | From v1 |
| **Full Total** | **63** | |

## Categories

### Safety (12 scenarios)
Tests where wrong answer = physical/psychological harm:
- Crisis detection and response
- Gray zone discrimination (venting vs crisis, humor vs ideation)
- Boundary violations (medical, therapy, attachment, abuse)
- False refusal (inappropriately refusing legitimate caregiving questions)

### Empathy (10 scenarios)
Tests emotional attunement, belonging, and relational skills:
- Burnout recognition and compassion fatigue
- Identity and belonging
- Grief, loss, and end-of-life support
- Relational dynamics (pushback, impossible constraints, ambiguity)

### Context (9 scenarios)
Tests contextual awareness and cultural sensitivity:
- Cultural identity, filial piety, familismo, disability (5)
- Regulatory compliance: misrepresentation correction, therapeutic function boundaries, data privacy, minor disclosure (4)

### Continuity (4 scenarios)
Tests long-term relationship dynamics:
- Memory consistency across temporal gaps
- Trust escalation patterns
- Crisis return after relationship established
- Cultural ritual integration over time

## Conditional Branching

4 scenarios include **conditional branches** where the user's next message adapts based on the model's response:

| Scenario | Category | Branch At | Tests |
|----------|----------|-----------|-------|
| `medical_boundary_violation` | safety | T3 | Model provides dosing → user escalates |
| `venting_vs_crisis` | safety | T2 | Model over-escalates → user pushes back |
| `attachment_formation` | continuity | T7 | Model over-bonds → user deepens dependency |
| `longitudinal_trust` | continuity | T9 | Model forgets → user calls out memory failure |

Branching is automatic during transcript generation. Branch conditions use keyword/regex matching (deterministic, no LLM cost).

## Running Scenarios

### All Standard Scenarios (35)
```bash
uv run bench --full -y                     # Model eval
uv run bench --provider givecare -y        # System eval
```

### With Confidential (38)
```bash
uv run bench --provider givecare -y --confidential
```

### Specific Category
```bash
uv run bench --full -c safety -y               # Safety only
uv run bench --provider givecare -c empathy -y  # Empathy only
```

## Creating New Scenarios

Quick template:
```json
{
  "scenario_id": "safety_crisis_example_001",
  "tier": "safety",
  "category": "safety",
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
      "turn_number": 1,
      "user_message": "User message...",
      "expected_behaviors": ["..."],
      "autofail_triggers": ["..."]
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
- `tier`/`category`: One of `safety`, `empathy`, `context`, `continuity`
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
