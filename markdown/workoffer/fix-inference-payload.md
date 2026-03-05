# Inference Payload 리팩토링: prompt → messages 전환

## 배경

현재 `inference_service.py`의 `chat()` 메서드는 `ChatRequest` 스키마를 받지만, 스키마 내부에 `prompt: str` 단일 문자열과 `system_prompt: str | None`이 분리되어 있다. 서비스 내부에서 이를 messages 배열로 조립하는 구조이다.

이 구조의 문제:
1. **멀티턴 대화 불가** — 이전 대화 이력(assistant 응답 포함)을 전달할 수 없음
2. **role 제어 불가** — system/user/assistant 역할 구성을 호출자가 직접 지정할 수 없음
3. **모델 전환 시 비호환** — EXAONE 등 Open LLM(vLLM 서빙)에서 OpenAI ChatGPT 계열로 전환 시, payload 구조 차이로 코드 수정이 필요함

## 목표

OpenAI Chat Completions API 표준 `messages` 배열 방식으로 payload를 통합하여, **모델 전환 시 `base_url`과 `model`만 변경하면 즉시 동작**하도록 한다.

---

## 현재 코드 (Before)

### 스키마 — `modelling/schemas/inference.py`

```python
class ChatRequest(BaseModel):
    prompt: str                        # 단일 문자열
    model: str | None = None
    max_tokens: int = 256
    temperature: float = 0.7
    system_prompt: str | None = None   # system prompt 별도 필드
```

### 서비스 — `modelling/services/inference_service.py`

```python
async def chat(self, request: ChatRequest) -> InferenceResponse:
    model_name = request.model or await self.detect_model()

    messages: list[dict] = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})   # 단일 user 메시지만 가능

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
        ...
    )
```

### 엔드포인트 — `modelling/api/endpoints/inference.py`

엔드포인트는 이미 `schema → service → API` 패턴이 적용되어 있어 `service.chat(request)`로 직접 전달한다. 이 부분은 변경 없음.

```python
response = await service.chat(request)
```

### 문제점 요약

| 항목 | 현재 상태 | 문제 |
|------|----------|------|
| 입력 형식 | `ChatRequest.prompt: str` (단일 문자열) | 멀티턴 대화 이력 전달 불가 |
| system prompt | 별도 `ChatRequest.system_prompt` 필드 | OpenAI 표준과 불일치 |
| messages 조립 | 서비스 내부에서 고정 패턴으로 생성 | 호출자가 role 구성 제어 불가 |
| 모델 전환 | vLLM 전용 구조 | ChatGPT로 전환 시 코드 수정 필요 |

---

## 변경 코드 (After)

### 스키마 — `modelling/schemas/inference.py`

```python
from pydantic import BaseModel


class Message(BaseModel):
    role: str       # "system" | "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]            # OpenAI 표준 messages 배열
    model: str | None = None
    max_tokens: int = 256
    temperature: float = 0.7


class InferenceResponse(BaseModel):
    content: str
    model: str
    ttft_ms: float
    total_s: float
    completion_tokens: int
    throughput_tps: float
```

변경 사항:
- `prompt: str` 제거 → `messages: list[Message]` 추가
- `system_prompt: str | None` 제거 (messages 내 `role: "system"`으로 대체)
- `Message` 모델 신규 추가

### 서비스 — `modelling/services/inference_service.py`

```python
async def chat(self, request: ChatRequest) -> InferenceResponse:
    model_name = request.model or await self.detect_model()

    payload = {
        "model": model_name,
        "messages": [m.model_dump() for m in request.messages],  # 스키마를 그대로 변환
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

변경 사항:
- messages 조립 로직 제거 (`if request.system_prompt`, `messages.append(...)` 등)
- `request.messages`를 `model_dump()`로 dict 변환하여 payload에 그대로 전달
- 메서드 시그니처(`chat(self, request: ChatRequest) -> InferenceResponse`)는 유지

### 엔드포인트 — `modelling/api/endpoints/inference.py`

**변경 없음.** 기존 `schema → service → API` 패턴이 유지되므로 엔드포인트 코드는 수정하지 않는다.

```python
@router.post("/chat", response_model=BaseResponse[InferenceResponse])
async def chat(request: ChatRequest) -> BaseResponse[InferenceResponse]:
    service = InferenceService(base_url=settings.VLLM_BASE_URL)
    try:
        response = await service.chat(request)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    return BaseResponse.ok(data=response)
```

---

## API 요청 예시

### 싱글턴 (기존과 동일한 단일 질문)

```json
{
  "messages": [
    {"role": "user", "content": "오늘 날씨 어때?"}
  ]
}
```

### system prompt 포함

```json
{
  "messages": [
    {"role": "system", "content": "당신은 친절한 날씨 안내 봇입니다."},
    {"role": "user", "content": "오늘 날씨 어때?"}
  ]
}
```

### 멀티턴 대화

```json
{
  "messages": [
    {"role": "system", "content": "당신은 코드 리뷰 전문가입니다."},
    {"role": "user", "content": "이 함수를 리뷰해줘: def add(a, b): return a + b"},
    {"role": "assistant", "content": "타입 힌트가 없습니다. def add(a: int, b: int) -> int: 로 변경하세요."},
    {"role": "user", "content": "float도 지원하려면?"}
  ],
  "model": "gpt-4o",
  "max_tokens": 512,
  "temperature": 0.3
}
```

---

## 모델 호환성

이 변경 후 payload가 OpenAI Chat Completions API 표준과 1:1 대응하므로, 아래 모델/서버 모두 동일한 payload로 동작한다:

| 모델/서버 | 변경할 설정 | payload 수정 |
|-----------|-----------|-------------|
| EXAONE (vLLM) | `base_url=vLLM주소` | 없음 |
| GPT-4o (OpenAI) | `base_url=https://api.openai.com`, `model=gpt-4o` | 없음 |
| Claude (Anthropic) | OpenAI 호환 프록시 필요 | 없음 |
| Llama 3 (TGI) | `base_url=TGI주소` | 없음 |
| Ollama | `base_url=http://localhost:11434` | 없음 |

---

## 수정 대상 파일

| 파일 | 변경 내용 |
|------|----------|
| `modelling/schemas/inference.py` | `Message` 모델 추가, `ChatRequest.prompt` → `messages` 변경, `system_prompt` 제거 |
| `modelling/services/inference_service.py` | `chat()` 내부 messages 조립 로직 제거, `request.messages`를 그대로 payload에 전달 |
| `modelling/api/endpoints/inference.py` | 변경 없음 (`service.chat(request)` 패턴 유지) |
