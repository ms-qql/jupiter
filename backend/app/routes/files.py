"""Fileexplorer- + Clipboard-API (PROJ-11).

Ein gemeinsamer ``/files``-Dienst speist beide Oberflächen: den vollen
Fileexplorer (Surface A) und den In-Session Dokument-Clipboard (Surface B).
Alles scoped auf ``allowed_roots`` (``realpath``-Härtung im ``FileService``).
Kein JWT/DB (Jupiter-Override). Handler sind synchron (``def``) → FastAPI führt
die blockierende Datei-I/O im Threadpool aus (echtes Streaming).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from ..engine.files import FileService
from ..schemas.files import (
    DeleteRequest,
    DeleteResult,
    DirListing,
    FileEntry,
    MkdirRequest,
    MoveRequest,
    RenameRequest,
    RootEntry,
    UploadResult,
)

router = APIRouter(prefix="/files", tags=["files"])


def _svc(request: Request) -> FileService:
    return request.app.state.files


def _400(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _os_error(exc: OSError) -> HTTPException:
    """OS-/Dateisystemfehler freundlich mappen statt 500 (Low-2)."""
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail="Keine Berechtigung für diesen Pfad.")
    return HTTPException(status_code=400, detail="Dateioperation fehlgeschlagen.")


@router.get("/roots", response_model=list[RootEntry])
def list_roots(request: Request) -> list[dict]:
    return _svc(request).roots()


@router.get("/list", response_model=DirListing)
def list_dir(
    request: Request,
    path: str | None = Query(None, description="Absoluter Ordnerpfad; Default = erste erlaubte Wurzel."),
) -> dict:
    try:
        return _svc(request).list_dir(path)
    except ValueError as exc:
        raise _400(exc) from exc


@router.get("/download")
def download(
    request: Request,
    path: str = Query(..., min_length=1, description="Absoluter Pfad einer Datei innerhalb der Roots."),
) -> FileResponse:
    try:
        real = _svc(request).resolve_download(path)
    except ValueError as exc:
        raise _400(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc
    return FileResponse(real, filename=os.path.basename(real))


@router.post("/upload", response_model=UploadResult)
def upload(
    request: Request,
    files: list[UploadFile] = File(..., description="Eine oder mehrere Dateien (auch Clipboard-Paste)."),
    target_dir: str | None = Form(None, description="Zielordner; Default = Clipboard-Ordner."),
) -> dict:
    svc = _svc(request)
    saved: list[dict] = []
    try:
        for uf in files:
            saved.append(svc.save_upload(uf.file, uf.filename, uf.content_type, target_dir))
    except ValueError as exc:  # außerhalb Roots / zu groß / Typ nicht erlaubt
        raise _400(exc) from exc
    except OSError as exc:  # z. B. keine Schreibrechte im Zielordner
        raise _os_error(exc) from exc
    return {"files": saved}


@router.post("/mkdir", response_model=FileEntry)
def mkdir(request: Request, payload: MkdirRequest) -> dict:
    try:
        return _svc(request).mkdir(payload.parent, payload.name)
    except ValueError as exc:
        raise _400(exc) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Ordner existiert bereits.") from exc
    except OSError as exc:
        raise _os_error(exc) from exc


@router.post("/rename", response_model=FileEntry)
def rename(request: Request, payload: RenameRequest) -> dict:
    try:
        return _svc(request).rename(payload.path, payload.new_name)
    except ValueError as exc:
        raise _400(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Zielname existiert bereits.") from exc
    except OSError as exc:
        raise _os_error(exc) from exc


@router.post("/move", response_model=FileEntry)
def move(request: Request, payload: MoveRequest) -> dict:
    try:
        return _svc(request).move(payload.path, payload.dest_dir)
    except ValueError as exc:
        raise _400(exc) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Im Zielordner existiert bereits eine Datei dieses Namens.") from exc
    except OSError as exc:
        raise _os_error(exc) from exc


@router.post("/delete", response_model=DeleteResult)
def delete(request: Request, payload: DeleteRequest) -> dict:
    return _svc(request).delete(payload.paths)
