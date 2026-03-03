# 프로젝트 구조 재구성 작업 명세

`utils/` 독립 CLI 스크립트를 레이어 기반 FastAPI 구조로 모듈화하여, API 서버와 CLI 양쪽에서 재사용 가능한 서비스 레이어를 구축하는 작업.

## 사전 조건

| 항목 | 값 |
|---|---|
| Python | 3.12 |
| 패키지 매니저 | `uv` |
| 프로젝트 루트 | `/workspace/modelling` |
| 아키텍처 규칙 | `.claude/claude.md` 참조 |

> **주의**: `.claude/claude.md`에 명시된 레이어 책임 분리 규칙을 반드시 준수하세요.
> - `services/`는 원시 데이터(`dict`, `tuple`, `str`)만 반환
> - `api/endpoints/`에서 Pydantic DTO 구성
> - `services/`는 `schemas/`를 import하지 않음

---

## 디렉토리 구조

```
modelling/
├── main.py                              # FastAPI 앱 인스턴스
├── env.sh                               # Shell 환경변수 설정
├── pyproject.toml                       # 의존성 관리
│
├── api/                                 # API 라우트 레이어
│   ├── route.py                         # 라우터 통합
│   └── endpoints/                       # 엔드포인트 구현
│       ├── inference.py                 # 추론 API
│       ├── models.py                    # 모델 관리 API
│       ├── testing.py                   # 테스트 API
│       ├── validation.py               # 평가 API
│       └── monitoring.py               # 모니터링 API
│
├── core/                                # 프로젝트 설정
│   └── config.py                        # Settings (통합)
│
├── schemas/                             # DTO (Pydantic 모델)
│   ├── base.py                          # BaseResponse[T]
│   ├── inference.py                     # ChatRequest, InferenceResponse
│   ├── model_registry.py               # ModelPullRequest, ModelPullResponse
│   ├── testing.py                       # TestSuiteResponse
│   ├── validation.py                    # ValidationSummaryResponse
│   └── monitoring.py                    # SnapshotResponse
│
├── services/                            # 비즈니스 로직
│   ├── inference_service.py             # InferenceService
│   ├── model_registry_service.py        # ModelRegistryService
│   ├── test_service.py                  # TestService
│   ├── validation_service.py            # ValidationService
│   ├── crawler_service.py              # CrawlerService (API 없음)
│   ├── data_processor_service.py       # DataProcessorService (API 없음)
│   └── monitoring/                      # 모니터링 서브패키지
│       ├── service.py                   # MonitoringService
│       ├── collectors.py                # GpuCollector, SystemCollector, VllmCollector
│       ├── datamodels.py                # 메트릭 dataclass
│       ├── logger.py                    # CsvLogger
│       └── dashboard.py                # Rich 대시보드
│
├── db/                                  # DB 연결
│   └── session.py                       # SQLAlchemy 세션
│
├── models/                              # DB 테이블 (향후 확장)
│
├── cli/                                 # CLI 진입점
│   ├── model_pulling.py
│   ├── model_testing.py
│   ├── model_validation.py
│   └── model_monitoring.py
│
├── data/                                # 데이터 아티팩트
├── docker/                              # 컨테이너 설정
└── markdown/                            # 문서
```

---

## 작업 목록

### Step 1. core/config.py 통합

`utils/config.py`의 `HFConfig`를 기존 `core/config.py`의 `Settings`에 병합.

- `HF_TOKEN`, `HF_HOME`, `HF_HUB_ENABLE_HF_TRANSFER` 추가
- `VLLM_BASE_URL`, `MONITORING_LOG_DIR`, `RAW_DATA_DIR`, `PROCESSED_DATA_DIR` 추가
- `extra="ignore"` 설정 (RunPod 환경변수 호환)

### Step 2. db/ 레이어 생성

`core/database.py` → `db/session.py`로 이동.

- `engine`, `SessionLocal`, `get_db()`, `init_db()` 보존

### Step 3. schemas/ 레이어 생성

