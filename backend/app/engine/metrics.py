"""VPS-Admin Metrik-Service (PROJ-42).

Read-only Host-Metriken (CPU/RAM/Disk/Load/Swap/Netz/Uptime/Prozesse) + systemd-
Service-Health. Ein Hintergrund-Worker (Vorbild ``_liveness_loop`` /
``_video_summary_loop``) ruft ``tick()`` niederfrequent auf; der Service hält den
letzten **Snapshot** und einen kurzen **rollierenden Verlauf** für die Sparklines
**im Speicher** (flüchtige Live-Daten, bewusst keine DB).

Grundsatz: **read-only** (das Dashboard verändert nichts) und **gecacht** — die
Routen lesen nur den letzten Snapshot, gemessen wird ausschließlich im Worker.
Defensiv: ein Fehler je Tick ist nie fatal (der Lifespan-Loop fängt ihn ab).
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections import deque
from datetime import datetime

import psutil

from ..config import METRIC_CRIT_PCT, METRIC_WARN_PCT, settings

logger = logging.getLogger(__name__)

# Ampel-Rang (für „schlechtester Einzelwert").
_SEVERITY = {"green": 0, "amber": 1, "red": 2}
_GB = 1024 ** 3
# Service-Status → Ampel-Beitrag. ``unknown`` zählt NICHT (grün-neutral), damit ein
# nicht vorhandener/umbenannter Dienst die Gesamt-Ampel nicht fälschlich rot färbt.
_SERVICE_TO_STATUS = {"failed": "red", "inactive": "amber", "active": "green"}


def _status_for(percent: float) -> str:
    """Auslastungs-% → Ampel: < WARN grün, WARN..CRIT gelb, > CRIT rot."""
    if percent > METRIC_CRIT_PCT:
        return "red"
    if percent >= METRIC_WARN_PCT:
        return "amber"
    return "green"


def _worst(statuses) -> str:
    """Schlechtester Status (höchster Rang) über alle übergebenen Ampeln."""
    worst = "green"
    for s in statuses:
        if _SEVERITY.get(s, 0) > _SEVERITY[worst]:
            worst = s
    return worst


class MetricsService:
    """Misst Host-Metriken + systemd-Status, cached Snapshot + Verlauf in-memory."""

    def __init__(self) -> None:
        n = max(1, settings.metrics_history_points)
        self._hist_cpu: deque[float] = deque(maxlen=n)
        self._hist_mem: deque[float] = deque(maxlen=n)
        self._hist_disk: deque[float] = deque(maxlen=n)
        self._hist_load: deque[float] = deque(maxlen=n)
        self._last_net: tuple[int, int, float] | None = None  # (sent, recv, ts)
        self._snapshot: dict | None = None
        # CPU-Messung primen — die erste ``cpu_percent``-Lesung ist sonst 0.0.
        try:
            psutil.cpu_percent(interval=None)
        except Exception:  # noqa: BLE001 — Primen ist best-effort.
            pass

    # --- Lifecycle ---------------------------------------------------------

    async def startup(self) -> None:
        """Einmal messen, damit ``/current`` sofort nach dem Start Daten liefert."""
        await self.tick()

    # --- Lesepfad (von den Routen) ----------------------------------------

    def snapshot(self) -> dict:
        """Letzter gecachter Snapshot (oder ein neutraler Leer-Stand vor dem 1. Tick)."""
        return self._snapshot if self._snapshot is not None else self._empty()

    def status(self) -> dict:
        """Nur die Gesamt-Ampel (leichtgewichtig für die Sidebar)."""
        return {"status": self.snapshot()["overall_status"]}

    # --- Worker-Tick -------------------------------------------------------

    async def tick(self) -> None:
        """Ein Mess-Schritt: Host-Metriken (Thread) + systemd-Status (async)."""
        host = await asyncio.to_thread(self._collect_host)
        services = await self._collect_services()
        host["services"] = services
        host["overall_status"] = _worst(
            [
                host["cpu"]["status"],
                host["memory"]["status"],
                host["disk"]["status"],
                host["load"]["status"],
            ]
            + [_SERVICE_TO_STATUS.get(s["status"], "green") for s in services]
        )
        self._snapshot = host

    def _collect_host(self) -> dict:
        """Synchrone psutil-Messung (läuft via ``to_thread`` außerhalb des Event-Loops)."""
        now = time.time()
        cores = psutil.cpu_count() or 1
        cpu_pct = float(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        du = psutil.disk_usage("/")
        try:
            load1, load5, load15 = os.getloadavg()
        except (OSError, AttributeError):  # getloadavg fehlt z. B. auf Windows.
            load1 = load5 = load15 = 0.0
        per_core = (load1 / cores) * 100.0

        # Netz-Rate aus dem Delta zweier aufeinanderfolgender Ticks.
        net = psutil.net_io_counters()
        rx_rate = tx_rate = 0.0
        if self._last_net is not None:
            prev_sent, prev_recv, prev_ts = self._last_net
            dt = max(now - prev_ts, 1e-6)
            tx_rate = max(0.0, (net.bytes_sent - prev_sent) / dt)
            rx_rate = max(0.0, (net.bytes_recv - prev_recv) / dt)
        self._last_net = (net.bytes_sent, net.bytes_recv, now)

        # Verlauf fortschreiben (rollierendes Fenster für die Sparklines).
        self._hist_cpu.append(round(cpu_pct, 1))
        self._hist_mem.append(round(vm.percent, 1))
        self._hist_disk.append(round(du.percent, 1))
        self._hist_load.append(round(per_core, 1))

        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {
                "percent": round(cpu_pct, 1),
                "cores": cores,
                "used_cores": round(cpu_pct / 100.0 * cores, 2),
                "status": _status_for(cpu_pct),
                "history": list(self._hist_cpu),
            },
            "memory": {
                "percent": round(vm.percent, 1),
                "used_gb": round(vm.used / _GB, 2),
                "total_gb": round(vm.total / _GB, 2),
                "status": _status_for(vm.percent),
                "history": list(self._hist_mem),
            },
            "swap": {
                "percent": round(sm.percent, 1),
                "used_gb": round(sm.used / _GB, 2),
                "total_gb": round(sm.total / _GB, 2),
            },
            "disk": {
                "percent": round(du.percent, 1),
                "used_gb": round(du.used / _GB, 2),
                "total_gb": round(du.total / _GB, 2),
                "mount": "/",
                "status": _status_for(du.percent),
                "history": list(self._hist_disk),
            },
            "load": {
                "load1": round(load1, 2),
                "load5": round(load5, 2),
                "load15": round(load15, 2),
                "per_core": round(per_core, 1),
                "status": _status_for(per_core),
                "history": list(self._hist_load),
            },
            "net": {
                "rx_bytes_per_sec": round(rx_rate, 1),
                "tx_bytes_per_sec": round(tx_rate, 1),
            },
            "uptime_seconds": round(max(0.0, now - psutil.boot_time()), 1),
            "top_processes": self._top_processes(),
        }

    def _top_processes(self) -> list[dict]:
        """Top-N Prozesse nach CPU (dann RAM). ``process_iter`` reicht gecachte
        Process-Objekte über Ticks weiter → ``cpu_percent`` wird ab dem 2. Tick
        sinnvoll. Verschwindende Prozesse werden übersprungen (nie fatal)."""
        procs: list[dict] = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = p.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            procs.append(
                {
                    "pid": info.get("pid") or 0,
                    "name": info.get("name") or "?",
                    "cpu_percent": round(float(info.get("cpu_percent") or 0.0), 1),
                    "mem_percent": round(float(info.get("memory_percent") or 0.0), 1),
                }
            )
        procs.sort(key=lambda x: (x["cpu_percent"], x["mem_percent"]), reverse=True)
        return procs[: max(1, settings.metrics_top_processes)]

    # --- systemd-Service-Health -------------------------------------------

    async def _collect_services(self) -> list[dict]:
        async def one(unit: str) -> dict:
            return {"name": unit, "status": await self._systemctl_is_active(unit)}

        return list(await asyncio.gather(*[one(u) for u in settings.metrics_services]))

    @staticmethod
    async def _systemctl_is_active(unit: str) -> str:
        """``systemctl is-active <unit>`` → active/inactive/failed/unknown.

        Feste Argumentliste (keine Shell-Interpolation), hartes Timeout. Jeder
        Fehler (kein systemctl, Timeout, …) degradiert zu ``unknown`` — nie ein Crash.
        """
        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "systemctl",
                "is-active",
                unit,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await asyncio.wait_for(
                proc.communicate(), timeout=settings.metrics_systemctl_timeout_seconds
            )
            value = (out or b"").decode(errors="replace").strip()
        except Exception:  # noqa: BLE001 — Status-Abfrage nie fatal.
            if proc is not None and proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
            return "unknown"
        if value in ("active", "inactive", "failed"):
            return value
        # Übergangszustände auf den nächstliegenden stabilen Zustand abbilden.
        if value in ("activating", "reloading"):
            return "active"
        if value == "deactivating":
            return "inactive"
        return "unknown"

    # --- Leer-Stand (vor dem ersten Tick) ---------------------------------

    @staticmethod
    def _empty() -> dict:
        cores = psutil.cpu_count() or 1
        zero_gauge = {"percent": 0.0, "status": "green", "history": []}
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "green",
            "cpu": {**zero_gauge, "cores": cores, "used_cores": 0.0},
            "memory": {**zero_gauge, "used_gb": 0.0, "total_gb": 0.0},
            "swap": {"percent": 0.0, "used_gb": 0.0, "total_gb": 0.0},
            "disk": {**zero_gauge, "used_gb": 0.0, "total_gb": 0.0, "mount": "/"},
            "load": {
                "load1": 0.0, "load5": 0.0, "load15": 0.0,
                "per_core": 0.0, "status": "green", "history": [],
            },
            "net": {"rx_bytes_per_sec": 0.0, "tx_bytes_per_sec": 0.0},
            "uptime_seconds": 0.0,
            "top_processes": [],
            "services": [{"name": u, "status": "unknown"} for u in settings.metrics_services],
        }
