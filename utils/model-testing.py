"""
Model Testing Script
Runs a suite of tests against the vLLM OpenAI-compatible API.

Usage:
    python /app/scripts/model-testing.py [--base-url http://localhost:8000]

Tests:
    1. Health check (/health)
    2. Model listing (/v1/models)
    3. Chat completion (/v1/chat/completions)
    4. Text completion (/v1/completions)
    5. Streaming chat completion
"""

import argparse
import sys
import time

import requests


def test_health(base_url: str) -> bool:
    """Test vLLM health endpoint."""
    try:
        resp = requests.get(f"{base_url}/health", timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def test_models(base_url: str) -> str | None:
    """Test /v1/models and return the first model ID."""
    resp = requests.get(f"{base_url}/v1/models", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    assert len(data["data"]) > 0, "No models loaded"
    return data["data"][0]["id"]


def test_chat_completion(base_url: str, model: str) -> dict:
    """Test /v1/chat/completions endpoint."""
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Say 'hello' and nothing else."}
        ],
        "max_tokens": 16,
        "temperature": 0.0,
    }
    start = time.time()
    resp = requests.post(
        f"{base_url}/v1/chat/completions", json=payload, timeout=60
    )
    latency = time.time() - start
    resp.raise_for_status()
    result = resp.json()
    content = result["choices"][0]["message"]["content"]
    assert len(content) > 0, "Empty response"
    return {
        "content": content,
        "latency_s": round(latency, 3),
        "usage": result["usage"],
    }


def test_completion(base_url: str, model: str) -> dict:
    """Test /v1/completions endpoint."""
    payload = {
        "model": model,
        "prompt": "The capital of France is",
        "max_tokens": 16,
        "temperature": 0.0,
    }
    start = time.time()
    resp = requests.post(
        f"{base_url}/v1/completions", json=payload, timeout=60
    )
    latency = time.time() - start
    resp.raise_for_status()
    result = resp.json()
    text = result["choices"][0]["text"]
    assert len(text) > 0, "Empty response"
    return {"text": text, "latency_s": round(latency, 3), "usage": result["usage"]}


def test_streaming(base_url: str, model: str) -> dict:
    """Test streaming chat completion."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Count from 1 to 5."}],
        "max_tokens": 64,
        "temperature": 0.0,
        "stream": True,
    }
    start = time.time()
    resp = requests.post(
        f"{base_url}/v1/chat/completions",
        json=payload,
        stream=True,
        timeout=60,
    )
    resp.raise_for_status()

    chunks = 0
    ttft = None
    for line in resp.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: ") and decoded != "data: [DONE]":
                if ttft is None:
                    ttft = time.time() - start
                chunks += 1

    total_latency = time.time() - start
    assert chunks > 0, "No streaming chunks received"
    return {
        "chunks": chunks,
        "ttft_s": round(ttft, 3),
        "total_s": round(total_latency, 3),
    }


def main():
    parser = argparse.ArgumentParser(description="Test vLLM model server")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="vLLM server base URL",
    )
    args = parser.parse_args()

    print(f"Testing vLLM server at {args.base_url}")
    print("=" * 50)

    passed = 0
    failed = 0

    # Test 1: Health
    print("\n[1/5] Health Check...", end=" ")
    if test_health(args.base_url):
        print("PASS")
        passed += 1
    else:
        print("FAIL - Server not responding")
        print(
            "Start vLLM with: vllm serve <model> --host 0.0.0.0 --port 8000 &"
        )
        sys.exit(1)

    # Test 2: Models
    print("[2/5] Model Listing...", end=" ")
    try:
        model = test_models(args.base_url)
        print(f"PASS (model: {model})")
        passed += 1
    except Exception as e:
        print(f"FAIL ({e})")
        failed += 1
        sys.exit(1)

    # Test 3: Chat Completion
    print("[3/5] Chat Completion...", end=" ")
    try:
        result = test_chat_completion(args.base_url, model)
        print(
            f"PASS (latency: {result['latency_s']}s, "
            f"tokens: {result['usage']['completion_tokens']})"
        )
        passed += 1
    except Exception as e:
        print(f"FAIL ({e})")
        failed += 1

    # Test 4: Text Completion
    print("[4/5] Text Completion...", end=" ")
    try:
        result = test_completion(args.base_url, model)
        print(
            f"PASS (latency: {result['latency_s']}s, "
            f"text: {result['text'][:50]}...)"
        )
        passed += 1
    except Exception as e:
        print(f"FAIL ({e})")
        failed += 1

    # Test 5: Streaming
    print("[5/5] Streaming...", end=" ")
    try:
        result = test_streaming(args.base_url, model)
        print(
            f"PASS (TTFT: {result['ttft_s']}s, "
            f"chunks: {result['chunks']}, total: {result['total_s']}s)"
        )
        passed += 1
    except Exception as e:
        print(f"FAIL ({e})")
        failed += 1

    # Summary
    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
