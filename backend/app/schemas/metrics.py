"""Pydantic-v2-Schemas für die VPS-Admin-Metrik-API (PROJ-42).

Read-only Host-Zustand. ``status``/``overall_status`` ist die Ampel
(``green``/``amber``/``red``) nach den Schwellen aus ``config`` (75/90 %).
``history`` je Gauge speist die Sparklines (kurzes rollierendes Fenster).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["green", "amber", "red"]
ServiceStatus = Literal["active", "inactive", "failed", "unknown"]


class GaugeCpu(BaseModel):
    percent: float
    cores: int
    used_cores: float = Field(..., description="Belegte Cores ≈ percent/100 · cores (für „0,2 / 8“).")
    status: Status
    history: list[float] = []


class GaugeMem(BaseModel):
    percent: float
    used_gb: float
    total_gb: float
    status: Status
    history: list[float] = []


class GaugeSwap(BaseModel):
    percent: float
    used_gb: float
    total_gb: float


class GaugeDisk(BaseModel):
    percent: float
    used_gb: float
    total_gb: float
    mount: str = "/"
    status: Status
    history: list[float] = []


class GaugeLoad(BaseModel):
    load1: float
    load5: float
    load15: float
    per_core: float = Field(..., description="(Load1/Cores)·100 — Bewertungsgröße für die Ampel.")
    status: Status
    history: list[float] = []


class NetIO(BaseModel):
    rx_bytes_per_sec: float
    tx_bytes_per_sec: float


class TopProcess(BaseModel):
    pid: int
    name: str
    cpu_percent: float
    mem_percent: float


class ServiceHealth(BaseModel):
    name: str
    status: ServiceStatus


class MetricsSnapshot(BaseModel):
    timestamp: str
    overall_status: Status
    cpu: GaugeCpu
    memory: GaugeMem
    swap: GaugeSwap
    disk: GaugeDisk
    load: GaugeLoad
    net: NetIO
    uptime_seconds: float
    top_processes: list[TopProcess]
    services: list[ServiceHealth]


class MetricsStatus(BaseModel):
    """Leichtgewichtige Gesamt-Ampel für die Sidebar (kein voller Snapshot)."""

    status: Status
