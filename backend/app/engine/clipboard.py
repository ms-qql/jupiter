"""Service-Schicht der Clipboard-Micro-App (PROJ-69)."""
from __future__ import annotations

import mimetypes
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from ..config import settings
from ..db.clipboard_items import ACTIVE, REMOVED, ClipboardRepository

_CHUNK = 1024 * 1024
_VALID_SOURCE_METHODS = {"drag_drop", "paste", "upload", "ios_share"}
_VALID_SOURCE_DEVICES = {"pc", "mac", "ipad", "iphone", "unknown"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _allowed_roots() -> list[str]:
    return [os.path.realpath(r) for r in settings.allowed_roots]


def _within(real: str, root: str) -> bool:
    return real == root or real.startswith(root + os.sep)


def _in_allowed_roots(real: str) -> bool:
    return any(_within(real, root) for root in _allowed_roots())


def _clean_name(filename: str | None) -> str:
    base = os.path.basename((filename or "").strip())
    if base in ("", ".", ".."):
        return ""
    return base.replace("\x00", "")


def _slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip(".-")
    return value[:80] or "item"


def _guess_extension(name: str, content_type: str | None) -> str:
    ext = os.path.splitext(name)[1].lower()
    if ext:
        return ext
    guessed = mimetypes.guess_extension(content_type or "") or ".bin"
    return ".jpg" if guessed == ".jpe" else guessed


def _check_extension(name: str) -> None:
    allowed = settings.upload_allowed_extensions
    if not allowed:
        return
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext not in allowed:
        raise ValueError(f"Dateityp '.{ext}' ist nicht erlaubt.")


class ClipboardService:
    """Nimmt Dateien an, schreibt sie in den Hal-Inbox und pflegt den Live-Index."""

    def __init__(self, repo: ClipboardRepository) -> None:
        self._repo = repo

    async def startup(self) -> None:
        await self._repo.init()
        self._inbox_dir()

    async def list_items(self, limit: int = 100) -> list[dict]:
        return await self._repo.list_active(limit)

    async def get_item(self, item_id: int) -> dict:
        row = await self._repo.get(item_id)
        if row is None:
            raise KeyError(item_id)
        return row

    async def add_upload(
        self,
        stream: BinaryIO,
        filename: str | None,
        content_type: str | None,
        *,
        source_method: str = "upload",
        source_device: str | None = None,
        notes: str | None = None,
    ) -> dict:
        if source_method not in _VALID_SOURCE_METHODS:
            raise ValueError("Ungültige Quelle.")
        device = source_device or "unknown"
        if device not in _VALID_SOURCE_DEVICES:
            device = "unknown"

        created = _utc_now()
        original = _clean_name(filename)
        ext = _guess_extension(original, content_type)
        display = original or f"clip-{created.strftime('%Y%m%d-%H%M%S')}{ext}"
        if not os.path.splitext(display)[1]:
            display = f"{display}{ext}"
        _check_extension(display)

        paths = self._target_paths(created, device, display, ext)
        try:
            size = self._write_stream(stream, paths["file"])
            self._write_sidecar(
                paths["metadata"],
                created=created,
                source_method=source_method,
                source_device=device,
                original_filename=original or None,
                display_name=display,
                mime_type=content_type,
                size_bytes=size,
                hal_inbox_path=paths["file"],
                notes=notes,
            )
            return await self._repo.add({
                "owner": settings.default_owner,
                "created_at": _iso(created),
                "source_method": source_method,
                "source_device": device,
                "original_filename": original or None,
                "display_name": display,
                "mime_type": content_type or mimetypes.guess_type(display)[0],
                "extension": os.path.splitext(display)[1].lower().lstrip(".") or None,
                "size_bytes": size,
                "hal_inbox_path": paths["file"],
                "metadata_path": paths["metadata"],
                "status": ACTIVE,
                "notes": notes,
            })
        except BaseException:
            for path in (paths["file"], paths["metadata"]):
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except OSError:
                    pass
            raise

    async def update_item(
        self, item_id: int, *, display_name: str | None = None, notes: str | None = None
    ) -> dict:
        row = await self.get_item(item_id)
        fields: dict = {}
        if display_name is not None:
            fields["display_name"] = display_name.strip()
        if notes is not None:
            fields["notes"] = notes
        if fields:
            await self._repo.update(item_id, **fields)
        updated = await self.get_item(item_id)
        self._rewrite_sidecar_from_row(updated)
        return updated

    async def remove_item(self, item_id: int) -> None:
        await self.get_item(item_id)
        await self._repo.update(
            item_id,
            status=REMOVED,
            removed_at=_iso(_utc_now()),
        )

    async def resolve_file(self, item_id: int) -> str:
        row = await self.get_item(item_id)
        path = os.path.realpath(row["hal_inbox_path"])
        inbox = self._inbox_dir()
        if not _within(path, inbox) or not os.path.isfile(path):
            raise FileNotFoundError(path)
        return path

    def settings_payload(self) -> dict:
        return {
            "inbox_dir": self._inbox_dir(),
            "max_file_bytes": settings.upload_max_file_bytes,
            "allowed_extensions": sorted(settings.upload_allowed_extensions),
        }

    def _inbox_dir(self) -> str:
        real = os.path.realpath(settings.clipboard_inbox_dir)
        vault = os.path.realpath(settings.vault_root)
        if not _within(real, vault):
            raise ValueError("Clipboard-Inbox liegt außerhalb des Hal-Vaults.")
        if not _in_allowed_roots(real):
            raise ValueError("Clipboard-Inbox liegt außerhalb der erlaubten Roots.")
        os.makedirs(real, exist_ok=True)
        return real

    def _target_paths(
        self, created: datetime, source_device: str, display_name: str, ext: str
    ) -> dict:
        inbox = self._inbox_dir()
        base_stem = (
            f"{created.strftime('%Y-%m-%d_%H%M%S')}_"
            f"{source_device}_{_slug(os.path.splitext(display_name)[0])}"
        )
        stem = base_stem
        i = 1
        while os.path.exists(os.path.join(inbox, f"{stem}{ext}")) or os.path.exists(
            os.path.join(inbox, f"{stem}.md")
        ):
            stem = f"{base_stem}-{i}"
            i += 1
        file_path = os.path.join(inbox, f"{stem}{ext}")
        metadata_path = os.path.join(inbox, f"{stem}.md")
        return {"file": file_path, "metadata": metadata_path}

    @staticmethod
    def _write_stream(stream: BinaryIO, final: str) -> int:
        directory = os.path.dirname(final)
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        total = 0
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = stream.read(_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    limit = settings.upload_max_file_bytes
                    if limit and total > limit:
                        raise ValueError(f"Datei zu groß (max {limit // (1024 * 1024)} MB).")
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, final)
            return total
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def _write_sidecar(path: str, **fields) -> None:
        lines = [
            "---",
            "type: clipboard-item",
            f"created_at: {fields['created'].isoformat()}",
            f"source_method: {fields['source_method']}",
            f"source_device: {fields['source_device']}",
            f"original_filename: {fields['original_filename'] or ''}",
            f"display_name: {fields['display_name']}",
            f"mime_type: {fields['mime_type'] or ''}",
            f"size_bytes: {fields['size_bytes']}",
            f"hal_inbox_path: {fields['hal_inbox_path']}",
            "---",
            "",
        ]
        if fields.get("notes"):
            lines.extend(["## Notiz", "", str(fields["notes"]), ""])
        tmp = f"{path}.tmp"
        Path(tmp).write_text("\n".join(lines), encoding="utf-8")
        os.replace(tmp, path)

    def _rewrite_sidecar_from_row(self, row: dict) -> None:
        created = datetime.fromisoformat(row["created_at"])
        self._write_sidecar(
            row["metadata_path"],
            created=created,
            source_method=row["source_method"],
            source_device=row.get("source_device") or "unknown",
            original_filename=row.get("original_filename"),
            display_name=row["display_name"],
            mime_type=row.get("mime_type"),
            size_bytes=row["size_bytes"],
            hal_inbox_path=row["hal_inbox_path"],
            notes=row.get("notes"),
        )
