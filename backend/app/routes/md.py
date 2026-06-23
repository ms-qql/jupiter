"""MD-Reader-API — read-only Markdown lesen/indizieren (PROJ-7).

Liest MD aus den erlaubten Roots (Vault + Projekt). Kein Schreibpfad. Pfad-Härtung
gegen ``allowed_roots`` (Muster ``validate_project_path``). Suche bleibt das
bestehende ``GET /vault/search`` (PROJ-2).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..engine.md_reader import MdConflictError, MdReaderService
from ..schemas.md import (
    MdBacklinksResult,
    MdFileRead,
    MdFileSave,
    MdIndexResult,
    MdSaveResult,
    MdSource,
)

router = APIRouter(prefix="/md", tags=["md-reader"])


def _reader(request: Request) -> MdReaderService:
    return request.app.state.md_reader


@router.get("/sources", response_model=list[MdSource])
async def list_sources(
    request: Request,
    project: str | None = Query(None, description="Optionaler Projektpfad (Default = config)."),
) -> list[dict]:
    return _reader(request).sources(project)


@router.get("/index", response_model=MdIndexResult)
async def index(
    request: Request,
    source: str = Query("vault", description="Lese-Quelle: vault | project."),
    project: str | None = Query(None, description="Projektpfad bei source=project."),
) -> dict:
    try:
        root, files = _reader(request).index(source, project)
    except ValueError as exc:  # unbekannte Quelle / Pfad-Ausbruch / kein Verzeichnis
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"source": source, "root": root, "files": files}


@router.get("/file", response_model=MdFileRead)
async def read_file(
    request: Request,
    path: str = Query(..., min_length=1, description="Absoluter Pfad einer .md innerhalb der erlaubten Roots."),
) -> dict:
    try:
        return _reader(request).read_file(path)
    except ValueError as exc:  # außerhalb der Roots / keine .md
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc


@router.post("/file", response_model=MdSaveResult)
async def save_file(request: Request, payload: MdFileSave) -> dict:
    """PROJ-12: Notiz atomar zurückschreiben. 400 = Pfad/Frontmatter, 409 = Konflikt."""
    try:
        return _reader(request).save_file(
            payload.path,
            payload.content,
            expected_mtime=payload.expected_mtime,
            expected_hash=payload.expected_hash,
            force=payload.force,
        )
    except MdConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="Datei wurde seit dem Laden extern geändert.",
        ) from exc
    except ValueError as exc:  # außerhalb der Roots / keine .md / ungültiges Frontmatter
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/backlinks", response_model=MdBacklinksResult)
async def backlinks(
    request: Request,
    path: str = Query(..., min_length=1, description="Absoluter .md-Pfad, dessen Backlinks gesucht werden."),
) -> dict:
    """PROJ-12: Notizen, die per [[…]] auf ``path`` verlinken (Reverse-Scan)."""
    try:
        links = _reader(request).backlinks(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc
    return {"path": path, "backlinks": links}
