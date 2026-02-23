"""
Model Calling Script
Sends a single inference request to the vLLM OpenAI-compatible API.

Usage:
    python utils/model-calling.py --prompt "Your prompt here" [--base-url http://localhost:8000]

Example:
    python utils/model-calling.py --prompt "Explain quantum computing in one paragraph."
"""

import argparse
import json
import sys
import time

import requests


def stream_completion(base_url: str, payload: dict) -> dict:
    """Stream chat completion and measure latency metrics."""
    payload["stream"] = True
    t_start = time.perf_counter()
    ttft = None
    full_content = ""
    completion_tokens = 0

    resp = requests.post(
        f"{base_url}/v1/chat/completions",
        json=payload,
        timeout=120,
        stream=True,
    )
    resp.raise_for_status()

    for raw_line in resp.iter_lines(decode_unicode=True):
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

    return {
        "content": full_content,
        "ttft_ms": (ttft or 0) * 1000,
        "total_s": t_total,
        "completion_tokens": completion_tokens,
    }


def main():
    parser = argparse.ArgumentParser(description="Call vLLM model server")
    parser.add_argument(
        "--prompt", required=True, help="Input prompt for generation"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="vLLM server base URL",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (auto-detected if not set)",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=256, help="Maximum tokens to generate"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="Sampling temperature"
    )
    args = parser.parse_args()

    model_name = args.model
    if model_name is None:
        try:
            resp = requests.get(f"{args.base_url}/v1/models", timeout=5)
            resp.raise_for_status()
            models = resp.json()["data"]
            model_name = models[0]["id"]
            print(f"Auto-detected model: {model_name}")
        except Exception as e:
            print(
                f"ERROR: Could not detect model. Is vLLM running? {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }

    try:
        result = stream_completion(args.base_url, payload)

        print(f"\n--- Response ---\n{result['content']}")
        print(f"\n--- Latency ---")
        print(f"TTFT (Time To First Token): {result['ttft_ms']:.1f} ms")
        print(f"Total time:                 {result['total_s']:.3f} s")
        if result["completion_tokens"] > 0 and result["total_s"] > 0:
            tps = result["completion_tokens"] / result["total_s"]
            print(f"Throughput:                 {tps:.1f} tokens/s")
        print(f"\n--- Usage ---")
        print(f"Completion tokens: {result['completion_tokens']}")
    except requests.ConnectionError:
        print(
            "ERROR: Cannot connect to vLLM server. Start it with:",
            file=sys.stderr,
        )
        print(
            "  vllm serve <model_id> --host 0.0.0.0 --port 8000 &",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
