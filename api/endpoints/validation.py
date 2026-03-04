from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.validation import (
    OverallScoreResponse,
    TypeScoreResponse,
    ValidationRequest,
    ValidationSummaryResponse,
)
from services.validation_service import ValidationService

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.post("/run", response_model=BaseResponse[ValidationSummaryResponse])
async def run_validation(
    request: ValidationRequest | None = None,
) -> BaseResponse[ValidationSummaryResponse]:
    base_url = request.base_url if request else settings.VLLM_BASE_URL
    csv_path_str = request.csv_path if request else None
    sample_size = request.sample_size if request else 0

    csv_path = (
        Path(csv_path_str)
        if csv_path_str
        else Path(settings.PROCESSED_DATA_DIR) / "processed_v3.csv"
    )

    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {csv_path}")

    service = ValidationService(base_url=base_url)
    try:
        model = await service.detect_model()
        result = await service.run_validation(model, csv_path, sample_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {e}")

    results_csv_path: str | None = None
    if result.get("results"):
        saved = service.save_results_csv(
            result["results"],
            Path(settings.PROCESSED_DATA_DIR) / "validation_results.csv",
        )
        results_csv_path = str(saved)

    overall = None
    if result.get("overall"):
        o = result["overall"]
        overall = OverallScoreResponse(
            correctness=o["correctness"],
            relevance=o["relevance"],
            completeness=o["completeness"],
            average=o["average"],
        )

    by_type = {
        k: TypeScoreResponse(
            count=v["count"],
            correctness=v["correctness"],
            relevance=v["relevance"],
            completeness=v["completeness"],
            average=v["average"],
        )
        for k, v in result.get("by_type", {}).items()
    }

    response = ValidationSummaryResponse(
        total=result["total"],
        valid=result["valid"],
        overall=overall,
        by_type=by_type,
        results_csv_path=results_csv_path,
    )
    return BaseResponse.ok(data=response)
