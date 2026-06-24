"""Pydantic-v2-Schemas für die Vault-API (PROJ-2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..config import MAX_INPUT_CHARS

# type → Unterordner: session_log → Sessions/, handover → Handovers/, curated → Knowledge/.
VaultType = Literal["session_log", "handover", "curated"]
OnExists = Literal["append", "version", "error"]


class VaultWriteRequest(BaseModel):
    type: VaultType = Field(..., description="session_log (roh) oder handover (kuratiert).")
    body: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS, description="MD-Body.")
    title: str | None = Field(default=None, max_length=200, description="Titel → Dateiname-Slug.")
    session_id: str | None = Field(default=None, max_length=64, description="Zugehörige Session.")
    on_exists: OnExists = Field(default="append", description="Verhalten bei Namenskollision.")


class HandoverRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS, description="Kuratierter Handover-Text (MD).")
    title: str | None = Field(default=None, max_length=200)
    on_exists: OnExists = "version"


class VaultWriteResult(BaseModel):
    path: str
    type: str
    created: str


class VaultFileRead(BaseModel):
    path: str
    frontmatter: dict
    body: str
    content: str


class VaultFileInfo(BaseModel):
    path: str
    name: str
    size: int
    modified: str


class VaultSearchHit(BaseModel):
    path: str
    line: int
    excerpt: str


class VaultSearchResult(BaseModel):
    query: str
    hits: list[VaultSearchHit]


# --- PROJ-19 (#23): Pointer/RAG --------------------------------------------


class VaultRagSnippet(BaseModel):
    path: str = Field(..., description="Vault-relativer Pfad (zugleich Pointer/Backlink).")
    line: int
    snippet: str = Field(..., description="Dichtester relevanter Ausschnitt (statt Volltext).")
    score: int = Field(..., description="Relevanz: getroffene Begriffe ×1000 + Gesamthäufigkeit.")
    terms_matched: int
    full_chars: int = Field(..., description="Volltext-Größe der Datei (für die Ersparnis-Messung).")


class VaultRagPreview(BaseModel):
    query: str
    snippets: list[VaultRagSnippet]
    fallback: bool = Field(..., description="True = kein relevanter Ausschnitt → Caller lädt Volltext.")
    reason: str | None = None
    context_chars: int = Field(..., description="Summe der gelieferten Snippet-Zeichen (RAG).")
    fulltext_chars: int = Field(..., description="Volltext-Zeichen der Top-N-Dateien (Baseline).")
    reduction_pct: float = Field(..., description="Kontext-Ersparnis ggü. Volltext in Prozent.")
