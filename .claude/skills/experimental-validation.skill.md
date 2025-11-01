# Experimental Validation Skill

## When to Use
Running evaluations, analyzing results, validating hypotheses, preparing results for papers, designing experiments

## Experimental Rigor for AI Systems

AI benchmarks are scientific instruments. Apply same rigor as human subject studies.

## Pre-Registration (Before Running Experiments)

Document BEFORE collecting data (prevents p-hacking and HARKing):

### Template (Use in dev/experiments/[name]/plan.md)

```markdown
## Experiment: [Name]

**Date**: YYYY-MM-DD
**Status**: 📋 Pre-registered | 🏃 Running | ✅ Complete | ❌ Failed

**Research Question**:
[One sentence - what are we trying to learn?]

**Hypothesis**:
[Specific, falsifiable prediction]

**Motivation**:
[Why does this matter? What gap does it fill?]

**Methodology**:
- **Models tested**: [List specific models with versions]
- **Scenarios**: [Which scenarios, how many]
- **Evaluation approach**: [Judges, metrics, aggregation]
- **Sample size**: [N runs per condition]
- **Randomization**: [How will we control for order effects?]

**Metrics**:
1. **Primary metric**: [Main outcome measure]
   - **Success threshold**: [What value would support hypothesis?]
   - **Measurement method**: [How calculated?]

2. **Secondary metrics**: [Additional outcomes]
   - **Success threshold**: [What value would support hypothesis?]
   - **Measurement method**: [How calculated?]

**Success Criteria** (defined BEFORE running):
- [ ] Primary metric meets threshold
- [ ] Effect size is meaningful (not just statistically significant)
- [ ] Result is stable across multiple runs (low variance)

**Failure Criteria** (what would falsify hypothesis):
- [ ] Primary metric below threshold
- [ ] High variance (unreliable measurement)
- [ ] Unexpected negative effects on other dimensions

**Statistical Plan**:
- **Significance level**: α = 0.05 (or Bonferroni corrected if multiple tests)
- **Power**: 1-β = 0.80 (80% chance of detecting real effect)
- **Effect size**: Minimum meaningful difference = [value]
- **Analysis method**: [t-test, ANOVA, bootstrap CI, etc.]

**Confounds to Control**:
- [ ] Model version drift (pin versions)
- [ ] Scenario order effects (randomize)
- [ ] Judge variance (multiple runs)
- [ ] Temperature settings (standardize)

**Resources Required**:
- **API cost estimate**: $[amount]
- **Compute time**: [hours/days]
- **Human annotation** (if needed): [hours]

**Timeline**:
- Setup: [date]
- Data collection: [date range]
- Analysis: [date]
- Paper integration: [date]
```

## Running Evaluations

### Your Project's Evaluation Commands

```bash
# Quick validation (3 models × 3 scenarios)
python benchmark/scripts/validation/run_minimal.py

# Single scenario evaluation with HTML report
python -m supportbench.yaml_cli \
  --scenario benchmark/scenarios/tier1/crisis/crisis_detection.json \
  --transcript your_transcript.jsonl \
  --rules benchmark/configs/scoring.yaml \
  --out results.html

# Full evaluation with JSON + HTML
python -m supportbench.yaml_cli \
  --scenario supportbench/scenarios/care-burnout-arc-01.yaml \
  --transcript tests/fixtures/sample_transcript.jsonl \
  --rules supportbench/rules/ny.yaml \
  --out report.html \
  --json results.json
```

### During Experiment Execution

**Best Practices**:
1. **Log everything**: Save raw API responses, not just scores
2. **Track metadata**: Model version, timestamp, random seed, temperature
3. **Checkpoint frequently**: Save intermediate results (in case of failure)
4. **Monitor costs**: Track API spend in real-time
5. **Sanity checks**: Inspect a few examples manually before full run

**Red Flags** (stop and investigate):
- API errors > 5%
- Results differ wildly from pilot run
- All models score identically (suggests measurement failure)
- Variance exceeds expected range

## Result Analysis Checklist

After running experiments, systematically analyze:

### 1. Sanity Checks

- [ ] **Face validity**: Do results make intuitive sense?
- [ ] **Baseline check**: Does random baseline perform as expected?
- [ ] **Ceiling check**: Does perfect baseline score 1.0?
- [ ] **Expected orderings**: Do known-good models outperform known-bad?

### 2. Variance Analysis

- [ ] **Within-model variance**: How stable are scores across runs?
  - Target: σ < 0.10 for reliable measurement
  - If σ > 0.15: Measurement is too noisy, need more runs or better rubric
- [ ] **Judge agreement**: For tri-judge, what's Fleiss' kappa?
  - κ > 0.60: Substantial agreement (good)
  - κ < 0.40: Poor agreement (judges interpreting differently)

### 3. Distribution Analysis

- [ ] **Check for ceiling effects**: Are all scores > 0.90? (test too easy)
- [ ] **Check for floor effects**: Are all scores < 0.20? (test too hard)
- [ ] **Check for bimodality**: Two distinct clusters? (may indicate subgroups)
- [ ] **Outlier detection**: Any extreme values? (inspect manually)

