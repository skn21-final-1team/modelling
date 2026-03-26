from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.validation import ValidationRequest, ValidationSummaryResponse
from services.validation_service import ValidationService

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.post("/run", response_model=BaseResponse[ValidationSummaryResponse])
async def run_validation(
    request: ValidationRequest | None = None,
) -> BaseResponse[ValidationSummaryResponse]:
    req = request or ValidationRequest()
    base_url = req.base_url or settings.VLLM_BASE_URL

    csv_path = (
        Path(req.csv_path)
        if req.csv_path
        else Path(settings.PROCESSED_DATA_DIR) / "processed_v3.csv"
    )

    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found: {csv_path}")

    service = ValidationService(base_url=base_url)
    try:
        response = await service.run_validation(req, csv_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {e}")

    return BaseResponse.ok(data=response)
