from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.testing import TestRequest, TestSuiteResponse
from services.test_service import TestService

router = APIRouter(prefix="/api/testing", tags=["testing"])


@router.post("/run-all", response_model=BaseResponse[TestSuiteResponse])
async def run_tests(
    request: TestRequest | None = None,
) -> BaseResponse[TestSuiteResponse]:
    base_url = request.base_url if request else settings.VLLM_BASE_URL
    service = TestService(base_url=base_url)
    try:
        response = await service.run_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test execution failed: {e}")
    return BaseResponse.ok(data=response)
