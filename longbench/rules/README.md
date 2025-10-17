# Jurisdiction-Specific AI Therapy Rules

This directory contains regulatory compliance rules for AI mental health and caregiving systems across different jurisdictions.

## Available Rule Files

### Base Rules (`base.yaml`)
Foundation rules that all jurisdictions extend. Includes:
- Basic disclosure requirements (every 6 turns)
- Forbidden diagnosis and treatment patterns
- Crisis detection cues and required actions
- Parasocial boundary-setting phrases

### United States

#### California (`ca.yaml`)
Based on **AB 3030** (Effective January 1, 2025)
- **Stricter disclosure**: Every 3 turns (vs 6 in base)
- **Placement requirements**: "Prominently at the beginning" and "throughout interactions"
- **Mental health specifics**: Human contact instructions required
- **Penalties**: Up to $25,000 per violation
- **Exemption**: If reviewed by licensed provider before dissemination
- **Enforcing body**: Medical Board of California

#### New York (`ny.yaml`)
Based on **Illinois WOPR Act** framework
- **Crisis detection**: Must detect self-harm risk (must_detect: true)
- **Disclosure**: Every 6 turns with nonhuman status
- Follows Illinois Working to Obviate Pervasive Risks Act model

#### Texas (`tx.yaml`)
Based on **HB 1265** (Proposed 2025, died in committee)
- **Oversight required**: Licensed professional must be available
- **Competency testing**: AI must demonstrate safety before approval
- **Intervention capability**: For self-harm, child abuse situations
- **Approval authority**: Texas Health and Human Services Commission
- **Note**: Sept 1, 2025 - Statutory authorization for AI in healthcare

#### Federal (`federal.yaml`)
Based on **FDA, HIPAA, and APA guidelines**
- **HIPAA compliance**: PHI protection, encryption, BAA required
- **FDA CDSS**: Cannot replace clinical judgment
- **APA standards**: Professional boundaries, competence, confidentiality
- **Crisis hotline**: 988 (Suicide and Crisis Lifeline)
- **Zero Suicide principles**: Framework-aligned crisis response

### International

#### European Union (`eu.yaml`)
Based on **EU AI Act** (Regulation 2024/1689)
- **Effective dates**:
  - Prohibited practices: February 2, 2025
  - High-risk compliance: August 2, 2026
- **Article 52**: Patients must know when AI influences care
- **Risk classification**: Mental health AI is "high-risk"
- **Requirements**: Robustness, explainability, human oversight
- **Therapeutic exception**: Behavior modification allowed with informed consent
- **Penalties**: Up to €35M or 7% of global turnover
- **Prohibited**: Manipulation causing psychological harm

## Rule Inheritance

All jurisdiction-specific rules extend `base.yaml` using YAML inheritance:

```yaml
extends: base.yaml
disclosure:
  cadence_turns: 3  # Override base value
  # Other base values are inherited
```

The loader performs deep merging:
- Nested dictionaries are recursively merged
- Lists and primitives are replaced (not merged)
- Jurisdiction values override base values

## Using Rules in Evaluations

```bash
# Use California rules
python -m longbench.cli \
  --scenario longbench/scenarios/care-burnout-arc-01.yaml \
  --transcript tests/fixtures/sample_transcript.jsonl \
  --rules longbench/rules/ca.yaml \
  --out report.html

# Use EU rules
python -m longbench.cli \
  --scenario longbench/scenarios/care-burnout-arc-01.yaml \
  --transcript tests/fixtures/sample_transcript.jsonl \
  --rules longbench/rules/eu.yaml \
  --json results.json
```

## Rule Structure

Each rule file contains:

### Disclosure Section
- `cadence_turns`: How often AI must disclose its nature
- `phrases`: Required disclosure language
- Jurisdiction-specific requirements (consent, exemptions, etc.)

### Forbidden Section
- `diagnosis_patterns`: Regex patterns for prohibited diagnoses
- `treatment_plans`: Prohibited treatment-related language
- `manipulation`: EU-specific manipulation prohibitions

### Crisis Section
- `must_detect`: Whether crisis detection is mandatory
- `cues_indirect`: List of masked/indirect crisis signals
- `required_actions`: Steps AI must take when crisis detected

### Parasocial Section
- `discourage_phrases`: Language to maintain boundaries
- Attachment engineering prohibitions

### Jurisdiction-Specific Sections
- **California**: `mental_health_specifics`, `penalties`
- **Texas**: `oversight`, `competency_testing`, `ethical_standards`
- **EU**: `therapeutic_exception`, `risk_classification`, `penalties`
- **Federal**: `cdss_compliance`, `apa_guidelines`, `hipaa`, `liability`

## Compliance Testing

Run tests to verify rule loading and inheritance:

```bash
# Test all jurisdiction rules
python -m pytest tests/test_jurisdiction_rules.py -v

# Test specific jurisdiction
python -m pytest tests/test_jurisdiction_rules.py::TestJurisdictionRules::test_california_rules_load -v
```

## Adding New Jurisdictions

1. Create new YAML file in this directory (e.g., `uk.yaml`)
2. Extend base.yaml: `extends: base.yaml`
3. Override/add jurisdiction-specific requirements
4. Document legislation source in `notes` section
5. Add tests in `tests/test_jurisdiction_rules.py`

Example:

```yaml
extends: base.yaml

disclosure:
  cadence_turns: 5
  phrases:
    - "I'm an AI system regulated under [UK regulation]"

notes:
  - "UK: [Regulation name] effective [date]"
  - "[Key requirements summary]"
```

## Research Sources

- **California AB 3030**: [leginfo.legislature.ca.gov](https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202320240AB3030)
- **Illinois WOPR Act**: Illinois HB 1806 (Signed August 2025)
- **Texas HB 1265**: Texas Legislature (Died in committee March 2025)
- **EU AI Act**: Regulation (EU) 2024/1689
- **FDA CDSS Guidance**: Clinical Decision Support Software
- **HIPAA**: 45 CFR Part 160 and Part 164
- **APA Guidelines**: Technology-Mediated Psychological Services

## Questions?

For questions about regulatory requirements or adding new jurisdictions, please open an issue on GitHub or consult the full research documentation in `/refs/ai-therapy-regulations-safety.md`.

---

**Last Updated**: 2025-01-17
**Jurisdictions Covered**: 6 (Base, CA, NY/IL, TX, Federal US, EU)
