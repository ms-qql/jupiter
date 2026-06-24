"""Agenten-API (PROJ-19 #26) — billige Späher-Agenten.

``POST /agents/scout`` delegiert eine Fazit-Aufgabe (viel lesen/suchen, wenig
zurück) an einen kurzlebigen Lauf auf dem günstigen Modell und gibt nur das
verdichtete Fazit zurück. MVP single-user: kein JWT (vgl. sessions.py).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..config import settings
from ..engine.scout import ScoutService
from ..schemas.agents import ScoutRequest, ScoutResult

router = APIRouter(prefix="/agents", tags=["agents"])


def _scout(request: Request) -> ScoutService:
    return request.app.state.scout


@router.post("/scout", response_model=ScoutResult)
async def run_scout(payload: ScoutRequest, request: Request) -> dict:
    if not settings.scout_enabled:
        raise HTTPException(status_code=503, detail="Späher-Agenten sind deaktiviert.")
    try:
        result = await _scout(request).scout(
            task=payload.task,
            query=payload.query,
            paths=payload.paths,
            project_path=payload.project_path,
            model=payload.model,
            top_n=payload.top_n,
        )
    except FileNotFoundError as exc:  # claude-Binary fehlt
        raise HTTPException(
            status_code=503, detail="Claude-CLI nicht gefunden — ist `claude` installiert/eingeloggt?"
        ) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:  # Lauf endete mit Fehler
        raise HTTPException(status_code=502, detail=f"Späher-Lauf fehlgeschlagen: {exc}") from exc
    return vars(result)
