"""Buch-Nuggets-API (PROJ-53) — Queue-CRUD + Kostenschätzung + Trigger + Einstellungen.

Single-User-MVP: kein JWT/RLS (Projekt-Entscheidung); ``owner`` wird serverseitig
gestempelt, nicht gefiltert. Die gesamte Verarbeitungs-/Drossel-Logik liegt im
``BookNuggetsWorker`` (``request.app.state.book_nuggets``), nicht hier.

Datei-Uploads laufen über den bestehenden ``/files/upload``-Endpunkt (PROJ-11,
Scope-Guard + Größenlimit); hier wird nur der resultierende Pfad als Quelle
eingereiht — kein zweiter Upload-Pfad.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from ..engine.book_nuggets import BookNuggetsWorker, DuplicateError
from ..schemas.book_nuggets import (
    BookNuggetsLibraryItem,
    BookNuggetsSettingsPatch,
    BookNuggetsSettingsRead,
    EstimateRequest,
    EstimateResult,
    QueueAddRequest,
    QueueAddResult,
    QueueRead,
)

router = APIRouter(prefix="/book-nuggets", tags=["book-nuggets"])


def _worker(request: Request) -> BookNuggetsWorker:
    return request.app.state.book_nuggets


@router.get("/queue", response_model=QueueRead)
async def get_queue(request: Request) -> dict:
    """Warteschlange + Worker-Zustand (für das UI-Polling)."""
    worker = _worker(request)
    return {"items": await worker.list_queue(), "state": worker.state()}


@router.post("/estimate", response_model=EstimateResult)
async def estimate(request: Request, payload: EstimateRequest) -> dict:
    """Best-effort-Kostenschätzung VOR dem Einreihen (D7)."""
    try:
        return await _worker(request).estimate(
            payload.source_type, payload.source_ref, payload.model_mode,
            payload.model_extract, payload.model_consolidate, payload.page_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/queue", response_model=QueueAddResult)
async def add_to_queue(request: Request, payload: QueueAddRequest):
    """Ein Buch einreihen (Quelle + Modellwahl + Seitenlimit). Verarbeitung startet
    automatisch. Erkanntes Duplikat (D9) ohne ``on_duplicate`` → 409."""
    try:
        return await _worker(request).add_source(
            payload.source_type, payload.source_ref, payload.model_mode,
            payload.model_extract, payload.model_consolidate, payload.page_limit,
            payload.on_duplicate,
        )
    except DuplicateError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "existing_id": exc.existing_id,
                "existing_status": exc.existing_status,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/library", response_model=list[BookNuggetsLibraryItem])
async def get_library(request: Request) -> list[dict]:
    """Bibliothek: alle bereits erzeugten Nuggets im Standard-Ordner (Vault-Scan)."""
    return await _worker(request).list_library()


@router.get("/settings", response_model=BookNuggetsSettingsRead)
async def get_settings_route(request: Request) -> dict:
    return await _worker(request).get_settings()


@router.patch("/settings", response_model=BookNuggetsSettingsRead)
async def patch_settings_route(request: Request, payload: BookNuggetsSettingsPatch) -> dict:
    """Default-Modellmodus/-Modelle + Default-Seitenlimit ändern (persistiert)."""
    fields = payload.model_dump(exclude_unset=True)
    return await _worker(request).save_settings(fields)
