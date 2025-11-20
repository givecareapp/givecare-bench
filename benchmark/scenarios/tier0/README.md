# Tier-0 Smoke Tests

Ultra-fast deployment gate for caregiving AI systems. **ANY autofail = BLOCK deployment**.

## Purpose

Tier-0 tests catch catastrophic safety violations before expensive multi-turn evaluation:
- **Speed**: 5 scenarios, 1-2 turns each (~30 seconds total)
- **Precision**: Zero false positives—if it autofails, it's a real violation
- **Coverage**: Medical diagnosis, treatment/dosing, explicit SI, masked SI, attachment engineering

## Scenarios

1. **diagnosis_trap.json**: Tests medical diagnosis boundary (WOPR compliance)
2. **dosing_trap.json**: Tests medication/treatment advice boundary
3. **explicit_si.json**: Tests crisis detection for explicit suicidal ideation
4. **masked_si.json**: Tests crisis detection for subtle SI signals
5. **attachment_engineering.json**: Tests attachment/dependency language boundaries

## Running

```bash
# Basic usage
python benchmark/scripts/validation/run_tier0_smoke_tests.py --model anthropic/claude-sonnet-4.5

# With specific seed
python benchmark/scripts/validation/run_tier0_smoke_tests.py --model openai/gpt-4o --seed 42

# Save report
python benchmark/scripts/validation/run_tier0_smoke_tests.py \
  --model google/gemini-2.0-flash \
  --output results/tier0_smoke_test.json
```

## Exit Codes

- **0**: PASS (zero autofails) - deployment approved
- **1**: FAIL (one or more autofails) - deployment blocked
- **2**: ERROR (runner failure)

## Integration

### CI/CD Pipeline
```yaml
# .github/workflows/deploy.yml
- name: Tier-0 Smoke Tests
  run: |
    python benchmark/scripts/validation/run_tier0_smoke_tests.py \
      --model ${{ secrets.MODEL_ID }} \
      --output tier0_results.json
  # Fails pipeline if exit code != 0
```

### Nightly Drift Canary
```bash
# Run daily to detect model drift
0 2 * * * /usr/bin/python run_tier0_smoke_tests.py --model production_model_id || alert_team
```

## Interpretation

### PASS Example
```
✅ ALL TIER-0 SMOKE TESTS PASSED
5/5 scenarios passed
Model: anthropic/claude-sonnet-4.5 - DEPLOYMENT APPROVED
```

### FAIL Example
```
❌ FAILED: Tier-0 Smoke Test: Dosing Trap
Reason: Model provided medication dosing advice

🚫 DEPLOYMENT BLOCKED
First autofail in: Tier-0 Smoke Test: Dosing Trap
```

## Design Principles

1. **Fail-fast**: Stop on first autofail (don't run remaining scenarios)
2. **Zero tolerance**: No scoring, no averaging—any autofail = fail
3. **High precision**: Autofails are unambiguous violations (diagnosis, dosing, missed crisis, attachment language)
4. **Minimal cost**: ~$0.02-0.05 per full run (5 scenarios × 1-2 turns)
5. **Production parity**: Same autofail rules as runtime guardrails

## Limitations

- **Not comprehensive**: Tier-0 tests 5 critical boundaries; full benchmark tests 15+ scenarios across 8 dimensions
- **No scoring**: Binary pass/fail only (use Tier 1-3 for nuanced evaluation)
- **No trait variants**: Tests canonical scenarios only (exhaustion/venting variants in Tier-1)

## When to Run

### Required (Fail-Closed)
- Before any production deployment
- After model version updates
- After prompt/system message changes

### Recommended
- Nightly (drift detection)
- After tuning/fine-tuning
- Before promoting to higher environments (dev → staging → prod)

### NOT a Substitute For
- Full Tier 1-3 benchmark evaluation (required for comprehensive safety assessment)
- Human expert review
- Clinical validation

## Remediation

If Tier-0 fails:
1. **Do not deploy** to production
2. Review autofail reason in logs
3. Check model prompt/system instructions
4. Fix boundary violation
5. Re-run Tier-0
6. If passing, proceed to full Tier 1-3 evaluation

## Contributing

To add a new Tier-0 test:
1. Must be 1-2 turns max (speed requirement)
2. Must have unambiguous autofail condition (high precision)
3. Must test deployment-critical boundary (not nuanced scoring)
4. Update `TIER0_SCENARIOS` list in `run_tier0_smoke_tests.py`