### 4. Edge Case Analysis

- [ ] **Inspect failures**: Why did model X fail scenario Y?
- [ ] **Inspect surprises**: Why did weak model outperform strong model?
- [ ] **Autofail analysis**: Which autofails triggered most often?
- [ ] **Dimension breakdown**: Which dimensions drive overall variance?

### 5. Bias Analysis

Break down results by:
- [ ] **Persona demographics**: Does model perform worse for certain groups?
- [ ] **Scenario type**: Crisis vs non-crisis, tier 1 vs 2 vs 3?
- [ ] **Cultural context**: Faith communities, collectivist cultures, etc.?
- [ ] **Socioeconomic factors**: Different performance by class indicators?

If disparities found: This is a FINDING, not a bug. Document and report.

### 6. Statistical Significance

- [ ] **Compute p-values**: But don't rely on them alone
- [ ] **Effect sizes**: Cohen's d, η² - are differences meaningful?
- [ ] **Confidence intervals**: Bootstrap 95% CIs for all key metrics
- [ ] **Multiple comparison correction**: Bonferroni if testing many hypotheses

**Important**: Statistical significance ≠ practical significance. A difference of 0.01 might be "significant" but meaningless.

## Interpreting SupportBench Results

### Your 8 Dimensions

1. **Crisis Safety** (20% weight) - Most critical
2. **Regulatory Fitness** (15% weight) - Hard pass/fail
3. **Trauma-Informed Flow** (15% weight)
4. **Belonging & Cultural Fitness** (15% weight)
5. **Relational Quality** (10% weight)
6. **Actionable Support** (10% weight)
7. **Longitudinal Consistency** (10% weight) - Tier 2/3 only
8. **Memory Hygiene** (5% weight + binary gate)

### Red Flags in Results

- **One dimension dominates**: Suggests weight miscalibration or rubric too strict/lenient
- **All models score similarly**: Test lacks discriminative power
- **Random model beats baseline**: Sanity check failure, something broken
- **High variance across runs**: Non-deterministic evaluation (bad)
- **Perfect correlation between dimensions**: Dimensions not independent (redundant)
- **No autofails triggered**: Scenarios too easy, or autofail conditions too strict

### Good Result Patterns

- **Clear rank ordering**: Top models consistently outperform weak models
- **Low within-model variance**: σ < 0.10 across runs
- **Dimension independence**: Low correlation between dimension scores
- **Meaningful spread**: Scores span 0.20-0.90 range (not all clustered)
- **Autofails sensible**: Triggered on actual safety failures, not false positives

## Documenting Results

### Template (Use in dev/experiments/[name]/results.md)

```markdown
## Experiment Results: [Name]

**Date Completed**: YYYY-MM-DD
**Pre-registration**: [link to plan.md]

**Quick Summary**:
[2-3 sentences: What did we find? Was hypothesis supported?]

---

### Setup (Actual, not planned)

**Models Tested**:
- Model A (version X.Y)
- Model B (version X.Y)

**Scenarios**: N scenarios from [tier/type]

**Runs per condition**: N runs (for variance estimation)

**Total evaluations**: N (models × scenarios × runs)

**Cost**: $X.XX

---

### Results

#### Primary Metric: [Metric Name]

| Model | Mean | SD | 95% CI | Effect Size vs Baseline |
|-------|------|----|----|--------------------------|
| Baseline | 0.65 | 0.08 | [0.61, 0.69] | - |
| Model A | 0.73 | 0.06 | [0.70, 0.76] | Cohen's d = 0.45 (medium) |
| Model B | 0.81 | 0.05 | [0.78, 0.84] | Cohen's d = 0.78 (large) |

**Statistical Tests**:
- One-way ANOVA: F(2, 27) = 12.4, p < 0.001
- Post-hoc: Model B > Model A > Baseline (all pairwise p < 0.05, Bonferroni corrected)

**Interpretation**: Hypothesis SUPPORTED. Model B shows large, statistically
significant improvement over baseline (d=0.78, p<0.001).

---

#### Secondary Metrics

[Similar tables for other metrics]

---

#### Dimension Breakdown

| Dimension | Baseline | Model A | Model B |
|-----------|----------|---------|---------|
| Crisis Safety | 0.71 | 0.78 | 0.85 |
| Regulatory | 0.89 | 0.91 | 0.93 |
| Trauma Flow | 0.62 | 0.69 | 0.77 |
| Belonging | 0.58 | 0.71 | 0.82 |
| ... | ... | ... | ... |

**Key Findings**:
- Largest improvement in Belonging dimension (+24pp for Model B)
- Crisis Safety shows consistent gains across all models
- Regulatory Fitness near ceiling (limited room for improvement)

---

#### Variance Analysis

**Within-model stability** (across 3 runs):
- Baseline: σ = 0.08 (acceptable)
- Model A: σ = 0.06 (good)
- Model B: σ = 0.05 (excellent)

**Judge agreement** (Fleiss' kappa):
- κ = 0.68 (substantial agreement)
- Crisis dimension: κ = 0.74 (highest agreement)
- Belonging dimension: κ = 0.61 (moderate agreement)

---

#### Failure Analysis

**Autofails triggered**:
- Missed crisis signal: 3 cases (all Baseline)
- Medical advice given: 1 case (Model A on scenario tier1_crisis_003)
- Demographic stereotyping: 2 cases (Baseline)

**Qualitative patterns**:
- Model B handles masked crisis signals better (5/5 detected vs 2/5 for Baseline)
- All models struggle with collectivist culture scenarios (avg 0.64 vs 0.81 for individualist)
- Tier 3 (20+ turn) scenarios show higher variance (σ = 0.12 vs 0.06 for Tier 1)

---

### Hypothesis Evaluation

**Pre-registered hypothesis**: "Increasing Crisis Safety weight from 15% to 20%
improves recall by ≥5pp without reducing precision by >3pp"

**Result**: ✅ SUPPORTED
- Recall improvement: +8pp (exceeded threshold)
- Precision change: -2pp (within acceptable range)
- Stable across all 3 models tested

---

### Limitations

1. **Sample size**: Only 5 scenarios per tier (small N for subgroup analysis)
2. **Model selection**: Tested only top-tier models (need weak model baseline)
3. **Scenario diversity**: Overrepresented middle-class caregivers (78% of personas)
4. **Judge variance**: One judge (Judge 2) showed higher variance (σ=0.11 vs 0.06)

---

### Recommendations

1. **Adopt change**: Update Crisis Safety weight to 20% in v0.9.0
2. **Additional testing**: Validate on full 17-scenario benchmark before release
3. **Judge calibration**: Retrain Judge 2 to reduce variance
4. **Scenario expansion**: Add more low-SES and collectivist-culture scenarios

---

### Paper Integration

**Target paper**: SupportBench.tex, Section 5.3 (Ablation Studies)

**Figures to generate**:
- Figure 8: Dimension weight comparison (before/after)
- Table 5: Per-model results with effect sizes

**Key claims to make**:
- "Empirical calibration of dimension weights improved overall discriminative power..."
- "Crisis Safety weight increase from 15% to 20% yielded 8pp recall improvement..."

**Limitations to disclose**:
- Small sample size for subgroup analysis
- Tested only on tier 1 scenarios (need tier 2/3 validation)

---

### Files Generated

- `results/experiment_crisis_weight/raw_data.json` - All raw scores
- `results/experiment_crisis_weight/analysis.ipynb` - Statistical analysis
- `results/experiment_crisis_weight/figures/` - Generated plots
```

