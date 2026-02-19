# ============================================================
# Builder Pod: 저비용 CPU pod — 모델 수집 및 평가 파이프라인 준비
# RunPod Network Volume (/workspace) 에 모델·캐시·스크립트를 영속 저장
# ============================================================
FROM ubuntu:22.04


ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    git-lfs \
    wget \
    curl \
    openssh-server \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*
    

# ── 2. Ollama (CPU 전용 — CUDA/ROCm/Vulkan 라이브러리 제외) ───
#   /bin/ollama          : 바이너리 (38MB)
#   /usr/lib/ollama/lib* : CPU runner + base (~6MB)
#   제외: cuda_v12(2.4GB), cuda_v13(932MB), mlx_cuda_v13(1.5GB), vulkan(55MB)
COPY --from=ollama/ollama:0.16.1 /bin/ollama /usr/local/bin/ollama
COPY --from=ollama/ollama:0.16.1 /usr/lib/ollama/libggml-base.so* /usr/lib/ollama/
COPY --from=ollama/ollama:0.16.1 /usr/lib/ollama/libggml-cpu-*.so /usr/lib/ollama/

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
    UV_PYTHON_INSTALL_DIR=/opt/uv_python \
    OLLAMA_MODELS=/workspace/ollama_models \
    HF_HOME=/workspace/.cache/huggingface

# ── 5. Python 3.12 설치 (프로젝트 .python-version 과 일치) ──
RUN uv python install 3.12

# ── 6. 의존성 설치 (pyproject.toml + uv.lock 기반) ──────────
COPY docker/builder/pyproject.toml docker/builder/uv.lock docker/builder/.python-version /app/
WORKDIR /app
RUN uv sync --frozen --no-dev


ENV PATH="/app/.venv/bin:$PATH"

# ── 7. SSH 서버 설정 (Remote-SSH / SFTP 접속용) ──────────────
RUN mkdir -p /run/sshd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && ssh-keygen -A \
    && echo "root:root" | chpasswd

EXPOSE 22

WORKDIR /workspace

CMD bash -c 'if [ -n "$SSH_PASSWORD" ]; then echo "root:$SSH_PASSWORD" | chpasswd; fi && /usr/sbin/sshd && exec tail -f /dev/null'
