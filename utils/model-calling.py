"""
Model Calling Script
Sends a single inference request to the vLLM OpenAI-compatible API.

Usage:
    python /app/scripts/model-calling.py --prompt "Your prompt here" [--base-url http://localhost:8000]

Example:
    python /app/scripts/model-calling.py --prompt "Explain quantum computing in one paragraph."
"""

import argparse
import sys

import requests


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

    # Auto-detect model name from /v1/models endpoint
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

    # Send chat completion request
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }

    try:
        resp = requests.post(
            f"{args.base_url}/v1/chat/completions",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        print(f"\n--- Response ---\n{content}")
        print(f"\n--- Usage ---")
        print(f"Prompt tokens: {result['usage']['prompt_tokens']}")
        print(f"Completion tokens: {result['usage']['completion_tokens']}")
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
