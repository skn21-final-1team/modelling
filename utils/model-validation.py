"""
Model Validation Script (LLM-as-a-Judge)
Evaluates model response quality using the same vLLM server as both answerer and judge.

Usage:
    python utils/model-validation.py [--base-url http://localhost:8000] [--sample-size 10]

Reads QA pairs from data/processed/processed_v3.csv and:
    1. Sends context + question to the model → gets model_answer
    2. Sends (question, reference_answer, model_answer) to the same model as judge → gets score
    3. Aggregates scores by question_type and outputs results
"""

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "data" / "processed" / "processed_v3.csv"
RESULTS_PATH = BASE_DIR / "data" / "processed" / "validation_results.csv"

ANSWER_SYSTEM_PROMPT = (
    "당신은 한국어 위키백과 기반의 질문에 정확하게 답변하는 AI 어시스턴트입니다. "
    "주어진 컨텍스트를 기반으로 질문에 답변해주세요. "
    "컨텍스트에 없는 정보는 추측하지 마세요."
)

JUDGE_SYSTEM_PROMPT = (
    "당신은 AI 응답 품질을 평가하는 전문 평가자입니다. "
    "질문, 참조 답변(정답), 모델 답변이 주어지면 아래 3가지 기준으로 1-5점 채점하세요.\n\n"
    "채점 기준:\n"
    "- correctness (정확성): 모델 답변이 참조 답변과 사실적으로 일치하는 정도 "
    "(1=완전히 틀림, 5=완벽히 일치)\n"
    "- relevance (관련성): 모델 답변이 질문에 대해 적절히 답하는 정도 "
    "(1=무관한 답변, 5=정확히 질문에 답함)\n"
    "- completeness (완전성): 참조 답변의 핵심 정보를 모델 답변이 포함하는 정도 "
    "(1=핵심 정보 누락, 5=모든 핵심 정보 포함)\n\n"
    "반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:\n"
    '{"correctness": N, "relevance": N, "completeness": N, "reasoning": "평가 근거"}'
)

JUDGE_USER_TEMPLATE = (
    "## 질문\n{question}\n\n"
    "## 참조 답변 (정답)\n{reference_answer}\n\n"
    "## 모델 답변\n{model_answer}\n\n"
    "위 내용을 기반으로 모델 답변을 평가하세요."
)


