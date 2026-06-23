"""Pydantic-v2-Schemas für die MD-Reader-API (PROJ-7, read-only)."""
from __future__ import annotations

from pydantic import BaseModel


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
