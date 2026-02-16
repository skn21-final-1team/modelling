# Builder Pod Dockerfile 검토 및 개선

- **작업일**: 2026-02-12
- **대상 파일**: `docker/builder/Dockerfile`
- **브랜치**: `feat/add-basemodel`

---

## 배경

RunPod Network Volume 기반 모델 평가 환경에서 builder pod(저비용 CPU)은
LLM 모델 수집(Ollama/HuggingFace)과 평가 파이프라인 준비를 담당한다.
기존 Dockerfile 초안을 `uv` 환경에 맞게 전면 개선하였다.

---

## 기존 문제점

| # | 문제 | 영향 |
|---|------|------|
| 1 | `apt-get update` 2회 중복 호출 | Docker 레이어 낭비, 빌드 시간 증가 |
| 2 | `python3-pip`, `python3-venv` 설치 | uv 사용 시 불필요, 이미지 크기 증가 |
| 3 | `pip3 install`로 패키지 설치 | uv를 설치해놓고 미사용, 일관성 결여 |
| 4 | uv 환경변수 미설정 | 캐시 영속화 불가, Network Volume 활용 미흡 |
| 5 | `ghcr.io/astral-sh/uv:latest` 사용 | 빌드 재현성 보장 불가 |
| 6 | 시스템 Python(3.10) 의존 | 프로젝트 요구사항 `>=3.12` 미충족 |
| 7 | 루트 pyproject.toml과 의존성 미분리 | builder/runtime 의존성 혼재 |

---

## 변경 내역

### Phase 1: Dockerfile uv 전환 (초기 개선)

1. **시스템 패키지 통합** — 2개 `RUN apt-get` → 1개, `python3-pip`/`python3-venv` 제거
2. **uv 버전 고정** — `:latest` → `:0.7`
3. **uv 환경변수 추가** — `UV_CACHE_DIR`, `UV_LINK_MODE`, `UV_COMPILE_BYTECODE`, `UV_PYTHON_INSTALL_DIR`
4. **Python 3.12 관리형 설치** — `uv python install 3.12`
5. **Docker 레이어 순서 최적화** — 변경 빈도 낮은 순서대로 배치

### Phase 2: 전용 pyproject.toml 분리

**목적**: builder pod 의존성을 루트 프로젝트와 완전히 분리

**신규 파일:**
- `docker/builder/pyproject.toml` — builder pod 전용 의존성 선언
- `docker/builder/.python-version` — Python 3.12 명시
- `docker/builder/uv.lock` — `uv lock`으로 78개 패키지 resolve

**Dockerfile 변경:**

- `uv tool install` 2개 → `COPY docker/builder/pyproject.toml docker/builder/uv.lock docker/builder/.python-version` + `uv sync --frozen --no-dev`
- `/app`에 의존성 설치 후 `PATH`에 `/app/.venv/bin` 추가
- `UV_PYTHON_INSTALL_DIR`을 `/opt/uv_python`으로 변경 (이미지 내 고정)

**빌드 방법** (build context = `.`):
```bash
docker build -t builder -f docker/builder/Dockerfile .
```

---

## Builder Pod 라이브러리

| 패키지 | 용도 |
|--------|------|
| `huggingface-hub` | `huggingface-cli`로 모델 다운로드 |
| `transformers` | 모델 구조 검사, 토크나이저, 포맷 변환 |
| `accelerate` | 대용량 모델 효율적 로딩/분할 |
| `safetensors` | `.safetensors` 포맷 지원 |
| `sentencepiece` | LLaMA 계열 등 LLM 토크나이저 |
| `datasets` | HuggingFace 평가 데이터셋 다운로드 |

---

## 검토 결과

- uv를 패키지 관리자로 일관되게 사용 (프로젝트 규칙 `.agent/rules/modelling-rule.md` 준수)
- builder/runtime 의존성 완전 분리 (`pyproject.toml` 각각 독립)
- `uv sync --frozen`으로 lockfile 기반 재현 가능한 설치
- Network Volume 영속화 전략으로 pod 재시작 시 재다운로드 최소화
- 양자화 도구는 미포함 (확인 완료: 모델 수집만 수행, 양자화 불필요)

---

## Docker Hub 배포 및 RunPod Template 연동

### 이미지 내부 파일 구조

```
Docker Image (Docker Hub에 push)
├── /app/pyproject.toml        ← COPY로 이미지에 bake
├── /app/uv.lock               ← COPY로 이미지에 bake
├── /app/.python-version       ← COPY로 이미지에 bake
├── /app/.venv/                ← uv sync로 설치된 패키지
│   └── bin/huggingface-cli    ← PATH에 추가됨
├── /opt/uv_python/            ← Python 3.12 바이너리
├── /bin/uv, /bin/uvx          ← uv 바이너리
└── ollama                     ← Ollama 바이너리

RunPod Network Volume (pod 시작 시 마운트)
└── /workspace/                ← 영속 저장소
    ├── ollama_models/         ← Ollama 모델
    ├── .uv_cache/             ← uv 패키지 캐시
    └── (사용자 스크립트/데이터)
```

**핵심**: 코드·의존성은 이미지에 고정, 모델·데이터는 Network Volume에 영속화

### 배포 순서

```bash
# 1. 빌드 (build context = .)
docker build -t <DOCKERHUB_USER>/modelling-builder:latest \
  -f docker/builder/Dockerfile \
  .

# 2. Docker Hub 로그인 & Push
docker login
docker push <DOCKERHUB_USER>/modelling-builder:latest
```

### RunPod Template Override 설정

| 항목 | 값 |
|------|-----|
| Container Image | `<DOCKERHUB_USER>/modelling-builder:latest` |
| Docker Command | (비워두거나 `bash`) |
| Volume Mount Path | `/workspace` |
| Expose Ports | 필요 시 `11434` (Ollama) |

### Pod 시작 후 사용 예시

```bash
# PATH에 /app/.venv/bin 포함 → 바로 사용 가능
huggingface-cli download meta-llama/Llama-3-8B --local-dir /workspace/models/llama3-8b
ollama pull llama3
python -c "from datasets import load_dataset; ds = load_dataset('squad')"
```
