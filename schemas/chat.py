from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7


class ChatResponse(BaseModel):
    content: str
    model: str
    ttft_ms: float
    total_s: float
    completion_tokens: int
    throughput_tps: float
