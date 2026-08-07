"""Pydantic-v2-Schemas für die Fileexplorer-/Clipboard-API (PROJ-11).

Reine Dateisystem-Ebene innerhalb der ``allowed_roots`` — kein DB-State, kein
JWT (Jupiter-Override). ``path`` ist immer ein absoluter, serverseitig gegen die
erlaubten Roots validierter Pfad (für „Pfad kopieren" / In-Session-Referenz).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    """Eine Datei oder ein Verzeichnis im Explorer/Clipboard-Ordner."""

    name: str            # Basisname inkl. Endung
    kind: str            # "file" | "dir"
    size: int            # Bytes (bei dir: 0)
    mtime: str           # ISO-8601 (UTC)
    path: str            # absoluter Pfad — direkt referenzierbar (Terminal/Session)
    editable: bool = False  # ob Datei im Texteditor bearbeitbar (PROJ-76)


class RootEntry(BaseModel):
    """Ein erlaubter Wurzel-Ordner (für den RootSelector)."""

    label: str
    path: str


class DirListing(BaseModel):
    path: str            # gelisteter Ordner (absolut)
    entries: list[FileEntry]


class UploadResult(BaseModel):
    """Antwort auf einen Upload/Paste — die gespeicherten Dateien mit absolutem Pfad."""

    files: list[FileEntry]


class MkdirRequest(BaseModel):
    parent: str = Field(..., min_length=1, description="Absoluter Eltern-Ordner innerhalb der Roots.")
    name: str = Field(..., min_length=1, description="Name des neuen Ordners.")


class RenameRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Absoluter Pfad der Datei/des Ordners.")
    new_name: str = Field(..., min_length=1, description="Neuer Basisname (ohne Pfadanteile).")


class MoveRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Absoluter Quell-Pfad.")
    dest_dir: str = Field(..., min_length=1, description="Absoluter Ziel-Ordner innerhalb der Roots.")


class DeleteRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1, description="Absolute Pfade, die gelöscht werden sollen.")


class DeleteResult(BaseModel):
    deleted: list[str]
    failed: list[str]


class ZipRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1, description="Absolute Pfade, die als ZIP gebündelt werden sollen.")


class ClipboardDirRead(BaseModel):
    """Aktueller Clipboard-Ordner (absoluter Pfad, garantiert innerhalb der Roots)."""

    path: str


class ClipboardDirPatch(BaseModel):
    path: str = Field(..., min_length=1, description="Neuer Clipboard-Ordner (innerhalb der Roots).")


class TextFileRead(BaseModel):
    """Inhalt einer editierbaren Textdatei (PROJ-76)."""

    path: str
    content: str
    size: int
    mtime: str
    hash: str


class TextFileWrite(BaseModel):
    """Schreib-Request: Pfad + vollständiger Inhalt + Hash (Konflikterkennung)."""

    path: str = Field(..., min_length=1, description="Absoluter Pfad innerhalb der Roots.")
    content: str = Field(..., description="Vollständiger neuer Dateiinhalt.")
    hash: str = Field(..., description="SHA256 des beim Laden/letzten Speichern bekannten Stands.")
    force: bool = Field(False, description="Überschreibt auch bei erkanntem Konflikt.")
