# ============================================================
# Testing Pod: GPU pod — OpenLLM serving and model evaluation
# RunPod Network Volume (/workspace) 에 모델·캐시를 영속 저장
# ============================================================
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04


ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /workspace

# ── 1. 시스템 패키지 ──────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    git-lfs \
    wget \
    curl \
    openssh-server \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

# ── 2. uv 바이너리 (버전 고정으로 재현 가능한 빌드) ─────────
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

# ── 3. uv 환경 설정 ─────────────────────────────────────────
#   UV_CACHE_DIR          : Network Volume에 패키지 캐시 영속화
#   UV_LINK_MODE          : Network Volume은 별도 파일시스템이라 hardlink 불가 → copy
#   UV_COMPILE_BYTECODE   : .pyc 사전 컴파일로 초기 import 지연 제거
#   UV_PYTHON_INSTALL_DIR : 관리형 Python을 이미지 내부에 고정 설치
ENV UV_CACHE_DIR=/workspace/.uv_cache \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_INSTALL_DIR=/opt/uv_python \
    HF_HOME=/workspace/.cache/huggingface

# ── 4. Python 3.12 설치 (프로젝트 .python-version 과 일치) ──
RUN uv python install 3.12

# ── 5. 의존성 설치 (pyproject.toml + uv.lock 기반) ──────────
COPY docker/testing/pyproject.toml docker/testing/uv.lock docker/testing/.python-version /workspace/
RUN uv sync --frozen --no-dev

ENV PATH="/workspace/.venv/bin:$PATH"

# ── 6. 스크립트 및 설정 파일 ─────────────────────────────────
COPY utils/model-pulling.py utils/model-calling.py utils/model-testing.py /workspace/scripts/
COPY utils/env.sh /workspace/scripts/

# ── 7. SSH 서버 설정 (Remote-SSH / SFTP 접속용) ──────────────
RUN mkdir -p /run/sshd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && ssh-keygen -A \
    && echo "root:root" | chpasswd

EXPOSE 22 8000

CMD bash -c 'if [ -n "$SSH_PASSWORD" ]; then echo "root:$SSH_PASSWORD" | chpasswd; fi && /usr/sbin/sshd && exec tail -f /dev/null'
