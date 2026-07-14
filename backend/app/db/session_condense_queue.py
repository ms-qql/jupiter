"""Session-Kondensierungs-Warteschlange (PROJ-55, Persistenz-Seam).

Spiegelt drei Dinge in SQLite, damit der Wochen-Sweep einen Backend-Neustart
überlebt und idempotent bleibt:

- **Queue** — eine Zeile je alter Session (``session_filename`` ist eindeutig →
  ``INSERT OR IGNORE`` beim Scannen verhindert Doppel-Verarbeitung).
- **Einstellungen** — Wochenplan, Altersschwelle (7 d), Archiv-Löschfrist (30 d),
  Trivial-Mindestlänge, Modell.
- **Läufe** — Kurz-Protokoll je Sweep (geprüft / kondensiert / trivial / archiviert /
  gelöscht / Fehler), damit dem Prozess vertraut werden kann (Akzeptanzkriterium).

Designprinzipien wie ``video_summary_queue.py``: best-effort, off-thread
(``asyncio.to_thread``), single-writer (ein uvicorn-Worker, WAL). Der Vault bleibt
die Wahrheit (Sessions/ ↔ _archiv/); diese Tabelle ist nur schneller Live-Index.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

# Status eines Queue-Eintrags (mechanischer Bearbeitungs-Zustand).
PENDING, RUNNING, DONE, ERROR = "pending", "running", "done", "error"
# Ergebnis-Klassifikation einer verarbeiteten Session (fachlich).
OUTCOME_CONDENSED, OUTCOME_TRIVIAL = "condensed", "trivial"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS session_condense_queue (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    session_filename   TEXT NOT NULL UNIQUE,
    session_id         TEXT,
    project            TEXT,
    session_created    TEXT,
    status             TEXT NOT NULL DEFAULT 'pending',
    outcome            TEXT,
    knowledge_paths    TEXT,
    archived_path      TEXT,
    error_message      TEXT,
    worker_session_id  TEXT,
    created_at         TEXT,
    started_at         TEXT,
    finished_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_scq_status ON session_condense_queue(status);

CREATE TABLE IF NOT EXISTS session_condense_settings (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    schedule          TEXT NOT NULL DEFAULT 'MON 03:00',
    age_days          INTEGER NOT NULL DEFAULT 7,
    retention_days    INTEGER NOT NULL DEFAULT 30,
    min_chars         INTEGER NOT NULL DEFAULT 800,
    engine            TEXT NOT NULL DEFAULT 'opencode',
    model             TEXT NOT NULL DEFAULT 'opencode-go/minimax-m3'
);

CREATE TABLE IF NOT EXISTS session_condense_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    finished_at  TEXT,
    checked      INTEGER NOT NULL DEFAULT 0,
    condensed    INTEGER NOT NULL DEFAULT 0,
    trivial      INTEGER NOT NULL DEFAULT 0,
    archived     INTEGER NOT NULL DEFAULT 0,
    errors       INTEGER NOT NULL DEFAULT 0,
    pruned       INTEGER NOT NULL DEFAULT 0
);
"""

_DEFAULT_SETTINGS = {
    "schedule": "MON 03:00",
    "age_days": 7,
    "retention_days": 30,
    "min_chars": 800,
    "engine": "opencode",
    "model": "opencode-go/minimax-m3",
}

# Claude-Kurz-Aliase — nötig, um beim Nachrüsten der `engine`-Spalte (Migration) für
# eine bestehende Settings-Zeile die passende Engine abzuleiten (altes Verhalten war
# immer Claude).
_CLAUDE_ALIASES: frozenset[str] = frozenset({"haiku", "sonnet", "opus", "fable"})


@runtime_checkable
class SessionCondenseRepository(Protocol):
    """Persistenz-Seam für Queue + Einstellungen + Lauf-Protokoll."""

    async def init(self) -> None: ...
    async def list_queue(self) -> list[dict]: ...
    async def add_candidate(self, fields: dict) -> dict | None: ...
    async def get(self, item_id: int) -> dict | None: ...
    async def update(self, item_id: int, **fields) -> None: ...
    async def delete(self, item_id: int) -> None: ...
    async def reset_running(self) -> None: ...
    async def get_settings(self) -> dict: ...
    async def save_settings(self, fields: dict) -> dict: ...
    async def open_run(self, started_at: str) -> int: ...
    async def bump_run(self, run_id: int, field: str, amount: int = 1) -> None: ...
    async def close_run(self, run_id: int, finished_at: str, pruned: int) -> None: ...
    async def list_runs(self, limit: int = 20) -> list[dict]: ...
    async def close(self) -> None: ...


