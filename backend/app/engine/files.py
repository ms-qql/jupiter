"""FileService — Dateisystem-Ebene des Fileexplorers + Clipboard (PROJ-11).

Operiert ausschließlich innerhalb der ``allowed_roots`` (``/home/dev/projects``,
``/home/dev/tools``) — kein MinIO, keine DB, kein JWT (Jupiter-Override). Pfad-
Härtung über dasselbe ``realpath`` + erlaubte-Wurzel-Muster wie ``md_reader`` /
``validate_project_path``. Schreiben atomar (temp + ``os.replace``) und Uploads
gestreamt mit hartem Größen-Abbruch (kein Voll-RAM).

Zwei Oberflächen, ein Dienst: der Fileexplorer (Surface A) und der In-Session
Dokument-Clipboard (Surface B) nutzen beide ``save_upload`` → der absolute Pfad
in der Antwort speist „Pfad kopieren" bzw. das Einfügen ins Session-Eingabefeld.
"""
from __future__ import annotations

import mimetypes
import os
import shutil
import tempfile
from datetime import datetime, timezone

from ..config import settings

_CHUNK = 1024 * 1024  # 1 MB Streaming-Häppchen


def _allowed_roots() -> list[str]:
    return [os.path.realpath(r) for r in settings.allowed_roots]


def _within(real: str, root: str) -> bool:
    return real == root or real.startswith(root + os.sep)


def _in_allowed_roots(real: str) -> bool:
    return any(_within(real, r) for r in _allowed_roots())


