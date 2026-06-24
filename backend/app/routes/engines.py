"""Engine-Registry-API (PROJ-18) — was kann der Smart Launcher anbieten?

Liefert alle konfigurierten Engines (Treiber-Tiefe), iFrame-Einbettungen und
Launch-Einträge inkl. Verfügbarkeit. Engine-agnostisch + secret-frei: das Frontend
graut nicht verfügbare Einträge aus (mit deutschem Setup-Hinweis), statt zu crashen.
Read-only; die Registrierung erfolgt zentral über ``engines.yaml`` (kein DB-Schreibweg).
"""
from __future__ import annotations

from fastapi import APIRouter

from ..engine.registry import engine_registry
from ..schemas.engines import EnginesOverview

router = APIRouter(prefix="/engines", tags=["engines"])


@router.get("", response_model=EnginesOverview)
async def list_engines() -> dict:
    """Alle Engines/iFrames/Launch-Einträge + Verfügbarkeit (für den Smart Launcher, PROJ-9)."""
    return engine_registry.snapshot()
