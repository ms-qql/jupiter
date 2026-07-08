"""Clipboard-Persistenz (PROJ-69).

SQLite hält nur den schnellen Live-Index der aktiven Clipboard-Liste. Die
eigentlichen Dateien und Sidecar-Metadaten liegen als offene Dateien im Hal-Vault.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

ACTIVE = "active"
REMOVED = "removed_from_clipboard"
ERROR = "error"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clipboard_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner              TEXT,
    created_at         TEXT NOT NULL,
    source_method      TEXT NOT NULL,
    source_device      TEXT,
    original_filename  TEXT,
    display_name       TEXT NOT NULL,
    mime_type          TEXT,
    extension          TEXT,
    size_bytes         INTEGER NOT NULL DEFAULT 0,
    hal_inbox_path     TEXT NOT NULL,
    metadata_path      TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active',
    notes              TEXT,
    error_message      TEXT,
    removed_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_clipboard_status_created
    ON clipboard_items(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_clipboard_owner_status
    ON clipboard_items(owner, status);
"""

_UPDATABLE: frozenset[str] = frozenset({
    "display_name", "notes", "status", "error_message", "removed_at",
})


@runtime_checkable
class ClipboardRepository(Protocol):
    async def init(self) -> None: ...
    async def add(self, fields: dict) -> dict: ...
    async def list_active(self, limit: int = 100) -> list[dict]: ...
    async def get(self, item_id: int) -> dict | None: ...
    async def update(self, item_id: int, **fields) -> None: ...
    async def close(self) -> None: ...


class SqliteClipboardRepository:
    """SQLite-Ablage der Clipboard-Metadaten (host-nativ, single-writer)."""

    _INSERTABLE: tuple[str, ...] = (
        "owner", "created_at", "source_method", "source_device",
        "original_filename", "display_name", "mime_type", "extension",
        "size_bytes", "hal_inbox_path", "metadata_path", "status", "notes",
        "error_message", "removed_at",
    )

    def __init__(self, db_path: str) -> None:
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_sync(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _add_sync(self, fields: dict) -> dict:
        cols = [c for c in self._INSERTABLE if c in fields]
        placeholders = ", ".join("?" for _ in cols)
        values = [fields[c] for c in cols]
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT INTO clipboard_items ({', '.join(cols)}) "
                f"VALUES ({placeholders})",
                values,
            )
            new_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM clipboard_items WHERE id = ?", (new_id,)
            ).fetchone()
        return dict(row)

    def _list_active_sync(self, limit: int) -> list[dict]:
        capped = max(1, min(int(limit), 200))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM clipboard_items "
                "WHERE status = 'active' ORDER BY created_at DESC, id DESC LIMIT ?",
                (capped,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _get_sync(self, item_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM clipboard_items WHERE id = ?", (item_id,)
            ).fetchone()
        return dict(row) if row else None

    def _update_sync(self, item_id: int, fields: dict) -> None:
        cols = [c for c in fields if c in _UPDATABLE]
        if not cols:
            return
        assignments = ", ".join(f"{c} = ?" for c in cols)
        values = [fields[c] for c in cols]
        values.append(item_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE clipboard_items SET {assignments} WHERE id = ?", values
            )

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def add(self, fields: dict) -> dict:
        return await asyncio.to_thread(self._add_sync, fields)

    async def list_active(self, limit: int = 100) -> list[dict]:
        return await asyncio.to_thread(self._list_active_sync, limit)

    async def get(self, item_id: int) -> dict | None:
        return await asyncio.to_thread(self._get_sync, item_id)

    async def update(self, item_id: int, **fields) -> None:
        await asyncio.to_thread(self._update_sync, item_id, fields)

    async def close(self) -> None:
        return None


def build_clipboard_repo(settings_obj) -> ClipboardRepository:
    return SqliteClipboardRepository(settings_obj.clipboard_db_path)
