#!/usr/bin/env python3
"""
Upload SupportBench to HuggingFace Hub.

Usage:
    python huggingface/upload_script.py --token YOUR_HF_TOKEN
"""

import argparse
from pathlib import Path
from huggingface_hub import HfApi, create_repo

def upload_supportbench(token: str, repo_name: str = "givecareapp/supportbench"):
    """Upload SupportBench dataset to HuggingFace Hub."""

    api = HfApi(token=token)

    # Create repository
    print(f"Creating repository: {repo_name}")
    try:
        create_repo(
            repo_id=repo_name,
            token=token,
            repo_type="dataset",
            exist_ok=True
        )
        print(f"✅ Repository created/verified: {repo_name}")
    except Exception as e:
        print(f"⚠️  Repository might already exist: {e}")

    # Upload files
    base_path = Path(__file__).parent.parent  # Project root
    hf_path = Path(__file__).parent  # huggingface/ directory

    files_to_upload = [
        (hf_path / "README_HF.md", "README.md"),  # Rename to README.md for HF
        (base_path / "scenarios/", "scenarios/"),
        (base_path / "configs/rules/", "rules/"),
        (base_path / "configs/scoring.yaml", "configs/scoring.yaml"),
        (base_path / "requirements.txt", "requirements.txt"),
        (base_path / "LICENSE", "LICENSE"),
        (base_path / "docs/CHANGELOG.md", "CHANGELOG.md"),  # Include version history
        (base_path / "docs/CONTRIBUTING.md", "CONTRIBUTING.md"),  # Include contribution guidelines
    ]

    for local_path, remote_path in files_to_upload:
        full_local_path = local_path

        if not full_local_path.exists():
            print(f"⚠️  Skipping {local_path} (not found)")
            continue

        print(f"📤 Uploading {local_path} → {remote_path}")

        try:
            if full_local_path.is_dir():
                api.upload_folder(
                    folder_path=str(full_local_path),
                    path_in_repo=remote_path,
                    repo_id=repo_name,
                    repo_type="dataset",
                    token=token
                )
            else:
                api.upload_file(
                    path_or_fileobj=str(full_local_path),
                    path_in_repo=remote_path,
                    repo_id=repo_name,
                    repo_type="dataset",
                    token=token
                )
            print(f"   ✅ Uploaded successfully")
        except Exception as e:
            print(f"   ❌ Error uploading {local_path}: {e}")

    print(f"\n{'='*60}")
    print(f"✅ Dataset upload complete!")
    print(f"{'='*60}")
    print(f"🔗 View at: https://huggingface.co/datasets/{repo_name}")
    print(f"📚 Documentation: https://huggingface.co/datasets/{repo_name}")
    print(f"\nTest loading with:")
    print(f'  from datasets import load_dataset')
    print(f'  dataset = load_dataset("{repo_name}")')

def main():
    parser = argparse.ArgumentParser(
        description="Upload SupportBench to HuggingFace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload to default repository
  python huggingface/upload_script.py --token hf_xxxxx

  # Upload to custom repository
  python huggingface/upload_script.py --token hf_xxxxx --repo myorg/mybenchmark

  # Use token from environment variable
  export HF_TOKEN=hf_xxxxx
  python huggingface/upload_script.py --token $HF_TOKEN
        """
    )
    parser.add_argument(
        "--token",
        required=True,
        help="HuggingFace API token (get from https://huggingface.co/settings/tokens)"
    )
    parser.add_argument(
        "--repo",
        default="givecareapp/supportbench",
        help="Repository name (default: givecareapp/supportbench)"
    )

    args = parser.parse_args()

    # Validate token format
    if not args.token.startswith("hf_"):
        print("⚠️  Warning: HuggingFace tokens typically start with 'hf_'")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    upload_supportbench(token=args.token, repo_name=args.repo)

if __name__ == "__main__":
    main()
