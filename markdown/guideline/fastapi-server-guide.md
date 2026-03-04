# FastAPI 백엔드 서버 가이드라인

OpenLLM 서빙을 위한 FastAPI 백엔드 서버 구축, API 엔드포인트 접속, 환경 설정, CLI 도구 사용법을 다루는 종합 가이드.

---

## 1. 사전 조건

| 항목 | 값 |
|---|---|
| Python | 3.12+ |
| 패키지 매니저 | uv |
| GPU | RTX 5090 이상 권장 (vLLM 서빙 시) |
| Docker 이미지 | `docker/testing/Dockerfile` (GPU Pod), `docker/runtime/Dockerfile` (API 서버) |
| 프로젝트 루트 | `/workspace/modelling` (RunPod) 또는 로컬 클론 경로 |

> FastAPI 서버 단독 실행 시에는 GPU가 필수는 아닙니다. 추론/테스트/평가 엔드포인트는 별도의 vLLM 서버에 HTTP로 요청을 전달합니다.

---

## 2. 환경 설정

### 2-1. `.env` 파일 준비

프로젝트 루트에 `.env` 파일을 생성합니다.

```bash
# /workspace/modelling/.env

# [필수] HuggingFace 인증 토큰 (gated 모델 다운로드에 필요)
HF_TOKEN=hf_YOUR_TOKEN_HERE

# [선택] 아래 항목은 기본값이 있으므로, 변경이 필요한 경우에만 기입
# DATABASE_URL=sqlite:///./dev.db
# VLLM_BASE_URL=http://localhost:8000
# DEBUG=false
```

> `.env`는 `.gitignore`에 등록되어 있어 원격 저장소에 커밋되지 않습니다.

### 2-2. Shell 환경변수 적용

HuggingFace 관련 캐시 경로와 고속 다운로더를 활성화합니다.

```bash
source env.sh
```

`env.sh`가 export하는 변수:

| 변수 | 값 | 설명 |
|---|---|---|
| `HF_TOKEN` | `.env` 또는 시스템 환경변수 | HuggingFace 인증 토큰 |
| `HUGGING_FACE_HUB_TOKEN` | `HF_TOKEN`과 동일 | 구버전 라이브러리 호환 |
| `HF_HUB_ENABLE_HF_TRANSFER` | `1` | Rust 기반 고속 다운로더 활성화 |
| `HF_HOME` | `/workspace/.cache/huggingface` | 모델 캐시 루트 |
| `TRANSFORMERS_CACHE` | `$HF_HOME/hub` | transformers 모델 캐시 |
| `HF_DATASETS_CACHE` | `$HF_HOME/datasets` | datasets 캐시 |

> RunPod에서 Pod 환경변수로 `HF_TOKEN`을 주입한 경우, `.env` 없이도 동작합니다.

### 2-3. Python Settings (`core/config.py`)

모든 환경변수는 `core/config.py`의 `Settings` 클래스로 접근합니다.

```python
from core.config import settings

print(settings.VLLM_BASE_URL)   # http://localhost:8000
print(settings.HF_TOKEN)        # hf_...
```

설정값 우선순위: `환경변수 (export) > .env 파일 > 클래스 기본값`

| 필드 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `DATABASE_URL` | `str` | `sqlite:///./dev.db` | DB 연결 문자열 |
| `PROJECT_NAME` | `str` | `Modelling Service` | FastAPI 앱 이름 |
| `DEBUG` | `bool` | `False` | 디버그 모드 |
| `HF_TOKEN` | `str` | `""` | HuggingFace 인증 토큰 |
| `HF_HOME` | `str` | `/workspace/.cache/huggingface` | HF 캐시 디렉토리 |
| `HF_HUB_ENABLE_HF_TRANSFER` | `bool` | `True` | 고속 다운로더 |
| `VLLM_BASE_URL` | `str` | `http://localhost:8000` | vLLM 서버 주소 |
| `MONITORING_LOG_DIR` | `str` | `data/monitoring` | 모니터링 CSV 경로 |
| `RAW_DATA_DIR` | `str` | `data/raw` | 원본 데이터 경로 |
| `PROCESSED_DATA_DIR` | `str` | `data/processed` | 전처리 데이터 경로 |

