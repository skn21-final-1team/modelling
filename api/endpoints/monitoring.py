from fastapi import APIRouter

from core.config import settings
from schemas.base import BaseResponse
from schemas.monitoring import SnapshotResponse
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
    response = service.collect_snapshot_response()
    return BaseResponse.ok(data=response)
