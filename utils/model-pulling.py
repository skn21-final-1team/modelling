"""
Model Pulling Script
Downloads a HuggingFace model to the local cache for use with vLLM.

Usage:
    python utils/model-pulling.py --model <model_id> [--revision <rev>]

Example:
    python utils/model-pulling.py --model meta-llama/Llama-3.1-8B-Instruct
"""

import argparse
import os
import sys

from huggingface_hub import snapshot_download


def main():
    parser = argparse.ArgumentParser(description="Download HuggingFace model")
    parser.add_argument(
        "--model",
        required=True,
        help="HuggingFace model ID (e.g. meta-llama/Llama-3.1-8B-Instruct)",
    )
    parser.add_argument(
        "--revision", default="main", help="Model revision/branch"
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("WARNING: HF_TOKEN not set. Gated models will fail to download.")
        print("Run: source utils/env.sh")

    cache_dir = os.environ.get("HF_HOME", "/workspace/.cache/huggingface")

    print(f"Downloading model: {args.model} (revision: {args.revision})")
    print(f"Cache directory: {cache_dir}")
    print(
        f"hf_transfer enabled: {os.environ.get('HF_HUB_ENABLE_HF_TRANSFER', '0')}"
    )

    try:
        path = snapshot_download(
            repo_id=args.model,
            revision=args.revision,
            cache_dir=cache_dir,
            token=token,
        )
        print(f"Model downloaded to: {path}")
    except Exception as e:
        print(f"ERROR: Failed to download model: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
