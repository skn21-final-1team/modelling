"""
HuggingFace model download CLI.

Usage:
    python -m cli.model_pulling --model meta-llama/Llama-3.1-8B-Instruct
    python -m cli.model_pulling --model <model_id> --revision <rev>
"""

import argparse
import asyncio
import sys

from core.config import settings
from services.model_registry_service import ModelRegistryService


def main() -> None:
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

    if not settings.HF_TOKEN:
        print("WARNING: HF_TOKEN not set. Gated models will fail to download.")

    service = ModelRegistryService(
        token=settings.HF_TOKEN,
        cache_dir=settings.HF_HOME,
    )

    print(f"Downloading model: {args.model} (revision: {args.revision})")
    print(f"Cache directory: {settings.HF_HOME}")
    print(f"hf_transfer enabled: {settings.HF_HUB_ENABLE_HF_TRANSFER}")

    try:
        result = asyncio.run(service.pull_model(args.model, args.revision))
        print(f"Model downloaded to: {result['local_path']}")
    except Exception as e:
        print(f"ERROR: Failed to download model: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
