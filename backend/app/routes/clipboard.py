"""Clipboard-Micro-App API (PROJ-69)."""
from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from ..engine.clipboard import ClipboardService
from ..schemas.clipboard import (
    ClipboardItemRead,
    ClipboardItemUpdate,
    ClipboardListRead,
    ClipboardSettingsRead,
)

router = APIRouter(prefix="/clipboard", tags=["clipboard"])


def _svc(request: Request) -> ClipboardService:
    return request.app.state.clipboard


def _400(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/items", response_model=ClipboardListRead)
async def list_items(
    request: Request,
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    return {"items": await _svc(request).list_items(limit)}


@router.post("/items", response_model=ClipboardItemRead)
async def create_item(
    request: Request,
    file: UploadFile = File(...),
    source_method: str = Form("upload"),
    source_device: str | None = Form(None),
    notes: str | None = Form(None),
) -> dict:
    try:
        return await _svc(request).add_upload(
            file.file,
            file.filename,
            file.content_type,
            source_method=source_method,
            source_device=source_device,
            notes=notes,
        )
    except ValueError as exc:
        raise _400(exc) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Clipboard-Upload fehlgeschlagen.") from exc


@router.get("/items/{item_id}", response_model=ClipboardItemRead)
async def get_item(request: Request, item_id: int) -> dict:
    try:
        return await _svc(request).get_item(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Clipboard-Eintrag nicht gefunden.") from exc


@router.patch("/items/{item_id}", response_model=ClipboardItemRead)
async def update_item(
    request: Request,
    item_id: int,
    payload: ClipboardItemUpdate,
) -> dict:
    try:
        return await _svc(request).update_item(
            item_id,
            display_name=payload.display_name,
            notes=payload.notes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Clipboard-Eintrag nicht gefunden.") from exc
    except ValueError as exc:
        raise _400(exc) from exc


@router.delete("/items/{item_id}", status_code=204, response_model=None)
async def remove_item(request: Request, item_id: int) -> None:
    try:
        await _svc(request).remove_item(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Clipboard-Eintrag nicht gefunden.") from exc


@router.get("/items/{item_id}/download")
async def download_item(request: Request, item_id: int) -> FileResponse:
    try:
        path = await _svc(request).resolve_file(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Clipboard-Eintrag nicht gefunden.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc
    return FileResponse(path, filename=os.path.basename(path))


@router.get("/items/{item_id}/preview")
async def preview_item(request: Request, item_id: int) -> FileResponse:
    try:
        path = await _svc(request).resolve_file(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Clipboard-Eintrag nicht gefunden.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc
    return FileResponse(path, filename=os.path.basename(path))


@router.get("/settings", response_model=ClipboardSettingsRead)
async def get_settings(request: Request) -> dict:
    try:
        return _svc(request).settings_payload()
    except ValueError as exc:
        raise _400(exc) from exc
