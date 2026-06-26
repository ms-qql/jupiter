"""Video-Summary-API (PROJ-41) — Queue-CRUD + Trigger + Einstellungen.

Single-User-MVP: kein JWT/RLS (Projekt-Entscheidung); ``owner`` wird serverseitig
gestempelt, nicht gefiltert. Die gesamte Drossel-/Zeitplan-Logik liegt im
``VideoSummaryWorker`` (``request.app.state.video_summary``), nicht hier.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request

from ..engine.video_summary import VideoSummaryWorker
from ..schemas.video_summary import (
    VALID_MODELS,
    QueueAddRequest,
    QueueAddResult,
    QueueRead,
    VideoSummaryLibraryItem,
    VideoSummarySettingsPatch,
    VideoSummarySettingsRead,
)

router = APIRouter(prefix="/video-summary", tags=["video-summary"])

_SCHEDULE_RE = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")


def _worker(request: Request) -> VideoSummaryWorker:
    return request.app.state.video_summary


@router.get("/queue", response_model=QueueRead)
async def get_queue(request: Request) -> dict:
    """Warteschlange + Worker-Zustand (für das UI-Polling)."""
    worker = _worker(request)
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.post("/queue", response_model=QueueAddResult)
async def add_to_queue(request: Request, payload: QueueAddRequest) -> dict:
    """URL(s) einreihen (Paste-Block erlaubt). Zerlegt/validiert/dedupliziert serverseitig."""
    result = await _worker(request).add_urls(payload.urls)
    if not result["added"] and result["rejected"] and not result["duplicates"]:
        # Ausschließlich ungültige Eingaben → klare Fehlermeldung (deutsch).
        raise HTTPException(
            status_code=400,
            detail="Keine gültige Video-URL erkannt. Bitte vollständige http(s)-Links angeben.",
        )
    return result


@router.delete("/queue/{item_id}", status_code=204, response_model=None)
async def remove_from_queue(request: Request, item_id: int) -> None:
    """Einen Warteschlangen-Eintrag entfernen (laufenden: Session wird gestoppt)."""
    try:
        await _worker(request).remove(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.") from exc


@router.post("/queue/{item_id}/retry", response_model=QueueRead)
async def retry_item(request: Request, item_id: int) -> dict:
    """Fehlgeschlagenen Eintrag erneut einreihen (→ pending) und Verarbeitung anstoßen."""
    worker = _worker(request)
    try:
        await worker.retry(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.post("/run-now", response_model=QueueRead)
async def run_now(request: Request) -> dict:
    """„Jetzt ausführen": Abarbeitung der Warteschlange sofort starten (idempotent)."""
    worker = _worker(request)
    await worker.run_now()
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.get("/library", response_model=list[VideoSummaryLibraryItem])
async def get_library(request: Request) -> list[dict]:
    """Bibliothek: alle bereits umgewandelten Notizen im Standard-Ordner (Vault-Scan,
    nicht die DB-Queue). Leerer/fehlender Ordner → leere Liste."""
    return await _worker(request).list_library()


@router.get("/settings", response_model=VideoSummarySettingsRead)
async def get_settings_route(request: Request) -> dict:
    return await _worker(request).get_settings()


@router.patch("/settings", response_model=VideoSummarySettingsRead)
async def patch_settings_route(request: Request, payload: VideoSummarySettingsPatch) -> dict:
    """Cooldown / Batch-Größe / Zeitplan / Modell ändern (persistiert). Nur angegebene Felder."""
    worker = _worker(request)
    current = await worker.get_settings()
    cooldown = payload.cooldown_minutes if payload.cooldown_minutes is not None else current["cooldown_minutes"]
    batch = payload.batch_size if payload.batch_size is not None else current["batch_size"]
    schedule = payload.schedule if payload.schedule is not None else current["schedule"]
    schedule = (schedule or "").strip()
    if schedule and not _SCHEDULE_RE.match(schedule):
        raise HTTPException(
            status_code=400,
            detail="Ungueltiger Zeitplan. Format HH:MM (24h) oder leer fuer nur manuell.",
        )
    model = payload.model if payload.model is not None else current["model"]
    model = (model or "").strip()
    if model not in VALID_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Ungueltiges Modell. Erlaubt: {', '.join(VALID_MODELS)}.",
        )
    return await worker.save_settings(cooldown, batch, schedule, model)
