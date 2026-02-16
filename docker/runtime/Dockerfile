# ============================================================
# Runtime Pod: FastAPI 서비스 — chunking, embedding, retrieval
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# ── 1. uv 바이너리 (버전 고정으로 재현 가능한 빌드) ─────────
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /usr/local/bin/

# ── 2. 의존성 설치 (레이어 캐싱 최적화: 소스보다 먼저 복사) ──
COPY pyproject.toml uv.lock .python-version /app/
RUN uv sync --frozen --no-dev

# ── 3. 애플리케이션 소스 코드 복사 ────────────────────────────
COPY main.py /app/
COPY core/ /app/core/
COPY chunking/ /app/chunking/
COPY embedding/ /app/embedding/
COPY retriever/ /app/retriever/

# ── 4. venv 의 bin을 PATH에 추가 ─────────────────────────────
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