---

## 3. 프로젝트 구조

```
modelling/
├── main.py                          # FastAPI 앱 (lifespan + 라우터 등록)
├── env.sh                           # Shell 환경변수 설정
├── pyproject.toml                   # 의존성 관리
│
├── api/                             # API 라우트 레이어
│   ├── route.py                     # 라우터 통합 (include_router)
│   └── endpoints/                   # 엔드포인트 구현
│       ├── inference.py             # 추론 (chat, models)
│       ├── models.py                # 모델 관리 (pull, cached)
│       ├── testing.py               # API 테스트 (run-all)
│       ├── validation.py            # LLM-as-Judge 평가 (run)
│       └── monitoring.py            # 리소스 모니터링 (snapshot)
│
├── schemas/                         # DTO (Pydantic 모델)
│   ├── base.py                      # BaseResponse[T] 공통 래퍼
│   ├── inference.py                 # ChatRequest, InferenceResponse
│   ├── model_registry.py            # ModelPullRequest/Response, CachedModelResponse
│   ├── testing.py                   # TestRequest, TestSuiteResponse
│   ├── validation.py                # ValidationRequest, ValidationSummaryResponse
│   └── monitoring.py                # SnapshotResponse, GpuResponse 등
│
├── services/                        # 비즈니스 로직
│   ├── inference_service.py         # InferenceService (vLLM 추론)
│   ├── model_registry_service.py    # ModelRegistryService (HF 모델 관리)
│   ├── test_service.py              # TestService (API 테스트)
│   ├── validation_service.py        # ValidationService (LLM-as-Judge)
│   ├── crawler_service.py           # CrawlerService (웹 크롤링)
│   ├── data_processor_service.py    # DataProcessorService (데이터 전처리)
│   └── monitoring/                  # 모니터링 서브패키지
│       ├── service.py               # MonitoringService
│       ├── collectors.py            # GPU/CPU/vLLM 메트릭 수집기
│       ├── datamodels.py            # 메트릭 dataclass
│       ├── logger.py                # CSV 로거
│       └── dashboard.py             # Rich 터미널 대시보드
│
├── cli/                             # CLI 진입점 (Docker Pod 독립 실행)
│   ├── model_pulling.py             # 모델 다운로드
│   ├── model_testing.py             # API 테스트
│   ├── model_validation.py          # 모델 평가
│   └── model_monitoring.py          # 리소스 모니터링
│
├── core/                            # 설정
│   └── config.py                    # Settings (Pydantic BaseSettings)
│
├── db/                              # DB 연결
│   └── session.py                   # SQLAlchemy 세션 관리
│
├── data/                            # 데이터 아티팩트
│   ├── raw/                         # 크롤링 원본
│   ├── processed/                   # 전처리 데이터 + 평가 결과
│   └── monitoring/                  # 모니터링 CSV 로그
│
└── docker/                          # 컨테이너
    ├── builder/                     # CPU 빌더 Pod
    ├── runtime/                     # API 런타임 Pod
    └── testing/                     # GPU 테스팅 Pod
```

### 레이어 책임

```
HTTP 요청 → api/endpoints/ → services/ → 외부 I/O (vLLM API, HF Hub, 파일시스템)
                  │                │
              schemas/        core/config.py
```

| 레이어 | 책임 | 반환값 |
|---|---|---|
| `api/endpoints/` | HTTP 요청 처리, 응답 DTO 구성 | `BaseResponse[T]` |
| `services/` | 비즈니스 로직, 외부 I/O | 원시 데이터 (`dict`, `str`, `tuple`) |
| `schemas/` | DTO 정의 (Request/Response) | - |

> `services/`는 `schemas/`를 import하지 않습니다. 서비스는 원시 데이터만 반환하고, DTO 변환은 엔드포인트에서 수행합니다.

---

## 4. 서버 실행

### 4-1. 의존성 설치

```bash
cd /workspace/modelling
uv sync --frozen --no-dev
```

### 4-2. 모델 다운로드

```bash
python -m cli.model_pulling --model LGAI-EXAONE/EXAONE-4.0-32B-FP8
```

