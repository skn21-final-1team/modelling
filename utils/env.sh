#!/usr/bin/env bash
# Environment variables for HuggingFace model access and download acceleration
# Usage: source utils/env.sh  (프로젝트 루트에서 실행)

# HuggingFace authentication token (set via RunPod environment variable or .env)
# Create .env with HF_TOKEN=your_token or export HF_TOKEN before sourcing
export HF_TOKEN="${HF_TOKEN:-}"
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"

# Enable hf_transfer for accelerated downloads (multi-connection Rust downloader)
export HF_HUB_ENABLE_HF_TRANSFER=1

# Model cache directory on Network Volume
export HF_HOME=/workspace/.cache/huggingface
