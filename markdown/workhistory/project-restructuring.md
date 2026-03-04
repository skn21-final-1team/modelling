# 프로젝트 구조 재구성 작업 이력

`utils/` 디렉토리의 독립 CLI 스크립트 8개(~1,926 LOC)를 `claude.md` 레이어 기반 FastAPI 구조(`api/endpoints/`, `services/`, `schemas/`)로 모듈화하고, 모든 비즈니스 로직을 재사용 가능한 서비스 클래스로 전환한 작업 기록.

---

## 1. 배경 및 목적

기존 `utils/` 디렉토리에 8개의 Python 스크립트가 독립 실행 전용으로 작성되어 있었음.
각 스크립트는 `if __name__ == "__main__":` 블록에 전체 로직이 포함되어 있어, API 서버나 다른 모듈에서 재사용이 불가능한 구조였음.

**기존 문제점:**

- 스크립트 간 코드 중복 (vLLM API 호출 로직, 모델 감지 로직 등)
- 설정값이 `utils/config.py`와 `core/config.py`에 분산
- `requests` 라이브러리 사용으로 async 지원 불가
- API 서버 없이 CLI로만 실행 가능
- 테스트/모킹이 어려운 절차적 코드 구조

**요구사항:**

- 모든 코드를 재사용 가능한 서비스 클래스로 모듈화
- FastAPI 기반 REST API로 외부에서 호출 가능하게 구성
- `claude.md`에 명시된 레이어 기반 아키텍처 준수
- CLI 독립 실행 기능도 유지 (Docker Pod 환경용)

---

## 2. 기술 선택

### 아키텍처: 레이어 기반 분리

`claude.md`에 명시된 레이어 책임 분리 원칙을 준수:

```
api/endpoints/  →  services/  →  외부 I/O (vLLM API, HF Hub, 파일시스템)
     │                │
  schemas/       core/config.py
```

| 레이어 | 책임 | 반환값 |
|--------|------|--------|
| `services/` | 비즈니스 로직, 외부 I/O | 원시 데이터 (`dict`, `tuple`, `str`) |
| `api/endpoints/` | HTTP 요청 처리, 응답 구성 | Pydantic DTO (`BaseResponse[T]`) |
| `schemas/` | DTO 정의 (Pydantic 모델) | - |

> **핵심 규칙**: `services/`는 `schemas/`를 import하지 않음. 서비스는 원시 데이터만 반환하고, DTO 변환은 엔드포인트에서 수행.

### 주요 기술 변경

| 항목 | 변경 전 | 변경 후 | 이유 |
|------|---------|---------|------|
| HTTP 클라이언트 | `requests` (sync) | `httpx.AsyncClient` (async) | FastAPI async 호환 |
| 설정 관리 | `utils/config.py` + `core/config.py` 분산 | `core/config.py` 통합 | 단일 설정 소스 |
| 블로킹 I/O | 직접 호출 | `asyncio.to_thread()` 래핑 | 이벤트 루프 블로킹 방지 |
| 서버 라이프사이클 | `@app.on_event("startup")` | `asynccontextmanager` lifespan | FastAPI deprecated 대응 |
| 응답 형식 | 비표준 | `BaseResponse[T]` 제네릭 래퍼 | 일관된 API 응답 |

### 의존성 추가

`pyproject.toml`에 추가된 패키지:

```python
"fastapi",           # 웹 프레임워크
"uvicorn[standard]", # ASGI 서버
"pydantic-settings", # 환경변수 기반 설정
"httpx",             # 비동기 HTTP 클라이언트
"beautifulsoup4",    # HTML 파싱 (크롤러)
"sqlalchemy",        # ORM / DB 세션 관리
```

---

## 3. 구현 구조

### 전체 디렉토리

