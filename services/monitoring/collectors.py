import re

import psutil
import requests

from services.monitoring.datamodels import GpuMetrics, SystemMetrics, VllmMetrics

try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False


class GpuCollector:

    def __init__(self) -> None:
        self._handle = None
        if not PYNVML_AVAILABLE:
            return
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except pynvml.NVMLError:
            self._handle = None

    def collect(self) -> GpuMetrics:
        m = GpuMetrics()
        if self._handle is None:
            return m
        try:
            m.name = pynvml.nvmlDeviceGetName(self._handle)
            if isinstance(m.name, bytes):
                m.name = m.name.decode()

            util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            m.utilization = float(util.gpu)

            mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            m.vram_used_gb = mem.used / (1024**3)
            m.vram_total_gb = mem.total / (1024**3)

            m.temperature = pynvml.nvmlDeviceGetTemperature(
                self._handle, pynvml.NVML_TEMPERATURE_GPU
            )

            m.power_draw_w = pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000.0
            try:
                m.power_limit_w = (
                    pynvml.nvmlDeviceGetEnforcedPowerLimit(self._handle) / 1000.0
                )
            except pynvml.NVMLError:
                m.power_limit_w = 0.0
        except pynvml.NVMLError:
            pass
        return m

    def shutdown(self) -> None:
        if PYNVML_AVAILABLE and self._handle is not None:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass


class SystemCollector:

    def collect(self) -> SystemMetrics:
        mem = psutil.virtual_memory()
        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=None),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            ram_used_gb=mem.used / (1024**3),
            ram_total_gb=mem.total / (1024**3),
        )


class VllmCollector:

    _GAUGE_PATTERNS = {
        "requests_running": re.compile(
            r'^vllm:num_requests_running\b.*?\s+([\d.eE+-]+)$', re.MULTILINE
        ),
        "requests_waiting": re.compile(
            r'^vllm:num_requests_waiting\b.*?\s+([\d.eE+-]+)$', re.MULTILINE
        ),
        "gpu_cache_usage": re.compile(
            r'^vllm:gpu_cache_usage_perc\b.*?\s+([\d.eE+-]+)$', re.MULTILINE
        ),
        "cpu_cache_usage": re.compile(
            r'^vllm:cpu_cache_usage_perc\b.*?\s+([\d.eE+-]+)$', re.MULTILINE
        ),
        "prompt_tps": re.compile(
            r'^vllm:avg_prompt_throughput_toks_per_s\b.*?\s+([\d.eE+-]+)$',
            re.MULTILINE,
        ),
        "generation_tps": re.compile(
            r'^vllm:avg_generation_throughput_toks_per_s\b.*?\s+([\d.eE+-]+)$',
            re.MULTILINE,
        ),
    }

    def __init__(self, base_url: str) -> None:
        self._metrics_url = f"{base_url}/metrics"
        self._models_url = f"{base_url}/v1/models"
        self._model_name: str | None = None

    def _detect_model(self) -> str:
        if self._model_name:
            return self._model_name
        try:
            resp = requests.get(self._models_url, timeout=3)
            resp.raise_for_status()
            self._model_name = resp.json()["data"][0]["id"]
            return self._model_name
        except Exception:
            return "N/A"

    def collect(self) -> VllmMetrics:
        m = VllmMetrics()
        try:
            resp = requests.get(self._metrics_url, timeout=3)
            resp.raise_for_status()
            body = resp.text
        except Exception:
            return m

        m.online = True
        m.model_name = self._detect_model()

        for attr, pattern in self._GAUGE_PATTERNS.items():
            match = pattern.search(body)
            if match:
                setattr(m, attr, float(match.group(1)))

        m.gpu_cache_usage *= 100
        m.cpu_cache_usage *= 100

        return m
