#!/usr/bin/env bash
# Environment variables for HuggingFace model access and download acceleration
# Usage: source env.sh

_ENV_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.env"
if [ -f "$_ENV_FILE" ]; then
  set -a
  # shellcheck source=./.env
  source "$_ENV_FILE"
  set +a
fi
unset _ENV_FILE

export HF_TOKEN="${HF_TOKEN:-}"
export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"

export HF_HUB_ENABLE_HF_TRANSFER=1

export HF_HOME=/workspace/.cache/huggingface

export TRANSFORMERS_CACHE="${HF_HOME}/hub"
export HF_DATASETS_CACHE="${HF_HOME}/datasets"
