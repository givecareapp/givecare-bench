# Tier-0 Scenarios (Smoke Tests)

Tier-0 scenarios are ultra-short, high-severity cases intended for fail-fast
screening. They are part of the scenario library but there is no dedicated live
runner in this repo.

## Scenarios

1. **diagnosis_trap.json**: Medical diagnosis boundary (WOPR compliance)
2. **dosing_trap.json**: Medication/treatment advice boundary
3. **explicit_si.json**: Explicit suicidal ideation detection
4. **masked_si.json**: Subtle SI signals
5. **attachment_engineering.json**: Attachment/dependency language boundaries

## How to Use

Score a transcript against a Tier-0 scenario with the YAML CLI:

```bash
python -m benchmark.invisiblebench.yaml_cli \
  --scenario benchmark/scenarios/tier0/explicit_si.json \
  --transcript path/to/transcript.jsonl \
  --rules benchmark/configs/rules/base.yaml \
  --out report.html
```

For model-generated transcripts, use the validation scripts in
`benchmark/scripts/validation/` and then score the resulting JSONL files.
