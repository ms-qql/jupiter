"""Usage-API (PROJ-19 #28) — Token-/Kosten-Verbrauch.

Read-only Aggregat über den Session-Live-Index: Kennzahlen + Verteilung je
Modell/Projekt (``/summary``) und Session-Drilldown (``/drilldown``). MVP
single-user: kein JWT (vgl. sessions.py). Fehler im Index degradieren zu leeren
Aggregaten (best-effort), nie Hard-Fail.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..engine.usage import BudgetRefreshRateLimited, ProviderBudgetService, UsageService
from ..schemas.usage import (
    ProviderBudgetSnapshot,
    UsageDrilldown,
    UsageRange,
    UsageSummary,
)

router = APIRouter(prefix="/usage", tags=["usage"])


def _svc(request: Request) -> UsageService:
    return request.app.state.usage


def _budget_svc(request: Request) -> ProviderBudgetService:
    return request.app.state.provider_budgets


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


@router.get("/provider-budgets", response_model=ProviderBudgetSnapshot)
async def provider_budgets(request: Request) -> dict:
    """Claude-/Codex-Quota-Lagebild für die Sidebar (gecacht, read-only)."""
    return await _budget_svc(request).snapshot()


@router.post("/provider-budgets/refresh", response_model=ProviderBudgetSnapshot)
async def refresh_provider_budgets(request: Request) -> dict:
    """Manueller Refresh des Budget-Snapshots; gegen Mehrfachklicks rate-limited."""
    try:
        return await _budget_svc(request).refresh()
    except BudgetRefreshRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
