# Community Submissions Quick Reference

Submit your SupportBench evaluation results to the public leaderboard!

## Quick Start

```bash
# 1. Run evaluation
python scripts/run_minimal_validation.py \
  --model your-model-name \
  --output results/your-submission

# 2. Copy template
cp community_results/TEMPLATE.json community_results/your-model-name.json

# 3. Edit with your results (open in your favorite editor)

# 4. Validate
python scripts/validate_submission.py community_results/your-model-name.json

# 5. Submit PR
git checkout -b add-your-model-results
git add community_results/your-model-name.json
git commit -m "Add results for [Your Model]"
git push origin add-your-model-results
# Create pull request on GitHub
```

## Files & Documentation

- **Submission Guide**: [`community_results/README.md`](community_results/README.md)
- **Template**: [`community_results/TEMPLATE.json`](community_results/TEMPLATE.json)
- **Validation Script**: [`scripts/validate_submission.py`](scripts/validate_submission.py)
- **Leaderboard Generator**: [`scripts/update_leaderboard.py`](scripts/update_leaderboard.py)
- **Live Leaderboard**: [bench.givecareapp.com/leaderboard.html](https://bench.givecareapp.com/leaderboard.html)

## Submission Rules

### Allowed
- Any publicly available model
- Custom fine-tuned models (with disclosure)
- Multiple runs (include variance)
- Updated results (submit new PR)

### Not Allowed
- Adversarial optimization to benchmark
- Cherry-picked best runs
- Modified scenarios
- Incomplete evaluations

## Cost Estimates

- **Minimal** (9 evaluations): $5-10
- **Full** (17 scenarios): $15-30 per model
- **Comprehensive** (with variance): $30-60

## Validation Features

The validation script checks:

- JSON structure matches template
- All required fields present
- Scores in valid range [0, 1]
- Reasonable cost and time values
- No duplicate submissions
- All 8 dimensions included
- Proper hard fail tracking

## Questions?

- **Issues**: [github.com/givecareapp/givecare-bench/issues](https://github.com/givecareapp/givecare-bench/issues)
- **Email**: ali@givecareapp.com
- **Website**: [bench.givecareapp.com](https://bench.givecareapp.com)

## Automated Review

All submissions are automatically validated via GitHub Actions:

1. You submit PR with your results
2. GitHub Actions validates format
3. Leaderboard preview is generated
4. Automated comment posted on PR
5. Maintainer reviews and merges
6. Leaderboard updates automatically

Expect review within 48 hours!
