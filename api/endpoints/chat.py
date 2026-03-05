from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.chat import ChatRequest, ChatResponse
from services.chat_service import ChatCompletionService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/completions", response_model=BaseResponse[ChatResponse])
async def chat(request: ChatRequest) -> BaseResponse[ChatResponse]:
    service = ChatCompletionService(base_url=settings.VLLM_BASE_URL)
    try:
        response = await service.chat(request)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    return BaseResponse.ok(data=response)


@router.get("/models")
async def list_models() -> BaseResponse[list[str]]:
    service = ChatCompletionService(base_url=settings.VLLM_BASE_URL)
    try:
        model = await service.detect_model()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"vLLM server error: {e}")
    return BaseResponse.ok(data=[model])
