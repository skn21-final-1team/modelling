"""
LLM-as-a-Judge model validation CLI.

Usage:
    python -m cli.model_validation
    python -m cli.model_validation --base-url http://localhost:8000 --sample-size 10
"""

import argparse
import asyncio
import sys
from pathlib import Path

from core.config import settings
from schemas.validation import ValidationRequest
from services.validation_service import ValidationService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM-as-a-Judge model validation"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="vLLM server base URL",
    )
    parser.add_argument(
        "--csv-path",
        default=None,
        help="Path to test data CSV",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Number of test cases to sample (0 = all)",
    )
    args = parser.parse_args()

    csv_path = (
        Path(args.csv_path)
        if args.csv_path
        else Path(settings.PROCESSED_DATA_DIR) / "processed_v3.csv"
    )

    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}", file=sys.stderr)
        sys.exit(1)

    print("LLM-as-a-Judge Model Validation")
    print(f"Server: {args.base_url}")
    print("=" * 60)

    service = ValidationService(base_url=args.base_url)
    request = ValidationRequest(
        base_url=args.base_url,
        csv_path=str(csv_path),
        sample_size=args.sample_size,
    )

    try:
        summary = asyncio.run(service.run_validation(request, csv_path))
    except Exception as e:
        print(f"FAIL - {e}", file=sys.stderr)
        sys.exit(1)

    if summary.valid == 0:
        print("\nERROR: No valid results obtained")
        sys.exit(1)

    if summary.overall:
        o = summary.overall
        print(f"\nOverall ({summary.valid} valid / {summary.total} total):")
        print(f"  correctness:  {o.correctness:.2f} / 5.00")
        print(f"  relevance:    {o.relevance:.2f} / 5.00")
        print(f"  completeness: {o.completeness:.2f} / 5.00")
        print(f"  average:      {o.average:.2f} / 5.00")

    for qtype, scores in summary.by_type.items():
        print(f"\n  {qtype} (n={scores.count}):")
        print(
            f"    correctness={scores.correctness:.2f}  "
            f"relevance={scores.relevance:.2f}  "
            f"completeness={scores.completeness:.2f}  "
            f"avg={scores.average:.2f}"
        )

    if summary.results_csv_path:
        print(f"\nDetailed results saved to {summary.results_csv_path}")


if __name__ == "__main__":
    main()
