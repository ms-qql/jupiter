"""Buch-Nuggets-Warteschlange (PROJ-53, Persistenz-Seam).

Spiegelt die **Warteschlange** (eine Zeile pro eingereichtem Buch) + die
**App-Einstellungen** (Default-Modellmodus/-Modelle, Default-Seitenlimit) in
SQLite, damit Queue und Einstellungen einen Backend-Neustart überdauern
(Akzeptanzkriterium).

Aufbau analog ``video_summary_queue.py`` (PROJ-41):
- **Best-effort, off-thread** — SQLite-I/O via ``asyncio.to_thread``.
- **Single-writer** — eine frische WAL-Verbindung pro Operation.
- **Live-Index, nicht die Wahrheit** — die erzeugten Nuggets (md/Abbildungen/PDF)
  leben im Hal-Vault; diese Tabelle hält nur den Bearbeitungs-Zustand.

Unterschiede zur Video-Summary-Queue: Quelle ist eine **Datei oder URL**
(``source_type``/``source_ref``), pro Eintrag wird das **Modell** gewählt
(Stufen-Logik), und es gibt einen ``book_hash`` für die Duplikaterkennung (D9).
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

# Status-Werte eines Warteschlangen-Eintrags (entsprechen den UI-Badges).
PENDING, RUNNING, DONE, ERROR = "pending", "running", "done", "error"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS book_nuggets_queue (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner              TEXT,
    source_type        TEXT NOT NULL,          -- 'url' | 'upload'
    source_ref         TEXT NOT NULL,          -- URL oder Pfad der hochgeladenen Datei
    title              TEXT,                    -- nach Verarbeitung gefüllt (best-effort)
    author             TEXT,
    book_hash          TEXT,                    -- Identität für Duplikaterkennung (D9)
    model_mode         TEXT NOT NULL DEFAULT 'staged',  -- 'staged' | 'single'
    model_extract      TEXT NOT NULL DEFAULT 'sonnet',
    model_consolidate  TEXT NOT NULL DEFAULT 'opus',
    page_limit         INTEGER,                 -- optionales Seitenlimit
    cost_estimate      REAL,                    -- best-effort, beim Einreihen berechnet (USD)
    status             TEXT NOT NULL DEFAULT 'pending',
    phase              TEXT,                    -- Anzeige bei running: parsing|analysis|contra|pdf
    result_dir         TEXT,
    result_note_path   TEXT,
    result_pdf_path    TEXT,
    error_message      TEXT,
    session_id         TEXT,
    created_at         TEXT,
    started_at         TEXT,
    finished_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_bnq_status ON book_nuggets_queue(status);
CREATE INDEX IF NOT EXISTS idx_bnq_hash ON book_nuggets_queue(book_hash);

CREATE TABLE IF NOT EXISTS book_nuggets_settings (
    id                         INTEGER PRIMARY KEY CHECK (id = 1),
    default_model_mode         TEXT NOT NULL DEFAULT 'staged',
    default_model_extract      TEXT NOT NULL DEFAULT 'opencode-go/deepseek-v4-flash',
    default_model_consolidate  TEXT NOT NULL DEFAULT 'opencode-go/deepseek-v4-flash',
    default_page_limit         INTEGER
);
"""

# Idempotente Spalten-Migrationen für bestehende DBs (Vorbild ``session_index.py``).
# Heute leer — Platzhalter für künftige additive Migrationen.
_MIGRATIONS: tuple[tuple[str, str], ...] = ()
_SETTINGS_MIGRATION_VERSION = 1


@runtime_checkable
class BookNuggetsRepository(Protocol):
    """Persistenz-Seam für Warteschlange + App-Einstellungen."""

    async def init(self) -> None: ...
    async def list_queue(self) -> list[dict]: ...
    async def add(self, fields: dict) -> dict: ...
    async def get(self, item_id: int) -> dict | None: ...
    async def update(self, item_id: int, **fields) -> None: ...
    async def delete(self, item_id: int) -> None: ...
    async def reset_running(self) -> None: ...
    async def get_settings(self) -> dict: ...
    async def save_settings(self, fields: dict) -> dict: ...
    async def close(self) -> None: ...


