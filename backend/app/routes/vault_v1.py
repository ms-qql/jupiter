"""Geteilter Vault-Dienst — versionierte API ``/vault/v1`` (PROJ-24).

Eine stabile, **versionierte** Fassade über der internen ``VaultService`` (PROJ-2/15/19),
die auch **eingebettete/fremde Apps** (PROJ-18, #13) nutzen können — die gemeinsame
Datenschicht der Kommandozentrale. Eine Wahrheit (offenes MD im Hal-Vault), viele Konsumenten.

Jeder Aufruf authentisiert sich per Header ``X-Vault-Consumer`` + ``X-Vault-Key`` gegen die
Konsumenten-Registry (``consumers.yaml``). **Scope serverseitig erzwungen** — ein Konsument
liest/schreibt nur die für ihn freigegebenen Pfade (kein Vollzugriff per Default). Schreib-
zugriffe sind versions-/konfliktsicher und tragen ihre Herkunft ins offene Audit-Log.

Ohne PROJ-25 (kein JWT): Identität = statischer Consumer-Key (Single-User-Brücke). Der
Vertrag (Endpunkte/Schemas/Header) bleibt gleich, wenn PROJ-25 die Auflösung gegen echtes
Auth austauscht.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from ..engine.consumers import Consumer
from ..engine.vault import VersionConflictError
from ..schemas.vault_v1 import (
    VaultV1Pointer,
    VaultV1Read,
    VaultV1ResolveResponse,
    VaultV1SearchResponse,
    VaultV1WriteRequest,
    VaultV1WriteResult,
)
from ..config import settings

router = APIRouter(prefix="/vault/v1", tags=["vault-v1"])


def _vault(request: Request):
    return request.app.state.vault


def get_consumer(
    request: Request,
    x_vault_consumer: str | None = Header(default=None, alias="X-Vault-Consumer"),
    x_vault_key: str | None = Header(default=None, alias="X-Vault-Key"),
) -> Consumer:
    """Authentisiert den Konsumenten über die Header gegen die Registry (401 sonst)."""
    registry = request.app.state.consumers
    consumer = registry.authenticate(x_vault_consumer, x_vault_key)
    if consumer is None:
        raise HTTPException(
            status_code=401,
            detail="Unbekannter oder nicht autorisierter Konsument (X-Vault-Consumer/X-Vault-Key).",
        )
    return consumer


def _require_read(consumer: Consumer, path: str) -> None:
    if not consumer.can_read(path):
        raise HTTPException(
            status_code=403,
            detail=f"Konsument „{consumer.id}“ hat keinen Lesezugriff auf „{path}“.",
        )


def _require_write(consumer: Consumer, path: str) -> None:
    if not consumer.can_write(path):
        raise HTTPException(
            status_code=403,
            detail=f"Konsument „{consumer.id}“ hat keinen Schreibzugriff auf „{path}“.",
        )


@router.get("/read", response_model=VaultV1Read)
async def read(
    request: Request,
    path: str = Query(..., min_length=1, description="Vault-relativer Pfad."),
    mode: str = Query("full", pattern="^(full|excerpt)$"),
    offset: int = Query(0, ge=0, description="Start-Offset (nur excerpt)."),
    limit: int | None = Query(None, ge=1, le=200_000, description="Max. Zeichen (nur excerpt)."),
    consumer: Consumer = Depends(get_consumer),
) -> dict:
    _require_read(consumer, path)
    try:
        return _vault(request).read_at(
            path, mode=mode, offset=offset, limit=limit, max_bytes=settings.vault_max_read_bytes
        )
    except ValueError as exc:
        # „zu groß für Volltext" → 413, sonstige Pfad-/mode-Fehler → 400.
        if "zu groß" in str(exc):
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc


@router.get("/search", response_model=VaultV1SearchResponse)
async def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Suchtext."),
    scope: str = Query("all", pattern="^(all|curated)$"),
    limit: int = Query(20, ge=1, le=100),
    consumer: Consumer = Depends(get_consumer),
) -> dict:
    """Sucht im Vault und liefert **Pointer** (Pfad+Zeile+Ausschnitt), kein Volltext.

    Ergebnisse werden auf den **Lese-Scope** des Konsumenten gefiltert — er sieht keine
    Treffer aus Bereichen, die er nicht lesen darf (kein Scope-Leck über die Suche).
    """
    vault = _vault(request)
    raw = vault.search_curated(q, limit) if scope == "curated" else vault.search(q, limit)
    hits = [
        VaultV1Pointer(path=h["path"], line=h["line"], snippet=h["excerpt"])
        for h in raw
        if consumer.can_read(h["path"])
    ]
    return {"query": q, "scope": scope, "hits": hits}


@router.get("/resolve", response_model=VaultV1ResolveResponse)
async def resolve(
    request: Request,
    path: str = Query(..., min_length=1, description="Vault-relativer Pfad."),
    line: int = Query(..., ge=1, description="Zeile, um die der Ausschnitt zentriert wird."),
    radius: int = Query(20, ge=0, le=500, description="Zeilen vor/nach der Trefferzeile."),
    consumer: Consumer = Depends(get_consumer),
) -> dict:
    _require_read(consumer, path)
    try:
        return _vault(request).resolve_pointer(path, line, radius)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden.") from exc


@router.post("/write", response_model=VaultV1WriteResult)
async def write(
    payload: VaultV1WriteRequest,
    request: Request,
    consumer: Consumer = Depends(get_consumer),
) -> dict:
    _require_write(consumer, payload.path)
    vault = _vault(request)
    try:
        result = vault.write_at(
            payload.path, payload.content, mode=payload.mode, base_version=payload.base_version
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except VersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current_version": exc.current},
        ) from exc
    except (PermissionError, OSError) as exc:  # Vault nicht erreichbar → klarer Fehler, keine Korruption
        raise HTTPException(status_code=503, detail=f"Vault-Schreibfehler: {exc}") from exc
    # Herkunft ins offene Audit-Log (best-effort, rollt den Schreibzugriff nicht zurück).
    vault.audit_write(
        consumer_id=consumer.id, path=result["path"], action=result["action"],
        byte_count=result["bytes"], version_before=result["version_before"],
        version_after=result["version"],
    )
    return result
