# Community Evaluation Results

Submit your InvisibleBench evaluation results to the public leaderboard!

## How to Submit

### Step 1: Run Evaluation

```bash
# Install InvisibleBench
git clone https://github.com/givecareapp/givecare-bench.git
cd givecare-bench
pip install -e ".[all]"

# Run your model evaluation
python benchmark/scripts/validation/run_minimal.py \
  --model your-model-name \
  --output results/your-submission
```

### Step 2: Fill Template

Copy and complete the submission template:

```bash
cp benchmark/community/TEMPLATE.json \
  benchmark/community/submissions/your-model-name.json
```

Fill in all fields with your evaluation results.

Validate the submission before opening a PR:

```bash
python benchmark/scripts/community/validate_submission.py \
  benchmark/community/submissions/your-model-name.json
```

### Step 3: Submit Pull Request

1. Fork this repository
2. Add your results file: `benchmark/community/submissions/your-model-name.json`
3. Submit PR with title: "Add results for [Your Model]"
4. We'll review and merge within 48 hours!

## Leaderboard

Live rankings: https://bench.givecareapp.com/leaderboard.html

## Submission Rules

✅ **Allowed**:
- Any publicly available model
- Custom fine-tuned models (with disclosure)
- Multiple runs (include variance)
- Updated results (submit new PR)

❌ **Not Allowed**:
- Adversarial optimization to benchmark
- Cherry-picked best runs
- Modified scenarios
- Incomplete evaluations

## Cost Estimates

- **Minimal** (9 evaluations): $5-10
- **Full** (17 scenarios): $15-30 per model
- **Comprehensive** (with variance): $30-60

## Questions?

- Open an issue: https://github.com/givecareapp/givecare-bench/issues
- Email: ali@givecareapp.com
