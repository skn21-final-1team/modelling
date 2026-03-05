# LLM Serve Architecture 리팩터링 변경내역

## 개요

`modelling/` 프로젝트의 아키텍처를 `schema → service → external API` 패턴으로 전면 리팩터링.
DB를 사용하지 않는 vLLM 모델 서빙 프로젝트에 맞게 불필요한 레이어를 제거하고, 서비스 계층이 Pydantic schema를 입출력으로 사용하도록 변경.

---

## 1. 삭제된 파일 및 디렉터리

### 1.1 `db/` 디렉터리 전체 삭제

- **파일**: `db/__init__.py`, `db/session.py`
- **이유**: SQLAlchemy engine, `SessionLocal`, `Base`, `init_db()`, `get_db()` 등이 정의되어 있었으나, 프로젝트 내 어떤 서비스에서도 import하지 않음. DB를 사용하지 않는 모델 서빙 프로젝트에 불필요.

### 1.2 `models/` 디렉터리 전체 삭제

- **파일**: `models/__init__.py`
- **이유**: 빈 `__init__.py`만 존재. SQLAlchemy ORM 모델이 없으며, DB가 없으므로 존재 이유 없음.

### 1.3 `services/crawler_service.py` 삭제

- **이유**: 웹 크롤링 서비스였으나, 이를 호출하는 API endpoint, CLI, 또는 다른 서비스가 전혀 없음 (orphan service).

### 1.4 `services/data_processor_service.py` 삭제

- **이유**: 텍스트 처리/QA 생성 서비스였으나, 이를 호출하는 API endpoint, CLI, 또는 다른 서비스가 전혀 없음 (orphan service).

---

## 2. `core/config.py` 변경

### 변경 내용
- `DATABASE_URL: str = "sqlite:///./dev.db"` 설정 제거

### 이유
- DB를 사용하지 않으므로 불필요한 설정

---

## 3. Service 계층 리팩터링

모든 서비스를 **schema 입력 → schema 출력** 패턴으로 통일.

### 3.1 `services/inference_service.py`

**Before:**
```python
async def chat(self, prompt: str, system_prompt: str | None = None,
               max_tokens: int = 1024, temperature: float = 0.7,
               model: str | None = None) -> dict:
    # ... primitive 파라미터 수신, dict 반환
    return {"content": ..., "model": ..., "ttft_ms": ..., ...}
```

**After:**
```python
from schemas.inference import ChatRequest, InferenceResponse

async def chat(self, request: ChatRequest) -> InferenceResponse:
    model_name = request.model or await self.detect_model()
    messages: list[dict] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
    }
    result = await self._stream_completion(payload)
    return InferenceResponse(
        content=result["content"],
        model=model_name,
        ttft_ms=result["ttft_ms"],
        total_s=result["total_s"],
        completion_tokens=result["completion_tokens"],
        throughput_tps=result["throughput_tps"],
    )
```

**추가 변경:**
- `stream_completion()` → `_stream_completion()` (private 메서드로 변경)

---

### 3.2 `services/test_service.py`

**Before:**
```python
async def run_all(self) -> dict:
    # 각 테스트 메서드가 dict 반환
    return {"base_url": ..., "model": ..., "total": ..., "results": [...]}
```

**After:**
```python
from schemas.testing import TestResultResponse, TestSuiteResponse

async def run_all(self) -> TestSuiteResponse:
    # 각 테스트 메서드가 TestResultResponse 반환
    return TestSuiteResponse(
        base_url=self._base_url,
        model=model,
        total=len(results),
        passed=passed,
        failed=failed,
        results=results,
    )
```

**추가 변경:**
- 개별 테스트 메서드(`health_check`, `list_models` 등) → `_health_check`, `_list_models` 등 (private)
- 각 테스트 메서드 반환 타입: `dict` → `TestResultResponse`

---

### 3.3 `services/validation_service.py`

**Before:**
```python
async def run_validation(self, base_url: str, csv_path: Path,
                         sample_size: int = 0) -> dict:
    # primitive 파라미터, dict 반환
    return {"total": ..., "valid": ..., "overall": {...}, "by_type": {...}}
```

**After:**
```python
from schemas.validation import (
    OverallScoreResponse, TypeScoreResponse,
    ValidationRequest, ValidationSummaryResponse,
)

async def run_validation(
    self, request: ValidationRequest, csv_path: Path
) -> ValidationSummaryResponse:
    # ValidationRequest schema 수신, ValidationSummaryResponse 반환
    return self._aggregate_scores(results, type_scores, results_csv_path)
```

**추가 변경:**
- `evaluate_single()` → `_evaluate_single()` (private)
- `aggregate_scores()` → `_aggregate_scores()` (private)
- `_aggregate_scores()`가 `OverallScoreResponse`, `TypeScoreResponse` schema 직접 생성하여 `ValidationSummaryResponse` 반환
- CSV 저장 로직을 서비스 내부로 이동

---

### 3.4 `services/model_registry_service.py`

**Before:**
```python
async def pull_model(self, model_id: str, revision: str = "main") -> dict:
    return {"model_id": ..., "local_path": ..., "status": "downloaded"}

def list_cached_models(self) -> list[dict]:
    return [{"model_id": ..., "size_gb": ..., ...}, ...]
```