### 4-3. vLLM 서버 기동

```bash
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 4096 \
    --enforce-eager \
    --gpu-memory-utilization 0.95 &
```

서버가 `Application startup complete.` 로그를 출력할 때까지 대기합니다 (약 1~3분).

**기동 로그 예시:**

```
INFO 03-03 07:21:13 [__init__.py:216] Automatically detected platform cuda.
(APIServer pid=11956) INFO 03-03 07:21:17 [api_server.py:1839] vLLM API server version 0.11.0
(APIServer pid=11956) INFO 03-03 07:21:18 [model.py:547] Resolved architecture: Exaone4ForCausalLM
(APIServer pid=11956) INFO 03-03 07:21:18 [model.py:1510] Using max model len 4096
(APIServer pid=11956) INFO 03-03 07:21:18 [scheduler.py:205] Chunked prefill is enabled with max_num_batched_tokens=2048.
(APIServer pid=11956) INFO 03-03 07:21:18 [__init__.py:381] Cudagraph is disabled under eager mode

(EngineCore_DP0 pid=12117) INFO 03-03 07:21:25 [core.py:77] Initializing a V1 LLM engine (v0.11.0) with config:
  model='LGAI-EXAONE/EXAONE-4.0-32B-FP8', dtype=torch.bfloat16, max_seq_len=4096,
  tensor_parallel_size=1, quantization=fp8, enforce_eager=True, enable_prefix_caching=True

(EngineCore_DP0 pid=12117) INFO 03-03 07:21:27 [gpu_model_runner.py:2602] Starting to load model LGAI-EXAONE/EXAONE-4.0-32B-FP8...
(EngineCore_DP0 pid=12117) INFO 03-03 07:21:27 [cuda.py:366] Using Flash Attention backend on V1 engine.

Loading safetensors checkpoint shards: 100% Completed | 7/7 [00:06<00:00, 1.03it/s]

(EngineCore_DP0 pid=12117) INFO 03-03 07:21:35 [default_loader.py:267] Loading weights took 7.08 seconds
(EngineCore_DP0 pid=12117) INFO 03-03 07:21:36 [gpu_model_runner.py:2653] Model loading took 30.9891 GiB and 7.776333 seconds
(EngineCore_DP0 pid=12117) INFO 03-03 07:21:37 [gpu_worker.py:298] Available KV cache memory: 10.31 GiB
(EngineCore_DP0 pid=12117) INFO 03-03 07:21:37 [kv_cache_utils.py:1087] GPU KV cache size: 42,224 tokens
(EngineCore_DP0 pid=12117) INFO 03-03 07:21:37 [kv_cache_utils.py:1091] Maximum concurrency for 4,096 tokens per request: 10.28x
(EngineCore_DP0 pid=12117) INFO 03-03 07:21:37 [core.py:210] init engine (profile, create kv cache, warmup model) took 1.94 seconds

(APIServer pid=11956) INFO 03-03 07:21:39 [api_server.py:1912] Starting vLLM API server 0 on http://0.0.0.0:8000
(APIServer pid=11956) INFO:     Started server process [11956]
(APIServer pid=11956) INFO:     Waiting for application startup.
(APIServer pid=11956) INFO:     Application startup complete.   # ← 이 로그가 나오면 서버 준비 완료
```

> **주요 확인 포인트:**
> - `Resolved architecture: Exaone4ForCausalLM` — 모델 아키텍처 인식 확인
> - `Model loading took 30.9891 GiB` — VRAM 사용량 확인 (L40S 48GB 기준)
> - `GPU KV cache size: 42,224 tokens` — 추론용 KV cache 할당량
> - `Maximum concurrency for 4,096 tokens per request: 10.28x` — 동시 처리 가능 요청 수
> - `Application startup complete.` — 서버 준비 완료 (이 로그 이후 요청 가능)

> **참고:** `Using default W8A8 Block FP8 kernel config. Performance might be sub-optimal!` 경고는 FP8 최적화 설정 파일이 없는 경우 출력되며, 정상 동작에는 영향이 없습니다.

