"""Pydantic-v2-Schemas für die MD-Reader-API (PROJ-7) + MD-Editor (PROJ-12)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MdSource(BaseModel):
    id: str       # "vault" | "project"
    label: str    # Anzeigename (Vault bzw. Projekt-Ordnername)
    root: str     # absoluter Wurzelpfad


class MdIndexEntry(BaseModel):
    path: str     # absoluter Pfad (zum Lesen via GET /md/file)
    rel: str      # relativ zur Quell-Wurzel (für den Datei-Baum)
    name: str     # Basisname inkl. .md (für die Wikilink-Auflösung)


class MdIndexResult(BaseModel):
    source: str
    root: str
    files: list[MdIndexEntry]


class MdFileRead(BaseModel):
    path: str
    frontmatter: dict
    body: str
    content: str
    # PROJ-12: Basis für die optimistische Konflikterkennung beim Speichern.
    mtime: float | None = None
    hash: str | None = None


class MdFileSave(BaseModel):
    """Request für POST /md/file (PROJ-12). ``content`` = voller Rohtext (Frontmatter+Body)."""

    path: str = Field(..., min_length=1, description="Absoluter .md-Pfad innerhalb der erlaubten Roots.")
    content: str = Field(..., description="Vollständiger Datei-Inhalt (Frontmatter-Block + Body, 1:1).")
    expected_mtime: float | None = Field(None, description="mtime beim Laden — für die Konfliktprüfung.")
    expected_hash: str | None = Field(None, description="SHA-256 beim Laden — für die Konfliktprüfung.")
    force: bool = Field(False, description="True überschreibt trotz erkannten Konflikts.")


class MdSaveResult(BaseModel):
    path: str
    mtime: float
    hash: str


class MdBacklinksResult(BaseModel):
    path: str
    backlinks: list[MdIndexEntry]
