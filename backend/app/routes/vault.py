"""Vault-API — MD lesen/auflisten/suchen/schreiben (PROJ-2).

Schreiben ist immer auf den Jupiter-Unterbaum begrenzt; Lesen/Suchen sehen den
ganzen Vault (read-only). MVP single-user: kein JWT, ``owner`` serverseitig.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..deps import CurrentUser, get_current_user
from ..engine.vault import VaultService
from ..schemas.vault import (
    VaultFileInfo,
    VaultFileRead,
    VaultRagPreview,
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
    scope: str = Query("all", pattern="^(all|curated)$",
                       description="all = ganzer Vault; curated = nur kuratiertes Wissen (PROJ-15)."),
) -> dict:
    vault = _vault(request)
    hits = vault.search_curated(q, limit) if scope == "curated" else vault.search(q, limit)
    return {"query": q, "hits": hits}


@router.get("/rag/preview", response_model=VaultRagPreview)
async def rag_preview(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Query für die Relevanz-Auswahl."),
    top_n: int = Query(5, ge=1, le=20, description="Maximale Anzahl Ausschnitte."),
    scope: str = Query("all", pattern="^(all|curated)$",
                       description="all = ganzer Vault; curated = nur kuratiertes Wissen (PROJ-15)."),
) -> dict:
    """Pointer/RAG (PROJ-19 #23): gerankte relevante Ausschnitte statt Volltext.

    Macht die Kontext-Ersparnis sichtbar (``reduction_pct``) und signalisiert via
    ``fallback`` einen leeren Treffer, damit der Caller auf Volltext zurückfallen kann.
    """
    return _vault(request).rag_preview(q, top_n=top_n, curated=scope == "curated")


@router.post("/files", response_model=VaultWriteResult, status_code=201)
async def write_file(
    payload: VaultWriteRequest, request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    try:
        result = _vault(request).write(
            type=payload.type,
            body=payload.body,
            title=payload.title,
            session_id=payload.session_id,
            owner=user.user_id,  # PROJ-25: Herkunft IMMER aus dem Token (Audit/Scope-Vertrag).
            on_exists=payload.on_exists,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PermissionError, OSError) as exc:  # Vault nicht erreichbar → klarer Fehler, keine Korruption
        raise HTTPException(status_code=503, detail=f"Vault-Schreibfehler: {exc}") from exc
    return vars(result)