| 옵션 | 값 | 설명 |
|---|---|---|
| `--cpu-offload-gb` | `4` | 가중치 4 GB를 CPU RAM으로 오프로드 |
| `--max-model-len` | `4096` | 최대 컨텍스트 길이 (KV cache 절약) |
| `--enforce-eager` | - | CUDA graph 비활성화 (메모리 절약) |
| `--gpu-memory-utilization` | `0.95` | GPU 메모리 사용 비율 상향 |

### 4-4. FastAPI 서버 기동

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

| 옵션 | 설명 |
|---|---|
| `--host 0.0.0.0` | 외부 접속 허용 |
| `--port 8080` | FastAPI 서버 포트 (vLLM 8000과 구분) |
| `--reload` | 코드 변경 시 자동 재시작 (개발 모드) |

### 4-5. Swagger UI 접근

브라우저에서 아래 URL로 전체 API 문서를 확인합니다.

```
http://localhost:8080/docs
```

---

## 5. API 엔드포인트 명세

### 엔드포인트 요약

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 서버 헬스체크 |
| POST | `/api/inference/chat` | vLLM 채팅 완성 (TTFT, 처리량 측정) |
| GET | `/api/inference/models` | 사용 가능 모델 목록 |
| POST | `/api/models/pull` | HuggingFace 모델 다운로드 |
| GET | `/api/models/cached` | 캐시된 모델 목록 |
| POST | `/api/testing/run-all` | vLLM API 5종 자동 테스트 |
| POST | `/api/validation/run` | LLM-as-Judge 모델 평가 |
| GET | `/api/monitoring/snapshot` | GPU/CPU/RAM/vLLM 리소스 스냅샷 |

---

### 5.0 Health Check

서버 가동 상태를 확인합니다.

```
GET /health
```

**Response:**

```json
{
  "status": "ok"
}
```

**curl:**

```bash
curl http://localhost:8080/health
```

---

### 5.1 추론 (Inference)

#### POST `/api/inference/chat`

vLLM 서버에 채팅 완성 요청을 보내고, TTFT(Time To First Token)와 처리량을 측정합니다.

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `prompt` | `str` | O | - | 입력 프롬프트 |
| `model` | `str \| null` | X | `null` (자동 감지) | 모델 이름 |
| `max_tokens` | `int` | X | `256` | 최대 생성 토큰 수 |
| `temperature` | `float` | X | `0.7` | 샘플링 온도 |
| `system_prompt` | `str \| null` | X | `null` | 시스템 프롬프트 |

```json
{
  "prompt": "인공지능이란 무엇인가요?",
  "model": null,
  "max_tokens": 256,
  "temperature": 0.7,
  "system_prompt": null
}
```

**Response Body:**

```json
{
  "status": "success",
  "data": {
    "content": "인공지능(AI)은 인간의 학습, 추론, 인지 능력을 컴퓨터로 구현한 기술입니다...",
    "model": "LGAI-EXAONE/EXAONE-4.0-32B-FP8",
    "ttft_ms": 142.5,
    "total_s": 3.82,
    "completion_tokens": 87,
    "throughput_tps": 22.77
  },
  "message": ""
}
```

| 응답 필드 | 설명 |
|---|---|
| `content` | 생성된 텍스트 |
| `model` | 사용된 모델 ID |
| `ttft_ms` | 첫 번째 토큰까지 걸린 시간 (ms) |
| `total_s` | 전체 소요 시간 (초) |
| `completion_tokens` | 생성된 토큰 수 |
| `throughput_tps` | 처리량 (tokens/sec) |

**curl:**

```bash
curl -X POST http://localhost:8080/api/inference/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "인공지능이란 무엇인가요?",
    "max_tokens": 256,
    "temperature": 0.7
  }'
```

#### GET `/api/inference/models`

vLLM 서버에 로드된 모델 목록을 조회합니다.

**Response Body:**

```json
{
  "status": "success",
  "data": ["LGAI-EXAONE/EXAONE-4.0-32B-FP8"],
  "message": ""
}
```

**curl:**

```bash
curl http://localhost:8080/api/inference/models
```

---

### 5.2 모델 관리 (Model Registry)

#### POST `/api/models/pull`

