import time

import httpx


class TestService:

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def test_health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/health")
                passed = resp.status_code == 200
            return {"name": "health", "passed": passed}
        except Exception as e:
            return {"name": "health", "passed": False, "error": str(e)}

    async def test_models(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/v1/models")
                resp.raise_for_status()
                data = resp.json()
                model_id = data["data"][0]["id"]
            return {
                "name": "models",
                "passed": True,
                "detail": {"model": model_id},
            }
        except Exception as e:
            return {"name": "models", "passed": False, "error": str(e)}

    async def test_chat_completion(self, model: str) -> dict:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Say 'hello' and nothing else."}
            ],
            "max_tokens": 16,
            "temperature": 0.0,
        }
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
            latency = time.perf_counter() - start
            resp.raise_for_status()
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            return {
                "name": "chat_completion",
                "passed": len(content) > 0,
                "latency_s": round(latency, 3),
                "detail": {"content": content, "usage": result["usage"]},
            }
        except Exception as e:
            return {"name": "chat_completion", "passed": False, "error": str(e)}

    async def test_completion(self, model: str) -> dict:
        payload = {
            "model": model,
            "prompt": "The capital of France is",
            "max_tokens": 16,
            "temperature": 0.0,
        }
        try:
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/completions", json=payload
                )
            latency = time.perf_counter() - start
            resp.raise_for_status()
            result = resp.json()
            text = result["choices"][0]["text"]
            return {
                "name": "completion",
                "passed": len(text) > 0,
                "latency_s": round(latency, 3),
                "detail": {"text": text, "usage": result["usage"]},
            }
        except Exception as e:
            return {"name": "completion", "passed": False, "error": str(e)}

    async def test_streaming(self, model: str) -> dict:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Count from 1 to 5."}],
            "max_tokens": 64,
            "temperature": 0.0,
            "stream": True,
        }
        try:
            start = time.perf_counter()
            ttft: float | None = None
            chunks = 0

            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            if ttft is None:
                                ttft = time.perf_counter() - start
                            chunks += 1

            total_latency = time.perf_counter() - start
            return {
                "name": "streaming",
                "passed": chunks > 0,
                "latency_s": round(total_latency, 3),
                "detail": {
                    "chunks": chunks,
                    "ttft_s": round(ttft, 3) if ttft else None,
                },
            }
        except Exception as e:
            return {"name": "streaming", "passed": False, "error": str(e)}

    async def run_all(self) -> dict:
        health = await self.test_health()
        if not health["passed"]:
            return {
                "base_url": self._base_url,
                "model": None,
                "total": 1,
                "passed": 0,
                "failed": 1,
                "results": [health],
            }

        models_result = await self.test_models()
        model = models_result.get("detail", {}).get("model")
        if not model:
            return {
                "base_url": self._base_url,
                "model": None,
                "total": 2,
                "passed": 1,
                "failed": 1,
                "results": [health, models_result],
            }

        chat = await self.test_chat_completion(model)
        completion = await self.test_completion(model)
        streaming = await self.test_streaming(model)

        results = [health, models_result, chat, completion, streaming]
        passed = sum(1 for r in results if r["passed"])
        failed = len(results) - passed

        return {
            "base_url": self._base_url,
            "model": model,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "results": results,
        }
