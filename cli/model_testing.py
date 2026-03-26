"""
vLLM API test suite CLI.

Usage:
    python -m cli.model_testing
    python -m cli.model_testing --base-url http://localhost:8000
"""

import argparse
import asyncio
import sys

from services.test_service import TestService


def main() -> None:
    parser = argparse.ArgumentParser(description="Test vLLM model server")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="vLLM server base URL",
    )
    args = parser.parse_args()

    print(f"Testing vLLM server at {args.base_url}")
    print("=" * 50)

    service = TestService(base_url=args.base_url)
    result = asyncio.run(service.run_all())

    for r in result.results:
        status = "PASS" if r.passed else "FAIL"
        detail_parts: list[str] = []
        if r.latency_s is not None:
            detail_parts.append(f"latency: {r.latency_s}s")
        if r.error:
            detail_parts.append(r.error)
        detail_str = f" ({', '.join(detail_parts)})" if detail_parts else ""
        print(f"  [{status}] {r.name}{detail_str}")

    print(f"\n{'=' * 50}")
    print(f"Results: {result.passed} passed, {result.failed} failed, {result.total} total")
    sys.exit(1 if result.failed > 0 else 0)


if __name__ == "__main__":
    main()