def load_test_data() -> list[dict]:
    """Load QA test data from the hardcoded CSV path."""
    if not CSV_PATH.exists():
        print(f"ERROR: CSV not found at {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    rows: list[dict] = []
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    print(f"Loaded {len(rows)} test cases from {CSV_PATH}")
    return rows


def detect_model(base_url: str) -> str:
    """Auto-detect model name from vLLM /v1/models endpoint."""
    try:
        resp = requests.get(f"{base_url}/v1/models", timeout=5)
        resp.raise_for_status()
        models = resp.json()["data"]
        model_name = models[0]["id"]
        print(f"Auto-detected model: {model_name}")
        return model_name
    except Exception as e:
        print(f"ERROR: Could not detect model. Is vLLM running? {e}", file=sys.stderr)
        sys.exit(1)


def get_model_answer(
    base_url: str, model: str, context: str, question: str
) -> dict:
    """Send context + question to vLLM and return the model's answer."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": f"{ANSWER_SYSTEM_PROMPT}\n\n## 컨텍스트\n{context}"},
            {"role": "user", "content": question},
        ],
        "max_tokens": 512,
        "temperature": 0.0,
    }

    start = time.time()
    resp = requests.post(
        f"{base_url}/v1/chat/completions", json=payload, timeout=120
    )
    latency = time.time() - start
    resp.raise_for_status()
    result = resp.json()

    return {
        "answer": result["choices"][0]["message"]["content"],
        "latency_s": round(latency, 3),
        "usage": result["usage"],
    }


def judge_answer(
    base_url: str,
    model: str,
    question: str,
    reference_answer: str,
    model_answer: str,
) -> dict:
    """Use the same LLM as judge to score the model's answer."""
    user_content = JUDGE_USER_TEMPLATE.format(
        question=question,
        reference_answer=reference_answer,
        model_answer=model_answer,
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 256,
        "temperature": 0.0,
    }

    start = time.time()
    resp = requests.post(
        f"{base_url}/v1/chat/completions", json=payload, timeout=120
    )
    latency = time.time() - start
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

    # Parse JSON from judge response
    try:
        # Handle cases where model wraps JSON in markdown code block
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        scores = json.loads(raw)
    except (json.JSONDecodeError, IndexError):
        # Fallback: try to extract JSON from response
        start_idx = raw.find("{")
        end_idx = raw.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            try:
                scores = json.loads(raw[start_idx:end_idx])
            except json.JSONDecodeError:
                scores = {
                    "correctness": 0,
                    "relevance": 0,
                    "completeness": 0,
                    "reasoning": f"JSON parse failed: {raw[:200]}",
                }
        else:
            scores = {
                "correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "reasoning": f"JSON parse failed: {raw[:200]}",
            }

    return {
        "correctness": scores.get("correctness", 0),
        "relevance": scores.get("relevance", 0),
        "completeness": scores.get("completeness", 0),
        "reasoning": scores.get("reasoning", ""),
        "judge_latency_s": round(latency, 3),
    }


def run_validation(
    base_url: str, model: str, sample_size: int
) -> dict:
    """Run the full LLM-as-a-Judge validation pipeline."""
    test_data = load_test_data()

    if sample_size > 0 and sample_size < len(test_data):
        random.seed(42)
        test_data = random.sample(test_data, sample_size)
        print(f"Sampled {sample_size} test cases (seed=42)")

    total = len(test_data)
    results: list[dict] = []
    type_scores: dict[str, list[dict]] = {}

    print(f"\nRunning validation on {total} test cases...")
    print("=" * 60)

    for i, row in enumerate(test_data):
        content_id = row["content_id"]
        question = row["question"]
        context = row["context"]
        reference_answer = row["reference_answer"]
        question_type = row["question_type"]

        print(f"\n[{i + 1}/{total}] content_id={content_id} type={question_type}")
        print(f"  Q: {question[:60]}...")

        # Step 1: Get model answer
        try:
            answer_result = get_model_answer(base_url, model, context, question)
            model_answer = answer_result["answer"]
            print(f"  A: {model_answer[:60]}... ({answer_result['latency_s']}s)")
        except Exception as e:
            print(f"  ERROR (answer): {e}")
            results.append({
                "content_id": content_id,
                "question_type": question_type,
                "question": question,
                "model_answer": "",
                "correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "reasoning": f"Answer generation failed: {e}",
                "answer_latency_s": 0,
                "judge_latency_s": 0,
            })
            continue

        # Step 2: Judge the answer
        try:
            judge_result = judge_answer(
                base_url, model, question, reference_answer, model_answer
            )
            print(
                f"  Score: correctness={judge_result['correctness']} "
                f"relevance={judge_result['relevance']} "
                f"completeness={judge_result['completeness']} "
                f"({judge_result['judge_latency_s']}s)"
            )
        except Exception as e:
            print(f"  ERROR (judge): {e}")
            judge_result = {
                "correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "reasoning": f"Judge failed: {e}",
                "judge_latency_s": 0,
            }

        record = {
            "content_id": content_id,
            "question_type": question_type,
            "question": question,
            "model_answer": model_answer,
            "correctness": judge_result["correctness"],
            "relevance": judge_result["relevance"],
            "completeness": judge_result["completeness"],
            "reasoning": judge_result["reasoning"],
            "answer_latency_s": answer_result["latency_s"],
            "judge_latency_s": judge_result["judge_latency_s"],
        }
        results.append(record)

        # Accumulate by type
        if question_type not in type_scores:
            type_scores[question_type] = []
        type_scores[question_type].append(judge_result)

    # Aggregate results
    summary = _aggregate_scores(results, type_scores)

    # Save detailed results to CSV
    _save_results_csv(results)

    return summary


def _aggregate_scores(
    results: list[dict], type_scores: dict[str, list[dict]]
) -> dict:
    """Aggregate scores by question_type and overall."""
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)

    valid_results = [r for r in results if r["correctness"] > 0]
    summary: dict = {"total": len(results), "valid": len(valid_results)}

    if valid_results:
        overall_correctness = sum(r["correctness"] for r in valid_results) / len(valid_results)
        overall_relevance = sum(r["relevance"] for r in valid_results) / len(valid_results)
        overall_completeness = sum(r["completeness"] for r in valid_results) / len(valid_results)
        overall_avg = (overall_correctness + overall_relevance + overall_completeness) / 3

        print(f"\nOverall ({len(valid_results)} valid / {len(results)} total):")
        print(f"  correctness:  {overall_correctness:.2f} / 5.00")
        print(f"  relevance:    {overall_relevance:.2f} / 5.00")
        print(f"  completeness: {overall_completeness:.2f} / 5.00")
        print(f"  average:      {overall_avg:.2f} / 5.00")

        summary["overall"] = {
            "correctness": round(overall_correctness, 2),
            "relevance": round(overall_relevance, 2),
            "completeness": round(overall_completeness, 2),
            "average": round(overall_avg, 2),
        }

    print(f"\nBy question_type:")
    summary["by_type"] = {}

    for qtype, scores in sorted(type_scores.items()):
        valid = [s for s in scores if s["correctness"] > 0]
        if not valid:
            print(f"  {qtype}: no valid scores")
            continue

        avg_c = sum(s["correctness"] for s in valid) / len(valid)
        avg_r = sum(s["relevance"] for s in valid) / len(valid)
        avg_comp = sum(s["completeness"] for s in valid) / len(valid)
        avg_all = (avg_c + avg_r + avg_comp) / 3

        print(f"  {qtype} (n={len(valid)}):")
        print(f"    correctness={avg_c:.2f}  relevance={avg_r:.2f}  "
              f"completeness={avg_comp:.2f}  avg={avg_all:.2f}")

        summary["by_type"][qtype] = {
            "count": len(valid),
            "correctness": round(avg_c, 2),
            "relevance": round(avg_r, 2),
            "completeness": round(avg_comp, 2),
            "average": round(avg_all, 2),
        }

    return summary


