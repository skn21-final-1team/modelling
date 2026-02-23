#!/usr/bin/env bash
# Environment variables for HuggingFace model access and download acceleration
# Usage: source utils/env.sh  (프로젝트 루트에서 실행)

# .env 파일 로딩 (utils/ 기준 상위 디렉토리, 즉 프로젝트 루트)
_ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../.env"
if [ -f "$_ENV_FILE" ]; then
  set -a
  # shellcheck source=../.env
  source "$_ENV_FILE"
  set +a
fi
unset _ENV_FILE

# HuggingFace authentication token (set via RunPod environment variable or .env)
# Create .env with HF_TOKEN=your_token or export HF_TOKEN before sourcing
export HF_TOKEN="${HF_TOKEN:-}"
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"

# Enable hf_transfer for accelerated downloads (multi-connection Rust downloader)
export HF_HUB_ENABLE_HF_TRANSFER=1

# Model cache directory on Network Volume
export HF_HOME=/workspace/.cache/huggingface

# Derived cache paths (kept in sync with HF_HOME)
export TRANSFORMERS_CACHE="${HF_HOME}/hub"
export HF_DATASETS_CACHE="${HF_HOME}/datasets"
