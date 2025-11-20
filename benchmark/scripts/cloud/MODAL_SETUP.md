# Modal Cloud Deployment Guide

Run the GiveCare benchmark on Modal cloud infrastructure for scalable, cost-effective execution.

## Quick Start

### 1. Install Modal

```bash
pip install modal
```

### 2. Set Up Modal Account

```bash
modal setup
```

This will:
- Open your browser to create/login to a Modal account
- Prompt you to create an API token
- Save credentials to `~/.modal.toml`

### 3. Configure API Keys

Add your API keys as Modal secrets:

```bash
# OpenRouter API key (for Claude, Gemini, GPT-4o Mini, DeepSeek, Qwen)
modal secret create openrouter-api-key OPENROUTER_API_KEY="sk-or-v1-..."

# Anthropic API key (optional, for direct Claude access)
modal secret create anthropic-api-key ANTHROPIC_API_KEY="sk-ant-..."
```

**Where to get API keys:**
- OpenRouter: https://openrouter.ai/keys
- Anthropic: https://console.anthropic.com/settings/keys

### 4. Run Benchmark

**Minimal test run (recommended first):**
```bash
modal run benchmark/scripts/cloud/run_benchmark_modal.py --mode minimal
```

- 1 model × 3 scenarios = 3 evaluations
- Cost: ~$5-10
- Time: ~15 minutes

**Full benchmark:**
```bash
modal run benchmark/scripts/cloud/run_benchmark_modal.py --mode full
```

- 5 models × 17 scenarios = 85 evaluations
- Cost: ~$50-60
- Time: 2-3 hours

## Benchmark Configurations

### Minimal (Test Mode)
- **Models:** Claude Sonnet 4.5
- **Scenarios:** 3 (one from each tier)
- **Total:** 3 evaluations
- **Cost:** $5-10
- **Time:** ~15 minutes

### Full (Production Mode)
- **Models:**
  - Claude Sonnet 4.5
  - Gemini 2.5 Flash
  - GPT-4o Mini
  - DeepSeek Chat V3
  - Qwen 3 235B
- **Scenarios:** 17 (5 Tier 1, 9 Tier 2, 3 Tier 3)
- **Total:** 85 evaluations
- **Cost:** $50-60
- **Time:** 2-3 hours

## Retrieving Results

### View files in volume
```bash
modal volume ls givecare-results
```

### Download results
```bash
# Download all results
modal volume get givecare-results ./local_results/

# Download specific directory
modal volume get givecare-results full_benchmark ./local_results/
```

### Results structure
```
results/
├── transcripts/              # Model conversation transcripts
│   └── *.jsonl
├── all_results.json          # Complete results JSON
├── summary_table.csv         # Results summary table
├── heatmap.png              # Dimension heatmap visualization
└── individual results/       # Per-evaluation JSON files
    └── *.json
```

## Monitoring Execution

### Real-time logs
Logs stream to your terminal automatically when using `modal run`.

### View past runs
```bash
modal app list
```

### View function logs
```bash
modal app logs givecare-benchmark
```

## Cost Management

### Pre-run cost estimate
```bash
# Test locally first (doesn't call APIs)
FULL_BENCHMARK=true python benchmark/scripts/validation/run_minimal.py --dry-run
```

### Monitor Modal credits
- Visit: https://modal.com/settings/billing
- Modal charges: ~$0.10-0.20/hour for compute (minimal)
- Main cost: API calls to LLM providers

### Cost breakdown (Full benchmark)
- Claude Sonnet 4.5: ~$30-35 (17 scenarios)
- Gemini 2.5 Flash: ~$2-3 (17 scenarios)
- GPT-4o Mini: ~$3-5 (17 scenarios)
- DeepSeek V3: ~$2-3 (17 scenarios)
- Qwen 3 235B: ~$8-10 (17 scenarios)
- **Total API cost:** ~$50-60
- **Modal compute:** ~$0.20-0.40
- **Grand total:** ~$50-61

## Troubleshooting

### "Secret not found" error
```bash
# List existing secrets
modal secret list

# Create missing secret
modal secret create openrouter-api-key OPENROUTER_API_KEY="your-key"
```

### "Import error" in Modal
The Modal image includes all dependencies. If you see import errors:
1. Check that the benchmark code is properly mounted
2. Verify the remote path: `/root/benchmark`

### Timeout errors
Default timeout is 3 hours for full benchmark. If needed, edit `run_benchmark_modal.py`:
```python
timeout=10800,  # Increase to 14400 (4 hours) if needed
```

### Volume permission errors
```bash
# Recreate volume
modal volume delete givecare-results
# Volume will auto-recreate on next run
```

## Advanced Usage

### Deploy as persistent app
```bash
# Deploy app (stays running)
modal deploy benchmark/scripts/cloud/run_benchmark_modal.py

# Trigger via Modal dashboard or API
```

### Run with custom scenarios
Edit `SCENARIOS_FULL` in `benchmark/scripts/validation/run_minimal.py` to customize which scenarios run.

### Parallel execution
For even faster execution, modify the Modal script to run model evaluations in parallel:
```python
@app.function(...)
def run_single_evaluation(model, scenario):
    # ... evaluation logic

# Then map over combinations
results = list(run_single_evaluation.map(
    [(m, s) for m in MODELS for s in SCENARIOS]
))
```

## Next Steps

1. **Start with minimal:** Test with `--mode minimal` first
2. **Verify results:** Check that transcripts and scores look reasonable
3. **Run full benchmark:** Once confident, run `--mode full`
4. **Download results:** Retrieve and analyze results locally
5. **Generate figures:** Use results for paper figures and analysis

## Support

- Modal docs: https://modal.com/docs
- Modal Discord: https://discord.gg/modal
- GiveCare issues: https://github.com/givecareapp/givecare-bench/issues
