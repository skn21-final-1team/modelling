from pydantic import BaseModel


class ChatRequest(BaseModel):
    prompt: str
    model: str | None = None
    max_tokens: int = 256
    temperature: float = 0.7
    system_prompt: str | None = None


class InferenceResponse(BaseModel):
    content: str
    model: str
    ttft_ms: float
    total_s: float
    completion_tokens: int
    throughput_tps: float
