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
from datetime import datetime, timezone
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
    # PROJ-18/19: welche Engine die Session fuhr. Der Manager emittierte das Feld
    # bereits, ohne dass es persistiert wurde → vor PROJ-19 ging es bei Rehydrierung
    # verloren (Default „claude"). Jetzt persistiert, u. a. fürs Kosten-Aggregat (#28).
    "engine",
    "permission_mode",
    "role",
    "status",
    "pid",
    "error",
    "created_at",
    "last_activity",
    "tokens_used",
    # PROJ-19 (#27): kumulative Cache-Tokens (Sichtbarkeit der Treffer übers Dashboard).
    "cache_read_tokens",
    "cache_creation_tokens",
    "total_cost_usd",
    "parent_session_id",
    "child_session_id",
    "abc_phase",
    "abc_phase_reached",
    "abc_feature",
    # PROJ-17: Recovery — Strang aus der Recovery-Ansicht verworfen (Vault-Log bleibt).
    "recovery_dismissed",
    # PROJ-33: Zeitpunkt eines geordneten Drains (Shutdown). Gesetzt = bewusst beendet
    # → Auto-Resume nach Neustart; NULL = Crash/unerwartet → kein Auto-Resume.
    "drained_at",
    # PROJ-56: engine-eigene Wiederaufnahme-ID (z. B. Codex' thread_id). Klein, selten
    # geändert → passt in den Metadaten-Upsert; überlebt so den Backend-Restart.
    "resume_id",
    # PROJ-56: Ergebnis der letzten Kontext-Wiederherstellung ("mit Kontext" /
    # "kontextlos (Grund)") — rein informativ fürs Cockpit.
    "context_status",
    # PROJ-63: Transport-Metadaten. "transport" ist "direct" (Default, unverändertes
    # Verhalten) oder "tmux". Die übrigen Felder sind nur bei "tmux" gefüllt.
    "transport",
    "tmux_session",
    "tmux_pane",
    "tmux_capture_cursor",
    "transport_status",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS session_index (
    session_id        TEXT PRIMARY KEY,
    owner             TEXT,
    project_path      TEXT,
    project_name      TEXT,
    model             TEXT,
    engine            TEXT DEFAULT 'claude',
    permission_mode   TEXT,
    role              TEXT,
    status            TEXT NOT NULL,
    pid               INTEGER,
    error             TEXT,
    created_at        TEXT,
    last_activity     TEXT,
    tokens_used       INTEGER DEFAULT 0,
    cache_read_tokens     INTEGER DEFAULT 0,
    cache_creation_tokens INTEGER DEFAULT 0,
    total_cost_usd    REAL DEFAULT 0,
    parent_session_id TEXT,
    child_session_id  TEXT,
    abc_phase         TEXT,
    abc_phase_reached TEXT,
    abc_feature       TEXT,
    recovery_dismissed INTEGER DEFAULT 0,
    drained_at         TEXT,
    resume_id          TEXT,
    context_status     TEXT,
    transport            TEXT DEFAULT 'direct',
    tmux_session          TEXT,
    tmux_pane             TEXT,
    tmux_capture_cursor   INTEGER DEFAULT 0,
    transport_status      TEXT
);
CREATE INDEX IF NOT EXISTS idx_session_index_status ON session_index(status);

-- PROJ-56: Kanonischer Konversationsverlauf für Engines OHNE serverseitiges Resume
-- (OpenAI/OpenRouter, z. B. GLM 5.2). Getrennt vom heißen Metadaten-Upsert, weil
-- der Verlauf groß werden kann und nur bei Turn-Abschluss geschrieben wird. Wird beim
-- Treiber-Neubau zurückgespielt, damit der Agent den Faden behält. Bewusst getrennt
-- vom Vault-Log (Historie, ggf. mit Reload-Dopplungen) — dies ist die Replay-Kopie.
CREATE TABLE IF NOT EXISTS session_context (
    session_id  TEXT PRIMARY KEY,
    messages    TEXT NOT NULL,
    updated_at  TEXT
);

