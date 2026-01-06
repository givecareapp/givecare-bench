#!/usr/bin/env python3
"""
Upload InvisibleBench to HuggingFace Hub.

Usage:
    python benchmark/huggingface/upload_script.py --token YOUR_HF_TOKEN
"""

import argparse
from pathlib import Path

from huggingface_hub import HfApi, create_repo


def upload_invisiblebench(token: str, repo_name: str = "givecareapp/invisiblebench"):
    """Upload InvisibleBench dataset to HuggingFace Hub."""

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
        (base_path.parent / "pyproject.toml", "pyproject.toml"),
        (base_path.parent / "LICENSE", "LICENSE"),
        (base_path / "README.md", "benchmark/README.md"),
        (base_path / "docs/transcript_format.md", "benchmark/transcript_format.md"),
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
            print("   ✅ Uploaded successfully")
        except Exception as e:
            print(f"   ❌ Error uploading {local_path}: {e}")

    print(f"\n{'='*60}")
    print("✅ Dataset upload complete!")
    print(f"{'='*60}")
    print(f"🔗 View at: https://huggingface.co/datasets/{repo_name}")
    print(f"📚 Documentation: https://huggingface.co/datasets/{repo_name}")
    print("\nTest loading with:")
    print('  from datasets import load_dataset')
    print(f'  dataset = load_dataset("{repo_name}")')

def main():
    parser = argparse.ArgumentParser(
        description="Upload InvisibleBench to HuggingFace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload to default repository
  python benchmark/huggingface/upload_script.py --token hf_xxxxx

  # Upload to custom repository
  python benchmark/huggingface/upload_script.py --token hf_xxxxx --repo myorg/mybenchmark

  # Use token from environment variable
  export HF_TOKEN=hf_xxxxx
  python benchmark/huggingface/upload_script.py --token $HF_TOKEN
        """
    )
    parser.add_argument(
        "--token",
        required=True,
        help="HuggingFace API token (get from https://huggingface.co/settings/tokens)"
    )
    parser.add_argument(
        "--repo",
        default="givecareapp/invisiblebench",
        help="Repository name (default: givecareapp/invisiblebench)"
    )

    args = parser.parse_args()

    # Validate token format
    if not args.token.startswith("hf_"):
        print("⚠️  Warning: HuggingFace tokens typically start with 'hf_'")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    upload_invisiblebench(token=args.token, repo_name=args.repo)

if __name__ == "__main__":
    main()
