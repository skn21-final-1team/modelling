# ============================================================
# Builder Pod: 저비용 CPU pod — 모델 수집 및 평가 파이프라인 준비
# RunPod Network Volume (/workspace) 에 모델·캐시·스크립트를 영속 저장
# ============================================================
FROM runpod/base:0.7.4-dev-ubuntu2204

# ── 1. 시스템 의존성 (단일 레이어) ───────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    git-lfs \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── 2. Ollama 설치 (LLM 서버 및 모델 관리) ──────────────────
RUN curl -fsSL https://ollama.com/install.sh | sh

# ── 3. uv 바이너리 (버전 고정으로 재현 가능한 빌드) ─────────
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

# ── 4. uv 환경 설정 ─────────────────────────────────────────
#   UV_CACHE_DIR          : Network Volume에 패키지 캐시 영속화
#   UV_LINK_MODE          : Network Volume은 별도 파일시스템이라 hardlink 불가 → copy
#   UV_COMPILE_BYTECODE   : .pyc 사전 컴파일로 초기 import 지연 제거
#   UV_PYTHON_INSTALL_DIR : 관리형 Python을 이미지 내부에 고정 설치
ENV UV_CACHE_DIR=/workspace/.uv_cache \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_INSTALL_DIR=/opt/uv_python

# ── 5. Python 3.12 설치 (프로젝트 .python-version 과 일치) ──
RUN uv python install 3.12

# ── 6. 의존성 설치 (pyproject.toml + uv.lock 기반) ──────────
COPY pyproject.toml uv.lock .python-version /app/
WORKDIR /app
RUN uv sync --frozen --no-dev

# ── 7. Ollama 모델 저장 경로 → Network Volume ───────────────
ENV OLLAMA_MODELS=/workspace/ollama_models

# ── 8. venv 의 bin을 PATH에 추가 → huggingface-cli 등 직접 사용
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /workspace

CMD ["bash"]
