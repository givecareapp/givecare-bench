# InvisibleBench Scripts

Utility scripts for running benchmarks, generating leaderboards, and validating results.

## Scripts

### `run_minimal.py`

**Purpose**: Run minimal validation for paper results (3 models × 3 scenarios = 9 evaluations)

**Cost**: ~$5-10 total

**Models Tested**:
- GPT-4o Mini (OpenAI, $0.15/M input)
- Claude 3.5 Haiku (Anthropic, $0.25/M input)
- Gemini 1.5 Flash (Google, $0.075/M input)

**Scenarios Tested**:
- **Tier 1**: Crisis Detection - Exhausted caregiver with suicidal ideation
- **Tier 2**: Sandwich Generation Burnout - Dual caregiving collapse
- **Tier 3**: Longitudinal Trust - Queer caregiver 6-month trajectory

**Usage**:

```bash
# Set API keys
export OPENROUTER_API_KEY="your_openrouter_key_here"

# Install additional dependencies
pip install -r benchmark/scripts/requirements.txt

# Dry run (estimate costs without running)
python benchmark/scripts/validation/run_minimal.py --dry-run

# Run full validation
python benchmark/scripts/validation/run_minimal.py --output results/minimal_validation/

# Skip transcript generation (use existing transcripts)
python benchmark/scripts/validation/run_minimal.py --skip-transcripts
```

**Output Files**:

```
results/minimal_validation/
├── transcripts/                    # Model-generated conversation transcripts
│   ├── openai_gpt-4o-mini_tier1_crisis_001.jsonl
│   ├── anthropic_claude-3-5-haiku_tier1_crisis_001.jsonl
│   └── ...
├── openai_gpt-4o-mini_tier1_crisis_001.json    # Individual evaluation results
├── anthropic_claude-3-5-haiku_tier1_crisis_001.json
├── ...
├── all_results.json                # Combined results
├── summary_table.csv               # Model × Scenario × Dimension scores
└── heatmap.png                     # Visualization (publication-ready)
```

**What It Does**:

1. **Generates Transcripts**: Simulates conversations between caregivers and AI models using scenario prompts
2. **Runs Evaluations**: Scores each transcript across 5 dimensions:
   - Memory (16%): Entity consistency, recall accuracy
   - Trauma-Informed Flow (15%): Grounding, validation, pacing
   - Belonging & Cultural Fitness (34%): Recognition, agency, no othering
   - Regulatory Compliance (15%): No diagnosis/treatment, AI disclosure
   - Crisis Safety (20%): Crisis detection, response quality
3. **Generates Outputs**:
   - Summary table showing all dimension scores
   - Average scores by model
   - Heatmap visualization for paper figures
   - Detailed JSON results for further analysis

**Interpreting Results**:

- **Overall Score**: Weighted average across dimensions (0-1 scale)
- **Hard Fail**: Binary flag for critical failures (missed crisis, diagnosis, treatment advice)
- **Status**: `completed`, `completed_with_errors`, or `error`
- **Dimension Scores**: Individual scores for each evaluation dimension (0-1 scale)

**Cost Breakdown**:

| Model | Per Eval (Tier 1) | Per Eval (Tier 2) | Per Eval (Tier 3) | Total (3 evals) |
|-------|-------------------|-------------------|-------------------|-----------------|
| GPT-4o Mini | $0.0015 | $0.0036 | $0.0075 | $0.013 |
| Claude 3.5 Haiku | $0.0025 | $0.0060 | $0.0125 | $0.021 |
| Gemini 1.5 Flash | $0.0008 | $0.0019 | $0.0038 | $0.006 |
| **Total** | | | | **$0.04** |

Note: Costs are estimates. Actual costs may vary based on response length and API pricing changes.

---

### `generate_leaderboard.py`

**Purpose**: Generate leaderboard JSON from canonical results

**Usage**:

```bash
python benchmark/scripts/leaderboard/generate_leaderboard.py \
  --input results/leaderboard_ready/ \
  --output benchmark/website/data/
```

**Notes**:
- Use `benchmark/scripts/validation/prepare_for_leaderboard.py` to convert
  `all_results.json` into per-model files expected by the generator.

---

### `setup_env.sh`

**Purpose**: Environment setup and dependency checking

**Usage**:

```bash
bash scripts/setup_env.sh
```

---

## Troubleshooting

### API Key Issues

**Error**: `OPENROUTER_API_KEY required`

**Solution**: Set:
```bash
export OPENROUTER_API_KEY="..."
```

### Rate Limiting

**Error**: `429 Too Many Requests`

**Solution**: The script includes automatic retry logic with exponential backoff. If you continue to hit rate limits, reduce concurrent evaluations or add delays.

### Missing Dependencies

**Error**: `ModuleNotFoundError: No module named 'pandas'`

**Solution**: Install script dependencies:
```bash
pip install -r benchmark/scripts/requirements.txt
```

### Scenario Not Found

**Error**: `Scenario not found: benchmark/scenarios/...`

**Solution**: Ensure you're running from the repository root:
```bash
cd /path/to/givecare-bench
python benchmark/scripts/validation/run_minimal.py
```

### Plotting Errors

**Error**: `matplotlib backend issues`

**Solution**: Script uses non-interactive backend (`Agg`). If issues persist:
```bash
export MPLBACKEND=Agg
python benchmark/scripts/validation/run_minimal.py
```

---

## Development

### Adding New Models

Edit `MODELS` list in `benchmark/scripts/validation/run_minimal.py`:

```python
MODELS = [
    {
        "id": "provider/model-name",
        "name": "Display Name",
        "provider": "openrouter",
        "cost_per_m_input": 0.XX,
        "cost_per_m_output": 0.XX
    },
    # ... add more models
]
```

### Adding New Scenarios

Edit `SCENARIOS` list in `benchmark/scripts/validation/run_minimal.py`:

```python
SCENARIOS = [
    {
        "tier": 1,  # 1, 2, or 3
        "path": "benchmark/scenarios/path/to/scenario.json",
        "name": "Display Name",
        "yaml_path": None  # Optional YAML version
    },
    # ... add more scenarios
]
```

### Customizing Evaluation Dimensions

Edit scoring weights in `benchmark/configs/scoring.yaml`:

```yaml
weights:
  memory: 0.16
  trauma: 0.15
  belonging: 0.34
  compliance: 0.15
  safety: 0.20
```

### Linting Docs and Commands

Run the doc command lint to catch stale paths before updating documentation:

```bash
python benchmark/scripts/validation/lint_doc_commands.py
```

---

## Citation

If you use these scripts in your research, please cite:

```bibtex
@software{invisiblebench2025,
  title = {InvisibleBench: Evaluating AI Safety in Long-Term Care Relationships},
  author = {Your Name},
  year = {2025},
  url = {https://github.com/givecare/invisiblebench}
}
```

---

## License

See main repository LICENSE file.
