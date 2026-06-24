"""Recovery-API (PROJ-17) — wiederherstellbare Stränge nach Reboot/Crash.

Read-only Sicht (``GET /recovery``) über Live-Index + Vault; ``restore`` nimmt einen
Strang als seed-versorgte Kind-Session wieder auf (wie PROJ-5), ``dismiss`` blendet
ihn aus (Vault-Eintrag bleibt). MVP single-user: kein JWT (vgl. sessions.py).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..engine.recovery import RecoveryService
from ..schemas.recovery import RecoveryList, RecoveryRestoreRequest
from ..schemas.sessions import SessionRead

router = APIRouter(prefix="/recovery", tags=["recovery"])


def _svc(request: Request) -> RecoveryService:
    return request.app.state.recovery


@router.get("", response_model=RecoveryList)
async def list_recovery(request: Request) -> dict:
    """Liste wiederherstellbarer Stränge (verwaist + ohne Nachfolger, jüngster zuerst)."""
    return {"candidates": _svc(request).candidates()}


@router.post("/{session_id}/restore", response_model=SessionRead, status_code=201)
async def restore_recovery(
    session_id: str, payload: RecoveryRestoreRequest, request: Request
) -> dict:
    """Strang wiederherstellen: Kind-Session mit verdichtetem Handover/Log als Seed."""
    try:
        child = await _svc(request).restore(session_id, initial_prompt=payload.initial_prompt)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Kein wiederherstellbarer Strang.") from exc
    except RuntimeError as exc:  # bereits wiederhergestellt (1 Strang = 1 Nachfolger)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:  # blockiert (Projektpfad weg) / ungültiges Modell
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:  # claude-Binary weg
        raise HTTPException(
            status_code=503, detail="Claude-CLI nicht gefunden — ist `claude` installiert/eingeloggt?"
        ) from exc
    return child.to_read()


@router.post("/{session_id}/dismiss", status_code=204, response_model=None)
async def dismiss_recovery(session_id: str, request: Request) -> None:
    """Kandidat aus der Recovery-Ansicht entfernen (idempotent). Vault-Eintrag bleibt."""
    _svc(request).dismiss(session_id)
