# HuggingFace Dataset Setup

## Prerequisites

1. **Create HuggingFace account**: https://huggingface.co/join
2. **Generate access token**: https://huggingface.co/settings/tokens
   - Select "Write" permissions
   - Copy the token (starts with `hf_`)
3. **Install dependencies**: `pip install huggingface_hub datasets`

## Upload Steps

### Option 1: Using Upload Script (Recommended)

```bash
# Store token securely (do NOT commit to git!)
export HF_TOKEN="your_token_here"

# Run upload script
python hf_upload_script.py --token $HF_TOKEN --repo givecareapp/supportbench
```

**What gets uploaded:**
- ✅ README_HF.md → README.md (dataset card)
- ✅ scenarios/ (all tier1, tier2, tier3, confidential scenarios)
- ✅ supportbench/rules/ (base.yaml, ny.yaml, etc.)
- ✅ configs/scoring.yaml (dimension weights)
- ✅ requirements.txt
- ✅ LICENSE (MIT)
- ✅ CHANGELOG.md (version history)
- ✅ CONTRIBUTING.md (contribution guidelines)

**What does NOT get uploaded** (see `.huggingface_ignore`):
- ❌ .git/, .venv/, __pycache__/
- ❌ papers/, archive/, tests/, examples/
- ❌ Development files (.env, .DS_Store, *.log)

### Option 2: Manual Upload via Web UI

1. Go to https://huggingface.co/new-dataset
2. Create dataset: `givecareapp/supportbench`
3. Select "Files and versions" tab
4. Upload files via web interface:
   - Rename `README_HF.md` to `README.md` when uploading
   - Upload `scenarios/` folder
   - Upload `supportbench/rules/` folder as `rules/`
   - Upload `configs/scoring.yaml`
   - Upload `requirements.txt`
   - Upload `LICENSE`
   - Upload `CHANGELOG.md`
   - Upload `CONTRIBUTING.md`

### Option 3: Using huggingface-cli

```bash
# Login
huggingface-cli login

# Upload entire dataset
huggingface-cli upload \
  givecareapp/supportbench \
  . \
  --repo-type=dataset \
  --include="scenarios/*,supportbench/rules/*,configs/*,README_HF.md,requirements.txt,LICENSE,CHANGELOG.md,CONTRIBUTING.md"
```

## Verify Upload

### 1. Check Dataset Card Renders

Visit: https://huggingface.co/datasets/givecareapp/supportbench

The README should display with:
- Metadata tags (ai-safety, caregiving, crisis-detection)
- Task categories (text-generation, text-classification)
- Full description and usage examples

### 2. Test Dataset Loading

```python
from datasets import load_dataset

# Load dataset
dataset = load_dataset("givecareapp/supportbench")
print(dataset)

# Should show splits/structure
# DatasetDict({
#     'scenarios': Dataset(...)
# })
```

### 3. Verify File Structure

```bash
# List all files in dataset
from huggingface_hub import list_repo_files

files = list_repo_files(
    "givecareapp/supportbench",
    repo_type="dataset"
)
print("\n".join(files))
```

Expected structure:
```
README.md
LICENSE
requirements.txt
CHANGELOG.md
CONTRIBUTING.md
scenarios/tier1/crisis/crisis_detection.json
scenarios/tier1/boundaries/attachment_boundary_test.json
scenarios/tier2/burnout/sandwich_generation_burnout.json
scenarios/tier3/...
rules/base.yaml
rules/ny.yaml
configs/scoring.yaml
```

## Update Dataset

To update after making changes:

```bash
# Pull latest changes
git pull

# Re-run upload script (incremental upload)
python hf_upload_script.py --token $HF_TOKEN
```

Changes are reflected immediately on HuggingFace (no versioning delay).

## Dataset Versioning

HuggingFace datasets support git-like versioning:

```bash
# Create a version tag
huggingface-cli tag givecareapp/supportbench v0.8.5 --repo-type=dataset

# Users can load specific version
from datasets import load_dataset
dataset = load_dataset("givecareapp/supportbench", revision="v0.8.5")
```

## Community Contributions

### Enable Discussions

1. Go to repository settings
2. Enable "Discussions" tab
3. Users can submit:
   - Model evaluation results
   - New scenario suggestions
   - Bug reports

### Add Community Leaderboard

Create a `leaderboard.md` file:

```markdown
# SupportBench Leaderboard

| Model | Overall Score | Crisis Safety | Regulatory Fitness | ... |
|-------|---------------|---------------|-------------------|-----|
| GPT-4 | 0.85 | 0.92 | 0.88 | ... |
| Claude-3.7-Sonnet | 0.87 | 0.95 | 0.89 | ... |

Submit your results via [GitHub PR](https://github.com/givecareapp/givecare-bench) or [Discussions](https://huggingface.co/datasets/givecareapp/supportbench/discussions).
```

Upload to HuggingFace:

```bash
huggingface-cli upload givecareapp/supportbench leaderboard.md --repo-type=dataset
```

### Accept Pull Requests

1. Go to repository settings
2. Enable "Pull Requests"
3. Community can submit:
   - New scenarios
   - Rule updates
   - Documentation improvements

## Security & Privacy

### Confidential Scenarios

The `scenarios/confidential/` directory contains adversarial test cases. These are uploaded but marked as confidential in the dataset card.

**To exclude confidential scenarios:**

Edit `.huggingface_ignore`:
```
scenarios/confidential/
```

### API Keys & Secrets

**NEVER** commit:
- `.env` files
- API tokens
- HuggingFace tokens

Use `.gitignore` and `.huggingface_ignore` to prevent accidental uploads.

## Troubleshooting

### Error: "Repository not found"

**Solution**: Create repository first:
```python
from huggingface_hub import create_repo
create_repo("givecareapp/supportbench", repo_type="dataset", token="hf_xxxxx")
```

### Error: "Token does not have write permissions"

**Solution**: Regenerate token with "Write" permissions at:
https://huggingface.co/settings/tokens

### Error: "File too large"

HuggingFace has a 50GB limit per file. For large datasets:

```bash
# Use git-lfs for large files
git lfs install
git lfs track "*.bin"
```

### Error: "Invalid YAML in README"

**Solution**: Validate YAML frontmatter at:
https://huggingface.co/docs/hub/datasets-cards

Required fields:
```yaml
---
license: mit
task_categories:
- text-generation
language:
- en
---
```

## Resources

- **HuggingFace Datasets Docs**: https://huggingface.co/docs/datasets
- **Dataset Cards Guide**: https://huggingface.co/docs/hub/datasets-cards
- **API Reference**: https://huggingface.co/docs/huggingface_hub
- **SupportBench GitHub**: https://github.com/givecareapp/givecare-bench

## Contact

For upload issues or questions:

- **Email**: ali@givecareapp.com
- **GitHub Issues**: https://github.com/givecareapp/givecare-bench/issues
- **HuggingFace Discussions**: https://huggingface.co/datasets/givecareapp/supportbench/discussions