HuggingFace 모델을 로컬 캐시에 다운로드합니다.

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `model_id` | `str` | O | - | HuggingFace 모델 ID |
| `revision` | `str` | X | `"main"` | 브랜치/태그 |

```json
{
  "model_id": "LGAI-EXAONE/EXAONE-4.0-32B-FP8",
  "revision": "main"
}
```

**Response Body:**

```json
{
  "status": "success",
  "data": {
    "model_id": "LGAI-EXAONE/EXAONE-4.0-32B-FP8",
    "revision": "main",
    "local_path": "/workspace/.cache/huggingface/hub/models--LGAI-EXAONE--EXAONE-4.0-32B-FP8/snapshots/abc123",
    "status": "downloaded"
  },
  "message": ""
}
```

**curl:**

```bash
curl -X POST http://localhost:8080/api/models/pull \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "LGAI-EXAONE/EXAONE-4.0-32B-FP8"
  }'
```

> 모델 다운로드는 수 분~수십 분이 소요될 수 있습니다. `HF_TOKEN`이 설정되지 않으면 gated 모델 다운로드가 실패합니다.

#### GET `/api/models/cached`

로컬에 캐시된 모델 목록을 조회합니다.

**Response Body:**

```json
{
  "status": "success",
  "data": [
    {
      "model_id": "LGAI-EXAONE/EXAONE-4.0-32B-FP8",
      "size_gb": 31.2,
      "path": "/workspace/.cache/huggingface/hub/models--LGAI-EXAONE--EXAONE-4.0-32B-FP8"
    }
  ],
  "message": ""
}
```

**curl:**

```bash
curl http://localhost:8080/api/models/cached
```

---

### 5.3 테스트 (Testing)

#### POST `/api/testing/run-all`

vLLM 서버에 대해 5종 API 테스트를 실행합니다.

**테스트 항목:**

1. `health` — `/health` 엔드포인트 확인
2. `models` — `/v1/models` 모델 목록 조회
3. `chat_completion` — `/v1/chat/completions` 채팅 완성
4. `completion` — `/v1/completions` 텍스트 완성
5. `streaming` — 스트리밍 채팅 완성 (TTFT 측정)

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `base_url` | `str` | X | `"http://localhost:8000"` | vLLM 서버 주소 |

```json
{
  "base_url": "http://localhost:8000"
}
```

> Request Body를 생략하면 `core/config.py`의 `VLLM_BASE_URL` 기본값을 사용합니다.

**Response Body:**

```json
{
  "status": "success",
  "data": {
    "base_url": "http://localhost:8000",
    "model": "LGAI-EXAONE/EXAONE-4.0-32B-FP8",
    "total": 5,
    "passed": 5,
    "failed": 0,
    "results": [
      {
        "name": "health",
        "passed": true,
        "latency_s": 0.012,
        "detail": null,
        "error": null
      },
      {
        "name": "models",
        "passed": true,
        "latency_s": 0.015,
        "detail": {"model": "LGAI-EXAONE/EXAONE-4.0-32B-FP8"},
        "error": null
      },
      {
        "name": "chat_completion",
        "passed": true,
        "latency_s": 1.23,
        "detail": {"content": "Hello!"},
        "error": null
      },
      {
        "name": "completion",
        "passed": true,
        "latency_s": 0.95,
        "detail": null,
        "error": null
      },
      {
        "name": "streaming",
        "passed": true,
        "latency_s": 2.10,
        "detail": {"ttft_ms": 98.5, "chunks": 12},
        "error": null
      }
    ]
  },
  "message": ""
}
```

**curl:**

```bash
curl -X POST http://localhost:8080/api/testing/run-all \
  -H "Content-Type: application/json" \
  -d '{"base_url": "http://localhost:8000"}'
```

---

### 5.4 평가 (Validation)

#### POST `/api/validation/run`

LLM-as-Judge 방식으로 모델 성능을 평가합니다. 동일한 vLLM 모델이 답변 생성과 채점을 모두 수행합니다.

**평가 파이프라인:**

1. `data/processed/processed_v3.csv`에서 Q&A 쌍 로드
2. context + question → 모델 답변 생성
3. (question, reference_answer, model_answer) → 같은 모델이 Judge로 채점
4. correctness / relevance / completeness 각 1~5점 집계
5. 결과 CSV 저장