```
modelling/
├── main.py                              # FastAPI 앱 + lifespan + 라우터 등록
├── env.sh                               # Shell 환경변수 설정
├── pyproject.toml                       # 의존성 관리
│
├── api/                                 # API 라우트 레이어
│   ├── route.py                         # 라우터 통합 (include_router)
│   └── endpoints/                       # 엔드포인트 구현
│       ├── inference.py                 # POST /api/inference/chat, GET /api/inference/models
│       ├── models.py                    # POST /api/models/pull, GET /api/models/cached
│       ├── testing.py                   # POST /api/testing/run-all
│       ├── validation.py               # POST /api/validation/run
│       └── monitoring.py               # GET /api/monitoring/snapshot
│
├── core/                                # 프로젝트 설정
│   └── config.py                        # Settings (HF + DB + vLLM 통합)
│
├── schemas/                             # DTO (Pydantic 모델)
│   ├── base.py                          # BaseResponse[T] 제네릭 래퍼
│   ├── inference.py                     # ChatRequest, InferenceResponse
│   ├── model_registry.py               # ModelPullRequest, ModelPullResponse, CachedModelResponse
│   ├── testing.py                       # TestSuiteResponse, TestResultResponse
│   ├── validation.py                    # ValidationRequest, ValidationSummaryResponse
│   └── monitoring.py                    # SnapshotResponse, GpuResponse, SystemResponse, VllmResponse
│
├── services/                            # 비즈니스 로직
│   ├── inference_service.py             # InferenceService (← model-calling.py)
│   ├── model_registry_service.py        # ModelRegistryService (← model-pulling.py)
│   ├── test_service.py                  # TestService (← model-testing.py)
│   ├── validation_service.py            # ValidationService (← model-validation.py)
│   ├── crawler_service.py              # CrawlerService (← crawling.py, API 없음)
│   ├── data_processor_service.py       # DataProcessorService (← make-data.py, API 없음)
│   └── monitoring/                      # 모니터링 서브패키지 (← model-monitoring.py)
│       ├── service.py                   # MonitoringService
│       ├── collectors.py                # GpuCollector, SystemCollector, VllmCollector
│       ├── datamodels.py                # GpuMetrics, SystemMetrics, VllmMetrics, Snapshot
│       ├── logger.py                    # CsvLogger
│       └── dashboard.py                # build_dashboard() (Rich 터미널 UI)
│
├── db/                                  # DB 연결 설정
│   └── session.py                       # engine, SessionLocal, get_db, init_db
│
├── models/                              # DB 테이블 정의 (향후 확장)
│
├── cli/                                 # CLI 진입점 (Docker Pod 독립 실행)
│   ├── model_pulling.py                 # python -m cli.model_pulling
│   ├── model_testing.py                 # python -m cli.model_testing
│   ├── model_validation.py              # python -m cli.model_validation
│   └── model_monitoring.py              # python -m cli.model_monitoring
│
├── data/                                # 데이터 아티팩트
├── docker/                              # 컨테이너 설정
└── markdown/                            # 문서
```

### 레이어 간 데이터 흐름

```
HTTP 요청
  ↓
api/endpoints/inference.py     ← ChatRequest (Pydantic)
  ↓
services/inference_service.py  → dict (content, ttft_ms, total_s, ...)
  ↓
api/endpoints/inference.py     → InferenceResponse (Pydantic) → BaseResponse[InferenceResponse]
  ↓
HTTP 응답
```

---

## 4. 주요 변경 사항

### utils/ → services/ 매핑

| utils/ 원본 (삭제됨) | services/ 신규 | 비고 |
|---|---|---|
| `config.py` | `core/config.py` (병합) | HFConfig → Settings 통합 |
| `model-calling.py` (135 LOC) | `services/inference_service.py` | httpx async 전환 |
| `model-pulling.py` (58 LOC) | `services/model_registry_service.py` | asyncio.to_thread 래핑 |
| `model-testing.py` (208 LOC) | `services/test_service.py` | 5종 테스트 메서드 |
| `model-validation.py` (413 LOC) | `services/validation_service.py` | LLM-as-Judge 파이프라인 |
| `model-monitoring.py` (558 LOC) | `services/monitoring/` (5파일) | 서브패키지 분리 |
| `crawling.py` (195 LOC) | `services/crawler_service.py` | API 없음 (Service only) |
| `make-data.py` (343 LOC) | `services/data_processor_service.py` | API 없음 (Service only) |

### API 엔드포인트 맵

| Method | Path | 설명 | 원본 |
|--------|------|------|------|
| GET | `/health` | 서버 헬스체크 | main.py |
| POST | `/api/inference/chat` | vLLM 채팅 완성 | model-calling.py |
| GET | `/api/inference/models` | 사용 가능 모델 목록 | model-calling.py |
| POST | `/api/models/pull` | HuggingFace 모델 다운로드 | model-pulling.py |
| GET | `/api/models/cached` | 캐시된 모델 목록 | 신규 |
| POST | `/api/testing/run-all` | vLLM API 5종 테스트 | model-testing.py |
| POST | `/api/validation/run` | LLM-as-Judge 평가 | model-validation.py |
| GET | `/api/monitoring/snapshot` | 리소스 스냅샷 | model-monitoring.py |

