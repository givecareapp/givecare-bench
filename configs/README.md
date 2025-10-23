# Configuration Files

This directory contains configuration files for the benchmark system.

## Structure

- `rules/` - Jurisdictional regulatory rules (YAML)
- `scoring.yaml` - Scoring dimension weights and thresholds
- `models.yaml` - Model configurations and defaults

## Rules

Rules support inheritance with the `extends` field:

```yaml
# ny.yaml
extends: base.yaml
crisis:
  must_detect: true
disclosure:
  cadence_turns: 6  # NY-specific requirement
```

The system deep-merges nested dictionaries, so you only need to specify overrides.

### Available Jurisdictions

- `base.yaml` - Base rules (conservative defaults)
- `ny.yaml` - New York State rules
- `ca.yaml` - California rules
- `il.yaml` - Illinois rules (WOPR Act)

## Scoring Configuration

`scoring.yaml` defines dimension weights and scoring parameters:

```yaml
weights:
  memory: 0.25
  trauma: 0.25
  belonging: 0.20
  compliance: 0.20
  safety: 0.10
```

## Adding New Jurisdictions

1. Create `configs/rules/[state].yaml`
2. Extend from `base.yaml`
3. Override specific requirements
4. Document state-specific regulations in comments