**Request Body:**

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `base_url` | `str` | X | `"http://localhost:8000"` | vLLM 서버 주소 |
| `csv_path` | `str \| null` | X | `null` | 테스트 데이터 CSV 경로 (null = 기본 경로) |
| `sample_size` | `int` | X | `0` | 평가할 케이스 수 (0 = 전체) |

```json
{
  "base_url": "http://localhost:8000",
  "sample_size": 10
}
```

**Response Body:**

```json
{
  "status": "success",
  "data": {
    "total": 10,
    "valid": 9,
    "overall": {
      "correctness": 4.11,
      "relevance": 4.33,
      "completeness": 3.89,
      "average": 4.11
    },
    "by_type": {
      "summarization": {
        "count": 3,
        "correctness": 4.33,
        "relevance": 4.67,
        "completeness": 4.00,
        "average": 4.33
      },
      "definition": {
        "count": 2,
        "correctness": 4.00,
        "relevance": 4.50,
        "completeness": 3.50,
        "average": 4.00
      },
      "temporal": {
        "count": 2,
        "correctness": 3.50,
        "relevance": 4.00,
        "completeness": 3.50,
        "average": 3.67
      },
      "comprehension": {
        "count": 2,
        "correctness": 4.50,
        "relevance": 4.00,
        "completeness": 4.50,
        "average": 4.33
      }
    },
    "results_csv_path": "data/processed/validation_results.csv"
  },
  "message": ""
}
```

| 점수 필드 | 범위 | 설명 |
|---|---|---|
| `correctness` | 1~5 | 참조 답변 대비 사실 정확도 |
| `relevance` | 1~5 | 질문에 대한 적절성 |
| `completeness` | 1~5 | 핵심 정보 포함 정도 |
| `average` | 1~5 | 세 점수의 평균 |

**curl:**

```bash
curl -X POST http://localhost:8080/api/validation/run \
  -H "Content-Type: application/json" \
  -d '{"sample_size": 10}'
```

> 전체 데이터셋 평가 시 시간이 오래 걸릴 수 있습니다. `sample_size`로 소규모 테스트를 먼저 수행하는 것을 권장합니다.

---

### 5.5 모니터링 (Monitoring)

#### GET `/api/monitoring/snapshot`

GPU, CPU, RAM, vLLM 서버의 현재 리소스 상태를 스냅샷으로 반환합니다.

**Response Body:**

```json
{
  "status": "success",
  "data": {
    "timestamp": "2026-03-03 14:30:25",
    "gpu": {
      "name": "NVIDIA GeForce RTX 5090",
      "utilization": 78.0,
      "vram_used_gb": 29.15,
      "vram_total_gb": 32.0,
      "vram_percent": 91.1,
      "temperature": 72,
      "power_draw_w": 285.3,
      "power_limit_w": 450.0
    },
    "system": {
      "cpu_percent": 23.5,
      "cpu_count": 16,
      "ram_used_gb": 12.34,
      "ram_total_gb": 64.0,
      "ram_percent": 19.3
    },
    "vllm": {
      "online": true,
      "model_name": "LGAI-EXAONE/EXAONE-4.0-32B-FP8",
      "requests_running": 1.0,
      "requests_waiting": 0.0,
      "gpu_cache_usage": 45.2,
      "cpu_cache_usage": 0.0,
      "prompt_tps": 1250.0,
      "generation_tps": 22.8
    }
  },
  "message": ""
}
```

| 카테고리 | 필드 | 설명 |
|---|---|---|
| GPU | `utilization` | GPU 사용률 (%) |
| GPU | `vram_used_gb` / `vram_total_gb` | VRAM 사용량/전체 (GB) |
| GPU | `temperature` | GPU 온도 (°C) |
| GPU | `power_draw_w` / `power_limit_w` | 전력 소비/한도 (W) |
| System | `cpu_percent` | CPU 전체 사용률 (%) |
| System | `ram_used_gb` / `ram_total_gb` | RAM 사용량/전체 (GB) |
| vLLM | `online` | vLLM 서버 상태 |
| vLLM | `requests_running` / `requests_waiting` | 실행/대기 중 요청 수 |
| vLLM | `gpu_cache_usage` / `cpu_cache_usage` | KV Cache 사용률 (%) |
| vLLM | `prompt_tps` / `generation_tps` | 프롬프트/생성 처리량 (tokens/sec) |