## Integration with This Project

### Experiment Workflow for SupportBench

```markdown
1. **Pre-register** experiment in dev/experiments/[name]/plan.md
   - Use template above
   - Specify hypothesis, metrics, success criteria BEFORE running

2. **Run evaluation** with your CLI tools
   - Save raw outputs: --json results.json
   - Multiple runs for variance: N=3 minimum

3. **Analyze results** systematically
   - Follow checklist above
   - Generate figures: python papers/*/generate_figures.py

4. **Document findings** in dev/experiments/[name]/results.md
   - Use template above
   - Include limitations, not just successes

5. **Update papers** if findings are significant
   - GiveCare.tex: System performance claims
   - SupportBench.tex: Benchmark methodology validation

6. **Archive experiment**
   - Move to dev/completed/ if successful
   - Move to dev/experiments/failed/ if hypothesis rejected
```

### Key Experiments to Pre-Register

Based on your CLAUDE.md, these should be formal experiments:

1. **Dimension Weight Calibration** (already done for v0.8.5, but document)
2. **Tri-Judge vs Single Judge** (justify ensemble approach)
3. **Median vs Mean Aggregation** (justify aggregation method)
4. **Memory Hygiene Threshold** (justify 0.70 cutoff + binary gate)
5. **Tier Turn-Count Validation** (justify 3-5, 8-12, 20+ turns)

## Statistical Testing Cheatsheet

### Common Tests for Benchmark Evaluation

| Question | Test | When to Use |
|----------|------|-------------|
| Do models differ? | One-way ANOVA | 3+ models, normal distribution |
| Which models differ? | Tukey HSD | Post-hoc after ANOVA |
| Does change help? | Paired t-test | Before/after comparison |
| Is effect real? | Bootstrap CI | Non-normal data, small N |
| Do judges agree? | Fleiss' kappa | Inter-rater reliability |
| Is variance acceptable? | F-test | Compare variances |

### Interpreting Effect Sizes

- **Cohen's d**:
  - d < 0.20: Trivial
  - 0.20 ≤ d < 0.50: Small
  - 0.50 ≤ d < 0.80: Medium
  - d ≥ 0.80: Large

- **η² (eta-squared)**:
  - η² < 0.01: Trivial
  - 0.01 ≤ η² < 0.06: Small
  - 0.06 ≤ η² < 0.14: Medium
  - η² ≥ 0.14: Large

**Rule of thumb**: Don't publish results without effect sizes. P-values alone are insufficient.

## See Also
- [Resource: Statistical Tests Cheatsheet](resources/statistical-tests.md)
- [Resource: Failure Analysis Template](resources/failure-analysis.md)
- [Resource: Pre-registration Template](resources/preregistration-template.md)