-- PROJ-66: vollständiges UI-Transkript (TranscriptEntry-Liste als JSON) je Session,
-- fuer ALLE Nicht-Claude-Engines (Oneshot-CLIs wie Codex/OpenCode, aber auch die
-- direkten OpenAI/OpenRouter-Treiber). Anders als session_context (Provider-Roh-
-- format, nur fuer Treiber ohne Self-Resume) ist dies das UI-Anzeigeformat und wird
-- unconditional bei jedem Persist-Zyklus als kompletter Blob ueberschrieben, damit
-- rehydrate() nach einem Neustart nicht mit einem leeren Transkript startet.
CREATE TABLE IF NOT EXISTS session_transcript (
    session_id  TEXT PRIMARY KEY,
    entries     TEXT NOT NULL,
    updated_at  TEXT
);
"""

# Nachzügler-Spalten (für bereits bestehende DBs ohne diese Spalte). ``CREATE TABLE
# IF NOT EXISTS`` legt sie bei einer alten Datei nicht nach → leichtgewichtige
# host-native Migration via ``ALTER TABLE … ADD COLUMN`` (idempotent).
_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("recovery_dismissed", "INTEGER DEFAULT 0"),
    ("drained_at", "TEXT"),  # PROJ-33
    ("engine", "TEXT DEFAULT 'claude'"),  # PROJ-19 (#28)
    ("cache_read_tokens", "INTEGER DEFAULT 0"),  # PROJ-19 (#27)
    ("cache_creation_tokens", "INTEGER DEFAULT 0"),  # PROJ-19 (#27)
    ("resume_id", "TEXT"),  # PROJ-56
    ("context_status", "TEXT"),  # PROJ-56
    ("transport", "TEXT DEFAULT 'direct'"),  # PROJ-63
    ("tmux_session", "TEXT"),  # PROJ-63
    ("tmux_pane", "TEXT"),  # PROJ-63
    ("tmux_capture_cursor", "INTEGER DEFAULT 0"),  # PROJ-63
    ("transport_status", "TEXT"),  # PROJ-63
)


@runtime_checkable
class SessionIndexRepository(Protocol):
    """Persistenz-Seam für den Session-Live-Index."""

    async def init(self) -> None:
        """Idempotent: Speicher anlegen (Datei/Schema)."""

    async def upsert(self, row: dict) -> None:
        """Eine Session anlegen/aktualisieren (PK = ``session_id``)."""

    async def list_all(self) -> list[dict]:
        """Alle persistierten Sessions (für den Reconcile beim Startup)."""

    async def delete(self, session_id: str) -> None:
        """Eine Session aus dem Live-Index entfernen (PROJ-21). Idempotent —
        eine unbekannte ID ist kein Fehler. Das Vault-Log bleibt unberührt.
        PROJ-56: entfernt auch den zugehörigen Konversationsverlauf."""

    async def save_context(self, session_id: str, messages_json: str) -> None:
        """PROJ-56: Kanonischen Konversationsverlauf (JSON) speichern/ersetzen."""

    async def load_context(self, session_id: str) -> str | None:
        """PROJ-56: Gespeicherten Konversationsverlauf (JSON) lesen; None wenn keiner."""

    async def save_transcript(self, session_id: str, entries_json: str) -> None:
        """PROJ-66: Vollständiges UI-Transkript (JSON) speichern/ersetzen."""

    async def load_transcript(self, session_id: str) -> str | None:
        """PROJ-66: Gespeichertes UI-Transkript (JSON) lesen; None wenn keines."""

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

    async def delete(self, session_id: str) -> None:  # noqa: D401 - no-op
        return None

    async def save_context(self, session_id: str, messages_json: str) -> None:
        return None

    async def load_context(self, session_id: str) -> str | None:
        return None

    async def save_transcript(self, session_id: str, entries_json: str) -> None:
        return None

    async def load_transcript(self, session_id: str) -> str | None:
        return None

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
            existing = {r["name"] for r in conn.execute("PRAGMA table_info(session_index)")}
            for col, ddl in _MIGRATIONS:
                if col not in existing:
                    conn.execute(f"ALTER TABLE session_index ADD COLUMN {col} {ddl}")

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

    def _delete_sync(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM session_index WHERE session_id = ?", (session_id,)
            )
            # PROJ-56: Verlauf mitentfernen (kein verwaister Kontext nach Löschung).
            conn.execute(
                "DELETE FROM session_context WHERE session_id = ?", (session_id,)
            )
            # PROJ-66: UI-Transkript mitentfernen (kein verwaister Datenmüll nach Löschung).
            conn.execute(
                "DELETE FROM session_transcript WHERE session_id = ?", (session_id,)
            )

    def _save_context_sync(self, session_id: str, messages_json: str, updated_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_context (session_id, messages, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET "
                "messages=excluded.messages, updated_at=excluded.updated_at",
                (session_id, messages_json, updated_at),
            )

    def _load_context_sync(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT messages FROM session_context WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row["messages"] if row else None

    def _save_transcript_sync(self, session_id: str, entries_json: str, updated_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO session_transcript (session_id, entries, updated_at) "
                "VALUES (?, ?, ?) ON CONFLICT(session_id) DO UPDATE SET "
                "entries=excluded.entries, updated_at=excluded.updated_at",
                (session_id, entries_json, updated_at),
            )

    def _load_transcript_sync(self, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entries FROM session_transcript WHERE session_id = ?", (session_id,)
            ).fetchone()
        return row["entries"] if row else None

    # --- Async-Fassade -----------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def upsert(self, row: dict) -> None:
        await asyncio.to_thread(self._upsert_sync, row)

    async def list_all(self) -> list[dict]:
        return await asyncio.to_thread(self._list_all_sync)

    async def delete(self, session_id: str) -> None:
        await asyncio.to_thread(self._delete_sync, session_id)

    async def save_context(self, session_id: str, messages_json: str) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._save_context_sync, session_id, messages_json, updated_at)

    async def load_context(self, session_id: str) -> str | None:
        return await asyncio.to_thread(self._load_context_sync, session_id)

    async def save_transcript(self, session_id: str, entries_json: str) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        await asyncio.to_thread(self._save_transcript_sync, session_id, entries_json, updated_at)

    async def load_transcript(self, session_id: str) -> str | None:
        return await asyncio.to_thread(self._load_transcript_sync, session_id)

    async def close(self) -> None:
        # Verbindungen sind kurzlebig (per-Operation) → nichts zu schließen.
        return None


def build_session_index_repo(settings) -> SessionIndexRepository:
    """Factory anhand der Settings: SQLite wenn aktiviert, sonst No-op."""
    if getattr(settings, "session_index_enabled", False):
        return SqliteSessionIndexRepository(settings.session_index_db_path)
    return NullSessionIndexRepository()
