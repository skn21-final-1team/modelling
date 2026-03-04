import csv
import json
import random
import time
from pathlib import Path

import httpx


class ValidationService:

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

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url

    async def detect_model(self) -> str:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self._base_url}/v1/models")
            resp.raise_for_status()
            models = resp.json()["data"]
            return models[0]["id"]

    def load_test_data(self, csv_path: Path) -> list[dict]:
        rows: list[dict] = []
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    async def get_model_answer(
        self, model: str, context: str, question: str
    ) -> dict:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": f"{self.ANSWER_SYSTEM_PROMPT}\n\n## 컨텍스트\n{context}",
                },
                {"role": "user", "content": question},
            ],
            "max_tokens": 512,
            "temperature": 0.0,
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions", json=payload
            )
        latency = time.perf_counter() - start
        resp.raise_for_status()
        result = resp.json()

        return {
            "answer": result["choices"][0]["message"]["content"],
            "latency_s": round(latency, 3),
            "usage": result["usage"],
        }

    async def judge_answer(
        self,
        model: str,
        question: str,
        reference_answer: str,
        model_answer: str,
    ) -> dict:
        user_content = self.JUDGE_USER_TEMPLATE.format(
            question=question,
            reference_answer=reference_answer,
            model_answer=model_answer,
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 256,
            "temperature": 0.0,
        }

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions", json=payload
            )
        latency = time.perf_counter() - start
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        scores = self._parse_judge_response(raw)
        scores["judge_latency_s"] = round(latency, 3)
        return scores

    def _parse_judge_response(self, raw: str) -> dict:
        try:
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except (json.JSONDecodeError, IndexError):
            start_idx = raw.find("{")
            end_idx = raw.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(raw[start_idx:end_idx])
                except json.JSONDecodeError:
                    pass
            return {
                "correctness": 0,
                "relevance": 0,
                "completeness": 0,
                "reasoning": f"JSON parse failed: {raw[:200]}",
            }

    async def run_validation(
        self, model: str, csv_path: Path, sample_size: int = 0
    ) -> dict:
        test_data = self.load_test_data(csv_path)

        if 0 < sample_size < len(test_data):
            random.seed(42)
            test_data = random.sample(test_data, sample_size)

        results: list[dict] = []
        type_scores: dict[str, list[dict]] = {}

        for row in test_data:
            content_id = row["content_id"]
            question = row["question"]
            context = row["context"]
            reference_answer = row["reference_answer"]
            question_type = row["question_type"]

            try:
                answer_result = await self.get_model_answer(model, context, question)
                model_answer = answer_result["answer"]
            except Exception as e:
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

            try:
                judge_result = await self.judge_answer(
                    model, question, reference_answer, model_answer
                )
            except Exception as e:
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
                "reasoning": judge_result.get("reasoning", ""),
                "answer_latency_s": answer_result["latency_s"],
                "judge_latency_s": judge_result["judge_latency_s"],
            }
            results.append(record)

            if question_type not in type_scores:
                type_scores[question_type] = []
            type_scores[question_type].append(judge_result)

        return self._aggregate_scores(results, type_scores)

    def _aggregate_scores(
        self, results: list[dict], type_scores: dict[str, list[dict]]
    ) -> dict:
        valid_results = [r for r in results if r["correctness"] > 0]
        summary: dict = {
            "total": len(results),
            "valid": len(valid_results),
            "results": results,
        }

        if valid_results:
            overall_correctness = sum(r["correctness"] for r in valid_results) / len(valid_results)
            overall_relevance = sum(r["relevance"] for r in valid_results) / len(valid_results)
            overall_completeness = sum(r["completeness"] for r in valid_results) / len(valid_results)
            overall_avg = (overall_correctness + overall_relevance + overall_completeness) / 3

            summary["overall"] = {
                "correctness": round(overall_correctness, 2),
                "relevance": round(overall_relevance, 2),
                "completeness": round(overall_completeness, 2),
                "average": round(overall_avg, 2),
            }

        summary["by_type"] = {}
        for qtype, scores in sorted(type_scores.items()):
            valid = [s for s in scores if s["correctness"] > 0]
            if not valid:
                continue
            avg_c = sum(s["correctness"] for s in valid) / len(valid)
            avg_r = sum(s["relevance"] for s in valid) / len(valid)
            avg_comp = sum(s["completeness"] for s in valid) / len(valid)
            avg_all = (avg_c + avg_r + avg_comp) / 3
            summary["by_type"][qtype] = {
                "count": len(valid),
                "correctness": round(avg_c, 2),
                "relevance": round(avg_r, 2),
                "completeness": round(avg_comp, 2),
                "average": round(avg_all, 2),
            }

        return summary

    def save_results_csv(self, results: list[dict], path: Path) -> Path:
        fieldnames = [
            "content_id", "question_type", "question", "model_answer",
            "correctness", "relevance", "completeness", "reasoning",
            "answer_latency_s", "judge_latency_s",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        return path
