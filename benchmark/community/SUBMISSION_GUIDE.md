# Community Evaluation Results

Submit your InvisibleBench evaluation results to the public leaderboard!

## How to Submit

### Step 1: Run Evaluation

```bash
# Install InvisibleBench
git clone https://github.com/givecareapp/givecare-bench.git
cd givecare-bench
pip install -r requirements.txt

# Run your model evaluation
python scripts/run_minimal_validation.py \
  --model your-model-name \
  --output results/your-submission
```

### Step 2: Fill Template

Copy and complete the submission template:

```bash
cp community_results/TEMPLATE.json community_results/your-model-name.json
```

Fill in all fields with your evaluation results.

### Step 3: Submit Pull Request

1. Fork this repository
2. Add your results file: `community_results/your-model-name.json`
3. Submit PR with title: "Add results for [Your Model]"
4. We'll review and merge within 48 hours!

## Leaderboard

Live rankings: https://givecareapp.github.io/givecare-bench/leaderboard.html

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