### CLI 진입점

| 명령어 | 설명 |
|--------|------|
| `python -m cli.model_pulling --model <id>` | 모델 다운로드 |
| `python -m cli.model_testing --base-url <url>` | API 테스트 |
| `python -m cli.model_validation --sample-size 10` | 모델 평가 |
| `python -m cli.model_monitoring --interval 2` | 리소스 모니터링 |

---

## 5. 파일 변경 요약

### 신규 생성

| 파일 | 역할 |
|------|------|
| `api/__init__.py` | 패키지 초기화 |
| `api/route.py` | 라우터 통합 |
| `api/endpoints/__init__.py` | 패키지 초기화 |
| `api/endpoints/inference.py` | 추론 엔드포인트 |
| `api/endpoints/models.py` | 모델 관리 엔드포인트 |
| `api/endpoints/testing.py` | 테스트 엔드포인트 |
| `api/endpoints/validation.py` | 평가 엔드포인트 |
| `api/endpoints/monitoring.py` | 모니터링 엔드포인트 |
| `schemas/__init__.py` | 패키지 초기화 |
| `schemas/base.py` | BaseResponse[T] 제네릭 래퍼 |
| `schemas/inference.py` | 추론 DTO |
| `schemas/model_registry.py` | 모델 관리 DTO |
| `schemas/testing.py` | 테스트 DTO |
| `schemas/validation.py` | 평가 DTO |
| `schemas/monitoring.py` | 모니터링 DTO |
| `services/__init__.py` | 패키지 초기화 |
| `services/inference_service.py` | 추론 서비스 |
| `services/model_registry_service.py` | 모델 레지스트리 서비스 |
| `services/test_service.py` | 테스트 서비스 |
| `services/validation_service.py` | 평가 서비스 |
| `services/crawler_service.py` | 크롤러 서비스 |
| `services/data_processor_service.py` | 데이터 전처리 서비스 |
| `services/monitoring/__init__.py` | 모니터링 패키지 초기화 |
| `services/monitoring/service.py` | MonitoringService |
| `services/monitoring/collectors.py` | 메트릭 수집기 |
| `services/monitoring/datamodels.py` | 메트릭 데이터클래스 |
| `services/monitoring/logger.py` | CSV 로거 |
| `services/monitoring/dashboard.py` | Rich 대시보드 |
| `db/__init__.py` | 패키지 초기화 |
| `db/session.py` | DB 세션 관리 |
| `models/__init__.py` | 패키지 초기화 |
| `cli/__init__.py` | 패키지 초기화 |
| `cli/model_pulling.py` | 모델 다운로드 CLI |
| `cli/model_testing.py` | API 테스트 CLI |
| `cli/model_validation.py` | 모델 평가 CLI |
| `cli/model_monitoring.py` | 리소스 모니터링 CLI |

### 수정

| 파일 | 변경 내용 |
|------|-----------|
| `main.py` | lifespan 패턴 + 라우터 등록 방식으로 재작성 |
| `core/config.py` | HFConfig 병합, VLLM_BASE_URL 등 추가 |
| `pyproject.toml` | fastapi, uvicorn, httpx 등 의존성 추가 |
| `env.sh` | 프로젝트 루트로 이동 |

### 삭제

| 파일 | 사유 |
|------|------|
| `utils/` 디렉토리 전체 (8 파일) | services/로 마이그레이션 완료 |
| `core/database.py` | db/session.py로 이동 |

---

## 6. 관련 파일

| 파일 | 역할 |
|------|------|
| `main.py` | FastAPI 앱 인스턴스 + lifespan + 라우터 등록 |
| `core/config.py` | 통합 설정 (HF + DB + vLLM) |
| `api/route.py` | 5개 엔드포인트 라우터 통합 |
| `schemas/base.py` | BaseResponse[T] 제네릭 응답 래퍼 |
| `services/inference_service.py` | vLLM API 호출 (TTFT, 처리량 측정) |
| `services/monitoring/service.py` | GPU/CPU/RAM/vLLM 메트릭 수집 오케스트레이션 |
| `db/session.py` | SQLAlchemy 엔진 + 세션 + pgvector 초기화 |
| `.claude/claude.md` | 프로젝트 구조 규칙 정의 |