class SqliteBookNuggetsRepository:
    """SQLite-Ablage der Queue + Einstellungen (host-nativ, single-writer)."""

    # Spalten, die ``add`` setzen darf (Whitelist gegen Spalten-Injection).
    _INSERTABLE: tuple[str, ...] = (
        "owner", "source_type", "source_ref", "title", "author", "book_hash",
        "model_mode", "model_extract", "model_consolidate", "page_limit",
        "cost_estimate", "created_at",
    )
    # Spalten, die ``update`` schreiben darf.
    _UPDATABLE: frozenset[str] = frozenset({
        "title", "author", "book_hash", "status", "phase", "result_dir",
        "result_note_path", "result_pdf_path", "error_message", "session_id",
        "started_at", "finished_at",
    })
    _SETTINGS_FIELDS: tuple[str, ...] = (
        "default_model_mode", "default_model_extract",
        "default_model_consolidate", "default_page_limit",
    )
    _SETTINGS_DEFAULTS: dict = {
        "default_model_mode": "staged",
        "default_model_extract": "opencode-go/deepseek-v4-flash",
        "default_model_consolidate": "opencode-go/deepseek-v4-flash",
        "default_page_limit": None,
    }

    def __init__(self, db_path: str) -> None:
        self._path = db_path

    # --- Sync-Kern (läuft via to_thread außerhalb der Event-Loop) ----------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_sync(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            for _col, ddl in _MIGRATIONS:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # Spalte existiert bereits.
            conn.execute(
                "INSERT OR IGNORE INTO book_nuggets_settings "
                "(id, default_model_mode, default_model_extract, "
                "default_model_consolidate, default_page_limit) "
                "VALUES (1, ?, ?, ?, ?)",
                (
                    self._SETTINGS_DEFAULTS["default_model_mode"],
                    self._SETTINGS_DEFAULTS["default_model_extract"],
                    self._SETTINGS_DEFAULTS["default_model_consolidate"],
                    self._SETTINGS_DEFAULTS["default_page_limit"],
                ),
            )
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version < _SETTINGS_MIGRATION_VERSION:
                conn.execute(
                    "UPDATE book_nuggets_settings "
                    "SET default_model_extract = ?, default_model_consolidate = ? "
                    "WHERE id = 1 AND default_model_mode = 'staged' "
                    "AND default_model_extract = 'sonnet' "
                    "AND default_model_consolidate = 'opus'",
                    (
                        self._SETTINGS_DEFAULTS["default_model_extract"],
                        self._SETTINGS_DEFAULTS["default_model_consolidate"],
                    ),
                )
                conn.execute(f"PRAGMA user_version = {_SETTINGS_MIGRATION_VERSION}")

    def _list_queue_sync(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM book_nuggets_queue ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def _add_sync(self, fields: dict) -> dict:
        cols = [c for c in self._INSERTABLE if c in fields]
        placeholders = ", ".join("?" for _ in cols)
        values = [fields[c] for c in cols]
        with self._connect() as conn:
            cur = conn.execute(
                f"INSERT INTO book_nuggets_queue ({', '.join(cols)}, status) "
                f"VALUES ({placeholders}, 'pending')",
                values,
            )
            new_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM book_nuggets_queue WHERE id = ?", (new_id,)
            ).fetchone()
        return dict(row)

    def _get_sync(self, item_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM book_nuggets_queue WHERE id = ?", (item_id,)
            ).fetchone()
        return dict(row) if row else None

    def _update_sync(self, item_id: int, fields: dict) -> None:
        cols = [c for c in fields if c in self._UPDATABLE]
        if not cols:
            return
        assignments = ", ".join(f"{c} = ?" for c in cols)
        values = [fields[c] for c in cols]
        values.append(item_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE book_nuggets_queue SET {assignments} WHERE id = ?", values
            )

    def _delete_sync(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM book_nuggets_queue WHERE id = ?", (item_id,))

    def _reset_running_sync(self) -> None:
        # Nach einem Neustart ist keine zugehörige Session mehr steuerbar →
        # laufende Einträge zurück auf pending (kein Verlust der Warteschlange).
        with self._connect() as conn:
            conn.execute(
                "UPDATE book_nuggets_queue SET status = 'pending', session_id = NULL, "
                "phase = NULL, started_at = NULL WHERE status = 'running'"
            )

    def _get_settings_sync(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT default_model_mode, default_model_extract, "
                "default_model_consolidate, default_page_limit "
                "FROM book_nuggets_settings WHERE id = 1"
            ).fetchone()
        if row is None:
            return dict(self._SETTINGS_DEFAULTS)
        return dict(row)

    def _save_settings_sync(self, fields: dict) -> dict:
        merged = {**self._get_settings_sync(), **{
            k: fields[k] for k in self._SETTINGS_FIELDS if k in fields
        }}
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO book_nuggets_settings "
                "(id, default_model_mode, default_model_extract, "
                "default_model_consolidate, default_page_limit) "
                "VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "default_model_mode = excluded.default_model_mode, "
                "default_model_extract = excluded.default_model_extract, "
                "default_model_consolidate = excluded.default_model_consolidate, "
                "default_page_limit = excluded.default_page_limit",
                (
                    merged["default_model_mode"],
                    merged["default_model_extract"],
                    merged["default_model_consolidate"],
                    merged["default_page_limit"],
                ),
            )
        return merged

    # --- Async-Fassade -----------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def list_queue(self) -> list[dict]:
        return await asyncio.to_thread(self._list_queue_sync)

    async def add(self, fields: dict) -> dict:
        return await asyncio.to_thread(self._add_sync, fields)

    async def get(self, item_id: int) -> dict | None:
        return await asyncio.to_thread(self._get_sync, item_id)

    async def update(self, item_id: int, **fields) -> None:
        await asyncio.to_thread(self._update_sync, item_id, fields)

    async def delete(self, item_id: int) -> None:
        await asyncio.to_thread(self._delete_sync, item_id)

    async def reset_running(self) -> None:
        await asyncio.to_thread(self._reset_running_sync)

    async def get_settings(self) -> dict:
        return await asyncio.to_thread(self._get_settings_sync)

    async def save_settings(self, fields: dict) -> dict:
        return await asyncio.to_thread(self._save_settings_sync, fields)

    async def close(self) -> None:
        return None


def build_book_nuggets_repo(settings) -> BookNuggetsRepository:
    """Factory: SQLite-Repo am konfigurierten Pfad."""
    return SqliteBookNuggetsRepository(settings.book_nuggets_db_path)
