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

import hashlib
import os
import re

from ..config import settings
from .vault import VaultService, _parse_frontmatter

# Wikilink-Muster für den Backlink-Scan — spiegelt remark-wikilink.ts:
# [[Ziel]], [[Ziel|Alias]], [[Ziel#Anker]] und Embeds ![[Ziel]].
_WIKILINK_RE = re.compile(r"!?\[\[([^\]\n]+?)\]\]")
# Dateien über dieser Größe beim Backlink-Scan überspringen (Performance/DoS).
_MAX_SCAN_FILE_BYTES = 1_000_000


class MdConflictError(Exception):
    """Datei wurde seit dem Laden extern geändert (mtime/Hash weichen ab)."""

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


def _validate_md_write(path: str) -> str:
    """Realpfad einer (ggf. noch nicht existierenden) ``.md`` innerhalb ``allowed_roots``.

    Gleiche Pfad-Härtung wie beim Lesen, aber ``isfile`` wird NICHT verlangt — Speichern
    darf eine neue Datei anlegen. ``realpath`` stellt sicher, dass das Ziel (Symlinks
    aufgelöst) im erlaubten Bereich liegt.
    """
    real = os.path.realpath(path)
    if not _in_allowed_roots(real):
        raise ValueError("Pfad liegt außerhalb des erlaubten Bereichs.")
    if not real.endswith(".md"):
        raise ValueError("Nur .md-Dateien können gespeichert werden.")
    if os.path.isdir(real):
        raise ValueError("Pfad ist ein Verzeichnis.")
    return real


def _validate_frontmatter(content: str) -> None:
    """Strukturprüfung des führenden ``---``-Blocks. Offen, aber nicht geschlossen → Fehler.

    Bewusst keine volle YAML-Validierung (der Vault nutzt einen toleranten
    zeilenbasierten Parser); fängt aber den realistischen Datenverlust-Fall ab:
    ein geöffneter Frontmatter-Block ohne schließendes ``---``.
    """
    if not content.startswith("---\n"):
        return
    if content.find("\n---\n", 4) != -1:
        return
    if content.rstrip().endswith("---") and content.rstrip() != "---":
        return
    raise ValueError("Ungültiges Frontmatter: Block ist nicht mit '---' geschlossen.")


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_key(s: str) -> str:
    return re.sub(r"\.md$", "", s.strip(), flags=re.IGNORECASE).lower()


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
        return {
            "path": real,
            "frontmatter": frontmatter,
            "body": body,
            "content": content,
            # PROJ-12: mtime + Hash → Basis der optimistischen Konflikterkennung.
            "mtime": os.path.getmtime(real),
            "hash": _content_hash(content),
        }

    def save_file(
        self,
        path: str,
        content: str,
        *,
        expected_mtime: float | None = None,
        expected_hash: str | None = None,
        force: bool = False,
    ) -> dict:
        """Schreibt eine ``.md`` atomar zurück (PROJ-12).

        - Pfad-Härtung gegen ``allowed_roots`` (wie Lesen, aber Neuanlage erlaubt).
        - Frontmatter wird strukturell validiert (offener, ungeschlossener Block → ``ValueError``).
        - Optimistische Konfliktprüfung: weicht der aktuelle Stand (mtime ODER Hash) vom
          erwarteten ab und ``force`` ist nicht gesetzt → ``MdConflictError`` (→ 409).
        - Schreiben via ``VaultService._atomic_write`` (temp + ``os.replace``).
        """
        real = _validate_md_write(path)
        _validate_frontmatter(content)

        # Konfliktprüfung nur, wenn die Datei existiert und ein Erwartungswert vorliegt.
        if os.path.isfile(real) and not force and (expected_mtime is not None or expected_hash is not None):
            with open(real, encoding="utf-8") as fh:
                current = fh.read()
            current_hash = _content_hash(current)
            current_mtime = os.path.getmtime(real)
            changed = (expected_hash is not None and expected_hash != current_hash) or (
                expected_hash is None and expected_mtime is not None and expected_mtime != current_mtime
            )
            if changed:
                raise MdConflictError(real)

        VaultService._atomic_write(real, content)
        return {"path": real, "mtime": os.path.getmtime(real), "hash": _content_hash(content)}

    def backlinks(self, path: str) -> list[dict]:
        """Notizen, die per ``[[…]]`` auf ``path`` verlinken (Reverse-Scan, PROJ-12).

        Scannt die Quell-Sammlung, die die Zieldatei enthält (Vault ODER das
        Default-Projekt), und matcht Wikilink-Ziele gegen Basisname bzw. vollen
        rel-Pfad der Zielnotiz — dieselbe Auflösung wie im Frontend.
        """
        target = _validate_md_file(path)
        scan_root = self._source_root_for(target)

        target_base = _normalize_key(os.path.basename(target))
        target_rel = _normalize_key(os.path.relpath(target, scan_root))

        hits: list[dict] = []
        for dirpath, dirs, files in os.walk(scan_root):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            for name in files:
                if not name.endswith(".md"):
                    continue
                real = os.path.realpath(os.path.join(dirpath, name))
                if real == target or not _within(real, scan_root):
                    continue
                try:
                    if os.path.getsize(real) > _MAX_SCAN_FILE_BYTES:
                        continue
                    with open(real, encoding="utf-8") as fh:
                        text = fh.read()
                except OSError:
                    continue
                if self._links_to(text, target_base, target_rel):
                    hits.append({"path": real, "rel": os.path.relpath(real, scan_root), "name": name})
                    if len(hits) >= _MAX_INDEX_FILES:
                        break
            if len(hits) >= _MAX_INDEX_FILES:
                break
        hits.sort(key=lambda e: e["rel"])
        return hits

    @staticmethod
    def _links_to(text: str, target_base: str, target_rel: str) -> bool:
        """True, wenn ein ``[[…]]`` in ``text`` auf die Zielnotiz zeigt (Basisname oder rel-Pfad)."""
        for match in _WIKILINK_RE.finditer(text):
            raw = match.group(1)
            # Alias (|) und Anker (#) abtrennen, dann normalisieren.
            link = _normalize_key(raw.split("|")[0].split("#")[0])
            if not link:
                continue
            if link == target_rel or link == target_base or link.split("/")[-1] == target_base:
                return True
        return False

    def _source_root_for(self, real_target: str) -> str:
        """Quell-Wurzel, die die Zieldatei enthält: Vault, Default-Projekt, sonst der Allowed-Root."""
        vault = os.path.realpath(settings.vault_root)
        if _within(real_target, vault):
            return vault
        proj = settings.reader_default_project
        if proj:
            preal = os.path.realpath(proj)
            if _within(real_target, preal):
                return preal
        for r in _allowed_roots():
            if _within(real_target, r):
                return r
        raise ValueError("Zieldatei liegt in keiner bekannten Quelle.")
