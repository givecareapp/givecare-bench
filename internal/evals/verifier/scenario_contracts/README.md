# Scenario Contracts

Verifier-ready summaries for the highest-noise scenarios on the current board.

These files are not replacements for the underlying scenario JSON. They are compact
adjudication sheets for verifier use.

## Included scenarios

- `context_regulatory_data_privacy_001.md`
- `tier1_scope_honesty_001.md`
- `context_regulatory_misrepresentation_001.md`
- `context_regulatory_therapy_function_001.md`
- `tier1_attachment_002.md`
- `tier2_attachment_001.md`
- `tier3_longitudinal_001.md`
- `tier2_regulatory_001_minor_disclosure.md`
- `tier1_false_refusal_med_001.md`
- `tier1_crisis_indirect_bridge_001.md`

## Contract format

Each file records:

- target capability
- public hard-fail conditions
- soft issues to track
- allowed edge cases to protect
- common scorer / verifier confusion points

## Usage rule

The scenario contract narrows interpretation. It should be used together with the core verifier rubric and taxonomy, not in isolation.
