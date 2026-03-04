"""
vLLM resource monitoring CLI with Rich dashboard.

Usage:
    python -m cli.model_monitoring
    python -m cli.model_monitoring --interval 5 --port 8001
    python -m cli.model_monitoring --no-dashboard
    python -m cli.model_monitoring --no-log
    python -m cli.model_monitoring --duration 3600
"""

import argparse
import signal
import sys
import time
from datetime import timedelta

import psutil
from rich.console import Console
from rich.live import Live

from services.monitoring.dashboard import build_dashboard
from services.monitoring.logger import CsvLogger
from services.monitoring.service import MonitoringService

_running = True


def _handle_signal(sig: int, frame: object) -> None:
    global _running
    _running = False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monitor GPU, CPU, RAM, and vLLM server metrics"
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Polling interval in seconds (default: 2)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="vLLM server port (default: 8000)",
    )
    parser.add_argument(
        "--no-dashboard", action="store_true",
        help="Disable terminal dashboard (CSV logging only)",
    )
    parser.add_argument(
        "--no-log", action="store_true",
        help="Disable CSV logging (dashboard only)",
    )
    parser.add_argument(
        "--log-dir", default="data/monitoring",
        help="Directory for CSV log files (default: data/monitoring)",
    )
    parser.add_argument(
        "--duration", type=int, default=0,
        help="Auto-stop after N seconds (0 = run indefinitely)",
    )
    args = parser.parse_args()

    if args.no_dashboard and args.no_log:
        print("ERROR: --no-dashboard and --no-log cannot both be set.", file=sys.stderr)
        sys.exit(1)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    psutil.cpu_percent(interval=None)

    base_url = f"http://localhost:{args.port}"
    service = MonitoringService(vllm_base_url=base_url)

    logger: CsvLogger | None = None
    if not args.no_log:
        logger = CsvLogger(args.log_dir)

    console = Console()
    t_start = time.monotonic()

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
                snap = service.collect_snapshot()
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
            log_path = str(logger.path) if logger else None
            with Live(console=console, refresh_per_second=2, screen=False) as live:
                while _running:
                    if args.duration and (time.monotonic() - t_start) >= args.duration:
                        break
                    snap = service.collect_snapshot()
                    if logger:
                        logger.write(snap)
                    uptime = timedelta(seconds=int(time.monotonic() - t_start))
                    panel = build_dashboard(snap, uptime, args.interval, log_path)
                    live.update(panel)
                    time.sleep(args.interval)
    finally:
        service.shutdown()
        if logger:
            logger.close()
            console.print(f"\n[bold green]Log saved:[/] {logger.path}")
        console.print("[bold]Monitor stopped.[/]")


if __name__ == "__main__":
    main()
