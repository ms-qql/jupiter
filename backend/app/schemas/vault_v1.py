"""Pydantic-v2-Schemas für die versionierte, geteilte Vault-API ``/vault/v1`` (PROJ-24).

Stabiler Vertrag über der internen ``VaultService``: lesen (Volltext/Ausschnitt), suchen
(Pointer), Pointer auflösen, schreiben (versions-/konfliktsicher). Konsumenten authentisieren
per Header (``X-Vault-Consumer`` + ``X-Vault-Key``); der Scope wird serverseitig erzwungen.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..config import MAX_INPUT_CHARS

WriteMode = Literal["create", "overwrite", "append"]
ReadMode = Literal["full", "excerpt"]


class VaultV1Read(BaseModel):
    path: str = Field(..., description="Vault-relativer Pfad (zugleich Pointer/Backlink).")
    version: str = Field(..., description="Inhalts-Hash — für optimistische Schreib-Konfliktprüfung.")
    content: str = Field(..., description="Volltext oder Ausschnitt (je nach mode).")
    offset: int = Field(..., description="Start-Offset des Ausschnitts (0 bei full).")
    returned_chars: int = Field(..., description="Anzahl zurückgegebener Zeichen.")
    total_chars: int = Field(..., description="Gesamtgröße der Datei in Zeichen.")
    truncated: bool = Field(..., description="True = es folgt noch mehr Text (Ausschnitt).")


class VaultV1Pointer(BaseModel):
    path: str
    line: int = Field(..., description="Treffer-Zeile (1-basiert).")
    snippet: str = Field(..., description="Kurzer Ausschnitt um den Treffer (kein Volltext).")
    score: int | None = Field(default=None, description="Relevanz (nur bei rag-gestützter Suche).")


class VaultV1SearchResponse(BaseModel):
    query: str
    scope: str = Field(..., description="all = ganzer (erlaubter) Vault; curated = nur Knowledge/.")
    hits: list[VaultV1Pointer]


class VaultV1ResolveResponse(BaseModel):
    path: str
    version: str
    line: int
    start_line: int
    end_line: int
    total_lines: int
    excerpt: str


class VaultV1WriteRequest(BaseModel):
    path: str = Field(
        ..., min_length=1, max_length=400,
        description="Vault-relativer Zielpfad (.md). Muss im Schreib-Scope des Konsumenten liegen.",
    )
    content: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS, description="MD-Inhalt.")
    mode: WriteMode = Field(default="create", description="create | overwrite | append.")
    base_version: str | None = Field(
        default=None,
        description="Bei overwrite einer bestehenden Datei nötig: die zuvor gelesene version.",
    )


class VaultV1WriteResult(BaseModel):
    path: str
    version: str = Field(..., description="Neue Version nach dem Schreiben.")
    action: str
    bytes: int
    version_before: str | None = None