def _save_results_csv(results: list[dict]) -> None:
    """Save detailed validation results to CSV."""
    if not results:
        return

    fieldnames = [
        "content_id", "question_type", "question", "model_answer",
        "correctness", "relevance", "completeness", "reasoning",
        "answer_latency_s", "judge_latency_s",
    ]

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDetailed results saved to {RESULTS_PATH}")


def main():
    parser = argparse.ArgumentParser(
        description="LLM-as-a-Judge model validation"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="vLLM server base URL",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=0,
        help="Number of test cases to sample (0 = all)",
    )
    args = parser.parse_args()

    print("LLM-as-a-Judge Model Validation")
    print(f"Server: {args.base_url}")
    print("=" * 60)

    # Health check
    print("\n[Health Check]...", end=" ")
    try:
        resp = requests.get(f"{args.base_url}/health", timeout=10)
        if resp.status_code != 200:
            print(f"FAIL (status={resp.status_code})")
            sys.exit(1)
        print("OK")
    except Exception:
        print("FAIL - Server not responding")
        sys.exit(1)

    # Detect model
    model = detect_model(args.base_url)

    # Run validation
    summary = run_validation(args.base_url, model, args.sample_size)

    # Exit code based on results
    if summary.get("valid", 0) == 0:
        print("\nERROR: No valid results obtained")
        sys.exit(1)

    avg = summary.get("overall", {}).get("average", 0)
    print(f"\nFinal average score: {avg:.2f} / 5.00")
    sys.exit(0)


if __name__ == "__main__":
    main()
