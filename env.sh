#!/usr/bin/env bash
# Environment variables for HuggingFace model access and download acceleration
# Usage: source env.sh



# uv가 없으면 설치
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || {
  curl -LsSf https://astral.sh/uv/install.sh | sh
}


# docker storage mount 특성 상 venv가 터지므로 가상환경 밖에 생성 후 접근
# mfs 밖에 venv 생성
if [ ! -d /opt/venvs/modelling ]; then
  python -m venv /opt/venvs/modelling
fi
source /opt/venvs/modelling/bin/activate

# 안전 모드
export UV_LINK_MODE=copy
export UV_CACHE_DIR=/workspace/.uv_cache
export UV_COMPILE_BYTECODE=1
export TMPDIR=/tmp
export VIRTUAL_ENV=/opt/venvs/modelling
export UV_PROJECT_ENVIRONMENT=/opt/venvs/modelling

uv sync

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
