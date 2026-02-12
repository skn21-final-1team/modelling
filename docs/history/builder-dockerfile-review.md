# Builder Pod Dockerfile 검토 및 개선

- **작업일**: 2026-02-12
- **대상 파일**: `.devcontainer/builder/Dockerfile`
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
- `.devcontainer/builder/pyproject.toml` — builder pod 전용 의존성 선언
- `.devcontainer/builder/.python-version` — Python 3.12 명시
- `.devcontainer/builder/uv.lock` — `uv lock`으로 78개 패키지 resolve

**Dockerfile 변경:**
- `uv tool install` 2개 → `COPY pyproject.toml uv.lock .python-version` + `uv sync --frozen --no-dev`
- `/app`에 의존성 설치 후 `PATH`에 `/app/.venv/bin` 추가
- `UV_PYTHON_INSTALL_DIR`을 `/opt/uv_python`으로 변경 (이미지 내 고정)

**빌드 방법** (build context = `.devcontainer/builder/`):
```bash
docker build -t builder -f .devcontainer/builder/Dockerfile .devcontainer/builder/
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
