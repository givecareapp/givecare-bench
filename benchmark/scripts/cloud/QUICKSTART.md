# Modal Deployment - Quick Start

## One-Time Setup (5 minutes)

```bash
# 1. Install Modal
pip install modal

# 2. Login to Modal (opens browser)
modal setup

# 3. Add API keys
modal secret create openrouter-api-key OPENROUTER_API_KEY="sk-or-v1-..."
modal secret create anthropic-api-key ANTHROPIC_API_KEY="sk-ant-..."
```

Get API keys:
- OpenRouter: https://openrouter.ai/keys
- Anthropic: https://console.anthropic.com/settings/keys

## Run Benchmark

### Test Run (Recommended First)
```bash
modal run benchmark/scripts/cloud/run_benchmark_modal.py --mode minimal
```
- 3 evaluations, ~15 min, ~$5-10

### Full Production Run
```bash
modal run benchmark/scripts/cloud/run_benchmark_modal.py --mode full
```
- 85 evaluations, ~2-3 hrs, ~$50-60

## Get Results

```bash
# List files
modal volume ls givecare-results

# Download everything
modal volume get givecare-results ./results/
```

## Cost Tracking

Check your balance:
- OpenRouter: https://openrouter.ai/credits
- Modal: https://modal.com/settings/billing

## Need Help?

See full documentation: `benchmark/scripts/cloud/MODAL_SETUP.md`
