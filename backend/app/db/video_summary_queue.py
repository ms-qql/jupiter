"""Video-Summary-Warteschlange (PROJ-41, Persistenz-Seam).

Spiegelt die **Warteschlange** (eine Zeile pro eingereichtem Video) + die
**Worker-Einstellungen** (Cooldown, Batch-Größe, Zeitplan) in SQLite, damit Queue
und Einstellungen einen Backend-Neustart überdauern (Akzeptanzkriterium).

Designprinzipien (analog ``session_index.py``):
- **Best-effort, off-thread** — die eigentliche SQLite-I/O läuft via
  ``asyncio.to_thread`` außerhalb der Event-Loop.
- **Single-writer** — genau ein uvicorn-Worker; pro Operation eine frische
  Verbindung (WAL-Modus) bei niedriger Schreibfrequenz.
- **Live-Index, nicht die Wahrheit** — die erzeugten Notizen/PDFs leben im
  Hal-Vault (Dateisystem); diese Tabelle hält nur den Bearbeitungs-Zustand.

Das Repository ist ein abstraktes Seam: SQLite heute, Postgres (Phase 2) kann
dieselbe Schnittstelle implementieren.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

# Status-Werte eines Warteschlangen-Eintrags (entsprechen den UI-Badges).
PENDING, RUNNING, DONE, ERROR = "pending", "running", "done", "error"

# Spalten der Queue-Tabelle (Reihenfolge = Insert-Reihenfolge).
QUEUE_COLUMNS: tuple[str, ...] = (
    "id",
    "url",
    "owner",
    "status",
    "result_note_path",
    "result_pdf_path",
    "error_message",
    "session_id",
    "created_at",
    "started_at",
    "finished_at",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS video_summary_queue (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    url               TEXT NOT NULL,
    owner             TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    result_note_path  TEXT,
    result_pdf_path   TEXT,
    error_message     TEXT,
    session_id        TEXT,
    created_at        TEXT,
    started_at        TEXT,
    finished_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_vsq_status ON video_summary_queue(status);

CREATE TABLE IF NOT EXISTS video_summary_settings (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    cooldown_minutes  INTEGER NOT NULL DEFAULT 30,
    batch_size        INTEGER NOT NULL DEFAULT 4,
    schedule          TEXT NOT NULL DEFAULT ''
);
"""


@runtime_checkable
class VideoSummaryRepository(Protocol):
    """Persistenz-Seam für Warteschlange + Worker-Einstellungen."""

    async def init(self) -> None: ...
    async def list_queue(self) -> list[dict]: ...
    async def add(self, url: str, owner: str, created_at: str) -> dict: ...
    async def get(self, item_id: int) -> dict | None: ...
    async def update(self, item_id: int, **fields) -> None: ...
    async def delete(self, item_id: int) -> None: ...
    async def reset_running(self) -> None: ...
    async def get_settings(self) -> dict: ...
    async def save_settings(
        self, cooldown_minutes: int, batch_size: int, schedule: str
    ) -> dict: ...
    async def close(self) -> None: ...


class SqliteVideoSummaryRepository:
    """SQLite-Ablage der Queue + Einstellungen (host-nativ, single-writer)."""

    # Nur diese Felder dürfen via ``update`` geschrieben werden (Whitelist gegen
    # SQL-Injection über Spaltennamen).
    _UPDATABLE: frozenset[str] = frozenset(
        {
            "url",
            "owner",
            "status",
            "result_note_path",
            "result_pdf_path",
            "error_message",
            "session_id",
            "started_at",
            "finished_at",
        }
    )

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
            # Default-Einstellungszeile sicherstellen (idempotent).
            conn.execute(
                "INSERT OR IGNORE INTO video_summary_settings "
                "(id, cooldown_minutes, batch_size, schedule) VALUES (1, 30, 4, '')"
            )

    def _list_queue_sync(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM video_summary_queue ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def _add_sync(self, url: str, owner: str, created_at: str) -> dict:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO video_summary_queue (url, owner, status, created_at) "
                "VALUES (?, ?, 'pending', ?)",
                (url, owner, created_at),
            )
            new_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM video_summary_queue WHERE id = ?", (new_id,)
            ).fetchone()
        return dict(row)

    def _get_sync(self, item_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM video_summary_queue WHERE id = ?", (item_id,)
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
                f"UPDATE video_summary_queue SET {assignments} WHERE id = ?", values
            )

    def _delete_sync(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM video_summary_queue WHERE id = ?", (item_id,))

    def _reset_running_sync(self) -> None:
        # Nach einem Neustart ist keine zugehörige Session mehr steuerbar →
        # laufende Einträge zurück auf pending (kein Verlust der Warteschlange).
        with self._connect() as conn:
            conn.execute(
                "UPDATE video_summary_queue SET status = 'pending', session_id = NULL, "
                "started_at = NULL WHERE status = 'running'"
            )

    def _get_settings_sync(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cooldown_minutes, batch_size, schedule "
                "FROM video_summary_settings WHERE id = 1"
            ).fetchone()
        if row is None:
            return {"cooldown_minutes": 30, "batch_size": 4, "schedule": ""}
        return dict(row)

    def _save_settings_sync(
        self, cooldown_minutes: int, batch_size: int, schedule: str
    ) -> dict:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO video_summary_settings (id, cooldown_minutes, batch_size, schedule) "
                "VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "cooldown_minutes = excluded.cooldown_minutes, "
                "batch_size = excluded.batch_size, schedule = excluded.schedule",
                (cooldown_minutes, batch_size, schedule),
            )
        return {
            "cooldown_minutes": cooldown_minutes,
            "batch_size": batch_size,
            "schedule": schedule,
        }

    # --- Async-Fassade -----------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def list_queue(self) -> list[dict]:
        return await asyncio.to_thread(self._list_queue_sync)

    async def add(self, url: str, owner: str, created_at: str) -> dict:
        return await asyncio.to_thread(self._add_sync, url, owner, created_at)

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

    async def save_settings(
        self, cooldown_minutes: int, batch_size: int, schedule: str
    ) -> dict:
        return await asyncio.to_thread(
            self._save_settings_sync, cooldown_minutes, batch_size, schedule
        )

    async def close(self) -> None:
        return None


def build_video_summary_repo(settings) -> VideoSummaryRepository:
    """Factory: SQLite-Repo am konfigurierten Pfad."""
    return SqliteVideoSummaryRepository(settings.video_summary_db_path)