def _now_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class FileService:
    """Verzeichnis-Listing, Up-/Download, Datei-Operationen und Clipboard-Ordner."""

    # --- Pfad-Härtung ------------------------------------------------------

    def _validate_dir(self, path: str, *, create: bool = False) -> str:
        """Realpfad eines Verzeichnisses innerhalb ``allowed_roots`` (optional anlegen)."""
        real = os.path.realpath(path)
        if not _in_allowed_roots(real):
            raise ValueError(
                "Pfad liegt außerhalb des erlaubten Bereichs "
                f"({', '.join(settings.allowed_roots)})."
            )
        if create:
            os.makedirs(real, exist_ok=True)
        if not os.path.isdir(real):
            raise ValueError("Pfad existiert nicht oder ist kein Verzeichnis.")
        return real

    def _real_existing(self, path: str) -> str:
        """Realpfad einer existierenden Datei/eines Ordners innerhalb der Roots."""
        real = os.path.realpath(path)
        if not _in_allowed_roots(real):
            raise ValueError("Pfad liegt außerhalb des erlaubten Bereichs.")
        if not os.path.exists(real):
            raise FileNotFoundError(real)
        return real

    def _child_real(self, parent_real: str, name: str) -> str:
        """Kind-Pfad, der garantiert innerhalb des Eltern-Ordners bleibt (Traversal-Schutz)."""
        candidate = os.path.realpath(os.path.join(parent_real, name))
        if not _within(candidate, parent_real):
            raise ValueError("Ungültiges Ziel.")
        return candidate

    @staticmethod
    def _safe_name(name: str) -> str:
        """Strikter Basisname für vom Nutzer benannte Ziele (mkdir/rename) — keine Pfadanteile."""
        raw = (name or "").strip()
        if not raw or raw in (".", "..") or "/" in raw or "\\" in raw or "\x00" in raw:
            raise ValueError("Ungültiger Name.")
        return raw

    @staticmethod
    def _clean_upload_name(name: str | None) -> str:
        """Toleranter Basisname eines Uploads (Browser liefert i. d. R. nur den Basisnamen)."""
        base = os.path.basename((name or "").strip())
        return "" if base in ("", ".", "..") else base

    @staticmethod
    def _generated_name(content_type: str | None) -> str:
        """Name für namenlose Pastes (Screenshots): ``clip-YYYYMMDD-HHMMSS.<ext>``."""
        ext = mimetypes.guess_extension(content_type or "") or ".bin"
        if ext == ".jpe":
            ext = ".jpg"
        return f"clip-{datetime.now().strftime('%Y%m%d-%H%M%S')}{ext}"

    @staticmethod
    def _check_extension(name: str) -> None:
        allowed = settings.upload_allowed_extensions
        if not allowed:  # leere Whitelist = alles erlaubt (Escape-Hatch)
            return
        ext = os.path.splitext(name)[1].lower().lstrip(".")
        if ext not in allowed:
            raise ValueError(f"Dateityp '.{ext}' ist nicht erlaubt.")

    @staticmethod
    def _unique_path(dir_real: str, name: str) -> str:
        """Kollisionsfreier Zielpfad: hängt ``-1``/``-2``/… an, bis frei (wie Rubric uniqueName)."""
        base, ext = os.path.splitext(name)
        candidate = os.path.join(dir_real, name)
        i = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dir_real, f"{base}-{i}{ext}")
            i += 1
        return candidate

    def _entry(self, path: str) -> dict:
        real = os.path.realpath(path)
        st = os.stat(real)
        is_dir = os.path.isdir(real)
        return {
            "name": os.path.basename(real),
            "kind": "dir" if is_dir else "file",
            "size": 0 if is_dir else st.st_size,
            "mtime": _now_iso(st.st_mtime),
            "path": real,
        }

    # --- Clipboard-Ordner --------------------------------------------------

    def clipboard_dir(self) -> str:
        """Aktueller Clipboard-Ordner (validiert + bei Bedarf angelegt)."""
        return self._validate_dir(settings.clipboard_dir, create=True)

    def set_clipboard_dir(self, path: str) -> str:
        """Clipboard-Ordner setzen (innerhalb der Roots, wird angelegt) — in-memory."""
        real = self._validate_dir(path, create=True)
        settings.clipboard_dir = real
        return real

    # --- Lesen / Listen ----------------------------------------------------

    def roots(self) -> list[dict]:
        """Erlaubte Wurzel-Ordner (für den RootSelector)."""
        return [{"label": os.path.basename(r) or r, "path": r} for r in _allowed_roots()]

    def list_dir(self, path: str | None) -> dict:
        """Inhalt eines Verzeichnisses (Ordner zuerst, dann alphabetisch)."""
        real = self._validate_dir(path or _allowed_roots()[0])
        entries: list[dict] = []
        with os.scandir(real) as it:
            for de in it:
                try:
                    entries.append(self._entry(de.path))
                except OSError:
                    continue  # z. B. kaputter Symlink → überspringen
        entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
        return {"path": real, "entries": entries}

    def resolve_download(self, path: str) -> str:
        """Realpfad einer existierenden Datei innerhalb der Roots (für FileResponse)."""
        real = os.path.realpath(path)
        if not _in_allowed_roots(real):
            raise ValueError("Pfad liegt außerhalb des erlaubten Bereichs.")
        if not os.path.isfile(real):
            raise FileNotFoundError(real)
        return real

    # --- Schreiben / Operationen ------------------------------------------

    def save_upload(self, stream, filename: str | None, content_type: str | None,
                    target_dir: str | None = None) -> dict:
        """Eine hochgeladene Datei gestreamt in den Zielordner schreiben (Default: Clipboard).

        ``stream`` ist ein synchrones File-Objekt (z. B. ``UploadFile.file``).
        Namenlose Pastes erhalten einen ``clip-…``-Zeitstempelnamen; Kollisionen
        werden über ``-1/-2`` aufgelöst.
        """
        target = self._validate_dir(target_dir or settings.clipboard_dir, create=True)
        name = self._clean_upload_name(filename)
        if not name:
            # Namenloser Paste (Screenshot) → clip-Zeitstempelname.
            name = self._generated_name(content_type)
        elif not os.path.splitext(name)[1]:
            # Name ohne Endung (z. B. Clipboard-„blob") → Endung aus content_type ergänzen.
            ext = mimetypes.guess_extension(content_type or "") or ""
            name = name + (".jpg" if ext == ".jpe" else ext)
        self._check_extension(name)
        self._child_real(target, name)  # Defense-in-Depth gegen Traversal
        final = self._unique_path(target, name)
        self._stream_to_file(stream, final, target)
        return self._entry(final)

    @staticmethod
    def _stream_to_file(stream, final: str, directory: str) -> None:
        """Gestreamt in eine temp-Datei + ``os.replace`` (atomar); harter Größen-Abbruch."""
        limit = settings.upload_max_file_bytes
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        total = 0
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = stream.read(_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if limit and total > limit:
                        raise ValueError(
                            f"Datei zu groß (max {limit // (1024 * 1024)} MB)."
                        )
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, final)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def mkdir(self, parent: str, name: str) -> dict:
        parent_real = self._validate_dir(parent)
        target = self._child_real(parent_real, self._safe_name(name))
        if os.path.exists(target):
            raise FileExistsError(target)
        os.makedirs(target)
        return self._entry(target)

    def rename(self, path: str, new_name: str) -> dict:
        real = self._real_existing(path)
        dest = self._child_real(os.path.dirname(real), self._safe_name(new_name))
        if os.path.exists(dest):
            raise FileExistsError(dest)
        os.rename(real, dest)
        return self._entry(dest)

    def move(self, path: str, dest_dir: str) -> dict:
        real = self._real_existing(path)
        target_dir = self._validate_dir(dest_dir)
        dest = self._child_real(target_dir, os.path.basename(real))
        if os.path.exists(dest):
            raise FileExistsError(dest)
        os.rename(real, dest)
        return self._entry(dest)

    def delete(self, paths: list[str]) -> dict:
        deleted: list[str] = []
        failed: list[str] = []
        for p in paths:
            try:
                real = self._real_existing(p)
                if os.path.isdir(real):
                    shutil.rmtree(real)
                else:
                    os.remove(real)
                deleted.append(real)
            except (ValueError, OSError):
                failed.append(p)
        return {"deleted": deleted, "failed": failed}
