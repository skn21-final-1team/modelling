from datetime import datetime

from schemas.monitoring import GpuResponse, SnapshotResponse, SystemResponse, VllmResponse
from services.monitoring.collectors import GpuCollector, SystemCollector, VllmCollector
from services.monitoring.datamodels import Snapshot


class MonitoringService:

    def __init__(self, vllm_base_url: str) -> None:
        self._gpu = GpuCollector()
        self._sys = SystemCollector()
        self._vllm = VllmCollector(vllm_base_url)

    def collect_snapshot(self) -> Snapshot:
        return Snapshot(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            gpu=self._gpu.collect(),
            system=self._sys.collect(),
            vllm=self._vllm.collect(),
        )

    def collect_snapshot_response(self) -> SnapshotResponse:
        snap = self.collect_snapshot()
        return SnapshotResponse(
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

    def shutdown(self) -> None:
        self._gpu.shutdown()
