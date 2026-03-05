# Migration History

## 2026-03-05: inference → chat 리네임

### 변경 사유

OpenAI 호환 API 네이밍 컨벤션에 맞추기 위해 `inference` 관련 이름을 `chat`으로 전면 리네임.

### 파일명 변경

| Before | After |
|--------|-------|
| `schemas/inference.py` | `schemas/chat.py` |
| `services/inference_service.py` | `services/chat_service.py` |
| `api/endpoints/inference.py` | `api/endpoints/chat.py` |

### 클래스/모델명 변경

| Before | After |
|--------|-------|
| `InferenceService` | `ChatCompletionService` |
| `InferenceResponse` | `ChatResponse` |

### 엔드포인트 변경

| Before | After |
|--------|-------|
| `POST /api/inference/chat` | `POST /api/chat/completions` |
| `GET /api/inference/models` | `GET /api/chat/models` |

### 기타

- `ChatRequest.max_tokens` 기본값: 256 → 1024
