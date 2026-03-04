from pydantic import BaseModel


class GpuResponse(BaseModel):
    name: str
    utilization: float
    vram_used_gb: float
    vram_total_gb: float
    vram_percent: float
    temperature: int
    power_draw_w: float
    power_limit_w: float


class SystemResponse(BaseModel):
    cpu_percent: float
    cpu_count: int
    ram_used_gb: float
    ram_total_gb: float
    ram_percent: float


class VllmResponse(BaseModel):
    online: bool
    model_name: str
    requests_running: float
    requests_waiting: float
    gpu_cache_usage: float
    cpu_cache_usage: float
    prompt_tps: float
    generation_tps: float


class SnapshotResponse(BaseModel):
    timestamp: str
    gpu: GpuResponse
    system: SystemResponse
    vllm: VllmResponse