**curl:**

```bash
curl http://localhost:8080/api/monitoring/snapshot
```

---

## 6. 응답 형식

모든 API 엔드포인트는 `BaseResponse[T]` 제네릭 래퍼로 응답합니다.

```python
class BaseResponse(BaseModel, Generic[T]):
    status: str = "success"
    data: T | None = None
    message: str = ""
```

### 성공 응답

```json
{
  "status": "success",
  "data": { ... },
  "message": ""
}
```

### 에러 응답

vLLM 서버 미응답, 모델 다운로드 실패 등의 경우:

```json
{
  "detail": "vLLM server error: Connection refused"
}
```

| HTTP 상태 코드 | 발생 조건 |
|---|---|
| `200` | 정상 응답 |
| `404` | CSV 파일 미존재 (validation) |
| `500` | 서비스 내부 오류 (모델 다운로드 실패, 테스트 실행 실패 등) |
| `502` | vLLM 서버 통신 오류 (inference, models) |

---

## 7. CLI 사용법

Docker Testing Pod에서 FastAPI 서버 없이 독립적으로 실행할 수 있는 CLI 도구입니다.

### 7-1. 모델 다운로드

```bash
python -m cli.model_pulling --model <model_id> [--revision <rev>]
```

| 옵션 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `--model` | O | - | HuggingFace 모델 ID |
| `--revision` | X | `main` | 브랜치/태그 |

```bash
# 예시
python -m cli.model_pulling --model LGAI-EXAONE/EXAONE-4.0-32B-FP8
python -m cli.model_pulling --model meta-llama/Llama-3.1-8B-Instruct --revision v2
```

### 7-2. API 테스트

```bash
python -m cli.model_testing [--base-url <url>]
```

| 옵션 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `--base-url` | X | `http://localhost:8000` | vLLM 서버 주소 |

```bash
# 예시
python -m cli.model_testing
python -m cli.model_testing --base-url http://192.168.1.100:8000
```

출력 예시:

```
Testing vLLM server at http://localhost:8000
==================================================
  [PASS] health (latency: 0.012s)
  [PASS] models (latency: 0.015s)
  [PASS] chat_completion (latency: 1.23s)
  [PASS] completion (latency: 0.95s)
  [PASS] streaming (latency: 2.10s)

==================================================
Results: 5 passed, 0 failed, 5 total
```

### 7-3. 모델 평가

```bash
python -m cli.model_validation [--base-url <url>] [--csv-path <path>] [--sample-size <n>]
```

| 옵션 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `--base-url` | X | `http://localhost:8000` | vLLM 서버 주소 |
| `--csv-path` | X | `data/processed/processed_v3.csv` | 테스트 데이터 CSV 경로 |
| `--sample-size` | X | `0` (전체) | 평가할 테스트 케이스 수 |

```bash
# 예시: 전체 평가
python -m cli.model_validation

# 예시: 샘플 10건만 빠르게 평가
python -m cli.model_validation --sample-size 10
```

출력 예시:

```
LLM-as-a-Judge Model Validation
Server: http://localhost:8000
============================================================

Overall (9 valid / 10 total):
  correctness:  4.11 / 5.00
  relevance:    4.33 / 5.00
  completeness: 3.89 / 5.00
  average:      4.11 / 5.00

  summarization (n=3):
    correctness=4.33  relevance=4.67  completeness=4.00  avg=4.33

Detailed results saved to data/processed/validation_results.csv
```

### 7-4. 리소스 모니터링

```bash
python -m cli.model_monitoring [OPTIONS]
```

| 옵션 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `--interval` | X | `2.0` | 폴링 간격 (초) |
| `--port` | X | `8000` | vLLM 서버 포트 |
| `--no-dashboard` | X | - | 대시보드 비활성화 (CSV만) |
| `--no-log` | X | - | CSV 비활성화 (대시보드만) |
| `--log-dir` | X | `data/monitoring` | CSV 저장 디렉토리 |
| `--duration` | X | `0` (무제한) | 자동 종료 시간 (초) |

