# Cloud Deployment Scripts

Deploy and run GiveCare benchmark on cloud platforms for scalable execution.

## Available Platforms

### Modal (Recommended)
Serverless Python platform with simple deployment and auto-scaling.

**Files:**
- `run_benchmark_modal.py` - Modal deployment script
- `MODAL_SETUP.md` - Complete setup guide
- `QUICKSTART.md` - Quick reference

**Quick Start:**
```bash
pip install modal
modal setup
modal secret create openrouter-api-key OPENROUTER_API_KEY="your-key"
modal run benchmark/scripts/cloud/run_benchmark_modal.py --mode minimal
```

## Benchmark Modes

### Minimal (Test)
- 1 model × 3 scenarios = 3 evaluations
- Cost: ~$5-10
- Time: ~15 minutes
- Use: Testing setup and validating results

### Full (Production)
- 5 models × 17 scenarios = 85 evaluations
- Cost: ~$50-60
- Time: 2-3 hours
- Use: Complete benchmark for paper results

## Cost Breakdown (Full Benchmark)

**API Costs (estimated):**
- Claude Sonnet 4.5: ~$30-35 (17 scenarios)
- Gemini 2.5 Flash: ~$2-3 (17 scenarios)
- GPT-4o Mini: ~$3-5 (17 scenarios)
- DeepSeek Chat V3: ~$2-3 (17 scenarios)
- Qwen 3 235B: ~$8-10 (17 scenarios)

**Infrastructure:**
- Modal compute: ~$0.20-0.40 (2-3 hours)

**Total: ~$50-61**

## Features

- Automatic dependency installation
- Secure API key management via secrets
- Real-time log streaming
- Persistent result storage
- Auto-shutdown on completion
- No manual cleanup required

## Results

Results are saved to Modal persistent volume and include:
- Conversation transcripts (JSONL)
- Dimension scores (JSON)
- Summary tables (CSV)
- Visualizations (PNG)

Download with:
```bash
modal volume get givecare-results ./local_results/
```

## Documentation

- `QUICKSTART.md` - Quick reference (1 page)
- `MODAL_SETUP.md` - Complete guide with troubleshooting
- `run_benchmark_modal.py` - Deployment script with inline docs

## Support

Issues? See:
- Modal docs: https://modal.com/docs
- GiveCare issues: https://github.com/givecareapp/givecare-bench/issues
