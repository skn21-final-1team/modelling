import json
import time

import httpx

from schemas.inference import ChatRequest, InferenceResponse


class InferenceService:

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def detect_model(self) -> str:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self._base_url}/v1/models")
            resp.raise_for_status()
            models = resp.json()["data"]
            return models[0]["id"]

    async def _stream_completion(self, payload: dict) -> dict:
        payload["stream"] = True
        t_start = time.perf_counter()
        ttft: float | None = None
        full_content = ""
        completion_tokens = 0

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for raw_line in resp.aiter_lines():
                    if not raw_line or not raw_line.startswith("data: "):
                        continue
                    data_str = raw_line[len("data: "):]
                    if data_str.strip() == "[DONE]":
                        break

                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    token_text = delta.get("content", "")
                    if token_text:
                        if ttft is None:
                            ttft = time.perf_counter() - t_start
                        full_content += token_text
                        completion_tokens += 1

        t_total = time.perf_counter() - t_start
        throughput = completion_tokens / t_total if t_total > 0 else 0.0

        return {
            "content": full_content,
            "ttft_ms": (ttft or 0) * 1000,
            "total_s": t_total,
            "completion_tokens": completion_tokens,
            "throughput_tps": round(throughput, 1),
        }

    async def chat(self, request: ChatRequest) -> InferenceResponse:
        model_name = request.model or await self.detect_model()

        payload = {
            "model": model_name,
            "messages": [m.model_dump() for m in request.messages],
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
