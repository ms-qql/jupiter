"""Marktplatz/Registry-API für Rollen/Skills/Agenten (PROJ-26).

File-first (kein Postgres), Vertrag aus dem Tech-Design der Spec. Aktiv = Datei am
Resolver-Pfad → Sessions/Launcher (PROJ-9) sehen aktive Rollen ohne Umbau.

Import ist bewusst zweistufig: ``POST /registry/import`` validiert + zeigt die
Capability-/Policy-Vorschau (NICHT aktiv), ``POST /registry/import/confirm`` aktiviert
erst nach menschlicher Bestätigung (Human-in-the-Loop, PROJ-10). ``owner`` kommt aus
dem Token/Server (PROJ-25), nie aus dem Client-Payload.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from fastapi import File as FileParam

from ..deps import CurrentUser, get_current_user
from ..engine.marketplace import RegistryError, registry_store
from ..schemas.registry import (
    RegistryCatalogRead,
    RegistryEntryDetailRead,
    RegistryEntryRead,
    RegistryImportConfirmBody,
    RegistryImportPreviewRead,
    RegistryRollbackBody,
)

router = APIRouter(prefix="/registry", tags=["registry"])

# Harte Obergrenze für Paket-Uploads (Schutz vor Zip-Bomben/Missbrauch).
MAX_PACKAGE_BYTES = 2 * 1024 * 1024


def _handle(exc: RegistryError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/catalog", response_model=RegistryCatalogRead)
async def get_catalog(
    typ: str | None = None, status: str | None = None, query: str | None = None
) -> dict:
    """Durchsuchbarer Katalog mit Status (installed/active/inactive)."""
    return {"entries": registry_store.catalog(typ=typ, status=status, query=query)}


@router.post("/import", response_model=RegistryImportPreviewRead)
async def import_preview(file: UploadFile = FileParam(...)) -> dict:
    """`.jupkg` hochladen → Capability-/Policy-Vorschau. Validiert, aktiviert NICHTS."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Leeres Paket hochgeladen.")
    if len(data) > MAX_PACKAGE_BYTES:
        raise HTTPException(status_code=413, detail="Paket zu groß (max. 2 MB).")
    try:
        return registry_store.import_preview(data)
    except RegistryError as exc:
        raise _handle(exc) from exc


@router.post("/import/confirm", response_model=RegistryEntryRead)
async def import_confirm(
    payload: RegistryImportConfirmBody, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Nach Bestätigung der Vorschau installieren + aktivieren. `owner` aus dem Token."""
    try:
        return registry_store.import_confirm(payload.token, owner=user.user_id)
    except RegistryError as exc:
        raise _handle(exc) from exc


@router.get("/{typ}/{entry_id}", response_model=RegistryEntryDetailRead)
async def get_entry(typ: str, entry_id: str) -> dict:
    """Detail inkl. Definition-Text + Versions-Historie + Capabilities."""
    try:
        return registry_store.detail(typ, entry_id)
    except RegistryError as exc:
        raise _handle(exc) from exc


@router.post("/{typ}/{entry_id}/install", response_model=RegistryEntryRead)
async def install_entry(typ: str, entry_id: str) -> dict:
    """Vorhandenen Eintrag aktivieren (Datei am Resolver-Pfad ablegen)."""
    try:
        return registry_store.install(typ, entry_id)
    except RegistryError as exc:
        raise _handle(exc) from exc


@router.patch("/{typ}/{entry_id}/toggle", response_model=RegistryEntryRead)
async def toggle_entry(typ: str, entry_id: str) -> dict:
    """Aktivieren ↔ Deaktivieren. Deaktivieren wirkt erst auf NEUE Sessions."""
    try:
        return registry_store.toggle(typ, entry_id)
    except RegistryError as exc:
        raise _handle(exc) from exc


@router.post("/{typ}/{entry_id}/rollback", response_model=RegistryEntryRead)
async def rollback_entry(typ: str, entry_id: str, payload: RegistryRollbackBody) -> dict:
    """Auf eine frühere Version zurückrollen (Hinweis statt Crash bei fehlendem Tool)."""
    try:
        return registry_store.rollback(typ, entry_id, payload.version)
    except RegistryError as exc:
        raise _handle(exc) from exc


@router.delete("/{typ}/{entry_id}", status_code=204)
async def delete_entry(typ: str, entry_id: str) -> Response:
    """Deinstallieren (Resolver-Datei + Versionen entfernen)."""
    try:
        registry_store.delete(typ, entry_id)
    except RegistryError as exc:
        raise _handle(exc) from exc
    return Response(status_code=204)


@router.get("/{typ}/{entry_id}/export")
async def export_entry(typ: str, entry_id: str) -> Response:
    """Eintrag als portierbares `.jupkg` herunterladen."""
    try:
        data = registry_store.export_package(typ, entry_id)
    except RegistryError as exc:
        raise _handle(exc) from exc
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{entry_id}.jupkg"'},
    )
