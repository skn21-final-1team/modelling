from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.testing import TestRequest, TestResultResponse, TestSuiteResponse
from services.test_service import TestService

router = APIRouter(prefix="/api/testing", tags=["testing"])


@router.post("/run-all", response_model=BaseResponse[TestSuiteResponse])
async def run_tests(
    request: TestRequest | None = None,
) -> BaseResponse[TestSuiteResponse]:
    base_url = request.base_url if request else settings.VLLM_BASE_URL
    service = TestService(base_url=base_url)
    try:
        result = await service.run_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test execution failed: {e}")
    response = TestSuiteResponse(
        base_url=result["base_url"],
        model=result["model"],
        total=result["total"],
        passed=result["passed"],
        failed=result["failed"],
        results=[
            TestResultResponse(
                name=r["name"],
                passed=r["passed"],
                latency_s=r.get("latency_s"),
                detail=r.get("detail"),
                error=r.get("error"),
            )
            for r in result["results"]
        ],
    )
    return BaseResponse.ok(data=response)
