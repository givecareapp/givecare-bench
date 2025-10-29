---
task_categories:
- text-generation
- text-classification
language:
- en
tags:
- ai-safety
- caregiving
- crisis-detection
- benchmark
- evaluation
- mental-health
size_categories:
- n<1K
license: mit
---

# SupportBench: AI Safety Benchmark for Persistent Caregiving Relationships

## Dataset Description

SupportBench is the first benchmark designed to evaluate AI safety across multi-turn (3-20+) conversations in caregiving contexts. Unlike single-turn benchmarks, SupportBench captures failure modes that emerge over extended relationships: attachment engineering, performance degradation, cultural othering, crisis calibration failures, and regulatory boundary creep.

### Key Features

- **Three-Tier Architecture**:
  - Tier 1 (3-5 turns): Basic safety and crisis detection
  - Tier 2 (8-12 turns): Relationship formation and boundary maintenance
  - Tier 3 (20+ turns across sessions): Longitudinal memory and consistency

- **Eight Evaluation Dimensions**:
  1. Crisis Safety (20%)
  2. Regulatory Fitness (15%)
  3. Trauma-Informed Flow (15%)
  4. Belonging & Cultural Fitness (15%)
  5. Relational Quality (10%)
  6. Actionable Support (10%)
  7. Longitudinal Consistency (10%)
  8. Memory Hygiene (5%)

- **17 Scenarios**: Covering crisis detection, boundaries, cultural sensitivity, burnout, and long-term relationship dynamics

- **Tri-Judge Ensemble**: Evaluation system using median aggregation for robust scoring

### Dataset Structure

```
supportbench/
├── scenarios/
│   ├── tier1/          # 3-5 turn scenarios
│   ├── tier2/          # 8-12 turn scenarios
│   ├── tier3/          # 20+ turn scenarios
│   └── confidential/   # Adversarial test cases (not public)
├── rules/
│   ├── base.yaml       # Base regulatory rules
│   ├── ny.yaml         # New York-specific rules
│   └── ...
└── configs/
    └── scoring.yaml    # Dimension weights and rubrics
```

### Usage

```python
from datasets import load_dataset

# Load scenarios
dataset = load_dataset("givecareapp/supportbench")

# Run evaluation with your model
from supportbench import evaluate_model

results = evaluate_model(
    model="your-model-name",
    scenarios=dataset["tier1"],
    rules="ny"  # jurisdiction
)
```

### Installation & Evaluation

```bash
# Clone repository
git clone https://github.com/givecareapp/givecare-bench.git
cd givecare-bench

# Install dependencies
pip install -r requirements.txt

# Run evaluation
python -m supportbench.yaml_cli \
  --scenario scenarios/tier1/crisis/crisis_detection.json \
  --transcript your_model_responses.jsonl \
  --rules supportbench/rules/base.yaml \
  --out results.html
```

### Cost Estimates

- **Tier 1 eval**: $0.03-0.05 per scenario
- **Tier 2 eval**: $0.05-0.08 per scenario
- **Tier 3 eval**: $0.06-0.10 per scenario

**Full benchmark** (17 scenarios): ~$1-2 per model

### Citation

If you use SupportBench in your research, please cite:

```bibtex
@misc{madad_supportbench_2025,
  author       = {Ali Madad},
  title        = {{SupportBench}: AI Safety Benchmark for Persistent Caregiver Support},
  howpublished = {\url{https://github.com/givecareapp/givecare-bench}},
  year         = {2025}
}
```

### Paper

[SupportBench: A Benchmark for Evaluating AI Safety in Persistent Caregiving Relationships](https://arxiv.org/abs/XXXX.XXXXX) (arXiv, 2025)

### Leaderboard

See live community leaderboard at: https://givecareapp.github.io/givecare-bench/leaderboard.html

### License

MIT License - See LICENSE file for details.

### Contact

- **Author**: Ali Madad
- **Email**: ali@givecareapp.com
- **GitHub**: https://github.com/givecareapp/givecare-bench
- **Website**: https://givecareapp.github.io/givecare-bench/

### Acknowledgments

This benchmark was developed with support from the caregiving community and builds on research in AI safety, mental health chatbots, and trauma-informed care.

### Dataset Statistics

- **Total Scenarios**: 17 (+ confidential adversarial tests)
- **Total Turns**: 150+ across all scenarios
- **Languages**: English
- **Domain**: Healthcare, Caregiving, Mental Health Support
- **Format**: JSON scenarios + JSONL transcripts + YAML rules

### Evaluation Framework

SupportBench uses a tri-judge ensemble system:

1. **Judge 1** (Instruction-Following + Regulatory): Crisis Safety, Regulatory Fitness
2. **Judge 2** (Cultural Reasoning + Emotional Intelligence): Trauma-Informed Flow, Belonging & Cultural Fitness
3. **Judge 3** (Long-Context + Relationship Dynamics): Relational Quality, Actionable Support, Longitudinal Consistency

Scores are aggregated using median to ensure robustness against outliers.

### Regulatory Compliance

- **Illinois WOPR Act** (HB1806 / PA 104-0054): No diagnosis, treatment plans, or medication dosing
- **Crisis Response Standards**: Explicit and masked crisis signal detection
- **PII Protection**: Memory hygiene evaluation for PHI/PII minimization

### Community Contributions

We welcome:
- Model evaluation results
- New scenario contributions
- Bug reports and improvements
- Research collaborations

Submit via:
- HuggingFace Discussions
- GitHub Issues/PRs: https://github.com/givecareapp/givecare-bench
- Email: ali@givecareapp.com

### Version History

- **v0.8.5** (2025-10-25): Current release with rebalanced weights and enhanced belonging dimension
- **v0.9.0** (Target: 2025-11): Phase 2 enhancements (multi-judge ensemble, expanded scenarios)
- **v1.0.0** (Target: 2025-12): Production release with peer review

See CHANGELOG.md for complete version history.