**After:**
```python
from schemas.model_registry import CachedModelResponse, ModelPullRequest, ModelPullResponse

async def pull_model(self, request: ModelPullRequest) -> ModelPullResponse:
    path = await asyncio.to_thread(
        snapshot_download,
        repo_id=request.model_id,
        revision=request.revision,
        cache_dir=self._cache_dir,
        token=self._token,
    )
    return ModelPullResponse(
        model_id=request.model_id,
        revision=request.revision,
        local_path=str(path),
        status="downloaded",
    )

def list_cached_models(self) -> list[CachedModelResponse]:
    # CachedModelResponse schema 객체 리스트 반환
```

---

### 3.5 `services/monitoring/service.py`

**Before:**
- `collect_snapshot()` 만 존재, 내부 dataclass(`Snapshot`) 반환
- endpoint에서 dataclass → schema 변환 수행 (60줄)

**After:**
- `collect_snapshot()` 유지 (대시보드/로거에서 dataclass 직접 사용)
- `collect_snapshot_response()` 메서드 추가: `SnapshotResponse` schema 반환

```python
from schemas.monitoring import GpuResponse, SnapshotResponse, SystemResponse, VllmResponse

def collect_snapshot_response(self) -> SnapshotResponse:
    snap = self.collect_snapshot()
    return SnapshotResponse(
        timestamp=snap.timestamp,
        gpu=GpuResponse(
            name=snap.gpu.name,
            utilization=snap.gpu.utilization,
            vram_used_gb=round(snap.gpu.vram_used_gb, 2),
            vram_total_gb=round(snap.gpu.vram_total_gb, 2),
            vram_percent=round(snap.gpu.vram_percent, 1),
            temperature=snap.gpu.temperature,
            power_draw_w=round(snap.gpu.power_draw_w, 1),
            power_limit_w=round(snap.gpu.power_limit_w, 1),
        ),
        system=SystemResponse(
            cpu_percent=round(snap.system.cpu_percent, 1),
            cpu_count=snap.system.cpu_count,
            ram_used_gb=round(snap.system.ram_used_gb, 2),
            ram_total_gb=round(snap.system.ram_total_gb, 2),
            ram_percent=round(snap.system.ram_percent, 1),
        ),
        vllm=VllmResponse(
            online=snap.vllm.online,
            model_name=snap.vllm.model_name,
            requests_running=snap.vllm.requests_running,
            requests_waiting=snap.vllm.requests_waiting,
            gpu_cache_usage=round(snap.vllm.gpu_cache_usage, 1),
            cpu_cache_usage=round(snap.vllm.cpu_cache_usage, 1),
            prompt_tps=round(snap.vllm.prompt_tps, 1),
            generation_tps=round(snap.vllm.generation_tps, 1),
        ),
    )
```

---

## 4. API Endpoint 계층 간소화

서비스가 schema를 반환하므로, endpoint에서 dict → schema 변환 보일러플레이트 제거.

### 4.1 `api/endpoints/inference.py`

- 서비스 호출 후 dict에서 `InferenceResponse` 수동 생성 → `service.chat(request)` 직접 반환

### 4.2 `api/endpoints/testing.py`

- `TestResultResponse` 리스트 수동 생성 (list comprehension) 제거 → `service.run_all()` 결과 직접 반환

### 4.3 `api/endpoints/validation.py`

- **78줄 → 35줄**으로 축소
- `OverallScoreResponse`, `TypeScoreResponse` 수동 생성 코드 전체 제거 → `service.run_validation()` 결과 직접 반환

### 4.4 `api/endpoints/models.py`

- dict → `ModelPullResponse`, `CachedModelResponse` 변환 제거 → 서비스 반환값 직접 사용

### 4.5 `api/endpoints/monitoring.py`

- **60줄 → 25줄**으로 축소
- dataclass → schema 변환 코드 전체 제거 → `service.collect_snapshot_response()` 직접 사용

---

## 5. CLI 계층 변경

### 5.1 `cli/model_pulling.py`

- `ModelPullRequest` schema 생성하여 서비스에 전달
- 결과를 attribute 접근 (`result.local_path`)으로 변경 (기존: `result['local_path']`)

### 5.2 `cli/model_testing.py`

- 서비스 반환 `TestSuiteResponse` schema의 attribute 접근 사용
- `result.results`, `r.passed`, `r.name`, `r.latency_s`, `r.error` 등

### 5.3 `cli/model_validation.py`

- `ValidationRequest` schema 생성하여 서비스에 전달
- 결과 `ValidationSummaryResponse` attribute 접근: `summary.valid`, `summary.overall.correctness` 등

---

## 6. 변경 요약

| 구분 | Before | After |
|------|--------|-------|
| Service 입력 | primitive 파라미터 | Pydantic schema |
| Service 출력 | dict | Pydantic schema |
| Endpoint 역할 | dict ↔ schema 변환 + 에러 처리 | 에러 처리만 |
| 불필요한 디렉터리 | `db/`, `models/` | 삭제 |
| 불필요한 서비스 | `crawler_service`, `data_processor_service` | 삭제 |
| 불필요한 설정 | `DATABASE_URL` | 삭제 |
| 아키텍처 패턴 | 혼재 (DB 패턴 + 직접 호출) | `schema → service → external API` 통일 |