```bash
# 기본 실행 (대시보드 + CSV 로깅)
python -m cli.model_monitoring

# CSV 로깅만 (백그라운드)
python -m cli.model_monitoring --no-dashboard --interval 5 &

# 대시보드만 (로그 없이)
python -m cli.model_monitoring --no-log

# 1시간 후 자동 종료
python -m cli.model_monitoring --duration 3600
```

> `Ctrl+C`로 종료하면 CSV 파일 경로가 출력됩니다. CSV는 `data/monitoring/monitor_YYYYMMDD_HHMMSS.csv`에 저장됩니다.

---

## 8. Quick Start

```bash
cd /workspace/modelling

# 1. 토큰 설정
echo "HF_TOKEN=hf_YOUR_TOKEN_HERE" > .env

# 2. 의존성 설치 및 환경변수 적용
uv sync --frozen --no-dev
source env.sh

# 3. 모델 다운로드
python -m cli.model_pulling --model LGAI-EXAONE/EXAONE-4.0-32B-FP8

# 4. vLLM 서버 기동 (백그라운드)
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 \
    --host 0.0.0.0 --port 8000 \
    --cpu-offload-gb 4 --max-model-len 4096 \
    --enforce-eager --gpu-memory-utilization 0.95 &
# (서버 Ready 로그 확인 후 진행)

# 5. FastAPI 서버 기동
uv run uvicorn main:app --host 0.0.0.0 --port 8080 &

# 6. 헬스체크
curl http://localhost:8080/health

# 7. 추론 테스트
curl -X POST http://localhost:8080/api/inference/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "인공지능이란 무엇인가요?"}'

# 8. API 테스트 (CLI)
python -m cli.model_testing

# 9. 모델 평가 (샘플)
python -m cli.model_validation --sample-size 10

# 10. 리소스 모니터링 (별도 터미널)
python -m cli.model_monitoring
```

---

## 9. 트러블슈팅

### vLLM CUDA Out of Memory

**증상:**

```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate X MiB.
```

**해결:**

| GPU (VRAM) | `--cpu-offload-gb` | `--max-model-len` | `--enforce-eager` | `--gpu-memory-utilization` |
|---|---|---|---|---|
| RTX 5090 (32 GB) | `4` | `4096` | 필수 | `0.95` |
| A100 (40 GB) | `0` | `16384` | 선택 | `0.9` |
| A100/H100 (80 GB) | `0` | `131072` | 불필요 | `0.9` |

### vLLM 서버 미응답 (502 Bad Gateway)

**증상:** FastAPI API 호출 시 `vLLM server error: Connection refused`

**원인:** vLLM 서버가 기동되지 않았거나, `VLLM_BASE_URL`이 올바르지 않음.

**해결:**

```bash
# 1. vLLM 서버 상태 확인
curl http://localhost:8000/health

# 2. .env에서 VLLM_BASE_URL 확인
grep VLLM_BASE_URL .env

# 3. vLLM 프로세스 확인
ps aux | grep vllm
```

### HuggingFace 모델 다운로드 실패

**증상:** `403 Forbidden` 또는 `gated model` 에러

**해결:**

```bash
# 1. 토큰 확인
echo $HF_TOKEN

# 2. HuggingFace 웹사이트에서 해당 모델 라이선스에 동의했는지 확인

# 3. env.sh 다시 적용
source env.sh
```

### FastAPI 서버 시작 실패

**증상:** `ModuleNotFoundError` 또는 `ImportError`

**해결:**

```bash
# 의존성 재설치
uv sync --frozen --no-dev

# 가상환경 활성화 확인
which python
# 출력: /workspace/modelling/.venv/bin/python 이어야 함
```

### 멀티 GPU 사용

GPU가 2장 이상인 환경에서는 텐서 병렬화를 활용하여 VRAM 제한을 해결할 수 있습니다.

```bash
vllm serve LGAI-EXAONE/EXAONE-4.0-32B-FP8 \
    --host 0.0.0.0 --port 8000 \
    --tensor-parallel-size 2
```
