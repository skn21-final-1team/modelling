from datetime import datetime

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

    def shutdown(self) -> None:
        self._gpu.shutdown()
