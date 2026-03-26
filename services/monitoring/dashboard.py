from datetime import timedelta

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from services.monitoring.datamodels import Snapshot


def _bar(percent: float, width: int = 20) -> Text:
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
    gpu = snap.gpu
    sys_m = snap.system
    vllm = snap.vllm

    uptime_str = str(uptime).split(".")[0]
    log_str = str(log_path) if log_path else "disabled"

    header = Table.grid(padding=(0, 2))
    header.add_row(
        f"[bold]Uptime:[/] {uptime_str}",
        f"[bold]Interval:[/] {interval}s",
        f"[bold]Log:[/] {log_str}",
    )

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
