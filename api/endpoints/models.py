from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.model_registry import CachedModelResponse, ModelPullRequest, ModelPullResponse
from services.model_registry_service import ModelRegistryService

router = APIRouter(prefix="/api/models", tags=["models"])


def _get_service() -> ModelRegistryService:
    return ModelRegistryService(
        token=settings.HF_TOKEN,
        cache_dir=settings.HF_HOME,
    )


@router.post("/pull", response_model=BaseResponse[ModelPullResponse])
async def pull_model(
    request: ModelPullRequest,
) -> BaseResponse[ModelPullResponse]:
    service = _get_service()
    try:
        response = await service.pull_model(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model pull failed: {e}")
    return BaseResponse.ok(data=response)


@router.get("/cached", response_model=BaseResponse[list[CachedModelResponse]])
async def list_cached() -> BaseResponse[list[CachedModelResponse]]:
    service = _get_service()
    response = await service.list_cached_models()
    return BaseResponse.ok(data=response)
