# Modelling

> RunPod GPU 인프라 위에서 LLM 서빙, 테스트, 평가, 모니터링을 수행하는 통합 도구

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![vLLM](https://img.shields.io/badge/vLLM-Inference-blueviolet)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![HuggingFace](https://img.shields.io/badge/HuggingFace-FFD21E?logo=huggingface&logoColor=black)

---

## 기능 개요

| 기능 | 설명 | 인터페이스 |
|------|------|-----------|
| **Model Pulling** | HuggingFace Hub에서 모델 다운로드 및 캐시 관리 | CLI / API |
| **Model Testing** | vLLM 서버 상태 점검 및 추론 API 테스트 (5종) | CLI / API |
| **Model Validation** | LLM-as-Judge 기반 모델 품질 평가 (정확성, 관련성, 완전성) | CLI / API |
| **Resource Monitoring** | GPU/CPU/RAM 및 vLLM 서버 메트릭 실시간 수집 | CLI / API |

---

## 프로젝트 구조

```
modelling/
├── api/                          # FastAPI 엔드포인트
│   ├── route.py                  # 라우터 집약
│   └── endpoints/
│       ├── models.py             # 모델 다운로드/캐시 조회
│       ├── testing.py            # vLLM API 테스트
│       ├── validation.py         # LLM-as-Judge 평가
│       └── monitoring.py         # 시스템 모니터링
├── cli/                          # CLI 도구
│   ├── model_pulling.py          # 모델 다운로드
│   ├── model_testing.py          # 추론 테스트
│   ├── model_validation.py       # 모델 평가
│   └── model_monitoring.py       # 리소스 모니터링 대시보드
├── core/
│   └── config.py                 # 환경 설정 (Pydantic Settings)
├── schemas/                      # Pydantic 데이터 모델
│   ├── base.py                   # BaseResponse[T] 제네릭 래퍼
│   ├── model_registry.py         # 모델 관리 스키마
│   ├── testing.py                # 테스트 스키마
│   ├── validation.py             # 평가 스키마
│   └── monitoring.py             # 모니터링 스키마
├── services/                     # 비즈니스 로직
│   ├── model_registry_service.py # HuggingFace 모델 다운로드
│   ├── test_service.py           # vLLM API 테스트 (5종)
│   ├── validation_service.py     # LLM-as-Judge 평가 파이프라인
│   └── monitoring/               # 리소스 모니터링 서브패키지
│       ├── service.py            # 메트릭 수집 오케스트레이션
│       ├── collectors.py         # GPU, CPU, vLLM 메트릭 수집기
│       ├── datamodels.py         # 메트릭 데이터 클래스
│       ├── logger.py             # CSV 로깅
│       └── dashboard.py          # Rich 터미널 대시보드
├── data/                         # 데이터
│   ├── raw/                      # 원본 테스트 데이터
│   ├── processed/                # 가공된 평가 데이터셋
│   └── monitoring/               # 모니터링 로그
├── docker/                       # 컨테이너 설정
│   ├── builder/                  # CPU 전용 (모델 준비)
│   ├── testing/                  # GPU (vLLM + 평가)
│   ├── runtime/                  # FastAPI 서버
│   └── serverless/               # RunPod Serverless 워커
├── markdown/                     # 프로젝트 문서
│   ├── guideline/                # 아키텍처/기술 가이드
│   ├── workhistory/              # 작업 이력
│   └── workoffer/                # 작업 명세
├── main.py                       # FastAPI 앱 진입점
├── pyproject.toml                # 의존성 정의
└── env.sh                        # 환경 초기화 스크립트
```

---

## Quick Start

### 1. 환경 설정

```bash
source env.sh
```

`env.sh`가 수행하는 작업:
- [x] `uv` 패키지 매니저 설치 (없을 경우)
- [x] 가상환경 생성 (`/opt/venvs/modelling`)
- [x] `uv sync`로 의존성 설치
- [x] `.env` 파일 로드
- [x] HuggingFace 캐시 경로 설정

### 2. `.env` 파일 작성

```bash
HF_TOKEN=hf_your_token_here
```

### 3. FastAPI 서버 실행

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 4. 헬스 체크

```bash
curl http://localhost:8080/health
# {"status": "ok"}
```

---

## CLI 사용법

### Model Pulling

HuggingFace Hub에서 모델을 다운로드한다.

```bash
python -m cli.model_pulling --model meta-llama/Llama-3.1-8B-Instruct
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--model` | HuggingFace 모델 ID | (필수) |
| `--revision` | 모델 리비전 | `main` |

### Model Testing

vLLM 서버에 5종 테스트를 실행한다.

```bash
python -m cli.model_testing --base-url http://localhost:8000
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--base-url` | vLLM 서버 URL | `http://localhost:8000` |

**테스트 항목:**

- [x] Health Check — 서버 가용성
- [x] Models — 모델 목록 조회
- [x] Chat Completion — 채팅 API + 응답 지연시간
- [x] Text Completion — 텍스트 완성 API
- [x] Streaming — SSE 스트리밍 + TTFT(Time-To-First-Token)

### Model Validation

LLM-as-Judge 방식으로 모델 품질을 평가한다.

```bash
python -m cli.model_validation --base-url http://localhost:8000 --sample-size 10
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--base-url` | vLLM 서버 URL | `http://localhost:8000` |
| `--sample-size` | 평가 샘플 수 (0 = 전체) | `0` |
| `--csv-path` | 평가 데이터셋 경로 | `data/processed/processed_v3.csv` |

**평가 지표 (1~5점):**

| 지표 | 설명 |
|------|------|
| Correctness | 답변의 사실적 정확성 |
| Relevance | 질문과의 관련성 |
| Completeness | 답변의 완전성 |

### Resource Monitoring

GPU, CPU, RAM 및 vLLM 메트릭을 실시간 대시보드로 확인한다.

```bash
python -m cli.model_monitoring --interval 2 --port 8000
```

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--interval` | 수집 주기 (초) | `2` |
| `--port` | vLLM 서버 포트 | `8000` |
| `--no-dashboard` | 대시보드 비활성화 | `false` |
| `--no-log` | CSV 로깅 비활성화 | `false` |
| `--duration` | 자동 종료 시간 (초) | `3600` |

**수집 메트릭:**

| 카테고리 | 메트릭 |
|----------|--------|
| GPU | 사용률, VRAM, 온도, 전력 |
| System | CPU 사용률, RAM, 코어 수 |
| vLLM | 요청 수, KV Cache 사용률, 처리량 (tok/s) |

---

## API Endpoints

모든 응답은 `BaseResponse[T]` 래퍼 형식을 따른다:

```json
{
  "status": "success",
  "data": { ... },
  "message": ""
}
```

### 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/health` | 헬스 체크 |
| `POST` | `/api/models/pull` | 모델 다운로드 |
| `GET` | `/api/models/cached` | 캐시된 모델 목록 |
| `POST` | `/api/testing/run-all` | vLLM 테스트 전체 실행 |
| `POST` | `/api/validation/run` | LLM-as-Judge 평가 실행 |
| `GET` | `/api/monitoring/snapshot` | 시스템 메트릭 스냅샷 |

### 요청/응답 예시

**모델 다운로드**

```bash
curl -X POST http://localhost:8080/api/models/pull \
  -H "Content-Type: application/json" \
  -d '{"model_id": "meta-llama/Llama-3.1-8B-Instruct", "revision": "main"}'
```

```json
{
  "status": "success",
  "data": {
    "model_id": "meta-llama/Llama-3.1-8B-Instruct",
    "revision": "main",
    "local_path": "/workspace/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B-Instruct",
    "status": "completed"
  },
  "message": ""
}
```

**vLLM 테스트 실행**

```bash
curl -X POST http://localhost:8080/api/testing/run-all \
  -H "Content-Type: application/json" \
  -d '{"base_url": "http://localhost:8000"}'
```

**모니터링 스냅샷**

```bash
curl http://localhost:8080/api/monitoring/snapshot
```

```json
{
  "status": "success",
  "data": {
    "gpu": {
      "name": "NVIDIA A100-SXM4-80GB",
      "utilization_pct": 45.2,
      "vram_used_gb": 32.1,
      "vram_total_gb": 80.0,
      "temperature_c": 52,
      "power_w": 180.5
    },
    "system": {
      "cpu_pct": 12.3,
      "ram_used_gb": 24.5,
      "ram_total_gb": 128.0,
      "cpu_cores": 32
    },
    "vllm": {
      "online": true,
      "model": "meta-llama/Llama-3.1-8B-Instruct",
      "requests_running": 2,
      "requests_waiting": 0,
      "gpu_cache_pct": 15.3,
      "prompt_tps": 1250.0,
      "gen_tps": 85.2
    }
  },
  "message": ""
}
```

---

## Docker

### Pod 구성

| Pod | Base Image | 용도 | 포트 |
|-----|-----------|------|------|
| **Builder** | `ubuntu:22.04` | 모델 준비, 데이터 수집 (CPU 전용) | 22 (SSH) |
| **Testing** | `nvidia/cuda:12.4.1-runtime-ubuntu22.04` | vLLM 서빙 + 모델 평가 (GPU) | 22, 8000 |
| **Runtime** | `python:3.12-slim` | FastAPI 서버 | 8080 |
| **Serverless** | `runpod/worker-v1-vllm:v2.14.0` | RunPod Serverless vLLM 워커 | - |

### Serverless 워커

RunPod Serverless 환경에서 vLLM 추론을 수행하는 워커 이미지다. 빌드 시 모델을 이미지 내부에 사전 다운로드하여 콜드 스타트를 최소화한다.

**기본 설정:**

| 환경 변수 | 값 | 설명 |
|----------|-----|------|
| `MODEL_NAME` | `LGAI-EXAONE/EXAONE-4.0-32B-FP8` | 서빙할 모델 |
| `MAX_MODEL_LEN` | `8192` | 최대 컨텍스트 길이 |
| `TENSOR_PARALLEL_SIZE` | `1` | 텐서 병렬화 GPU 수 |
| `GPU_MEMORY_UTILIZATION` | `0.90` | GPU 메모리 사용 비율 |

**빌드:**

```bash
docker build \
  --secret id=HF_TOKEN,env=HF_TOKEN \
  -t modelling-serverless \
  -f docker/serverless/Dockerfile .
```

> **Note:** Gated 모델 다운로드를 위해 `HF_TOKEN`을 Docker BuildKit secret으로 전달한다. 토큰은 이미지에 포함되지 않는다.

### 기타 Pod 빌드

```bash
# Builder Pod
docker build -t modelling-builder -f docker/builder/Dockerfile .

# Testing Pod (GPU)
docker build -t modelling-testing -f docker/testing/Dockerfile .

# Runtime Pod
docker build -t modelling-runtime -f docker/runtime/Dockerfile .
```

> **Note:** Testing Pod는 Network Volume(`/workspace`)에 마운트하여 모델 캐시와 패키지 캐시를 영속화한다.

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `HF_TOKEN` | HuggingFace 액세스 토큰 | (필수) |
| `HF_HOME` | HuggingFace 캐시 디렉토리 | `/workspace/.cache/huggingface` |
| `HF_HUB_ENABLE_HF_TRANSFER` | 고속 다운로드 활성화 | `1` |
| `VLLM_BASE_URL` | vLLM 서버 URL | `http://localhost:8000` |
| `UV_LINK_MODE` | uv 링크 모드 (Network Volume 호환) | `copy` |
| `UV_CACHE_DIR` | uv 패키지 캐시 경로 | `/workspace/.uv_cache` |
| `DEBUG` | 디버그 모드 | `false` |

---

## 아키텍처

```
API Endpoints (HTTP 라우팅, 유효성 검증)
    │
    ▼
Services (비즈니스 로직, 외부 API 호출)
    │
    ▼
Schemas (Pydantic 모델, 데이터 검증)
    │
    ▼
Configuration (환경 기반 설정)
```

- **데이터베이스 없음** — 모든 데이터는 외부 API(vLLM, HuggingFace Hub) 또는 파일 I/O를 통해 흐른다
- **스키마 기반 서비스** — 서비스는 Pydantic 스키마를 입출력으로 사용한다
- **CLI/API 공유** — 동일한 서비스 레이어를 CLI와 API 양쪽에서 호출한다
- **비동기 설계** — `async/await` 패턴, 블로킹 I/O는 `asyncio.to_thread()`로 래핑

---

## Dependencies

| 패키지 | 용도 |
|--------|------|
| `vllm` | LLM 추론 엔진 |
| `transformers` | 모델 로딩 |
| `huggingface-hub` | 모델 레지스트리 |
| `hf-transfer` | 고속 모델 다운로드 |
| `safetensors` | 모델 직렬화 |
| `sentencepiece` | 토크나이저 |
| `datasets` | 데이터셋 로딩 |
| `psutil` | 시스템 모니터링 |
| `nvidia-ml-py` | GPU 모니터링 (NVML) |
| `rich` | 터미널 대시보드 UI |

---

## 문서

### 가이드라인

| 문서 | 설명 |
|------|------|
| [llm-serve-architecture.md](markdown/guideline/llm-serve-architecture.md) | 아키텍처 분석 및 설계 패턴 |
| [fastapi-server-guide.md](markdown/guideline/fastapi-server-guide.md) | FastAPI 서버 구축 가이드 |
| [tokenizing.md](markdown/guideline/tokenizing.md) | LLM 토큰 샘플링 파이프라인 가이드 |
| [runpod.md](markdown/guideline/runpod.md) | RunPod 배포 가이드 |

### 작업 이력

| 문서 | 설명 |
|------|------|
| [project-restructuring.md](markdown/workhistory/project-restructuring.md) | utils/ → 레이어드 아키텍처 마이그레이션 |
| [llm-serve-architecture-output.md](markdown/workhistory/llm-serve-architecture-output.md) | 아키텍처 리팩토링 변경 이력 |
| [resource-monitoring.md](markdown/workhistory/resource-monitoring.md) | 리소스 모니터링 구현 상세 |
| [data_processing.md](markdown/workhistory/data_processing.md) | 데이터 파이프라인 (v1→v3) 진화 과정 |
| [migration.md](markdown/workhistory/migration.md) | inference → chat 네이밍 마이그레이션 |