각 도메인별 Pydantic DTO 정의:

| 파일 | 주요 모델 |
|------|-----------|
| `schemas/base.py` | `BaseResponse[T]` — `ok()`, `error()` 클래스 메서드 |
| `schemas/inference.py` | `ChatRequest`, `InferenceResponse` |
| `schemas/model_registry.py` | `ModelPullRequest`, `ModelPullResponse`, `CachedModelResponse` |
| `schemas/testing.py` | `TestResultResponse`, `TestSuiteResponse` |
| `schemas/validation.py` | `ValidationRequest`, `ValidationSummaryResponse` |
| `schemas/monitoring.py` | `SnapshotResponse`, `GpuResponse`, `SystemResponse`, `VllmResponse` |

### Step 4. services/inference_service.py

`utils/model-calling.py` → `InferenceService` 클래스.

- `async def detect_model() → str`
- `async def chat(prompt, model, max_tokens, temperature) → dict`
- `httpx.AsyncClient`로 vLLM streaming 호출
- TTFT, total time, throughput 측정값을 dict로 반환

### Step 5. services/model_registry_service.py

`utils/model-pulling.py` → `ModelRegistryService` 클래스.

- `async def pull_model(model_id, revision) → dict`
- `async def list_cached_models() → list[dict]`
- `snapshot_download` → `asyncio.to_thread()` 래핑

### Step 6. services/test_service.py

`utils/model-testing.py` → `TestService` 클래스.

- `test_health()`, `test_models()`, `test_chat_completion()`, `test_completion()`, `test_streaming()` 5개 async 메서드
- `async def run_all() → dict` 오케스트레이션

### Step 7. services/monitoring/ 서브패키지

`utils/model-monitoring.py` (558 LOC) → 5개 파일로 분리:

| 파일 | 내용 |
|------|------|
| `datamodels.py` | `GpuMetrics`, `SystemMetrics`, `VllmMetrics`, `Snapshot` (dataclass) |
| `collectors.py` | `GpuCollector` (pynvml), `SystemCollector` (psutil), `VllmCollector` (Prometheus 파싱) |
| `logger.py` | `CsvLogger` + `CSV_COLUMNS` |
| `dashboard.py` | `build_dashboard()` Rich 터미널 UI |
| `service.py` | `MonitoringService` — collectors 오케스트레이션 |

### Step 8. services/validation_service.py

`utils/model-validation.py` → `ValidationService` 클래스.

- `ANSWER_SYSTEM_PROMPT`, `JUDGE_SYSTEM_PROMPT`, `JUDGE_USER_TEMPLATE` → 클래스 상수
- `async def run_validation(model, csv_path, sample_size) → dict`
- `def save_results_csv(results, path) → Path`

### Step 9. services/crawler_service.py

`utils/crawling.py` → `CrawlerService` 클래스. API 엔드포인트 없음.

- `async def crawl_urls(urls) → list[dict]`
- `def save_raw_csv(data, output_path) → Path`

### Step 10. services/data_processor_service.py

`utils/make-data.py` → `DataProcessorService` 클래스. API 엔드포인트 없음.

- `def process_data(raw_data) → list[dict]`
- `def save_processed_csv(data, path) → Path`

### Step 11. api/endpoints/ 엔드포인트 구현

서비스 호출 → 응답 스키마 구성 패턴:

```python
# 예시: api/endpoints/inference.py
@router.post("/chat", response_model=BaseResponse[InferenceResponse])
async def chat(request: ChatRequest) -> BaseResponse[InferenceResponse]:
    service = InferenceService(base_url=settings.VLLM_BASE_URL)
    result = await service.chat(...)      # dict 반환
    response = InferenceResponse(...)      # DTO 변환
    return BaseResponse.ok(data=response)
```

### Step 12. api/route.py 라우터 통합

5개 엔드포인트 라우터를 `APIRouter`로 통합:

```python
router = APIRouter()
router.include_router(inference_router)
router.include_router(models_router)
router.include_router(testing_router)
router.include_router(validation_router)
router.include_router(monitoring_router)
```

### Step 13. main.py 재구성

- `asynccontextmanager` lifespan 패턴 적용
- `api.route.router` 단일 등록
- `/health` 엔드포인트 유지

### Step 14. cli/ 진입점 생성

각 CLI는 `argparse` + `asyncio.run()` + 서비스 클래스 호출:

| 파일 | 명령어 |
|------|--------|
| `cli/model_pulling.py` | `python -m cli.model_pulling --model <id>` |
| `cli/model_testing.py` | `python -m cli.model_testing --base-url <url>` |
| `cli/model_validation.py` | `python -m cli.model_validation --sample-size 10` |
| `cli/model_monitoring.py` | `python -m cli.model_monitoring --interval 2` |

### Step 15. pyproject.toml 의존성 추가

`fastapi`, `uvicorn[standard]`, `pydantic-settings`, `httpx`, `beautifulsoup4`, `sqlalchemy` 추가.

### Step 16. 정리

- `utils/` 디렉토리 전체 삭제
- `core/database.py` 삭제 (`db/session.py`로 이전)
- `env.sh` 프로젝트 루트로 이동

---

## API 엔드포인트 명세

| Method | Path | 설명 | Request Body | Response |
|--------|------|------|-------------|----------|
| GET | `/health` | 헬스체크 | - | `{"status": "ok"}` |
| POST | `/api/inference/chat` | 채팅 완성 | `ChatRequest` | `BaseResponse[InferenceResponse]` |
| GET | `/api/inference/models` | 모델 목록 | - | `BaseResponse[list]` |
| POST | `/api/models/pull` | 모델 다운로드 | `ModelPullRequest` | `BaseResponse[ModelPullResponse]` |
| GET | `/api/models/cached` | 캐시 모델 목록 | - | `BaseResponse[list[CachedModelResponse]]` |
| POST | `/api/testing/run-all` | API 5종 테스트 | - | `BaseResponse[TestSuiteResponse]` |
| POST | `/api/validation/run` | LLM-as-Judge 평가 | `ValidationRequest` | `BaseResponse[ValidationSummaryResponse]` |
| GET | `/api/monitoring/snapshot` | 리소스 스냅샷 | - | `BaseResponse[SnapshotResponse]` |

---

## CLI 사용법

### 모델 다운로드

```bash
python -m cli.model_pulling --model LGAI-EXAONE/EXAONE-4.0-32B-FP8
python -m cli.model_pulling --model <model_id> --revision <rev>
```

### API 테스트

```bash
python -m cli.model_testing
python -m cli.model_testing --base-url http://localhost:8000
```

### 모델 평가

```bash
python -m cli.model_validation
python -m cli.model_validation --base-url http://localhost:8000 --sample-size 10
```

### 리소스 모니터링

```bash
python -m cli.model_monitoring
python -m cli.model_monitoring --interval 5 --port 8001
python -m cli.model_monitoring --no-dashboard
python -m cli.model_monitoring --no-log
python -m cli.model_monitoring --duration 3600
```

---

## 검증 방법

### 1. API 서버 실행

```bash
cd /workspace/modelling
source env.sh
uv run uvicorn main:app --reload
```

### 2. 헬스체크

```bash
curl http://localhost:8000/health
# 예상 응답: {"status":"ok"}
```

### 3. Swagger UI 확인

브라우저에서 `http://localhost:8000/docs` 접속하여 전체 API 문서 확인.

### 4. CLI 동작 확인

```bash
python -m cli.model_monitoring --help
python -m cli.model_pulling --help
python -m cli.model_testing --help
python -m cli.model_validation --help
```

### 5. Import 확인

```python
from services.inference_service import InferenceService
from services.model_registry_service import ModelRegistryService
from services.test_service import TestService
from services.validation_service import ValidationService
from services.monitoring.service import MonitoringService
from schemas.base import BaseResponse
```
