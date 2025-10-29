# Quick HuggingFace Upload Guide

## TL;DR - Upload in 3 Steps

### Step 1: Get Token
https://huggingface.co/settings/tokens → Create new token with "Write" permissions

### Step 2: Run Upload
```bash
export HF_TOKEN="hf_your_token_here"
python hf_upload_script.py --token $HF_TOKEN
```

### Step 3: Verify
Visit: https://huggingface.co/datasets/givecareapp/supportbench

---

## What Gets Uploaded?

✅ **Included** (29.5 KB total):
- README_HF.md → README.md (5.5 KB)
- LICENSE (1.0 KB)
- requirements.txt (389 bytes)
- scenarios/ (13 scenarios: tier1, tier2, tier3, confidential)
- supportbench/rules/ → rules/ (base.yaml, ny.yaml)
- configs/scoring.yaml
- CHANGELOG.md
- CONTRIBUTING.md

❌ **Excluded** (.huggingface_ignore):
- .git/, .venv/, __pycache__/
- papers/, archive/, tests/, examples/
- Development files (.env, .DS_Store, *.log)

---

## Validation Check

Before uploading, run:
```bash
python validate_hf_structure.py
```

Expected output:
```
✅ All validation checks passed!
```

---

## Cost to Run

- **Per model evaluation**: $1-2 for full benchmark (13 scenarios)
- **Tier 1** (4 scenarios): $0.12-0.20
- **Tier 2** (5 scenarios): $0.25-0.40
- **Tier 3** (1 scenario): $0.06-0.10
- **Confidential** (3 scenarios): $0.09-0.15

---

## Test Dataset Loading

After upload:
```python
from datasets import load_dataset
dataset = load_dataset("givecareapp/supportbench")
print(dataset)
```

---

## Troubleshooting

### Error: "Token does not have write permissions"
→ Regenerate token at https://huggingface.co/settings/tokens with "Write" enabled

### Error: "Repository not found"
→ Script will auto-create it, or manually create at https://huggingface.co/new-dataset

### Error: "Invalid YAML in README"
→ Run validation script: `python validate_hf_structure.py`

---

## Full Documentation

- **Complete Setup**: See `HUGGINGFACE_SETUP.md`
- **Upload Summary**: See `HF_UPLOAD_SUMMARY.md`
- **Project Instructions**: See `CLAUDE.md`

---

## Files Created

All files are in: `/Users/amadad/Projects/give-care-else/givecare-bench/`

```
✅ LICENSE                      (1.0 KB)
✅ README_HF.md                 (5.5 KB) - HuggingFace dataset card
✅ requirements.txt             (389 B)  - Python dependencies
✅ hf_upload_script.py          (3.9 KB) - Upload automation
✅ validate_hf_structure.py     (6.4 KB) - Validation script
✅ .huggingface_ignore          (493 B)  - Upload exclusions
✅ HUGGINGFACE_SETUP.md         (6.3 KB) - Detailed instructions
✅ HF_UPLOAD_SUMMARY.md         (6.9 KB) - Complete summary
✅ QUICK_HF_UPLOAD.md           (2.0 KB) - This file
✅ .gitignore                   (updated) - Added HF exclusions
```

**Total**: 9 files created/updated (33.2 KB)

---

## Status

✅ **Ready for upload**
⚠️ **Action required**: User must provide HuggingFace token

---

## Contact

- **Author**: Ali Madad
- **Email**: ali@givecareapp.com
- **GitHub**: https://github.com/givecareapp/givecare-bench
