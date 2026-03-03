from fastapi import APIRouter, HTTPException

from core.config import settings
from schemas.base import BaseResponse
from schemas.model_registry import (
    CachedModelResponse,
    ModelPullRequest,
    ModelPullResponse,
)
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
        result = await service.pull_model(
            model_id=request.model_id,
            revision=request.revision,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model pull failed: {e}")
    response = ModelPullResponse(
        model_id=result["model_id"],
        revision=result["revision"],
        local_path=result["local_path"],
        status=result["status"],
    )
    return BaseResponse.ok(data=response)


@router.get("/cached", response_model=BaseResponse[list[CachedModelResponse]])
async def list_cached() -> BaseResponse[list[CachedModelResponse]]:
    service = _get_service()
    results = await service.list_cached_models()
    response = [
        CachedModelResponse(
            model_id=r["model_id"],
            size_gb=r["size_gb"],
            path=r["path"],
        )
        for r in results
    ]
    return BaseResponse.ok(data=response)
