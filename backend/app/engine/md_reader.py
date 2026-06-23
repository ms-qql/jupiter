"""MdReaderService — read-only Markdown-Leser über die erlaubten Roots (PROJ-7).

Der MD-Reader liest Markdown aus den bereits konfigurierten ``allowed_roots``
(``/home/dev/projects``, ``/home/dev/tools``) und deckt damit ZWEI Quellen in einem
Modell ab:

- **vault**   → der ganze Hal-Vault (``vault_root``), read-only.
- **project** → das ausgewählte Projekt-Repo (Feature-Specs unter ``features/``,
  Doku unter ``docs/``); Default = ``reader_default_project``, pro Request
  überschreibbar.

Rein lesend (kein Schreibpfad) und gegen Pfad-Ausbruch gehärtet — dasselbe
``realpath`` + erlaubte-Wurzel-Muster wie ``validate_project_path`` in
``manager.py``. Frontmatter wird mit dem PROJ-2-Parser getrennt vom Body geliefert
(``frontmatter`` als Objekt statt Rohtext).
"""
from __future__ import annotations

import os

from ..config import settings
from .vault import _parse_frontmatter

# Verzeichnisse, die beim Index-Walk übersprungen werden (kein nutzbares MD,
# aber potenziell riesig → DoS-/Performance-Schutz).
_EXCLUDE_DIRS = {
    ".git", "node_modules", ".next", "__pycache__", ".venv", "venv",
    "dist", "build", ".codegraph", ".obsidian", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".idea", ".turbo", ".cache",
}
# Obergrenze für die Anzahl indizierter Dateien (Schutz bei sehr großen Bäumen).
_MAX_INDEX_FILES = 10_000


def _allowed_roots() -> list[str]:
    return [os.path.realpath(r) for r in settings.allowed_roots]


def _within(real: str, root: str) -> bool:
    return real == root or real.startswith(root + os.sep)


def _in_allowed_roots(real: str) -> bool:
    return any(_within(real, r) for r in _allowed_roots())


def _validate_dir(path: str) -> str:
    """Realpfad eines Verzeichnisses innerhalb ``allowed_roots`` (Muster ``validate_project_path``)."""
    real = os.path.realpath(path)
    if not _in_allowed_roots(real):
        raise ValueError(
            "Pfad liegt außerhalb des erlaubten Bereichs "
            f"({', '.join(settings.allowed_roots)})."
        )
    if not os.path.isdir(real):
        raise ValueError("Pfad existiert nicht oder ist kein Verzeichnis.")
    return real


def _validate_md_file(path: str) -> str:
    """Realpfad einer ``.md``-Datei innerhalb ``allowed_roots``; sonst ``ValueError``/``FileNotFoundError``."""
    real = os.path.realpath(path)
    if not _in_allowed_roots(real):
        raise ValueError("Pfad liegt außerhalb des erlaubten Bereichs.")
    if not real.endswith(".md"):
        raise ValueError("Nur .md-Dateien können gelesen werden.")
    if not os.path.isfile(real):
        raise FileNotFoundError(real)
    return real


class MdReaderService:
    """Read-only Markdown-Zugriff über die erlaubten Roots (Vault + Projekt)."""

    def sources(self, project: str | None = None) -> list[dict]:
        """Verfügbare Lese-Quellen. Vault immer; Projekt, falls gültig (Default = config)."""
        out = [{"id": "vault", "label": "Vault", "root": os.path.realpath(settings.vault_root)}]
        proj = project or settings.reader_default_project
        if proj:
            try:
                real = _validate_dir(proj)
            except ValueError:
                real = None
            if real:
                out.append({"id": "project", "label": os.path.basename(real) or real, "root": real})
        return out

    def resolve_source_root(self, source: str, project: str | None = None) -> str:
        """``source`` → erlaubter, validierter Wurzelpfad."""
        if source == "vault":
            return _validate_dir(settings.vault_root)
        if source == "project":
            proj = project or settings.reader_default_project
            if not proj:
                raise ValueError("Kein Projektpfad angegeben.")
            return _validate_dir(proj)
        raise ValueError(f"Unbekannte Quelle '{source}'. Erlaubt: vault | project.")

    def index(self, source: str, project: str | None = None) -> tuple[str, list[dict]]:
        """Flache Liste aller ``.md`` unter der Quelle → ``(root, [{path, rel, name}])``.

        ``path`` ist absolut (zum Lesen via ``read_file``), ``rel`` relativ zur Wurzel
        (für den Baum), ``name`` der Basisname (für die Wikilink-Auflösung).
        """
        root = self.resolve_source_root(source, project)
        out: list[dict] = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for name in files:
                if not name.endswith(".md"):
                    continue
                real = os.path.realpath(os.path.join(dirpath, name))
                # Symlink, der aus der Wurzel ausbricht → überspringen (Exfiltration-Schutz).
                if not _within(real, root):
                    continue
                out.append({"path": real, "rel": os.path.relpath(real, root), "name": name})
                if len(out) >= _MAX_INDEX_FILES:
                    out.sort(key=lambda e: e["rel"])
                    return root, out
        out.sort(key=lambda e: e["rel"])
        return root, out

    def read_file(self, path: str) -> dict:
        """Liest eine ``.md`` (absoluter Pfad, gegen ``allowed_roots`` validiert)."""
        real = _validate_md_file(path)
        with open(real, encoding="utf-8") as fh:
            content = fh.read()
        frontmatter, body = _parse_frontmatter(content)
        return {"path": real, "frontmatter": frontmatter, "body": body, "content": content}
