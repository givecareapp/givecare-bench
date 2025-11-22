# HuggingFace Dataset Upload

## Quick Start (3 Steps)

### 1. Get Token
https://huggingface.co/settings/tokens → Create new token with "Write" permissions

### 2. Run Upload
```bash
export HF_TOKEN="hf_your_token_here"
python huggingface/upload_script.py --token $HF_TOKEN
```

### 3. Verify
Visit: https://huggingface.co/datasets/givecareapp/invisiblebench

---

## What Gets Uploaded

**Included:**
- README_HF.md → README.md (dataset card)
- scenarios/ (all tier1, tier2, tier3, confidential)
- configs/rules/ → rules/ (base.yaml, ny.yaml, etc.)
- configs/scoring.yaml
- requirements.txt, LICENSE
- CHANGELOG.md, CONTRIBUTING.md

**Excluded** (via `.huggingface_ignore`):
- .git/, .venv/, __pycache__/
- papers/, archive/, tests/, examples/
- Development files (.env, .DS_Store, *.log)

---

## Prerequisites

1. **Create HuggingFace account**: https://huggingface.co/join
2. **Generate access token**: https://huggingface.co/settings/tokens (Write permissions)
3. **Install dependencies**: `pip install huggingface_hub datasets`

---

## Upload Options

### Option 1: Using Upload Script (Recommended)

```bash
python huggingface/upload_script.py --token $HF_TOKEN --repo givecareapp/invisiblebench
```

### Option 2: Using huggingface-cli

```bash
huggingface-cli login
huggingface-cli upload givecareapp/invisiblebench . --repo-type=dataset \
  --include="scenarios/*,configs/rules/*,configs/scoring.yaml,README_HF.md,requirements.txt,LICENSE,CHANGELOG.md,CONTRIBUTING.md"
```

### Option 3: Manual Upload via Web UI

1. Go to https://huggingface.co/new-dataset
2. Create dataset: `givecareapp/invisiblebench`
3. Upload files via "Files and versions" tab
4. Rename `README_HF.md` to `README.md` when uploading

---

## Validation

Before uploading:
```bash
python huggingface/validate_structure.py
```

Expected output: `✅ All validation checks passed!`

---

## Verify Upload

### Test Dataset Loading

```python
from datasets import load_dataset

dataset = load_dataset("givecareapp/invisiblebench")
print(dataset)
```

### Check File Structure

```python
from huggingface_hub import list_repo_files

files = list_repo_files("givecareapp/invisiblebench", repo_type="dataset")
print("\n".join(files))
```

---

## Update Dataset

```bash
git pull
python huggingface/upload_script.py --token $HF_TOKEN
```

Changes are reflected immediately (no versioning delay).

---

## Dataset Versioning

```bash
# Create version tag
huggingface-cli tag givecareapp/invisiblebench v0.8.5 --repo-type=dataset

# Users load specific version
from datasets import load_dataset
dataset = load_dataset("givecareapp/invisiblebench", revision="v0.8.5")
```

---

## Troubleshooting

### "Token does not have write permissions"
→ Regenerate token at https://huggingface.co/settings/tokens with "Write" enabled

### "Repository not found"
→ Script auto-creates it, or manually create at https://huggingface.co/new-dataset

### "Invalid YAML in README"
→ Run validation: `python huggingface/validate_structure.py`

### "File too large"
→ HuggingFace has 50GB limit per file. Use git-lfs for large files:
```bash
git lfs install
git lfs track "*.bin"
```

---

## Community Features

### Enable Discussions
1. Repository settings → Enable "Discussions"
2. Users can submit model results, scenarios, bug reports

### Enable Pull Requests
1. Repository settings → Enable "Pull Requests"
2. Community can contribute scenarios, rules, docs

---

## Security

**NEVER commit:**
- `.env` files
- API tokens
- HuggingFace tokens

Use `.gitignore` and `.huggingface_ignore` to prevent accidental uploads.

**Confidential scenarios**: To exclude `scenarios/confidential/`, add to `.huggingface_ignore`

---

## Resources

- **HuggingFace Datasets**: https://huggingface.co/docs/datasets
- **Dataset Cards Guide**: https://huggingface.co/docs/hub/datasets-cards
- **InvisibleBench GitHub**: https://github.com/givecareapp/givecare-bench

---

## Contact

- **Email**: ali@givecareapp.com
- **GitHub Issues**: https://github.com/givecareapp/givecare-bench/issues
- **HuggingFace**: https://huggingface.co/datasets/givecareapp/invisiblebench/discussions
