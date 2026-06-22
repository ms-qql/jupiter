"""Vault-API — MD lesen/auflisten/suchen/schreiben (PROJ-2).

Schreiben ist immer auf den Jupiter-Unterbaum begrenzt; Lesen/Suchen sehen den
ganzen Vault (read-only). MVP single-user: kein JWT, ``owner`` serverseitig.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..engine.vault import VaultService
from ..schemas.vault import (
    VaultFileInfo,
    VaultFileRead,
    VaultSearchResult,
    VaultWriteRequest,
    VaultWriteResult,
)

router = APIRouter(prefix="/vault", tags=["vault"])


def _vault(request: Request) -> VaultService:
    return request.app.state.vault


@router.get("/files", response_model=list[VaultFileInfo])
async def list_files(request: Request, dir: str = Query("", description="Unterordner im Jupiter-Bereich.")) -> list[dict]:
    try:
        return _vault(request).list_files(dir)
    except ValueError as exc:  # Pfad-Ausbruch
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/file", response_model=VaultFileRead)
async def read_file(request: Request, path: str = Query(..., min_length=1, description="Pfad relativ zum Vault.")) -> dict:
    try:
        return _vault(request).read_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc


@router.get("/search", response_model=VaultSearchResult)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Suchtext."),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    hits = _vault(request).search(q, limit)
    return {"query": q, "hits": hits}


@router.post("/files", response_model=VaultWriteResult, status_code=201)
async def write_file(payload: VaultWriteRequest, request: Request) -> dict:
    try:
        result = _vault(request).write(
            type=payload.type,
            body=payload.body,
            title=payload.title,
            session_id=payload.session_id,
            on_exists=payload.on_exists,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PermissionError, OSError) as exc:  # Vault nicht erreichbar → klarer Fehler, keine Korruption
        raise HTTPException(status_code=503, detail=f"Vault-Schreibfehler: {exc}") from exc
    return vars(result)
