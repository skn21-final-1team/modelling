import asyncio
from pathlib import Path

from huggingface_hub import scan_cache_dir, snapshot_download

from schemas.model_registry import CachedModelResponse, ModelPullRequest, ModelPullResponse


class ModelRegistryService:

    def __init__(self, token: str, cache_dir: str) -> None:
        self._token = token or None
        self._cache_dir = cache_dir

    async def pull_model(self, request: ModelPullRequest) -> ModelPullResponse:
        path = await asyncio.to_thread(
            snapshot_download,
            repo_id=request.model_id,
            revision=request.revision,
            cache_dir=self._cache_dir,
            token=self._token,
        )
        return ModelPullResponse(
            model_id=request.model_id,
            revision=request.revision,
            local_path=str(path),
            status="downloaded",
        )

    async def list_cached_models(self) -> list[CachedModelResponse]:
        cache_dir = Path(self._cache_dir)
        if not cache_dir.exists():
            return []

        cache_info = await asyncio.to_thread(scan_cache_dir, self._cache_dir)
        results: list[CachedModelResponse] = []
        for repo in cache_info.repos:
            size_gb = repo.size_on_disk / (1024**3)
            results.append(CachedModelResponse(
                model_id=repo.repo_id,
                size_gb=round(size_gb, 2),
                path=str(repo.repo_path),
            ))
        return results
