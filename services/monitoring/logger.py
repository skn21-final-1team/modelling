import csv
import os
from datetime import datetime
from pathlib import Path

from services.monitoring.datamodels import Snapshot

CSV_COLUMNS = [
    "timestamp",
    "gpu_util",
    "vram_used_gb",
    "vram_total_gb",
    "gpu_temp",
    "gpu_power_w",
    "cpu_util",
    "ram_used_gb",
    "ram_total_gb",
    "vllm_online",
    "vllm_requests_running",
    "vllm_requests_waiting",
    "vllm_gpu_cache_pct",
    "vllm_cpu_cache_pct",
    "vllm_prompt_tps",
    "vllm_gen_tps",
]


class CsvLogger:

    def __init__(self, directory: str) -> None:
        os.makedirs(directory, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = Path(directory) / f"monitor_{ts}.csv"
        self._file = open(self._path, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(CSV_COLUMNS)
        self._file.flush()

    @property
    def path(self) -> Path:
        return self._path

    def write(self, snap: Snapshot) -> None:
        self._writer.writerow([
            snap.timestamp,
            f"{snap.gpu.utilization:.1f}",
            f"{snap.gpu.vram_used_gb:.2f}",
            f"{snap.gpu.vram_total_gb:.2f}",
            snap.gpu.temperature,
            f"{snap.gpu.power_draw_w:.1f}",
            f"{snap.system.cpu_percent:.1f}",
            f"{snap.system.ram_used_gb:.2f}",
            f"{snap.system.ram_total_gb:.2f}",
            int(snap.vllm.online),
            f"{snap.vllm.requests_running:.0f}",
            f"{snap.vllm.requests_waiting:.0f}",
            f"{snap.vllm.gpu_cache_usage:.1f}",
            f"{snap.vllm.cpu_cache_usage:.1f}",
            f"{snap.vllm.prompt_tps:.1f}",
            f"{snap.vllm.generation_tps:.1f}",
        ])
        self._file.flush()

    def close(self) -> None:
        self._file.close()
