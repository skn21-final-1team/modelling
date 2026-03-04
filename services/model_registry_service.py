import asyncio
import os
from pathlib import Path

from huggingface_hub import scan_cache_dir, snapshot_download


class ModelRegistryService:

    def __init__(self, token: str, cache_dir: str) -> None:
        self._token = token or None
        self._cache_dir = cache_dir

    async def pull_model(self, model_id: str, revision: str = "main") -> dict:
        path = await asyncio.to_thread(
            snapshot_download,
            repo_id=model_id,
            revision=revision,
            cache_dir=self._cache_dir,
            token=self._token,
        )
        return {
            "model_id": model_id,
            "revision": revision,
            "local_path": str(path),
            "status": "downloaded",
        }

    async def list_cached_models(self) -> list[dict]:
        cache_dir = Path(self._cache_dir)
        if not cache_dir.exists():
            return []

        cache_info = await asyncio.to_thread(scan_cache_dir, self._cache_dir)
        results: list[dict] = []
        for repo in cache_info.repos:
            size_gb = repo.size_on_disk / (1024**3)
            results.append({
                "model_id": repo.repo_id,
                "size_gb": round(size_gb, 2),
                "path": str(repo.repo_path),
            })
        return results
