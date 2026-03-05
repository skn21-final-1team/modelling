from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.inference import ChatRequest, InferenceResponse
from services.inference_service import InferenceService

router = APIRouter(prefix="/api/inference", tags=["inference"])


@router.post("/chat", response_model=BaseResponse[InferenceResponse])
async def chat(request: ChatRequest) -> BaseResponse[InferenceResponse]:
    service = InferenceService(base_url=settings.VLLM_BASE_URL)
    try:
        response = await service.chat(request)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    return BaseResponse.ok(data=response)


@router.get("/models")
async def list_models() -> BaseResponse[list[str]]:
    service = InferenceService(base_url=settings.VLLM_BASE_URL)
    try:
        model = await service.detect_model()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    return BaseResponse.ok(data=[model])
