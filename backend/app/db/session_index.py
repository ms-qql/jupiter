"""Session-Live-Index (PROJ-14, Persistenz-Seam).

Spiegelt die **wiederherstellbaren Metadaten** der In-Memory-Session-Registry in
SQLite. Bewusst KEIN Transkript, keine Subscriber, keine Live-Prozess-Handles —
nur der Übersichts-Zustand, der einen Backend-Neustart überdauern muss.

Designprinzipien (siehe Tech-Design PROJ-14):
- **Live-Index, nicht die Wahrheit** — die Wahrheit bleibt der Vault.
- **Best-effort** — DB-Fehler dürfen den In-Memory-Pfad nie blockieren; der
  Aufrufer (Manager) fängt Fehler ab und degradiert zu einer Warnung.
- **Hot-Path-schonend** — geschrieben wird nur bei Zustandswechseln, und die
  eigentliche SQLite-I/O läuft via ``asyncio.to_thread`` außerhalb der Event-Loop.
- **Single-writer** — genau ein uvicorn-Worker; pro Operation eine frische
  Verbindung (WAL-Modus), das genügt bei der niedrigen Schreibfrequenz.

Das Repository ist ein abstraktes Seam: SQLite heute, Postgres/Neon (Phase 2)
oder die Vault-Recovery (PROJ-17) können dieselbe Schnittstelle implementieren.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

# Spalten des Live-Index (Reihenfolge = Insert-Reihenfolge). Spiegelt die
# persistierbaren Felder von ``SessionState`` + die OS-PID des Subprozesses.
COLUMNS: tuple[str, ...] = (
    "session_id",
    "owner",
    "project_path",
    "project_name",
    "model",
    "permission_mode",
    "role",
    "status",
    "pid",
    "error",
    "created_at",
    "last_activity",
    "tokens_used",
    "total_cost_usd",
    "parent_session_id",
    "child_session_id",
    "abc_phase",
    "abc_phase_reached",
    "abc_feature",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS session_index (
    session_id        TEXT PRIMARY KEY,
    owner             TEXT,
    project_path      TEXT,
    project_name      TEXT,
    model             TEXT,
    permission_mode   TEXT,
    role              TEXT,
    status            TEXT NOT NULL,
    pid               INTEGER,
    error             TEXT,
    created_at        TEXT,
    last_activity     TEXT,
    tokens_used       INTEGER DEFAULT 0,
    total_cost_usd    REAL DEFAULT 0,
    parent_session_id TEXT,
    child_session_id  TEXT,
    abc_phase         TEXT,
    abc_phase_reached TEXT,
    abc_feature       TEXT
);
CREATE INDEX IF NOT EXISTS idx_session_index_status ON session_index(status);
"""


@runtime_checkable
class SessionIndexRepository(Protocol):
    """Persistenz-Seam für den Session-Live-Index."""

    async def init(self) -> None:
        """Idempotent: Speicher anlegen (Datei/Schema)."""

    async def upsert(self, row: dict) -> None:
        """Eine Session anlegen/aktualisieren (PK = ``session_id``)."""

    async def list_all(self) -> list[dict]:
        """Alle persistierten Sessions (für den Reconcile beim Startup)."""

    async def close(self) -> None:
        """Ressourcen freigeben."""


class NullSessionIndexRepository:
    """No-op-Implementierung — Persistenz aus (reines In-Memory)."""

    async def init(self) -> None:  # noqa: D401 - no-op
        return None

    async def upsert(self, row: dict) -> None:
        return None

    async def list_all(self) -> list[dict]:
        return []

    async def close(self) -> None:
        return None


class SqliteSessionIndexRepository:
    """SQLite-Spiegel des Live-Index (host-nativ, single-writer).

    Pro Operation eine frische Verbindung im WAL-Modus — bei Zustandswechsel-
    Frequenz unkritisch und vermeidet Thread-Affinitäts-Probleme mit
    ``asyncio.to_thread``.
    """

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

    def _upsert_sync(self, row: dict) -> None:
        cols = ", ".join(COLUMNS)
        placeholders = ", ".join("?" for _ in COLUMNS)
        updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "session_id")
        sql = (
            f"INSERT INTO session_index ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(session_id) DO UPDATE SET {updates}"
        )
        values = [row.get(c) for c in COLUMNS]
        with self._connect() as conn:
            conn.execute(sql, values)

    def _list_all_sync(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM session_index ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Async-Fassade -----------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def upsert(self, row: dict) -> None:
        await asyncio.to_thread(self._upsert_sync, row)

    async def list_all(self) -> list[dict]:
        return await asyncio.to_thread(self._list_all_sync)

    async def close(self) -> None:
        # Verbindungen sind kurzlebig (per-Operation) → nichts zu schließen.
        return None


def build_session_index_repo(settings) -> SessionIndexRepository:
    """Factory anhand der Settings: SQLite wenn aktiviert, sonst No-op."""
    if getattr(settings, "session_index_enabled", False):
        return SqliteSessionIndexRepository(settings.session_index_db_path)
    return NullSessionIndexRepository()
