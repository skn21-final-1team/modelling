"""
vLLM Resource Monitoring Tool
Real-time terminal dashboard + CSV logging for GPU, CPU, RAM, and vLLM server metrics.

Usage:
    python utils/model-monitoring.py                     # default (2s interval, dashboard + CSV)
    python utils/model-monitoring.py --interval 5        # 5s interval
    python utils/model-monitoring.py --no-dashboard      # CSV logging only
    python utils/model-monitoring.py --no-log            # dashboard only
    python utils/model-monitoring.py --port 8001         # custom vLLM port
    python utils/model-monitoring.py --duration 3600     # auto-stop after 1 hour
"""

import argparse
import csv
import os
import re
import signal
import sys
import time
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from pathlib import Path

import psutil
import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

try:
    import pynvml

    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False


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


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------

class GpuCollector:
    """Collects GPU metrics via NVML (nvidia-ml-py)."""

    def __init__(self):
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

    def shutdown(self):
        if PYNVML_AVAILABLE and self._handle is not None:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass


class SystemCollector:
    """Collects CPU and RAM metrics via psutil."""

    def collect(self) -> SystemMetrics:
        mem = psutil.virtual_memory()
        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=None),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            ram_used_gb=mem.used / (1024**3),
            ram_total_gb=mem.total / (1024**3),
        )


class VllmCollector:
    """Collects vLLM server metrics from the Prometheus /metrics endpoint."""

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

    def __init__(self, base_url: str):
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


# ---------------------------------------------------------------------------
# CSV Logger
# ---------------------------------------------------------------------------

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
    def __init__(self, directory: str):
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

    def write(self, snap: Snapshot):
        self._writer.writerow(
            [
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
            ]
        )
        self._file.flush()

    def close(self):
        self._file.close()


# ---------------------------------------------------------------------------
# Dashboard Renderer
# ---------------------------------------------------------------------------

def _bar(percent: float, width: int = 20) -> Text:
    """Render a colored progress bar as Rich Text."""
    filled = int(round(percent / 100 * width))
    filled = max(0, min(width, filled))
    empty = width - filled

    if percent < 50:
        color = "green"
    elif percent < 80:
        color = "yellow"
    else:
        color = "red"

    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * empty, style="bright_black")
    return bar


