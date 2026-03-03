from fastapi import APIRouter

from core.config import settings
from schemas.base import BaseResponse
from schemas.monitoring import (
    GpuResponse,
    SnapshotResponse,
    SystemResponse,
    VllmResponse,
)
from services.monitoring import MonitoringService

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

_service: MonitoringService | None = None


def _get_service() -> MonitoringService:
    global _service
    if _service is None:
        _service = MonitoringService(vllm_base_url=settings.VLLM_BASE_URL)
    return _service


@router.get("/snapshot", response_model=BaseResponse[SnapshotResponse])
async def get_snapshot() -> BaseResponse[SnapshotResponse]:
    service = _get_service()
    snap = service.collect_snapshot()
    response = SnapshotResponse(
        timestamp=snap.timestamp,
        gpu=GpuResponse(
            name=snap.gpu.name,
            utilization=snap.gpu.utilization,
            vram_used_gb=round(snap.gpu.vram_used_gb, 2),
            vram_total_gb=round(snap.gpu.vram_total_gb, 2),
            vram_percent=round(snap.gpu.vram_percent, 1),
            temperature=snap.gpu.temperature,
            power_draw_w=round(snap.gpu.power_draw_w, 1),
            power_limit_w=round(snap.gpu.power_limit_w, 1),
        ),
        system=SystemResponse(
            cpu_percent=round(snap.system.cpu_percent, 1),
            cpu_count=snap.system.cpu_count,
            ram_used_gb=round(snap.system.ram_used_gb, 2),
            ram_total_gb=round(snap.system.ram_total_gb, 2),
            ram_percent=round(snap.system.ram_percent, 1),
        ),
        vllm=VllmResponse(
            online=snap.vllm.online,
            model_name=snap.vllm.model_name,
            requests_running=snap.vllm.requests_running,
            requests_waiting=snap.vllm.requests_waiting,
            gpu_cache_usage=round(snap.vllm.gpu_cache_usage, 1),
            cpu_cache_usage=round(snap.vllm.cpu_cache_usage, 1),
            prompt_tps=round(snap.vllm.prompt_tps, 1),
            generation_tps=round(snap.vllm.generation_tps, 1),
        ),
    )
    return BaseResponse.ok(data=response)
