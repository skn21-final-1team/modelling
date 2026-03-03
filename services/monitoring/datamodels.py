from dataclasses import dataclass, field


@dataclass
class GpuMetrics:
    name: str = "N/A"
    utilization: float = 0.0
    vram_used_gb: float = 0.0
    vram_total_gb: float = 0.0
    temperature: int = 0
    power_draw_w: float = 0.0
    power_limit_w: float = 0.0

    @property
    def vram_percent(self) -> float:
        if self.vram_total_gb == 0:
            return 0.0
        return (self.vram_used_gb / self.vram_total_gb) * 100


@dataclass
class SystemMetrics:
    cpu_percent: float = 0.0
    cpu_count: int = 0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0

    @property
    def ram_percent(self) -> float:
        if self.ram_total_gb == 0:
            return 0.0
        return (self.ram_used_gb / self.ram_total_gb) * 100


@dataclass
class VllmMetrics:
    online: bool = False
    model_name: str = "N/A"
    requests_running: float = 0.0
    requests_waiting: float = 0.0
    gpu_cache_usage: float = 0.0
    cpu_cache_usage: float = 0.0
    prompt_tps: float = 0.0
    generation_tps: float = 0.0


@dataclass
class Snapshot:
    timestamp: str = ""
    gpu: GpuMetrics = field(default_factory=GpuMetrics)
    system: SystemMetrics = field(default_factory=SystemMetrics)
    vllm: VllmMetrics = field(default_factory=VllmMetrics)
