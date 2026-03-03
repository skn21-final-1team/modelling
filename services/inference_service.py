import json
import time

import httpx


class InferenceService:

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def detect_model(self) -> str:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self._base_url}/v1/models")
            resp.raise_for_status()
            models = resp.json()["data"]
            return models[0]["id"]

    async def stream_completion(self, payload: dict) -> dict:
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

    async def chat(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 256,
        temperature: float = 0.7,
        system_prompt: str | None = None,
    ) -> dict:
        model_name = model or await self.detect_model()

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        result = await self.stream_completion(payload)
        result["model"] = model_name
        return result
