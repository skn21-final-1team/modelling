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
        result = await service.chat(
            prompt=request.prompt,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system_prompt=request.system_prompt,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    response = InferenceResponse(
        content=result["content"],
        model=result["model"],
        ttft_ms=result["ttft_ms"],
        total_s=result["total_s"],
        completion_tokens=result["completion_tokens"],
        throughput_tps=result["throughput_tps"],
    )
    return BaseResponse.ok(data=response)


@router.get("/models")
async def list_models() -> BaseResponse[list[str]]:
    service = InferenceService(base_url=settings.VLLM_BASE_URL)
    try:
        model = await service.detect_model()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    return BaseResponse.ok(data=[model])
