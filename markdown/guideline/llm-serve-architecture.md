# Modelling 프로젝트 아키텍처 분석

## 1. 프로젝트 성격

GPU 서버(RunPod)에서 vLLM 기반 LLM을 서빙하고, 이를 테스트/검증/모니터링하는 도구.
외부 backend 서버로부터 요청을 받아 vLLM API를 호출하고 응답을 반환하는 **모델 서빙 프록시** 역할.

**핵심 특징:**
- DB를 직접 사용하지 않음 (모든 데이터는 외부 API 호출 또는 파일 I/O)
- vLLM OpenAI-compatible API를 내부적으로 호출
- HuggingFace Hub에서 모델 다운로드
- GPU/시스템 리소스 모니터링

---

## 2. 현재 구조 및 문제점

### 현재 디렉토리 구조
```
modelling/
├── core/           # 설정
├── db/             # SQLAlchemy 세션 (미사용)
├── models/         # DB 모델 (비어있음)
├── schemas/        # Pydantic 요청/응답 정의
├── services/       # 비즈니스 로직
│   └── monitoring/ # GPU/시스템 모니터링
├── api/endpoints/  # FastAPI 라우터
├── cli/            # CLI 도구
└── main.py
```

### 문제점

#### 2-1. 불필요한 DB 레이어
- `db/session.py`: SQLAlchemy 엔진, vector extension 초기화 코드가 있지만 **어떤 서비스도 DB 세션을 주입받거나 사용하지 않음**
- `models/__init__.py`: 빈 파일. DB 모델이 없음
- `core/config.py`의 `DATABASE_URL`: DB를 안 쓰는데 설정이 존재

#### 2-2. Service가 Schema를 활용하지 않음
Service 메서드가 primitive 파라미터를 개별적으로 받고, `dict`를 반환함.

```python
# 현재 (inference_service.py)
async def chat(self, prompt: str, model: str | None, max_tokens: int, ...) -> dict:
```

이로 인해 endpoint에서 schema를 풀고 → service 호출 → 다시 schema로 감싸는 보일러플레이트 발생:

```python
# 현재 (endpoints/inference.py)
result = await service.chat(
    prompt=request.prompt,        # schema → primitive 변환
    model=request.model,
    max_tokens=request.max_tokens,
    ...
)
response = InferenceResponse(     # dict → schema 재변환
    content=result["content"],
    model=result["model"],
    ...
)
```

#### 2-3. 고아 서비스
- `crawler_service.py`: 웹 크롤링 기능. API endpoint도 CLI도 없음
- `data_processor_service.py`: 텍스트 전처리/QA 생성. API endpoint도 CLI도 없음
- 둘 다 데이터 파이프라인 용도로 보이나, 현재 프로젝트에서 호출되는 곳이 없음

---

## 3. 적합한 아키텍처 패턴

이 프로젝트는 DB 기반이 아니므로 일반적인 `model → crud → schema → service` 패턴이 **맞지 않음**.

### 적합한 패턴: `schema → service → external API`

```
[Client Request]
    ↓
[API Endpoint] ← Schema(Request)로 검증
    ↓
[Service] ← Schema를 직접 받고, Schema를 반환
    ↓
[External API] ← vLLM, HuggingFace, GPU API 등
    ↓
[Service] → Schema(Response) 반환
    ↓
[API Endpoint] → BaseResponse로 감싸서 응답
```

### 각 레이어 역할

| 레이어 | 역할 | 예시 |
|--------|------|------|
| **Schema** | 요청/응답 데이터 구조 정의 및 검증 | `ChatRequest`, `InferenceResponse` |
| **Service** | 비즈니스 로직, 외부 API 호출, 데이터 변환 | `InferenceService.chat()` |
| **Endpoint** | HTTP 라우팅, 에러 핸들링, 응답 래핑 | `POST /api/inference/chat` |
| **CLI** | 터미널 인터페이스, Service 재사용 | `python -m cli.model_testing` |

---

## 4. 추천 디렉토리 구조

```
modelling/
├── core/
│   └── config.py              # 설정 (DATABASE_URL 제거)
├── schemas/                   # 요청/응답 정의
│   ├── base.py                # BaseResponse 래퍼
│   ├── inference.py
│   ├── testing.py
│   ├── validation.py
│   ├── monitoring.py
│   └── model_registry.py
├── services/                  # 비즈니스 로직 (schema 기반)
│   ├── inference_service.py   # ChatRequest → InferenceResponse
│   ├── test_service.py
│   ├── validation_service.py
│   ├── model_registry_service.py
│   └── monitoring/
│       ├── service.py
│       ├── collectors.py
│       ├── datamodels.py
│       ├── logger.py
│       └── dashboard.py
├── api/
│   ├── route.py
│   └── endpoints/
│       ├── inference.py
│       ├── testing.py
│       ├── validation.py
│       ├── models.py
│       └── monitoring.py
├── cli/
│   ├── model_pulling.py
│   ├── model_testing.py
│   ├── model_validation.py
│   └── model_monitoring.py
├── main.py
└── (db/, models/ 삭제)
```

### 제거 대상
- `db/` 디렉토리 전체
- `models/` 디렉토리 전체
- `core/config.py`의 `DATABASE_URL` 설정
- `crawler_service.py`, `data_processor_service.py` (사용처 없음, 별도 모듈로 분리 권장)

---

## 5. 리팩터링 방향

### 5-1. Service를 Schema 기반으로 변경

**Before:**
```python
class InferenceService:
    async def chat(self, prompt: str, model: str | None = None, ...) -> dict:
        ...
        return {"content": full_content, "ttft_ms": ..., ...}
```

**After:**
```python
class InferenceService:
    async def chat(self, request: ChatRequest) -> InferenceResponse:
        ...
        return InferenceResponse(content=full_content, model=model_name, ...)
```

### 5-2. Endpoint 단순화

**Before:**
```python
@router.post("/chat")
async def chat(request: ChatRequest):
    result = await service.chat(
        prompt=request.prompt,
        model=request.model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        system_prompt=request.system_prompt,
    )
    response = InferenceResponse(
        content=result["content"],
        model=result["model"],
        ...
    )
    return BaseResponse.ok(data=response)
```

**After:**
```python
@router.post("/chat")
async def chat(request: ChatRequest):
    response = await service.chat(request)
    return BaseResponse.ok(data=response)
```

### 5-3. 동일 패턴을 다른 서비스에도 적용
- `test_service.py` → `TestRequest` 받고 `TestSuiteResponse` 반환
- `validation_service.py` → `ValidationRequest` 받고 `ValidationSummaryResponse` 반환
- `model_registry_service.py` → `ModelPullRequest` 받고 `ModelPullResponse` 반환
