"""VPS-Admin Metrik-API (PROJ-42) — read-only Host-Zustand.

``/current`` liefert den vollständigen, gecachten Snapshot (Polling der App),
``/status`` nur die Gesamt-Ampel (leichtgewichtig für die Sidebar). MVP single-user:
kein JWT (vgl. ``usage.py``/``sessions.py``). Beide Endpunkte lesen den Worker-Cache,
messen also nicht pro Request.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..engine.metrics import MetricsService
from ..schemas.metrics import MetricsSnapshot, MetricsStatus

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _svc(request: Request) -> MetricsService:
    return request.app.state.metrics


@router.get("/current", response_model=MetricsSnapshot)
async def metrics_current(request: Request) -> dict:
    """Vollständiger Metrik-Snapshot inkl. Verlauf für die geöffnete App (Polling)."""
    return _svc(request).snapshot()


@router.get("/status", response_model=MetricsStatus)
async def metrics_status(request: Request) -> dict:
    """Nur die Gesamt-Ampel (green/amber/red) für das Sidebar-Status-Icon."""
    return _svc(request).status()
