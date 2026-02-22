#!/usr/bin/env bash
# Environment variables for HuggingFace model access and download acceleration
# Usage: source /app/scripts/env.sh

# HuggingFace authentication token (set via RunPod environment variable or manually)
export HF_TOKEN="${HF_TOKEN:-}"
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"

# Enable hf_transfer for accelerated downloads (multi-connection Rust downloader)
export HF_HUB_ENABLE_HF_TRANSFER=1

# Model cache directory on Network Volume
export HF_HOME=/workspace/.cache/huggingface
