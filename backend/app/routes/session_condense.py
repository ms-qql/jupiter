"""Session-Kondensierungs-API (PROJ-55) — Queue + Sweep-Trigger + Einstellungen.

Single-User-MVP: ``owner`` wird serverseitig gestempelt (Auth-Gate in ``main.py``).
Die gesamte Auswahl-/Archiv-/Zeitplan-Logik liegt im ``SessionCondenseWorker``
(``request.app.state.session_condense``), nicht hier.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from ..engine.registry import engine_registry
from ..engine.session_condense import SessionCondenseWorker
from ..schemas.session_condense import (
    QueueRead,
    RunRead,
    SettingsPatch,
    SettingsRead,
)

router = APIRouter(prefix="/session-condense", tags=["session-condense"])

# Wochenplan ``DOW HH:MM`` (z. B. ``MON 03:00``) oder leer (nur manuell).
_SCHEDULE_RE = re.compile(r"^(MON|TUE|WED|THU|FRI|SAT|SUN)\s+(?:[01]?\d|2[0-3]):[0-5]\d$", re.I)


def _worker(request: Request) -> SessionCondenseWorker:
    return request.app.state.session_condense


@router.get("/queue", response_model=QueueRead)
async def get_queue(request: Request) -> dict:
    """Warteschlange + Worker-Zustand (für das UI-Polling)."""
    worker = _worker(request)
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.post("/scan", response_model=QueueRead)
async def scan(request: Request) -> dict:
    """Alte Session-Logs (> Altersschwelle) als pending einreihen (kein Start)."""
    worker = _worker(request)
    await worker.scan()
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.post("/run", response_model=QueueRead)
async def run_now(request: Request) -> dict:
    """„Jetzt kondensieren": scannen + Sweep sofort starten (idempotent)."""
    worker = _worker(request)
    await worker.run_now()
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.get("/runs", response_model=list[RunRead])
async def list_runs(request: Request, limit: int = 20) -> list[dict]:
    """Letzte Lauf-Protokolle (geprüft / kondensiert / trivial / archiviert / gelöscht / Fehler)."""
    return await _worker(request).list_runs(limit)


@router.delete("/queue/{item_id}", status_code=204, response_model=None)
async def remove_from_queue(request: Request, item_id: int) -> None:
    """Einen Warteschlangen-Eintrag entfernen (laufenden: Session wird gestoppt)."""
    try:
        await _worker(request).remove(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.") from exc


@router.post("/queue/{item_id}/retry", response_model=QueueRead)
async def retry_item(request: Request, item_id: int) -> dict:
    """Fehlgeschlagenen Eintrag erneut einreihen (→ pending) und Sweep anstoßen."""
    worker = _worker(request)
    try:
        await worker.retry(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.get("/settings", response_model=SettingsRead)
async def get_settings_route(request: Request) -> dict:
    return await _worker(request).get_settings()


@router.patch("/settings", response_model=SettingsRead)
async def patch_settings_route(request: Request, payload: SettingsPatch) -> dict:
    """Wochenplan / Schwellen / Modell ändern (persistiert). Nur angegebene Felder."""
    worker = _worker(request)
    fields: dict = {}
    if payload.schedule is not None:
        schedule = payload.schedule.strip()
        if schedule and not _SCHEDULE_RE.match(schedule):
            raise HTTPException(
                status_code=400,
                detail="Ungueltiger Wochenplan. Format 'DOW HH:MM' (z. B. MON 03:00) oder leer.",
            )
        fields["schedule"] = schedule
    if payload.age_days is not None:
        fields["age_days"] = payload.age_days
    if payload.retention_days is not None:
        fields["retention_days"] = payload.retention_days
    if payload.min_chars is not None:
        fields["min_chars"] = payload.min_chars
    if payload.engine is not None or payload.model is not None:
        # Engine + Modell werden als Paar validiert (gegen engines.yaml). So kann jede
        # konfigurierte Session-Engine (Claude, OpenCode, …) samt gültigem Modell-Slug
        # gewählt werden — statt einer harten Claude-Only-Whitelist.
        current = await worker.get_settings()
        engine_key = (
            payload.engine if payload.engine is not None else current.get("engine")
        )
        engine_key = (engine_key or "").strip()
        profile = engine_registry.get(engine_key or None)
        if profile is None or not profile.is_session_engine:
            raise HTTPException(
                status_code=400,
                detail=f"Ungueltige Engine '{engine_key}'. Nur steuerbare Session-Engines erlaubt.",
            )
        model = (
            payload.model if payload.model is not None else current.get("model")
        )
        model = (model or "").strip() or (profile.default_model or "")
        if not profile.valid_model(model):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Modell '{model}' ist fuer Engine '{profile.key}' nicht konfiguriert. "
                    f"Erlaubt: {', '.join(profile.models) or '(beliebig)'}."
                ),
            )
        fields["engine"] = profile.key
        fields["model"] = model
    return await worker.save_settings(fields)