class SqliteSessionCondenseRepository:
    """SQLite-Ablage (host-nativ, single-writer)."""

    # Whitelist der via ``update`` schreibbaren Queue-Spalten (gegen SQL-Injection
    # über Spaltennamen).
    _UPDATABLE: frozenset[str] = frozenset({
        "session_id", "project", "session_created", "status", "outcome",
        "knowledge_paths", "archived_path", "error_message", "worker_session_id",
        "started_at", "finished_at",
    })
    _SETTINGS_KEYS: frozenset[str] = frozenset(_DEFAULT_SETTINGS)
    _RUN_COUNTERS: frozenset[str] = frozenset({
        "checked", "condensed", "trivial", "archived", "errors",
    })

    def __init__(self, db_path: str) -> None:
        self._path = db_path

    # --- Sync-Kern (via to_thread außerhalb der Event-Loop) ----------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_sync(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_engine_column(conn)
            conn.execute(
                "INSERT OR IGNORE INTO session_condense_settings "
                "(id, schedule, age_days, retention_days, min_chars, engine, model) "
                "VALUES (1, ?, ?, ?, ?, ?, ?)",
                (
                    _DEFAULT_SETTINGS["schedule"], _DEFAULT_SETTINGS["age_days"],
                    _DEFAULT_SETTINGS["retention_days"], _DEFAULT_SETTINGS["min_chars"],
                    _DEFAULT_SETTINGS["engine"], _DEFAULT_SETTINGS["model"],
                ),
            )

    @staticmethod
    def _migrate_engine_column(conn: sqlite3.Connection) -> None:
        """Bestandsdatenbanken (vor der Engine-Wahl) haben keine ``engine``-Spalte.
        Nachrüsten + für die bestehende Zeile die Engine ableiten: ein Claude-Alias-
        Modell → ``claude`` (altes Verhalten unverändert); alles andere → ``opencode``."""
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(session_condense_settings)")}
        if "engine" in cols:
            return
        conn.execute(
            "ALTER TABLE session_condense_settings ADD COLUMN engine "
            "TEXT NOT NULL DEFAULT 'opencode'"
        )
        row = conn.execute(
            "SELECT model FROM session_condense_settings WHERE id = 1"
        ).fetchone()
        if row is not None:
            engine = "claude" if (row["model"] or "") in _CLAUDE_ALIASES else "opencode"
            conn.execute(
                "UPDATE session_condense_settings SET engine = ? WHERE id = 1", (engine,)
            )

    def _list_queue_sync(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM session_condense_queue ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def _add_candidate_sync(self, fields: dict) -> dict | None:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO session_condense_queue "
                "(session_filename, session_id, project, session_created, status, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (
                    fields["session_filename"], fields.get("session_id"),
                    fields.get("project"), fields.get("session_created"),
                    fields.get("created_at"),
                ),
            )
            if cur.rowcount == 0:
                return None  # bereits vorhanden (Idempotenz)
            row = conn.execute(
                "SELECT * FROM session_condense_queue WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return dict(row)

    def _get_sync(self, item_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM session_condense_queue WHERE id = ?", (item_id,)
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
                f"UPDATE session_condense_queue SET {assignments} WHERE id = ?", values
            )

    def _delete_sync(self, item_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM session_condense_queue WHERE id = ?", (item_id,))

    def _reset_running_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE session_condense_queue SET status = 'pending', "
                "worker_session_id = NULL, started_at = NULL WHERE status = 'running'"
            )

    def _get_settings_sync(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT schedule, age_days, retention_days, min_chars, engine, model "
                "FROM session_condense_settings WHERE id = 1"
            ).fetchone()
        return dict(row) if row else dict(_DEFAULT_SETTINGS)

    def _save_settings_sync(self, fields: dict) -> dict:
        current = self._get_settings_sync()
        merged = {**current, **{k: v for k, v in fields.items() if k in self._SETTINGS_KEYS}}
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_condense_settings "
                "(id, schedule, age_days, retention_days, min_chars, engine, model) "
                "VALUES (1, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "schedule = excluded.schedule, age_days = excluded.age_days, "
                "retention_days = excluded.retention_days, min_chars = excluded.min_chars, "
                "engine = excluded.engine, model = excluded.model",
                (
                    merged["schedule"], int(merged["age_days"]), int(merged["retention_days"]),
                    int(merged["min_chars"]), merged["engine"], merged["model"],
                ),
            )
        return merged

    def _open_run_sync(self, started_at: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO session_condense_runs (started_at) VALUES (?)", (started_at,)
            )
            return int(cur.lastrowid)

    def _bump_run_sync(self, run_id: int, field: str, amount: int) -> None:
        if field not in self._RUN_COUNTERS:
            return
        with self._connect() as conn:
            conn.execute(
                f"UPDATE session_condense_runs SET {field} = {field} + ? WHERE id = ?",
                (amount, run_id),
            )

    def _close_run_sync(self, run_id: int, finished_at: str, pruned: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE session_condense_runs SET finished_at = ?, pruned = ? WHERE id = ?",
                (finished_at, pruned, run_id),
            )

    def _list_runs_sync(self, limit: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM session_condense_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Async-Fassade -----------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def list_queue(self) -> list[dict]:
        return await asyncio.to_thread(self._list_queue_sync)

    async def add_candidate(self, fields: dict) -> dict | None:
        return await asyncio.to_thread(self._add_candidate_sync, fields)

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

    async def open_run(self, started_at: str) -> int:
        return await asyncio.to_thread(self._open_run_sync, started_at)

    async def bump_run(self, run_id: int, field: str, amount: int = 1) -> None:
        await asyncio.to_thread(self._bump_run_sync, run_id, field, amount)

    async def close_run(self, run_id: int, finished_at: str, pruned: int) -> None:
        await asyncio.to_thread(self._close_run_sync, run_id, finished_at, pruned)

    async def list_runs(self, limit: int = 20) -> list[dict]:
        return await asyncio.to_thread(self._list_runs_sync, max(1, min(limit, 200)))

    async def close(self) -> None:
        return None


def build_session_condense_repo(settings) -> SessionCondenseRepository:
    """Factory: SQLite-Repo am konfigurierten Pfad."""
    return SqliteSessionCondenseRepository(settings.session_condense_db_path)