def build_dashboard(
    snap: Snapshot,
    uptime: timedelta,
    interval: float,
    log_path: str | None,
) -> Panel:
    """Build the full dashboard as a Rich Panel."""
    gpu = snap.gpu
    sys_m = snap.system
    vllm = snap.vllm

    uptime_str = str(uptime).split(".")[0]
    log_str = str(log_path) if log_path else "disabled"

    # --- Header ---
    header = Table.grid(padding=(0, 2))
    header.add_row(
        f"[bold]Uptime:[/] {uptime_str}",
        f"[bold]Interval:[/] {interval}s",
        f"[bold]Log:[/] {log_str}",
    )

    # --- GPU Section ---
    gpu_table = Table.grid(padding=(0, 2))
    gpu_table.add_column(width=16, justify="right")
    gpu_table.add_column(width=50)

    util_bar = _bar(gpu.utilization)
    util_text = Text()
    util_text.append_text(util_bar)
    util_text.append(f"  {gpu.utilization:5.1f}%")
    gpu_table.add_row("Utilization:", util_text)

    vram_bar = _bar(gpu.vram_percent)
    vram_text = Text()
    vram_text.append_text(vram_bar)
    vram_text.append(
        f"  {gpu.vram_used_gb:.1f} / {gpu.vram_total_gb:.1f} GB ({gpu.vram_percent:.0f}%)"
    )
    gpu_table.add_row("VRAM:", vram_text)

    power_str = f"{gpu.power_draw_w:.0f}W"
    if gpu.power_limit_w > 0:
        power_str += f" / {gpu.power_limit_w:.0f}W"
    gpu_table.add_row("Temp / Power:", Text(f"{gpu.temperature}°C    {power_str}"))

    # --- CPU / RAM Section ---
    sys_table = Table.grid(padding=(0, 2))
    sys_table.add_column(width=16, justify="right")
    sys_table.add_column(width=50)

    cpu_bar = _bar(sys_m.cpu_percent)
    cpu_text = Text()
    cpu_text.append_text(cpu_bar)
    cpu_text.append(f"  {sys_m.cpu_percent:5.1f}%  ({sys_m.cpu_count} cores)")
    sys_table.add_row("CPU:", cpu_text)

    ram_bar = _bar(sys_m.ram_percent)
    ram_text = Text()
    ram_text.append_text(ram_bar)
    ram_text.append(
        f"  {sys_m.ram_used_gb:.1f} / {sys_m.ram_total_gb:.1f} GB ({sys_m.ram_percent:.0f}%)"
    )
    sys_table.add_row("RAM:", ram_text)

    # --- vLLM Section ---
    vllm_table = Table.grid(padding=(0, 2))
    vllm_table.add_column(width=16, justify="right")
    vllm_table.add_column(width=50)

    status_style = "bold green" if vllm.online else "bold red"
    status_label = "Online" if vllm.online else "Offline"
    status_text = Text()
    status_text.append(status_label, style=status_style)
    status_text.append(f"    Model: {vllm.model_name}")
    vllm_table.add_row("Status:", status_text)

    vllm_table.add_row(
        "Requests:",
        f"Running: {vllm.requests_running:.0f}  |  Waiting: {vllm.requests_waiting:.0f}",
    )

    cache_bar_gpu = _bar(vllm.gpu_cache_usage, width=10)
    cache_bar_cpu = _bar(vllm.cpu_cache_usage, width=10)
    cache_text = Text()
    cache_text.append("GPU: ")
    cache_text.append_text(cache_bar_gpu)
    cache_text.append(f" {vllm.gpu_cache_usage:5.1f}%  |  CPU: ")
    cache_text.append_text(cache_bar_cpu)
    cache_text.append(f" {vllm.cpu_cache_usage:5.1f}%")
    vllm_table.add_row("KV Cache:", cache_text)

    vllm_table.add_row(
        "Throughput:",
        f"Prompt: {vllm.prompt_tps:,.1f} tok/s  |  Gen: {vllm.generation_tps:,.1f} tok/s",
    )

    # --- Assemble ---
    layout = Table.grid(padding=(1, 0))
    layout.add_row(header)
    layout.add_row(
        Panel(gpu_table, title=f"GPU ({gpu.name})", border_style="cyan")
    )
    layout.add_row(Panel(sys_table, title="CPU & Memory", border_style="blue"))
    layout.add_row(
        Panel(vllm_table, title="vLLM Server", border_style="magenta")
    )

    return Panel(
        layout,
        title="[bold]vLLM Resource Monitor[/]",
        border_style="bright_white",
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

_running = True


def _handle_signal(sig, frame):
    global _running
    _running = False


def main():
    parser = argparse.ArgumentParser(
        description="Monitor GPU, CPU, RAM, and vLLM server metrics"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="vLLM server port (default: 8000)",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable terminal dashboard (CSV logging only)",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable CSV logging (dashboard only)",
    )
    parser.add_argument(
        "--log-dir",
        default="data/monitoring",
        help="Directory for CSV log files (default: data/monitoring)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Auto-stop after N seconds (0 = run indefinitely)",
    )
    args = parser.parse_args()

    if args.no_dashboard and args.no_log:
        print("ERROR: --no-dashboard and --no-log cannot both be set.", file=sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Prime psutil cpu_percent (first call always returns 0)
    psutil.cpu_percent(interval=None)

    base_url = f"http://localhost:{args.port}"
    gpu_collector = GpuCollector()
    sys_collector = SystemCollector()
    vllm_collector = VllmCollector(base_url)

    logger: CsvLogger | None = None
    if not args.no_log:
        logger = CsvLogger(args.log_dir)

    console = Console()
    t_start = time.monotonic()

    def collect_snapshot() -> Snapshot:
        return Snapshot(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            gpu=gpu_collector.collect(),
            system=sys_collector.collect(),
            vllm=vllm_collector.collect(),
        )

    try:
        if args.no_dashboard:
            console.print(f"[bold]Logging to:[/] {logger.path}")
            console.print(
                f"[bold]Interval:[/] {args.interval}s  |  Press Ctrl+C to stop"
            )
            tick = 0
            while _running:
                if args.duration and (time.monotonic() - t_start) >= args.duration:
                    break
                snap = collect_snapshot()
                logger.write(snap)
                tick += 1
                if tick % 10 == 0:
                    console.print(
                        f"  [{snap.timestamp}] GPU {snap.gpu.utilization:.0f}%  "
                        f"VRAM {snap.gpu.vram_used_gb:.1f}GB  "
                        f"CPU {snap.system.cpu_percent:.0f}%  "
                        f"RAM {snap.system.ram_used_gb:.1f}GB"
                    )
                time.sleep(args.interval)
        else:
            log_path = logger.path if logger else None
            with Live(
                console=console,
                refresh_per_second=2,
                screen=False,
            ) as live:
                while _running:
                    if args.duration and (time.monotonic() - t_start) >= args.duration:
                        break
                    snap = collect_snapshot()
                    if logger:
                        logger.write(snap)
                    uptime = timedelta(seconds=int(time.monotonic() - t_start))
                    panel = build_dashboard(snap, uptime, args.interval, log_path)
                    live.update(panel)
                    time.sleep(args.interval)
    finally:
        gpu_collector.shutdown()
        if logger:
            logger.close()
            console.print(f"\n[bold green]Log saved:[/] {logger.path}")
        console.print("[bold]Monitor stopped.[/]")


if __name__ == "__main__":
    main()
