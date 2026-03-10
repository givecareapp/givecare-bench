# AutoResearch: Caregiving Model Training

You are an autonomous research agent fine-tuning Qwen3.5-4B to be a best-in-class caregiving AI, evaluated on the InvisibleBench benchmark.

## Single Metric

**Overall benchmark score** — mean across 44 scenarios on InvisibleBench.

## Architecture

```
prepare.py  →  train.py  →  eval.sh  →  compare  →  commit/revert
(data)         (LoRA)       (bench)     (score)
```

- **prepare.py**: Exports high-scoring transcripts from 12 frontier models as training data
- **train.py**: LoRA fine-tune Qwen3.5-4B on MLX (5-min wall-clock budget)
- **eval.sh**: Runs the fine-tuned model through InvisibleBench
- **Metric**: Overall benchmark score (0-1 mean across 44 scenarios)

## What You Optimize

Modify `train.py` between experiments. Tunable parameters:

| Parameter | Current | Range | Effect |
|-----------|---------|-------|--------|
| LORA_RANK | 8 | 4-64 | Higher = more capacity, slower |
| LORA_LAYERS | 16 | 8-32 | How many layers get LoRA adapters |
| LEARNING_RATE | 1e-5 | 1e-6 to 5e-4 | Higher = faster but less stable |
| BATCH_SIZE | 2 | 1-8 | Larger = smoother gradients |
| ITERS | 500 | 100-1000 | More = better fit, risk overfit |
| GRAD_ACCUM | 4 | 1-8 | Effective batch = batch * accum |

You can also modify `prepare.py` to change the training data:
- Raise/lower min_score threshold
- Switch between SFT and DPO
- Filter to specific scenario categories
- Weight safety scenarios more heavily

## Experiment Loop

```
WHILE score < target OR experiments < max_experiments:
    1. HYPOTHESIZE a change to train.py or prepare.py
    2. EDIT the file
    3. RUN: python autoresearch/train/prepare.py  (if data changed)
    4. RUN: python autoresearch/train/train.py
    5. RUN: ./autoresearch/train/eval.sh
    6. COMPARE score vs baseline
    7. DECIDE: commit or revert
    8. LOG results in experiment_log.md
```

## Training Data Sources

Your training data comes from 12 frontier model transcripts:
- 528 total transcripts (12 models x 44 scenarios)
- Each scored on safety, compliance, regard, coordination
- High-scoring responses (>0.80) used for SFT
- High vs low pairs used for DPO

## 5-Minute Budget

The wall-clock constraint forces you to discover what matters:
- Smaller LoRA rank trains faster → more experiments
- Data quality > data quantity at small scale
- Safety scenarios may need higher weight (7 GREAT differentiators are all safety)

## Starting

```bash
# 1. Install MLX
pip install mlx-lm

# 2. Prepare training data
python autoresearch/train/prepare.py

# 3. First training run
python autoresearch/train/train.py --iters 200

# 4. Evaluate
./autoresearch/train/eval.sh

# 5. Start optimizing
```
