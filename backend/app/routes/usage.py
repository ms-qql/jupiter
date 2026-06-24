"""Usage-API (PROJ-19 #28) — Token-/Kosten-Verbrauch.

Read-only Aggregat über den Session-Live-Index: Kennzahlen + Verteilung je
Modell/Projekt (``/summary``) und Session-Drilldown (``/drilldown``). MVP
single-user: kein JWT (vgl. sessions.py). Fehler im Index degradieren zu leeren
Aggregaten (best-effort), nie Hard-Fail.
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..engine.usage import UsageService
from ..schemas.usage import UsageDrilldown, UsageRange, UsageSummary

router = APIRouter(prefix="/usage", tags=["usage"])


def _svc(request: Request) -> UsageService:
    return request.app.state.usage


@router.get("/summary", response_model=UsageSummary)
async def usage_summary(
    request: Request,
    range_: UsageRange = Query("today", alias="range"),
) -> dict:
    """Verbrauchs-Kennzahlen + Verteilung je Modell/Projekt für den Zeitraum."""
    return await _svc(request).summary(range_)


@router.get("/drilldown", response_model=UsageDrilldown)
async def usage_drilldown(
    request: Request,
    range_: UsageRange = Query("today", alias="range"),
    model: str | None = Query(None, description="Filter auf ein Modell-Label, z. B. Opus."),
    project: str | None = Query(None, description="Filter auf einen Projektpfad."),
) -> dict:
    """Session-Drilldown (nach Tokens absteigend), optional nach Modell/Projekt gefiltert."""
    rows = await _svc(request).drilldown(range_, model=model, project=project)
    return {"range": range_, "rows": rows}
