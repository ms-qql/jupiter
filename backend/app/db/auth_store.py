"""Auth-Persistenz (PROJ-25) — Nutzer-Konten + Refresh-Token-Register.

Liegt in **derselben SQLite-Datei** wie der Session-Live-Index
(``session_index_db_path``) — Konten/Tokens sind, anders als der Live-Index,
die **Wahrheit** (kein flüchtiger Spiegel) und müssen jeden Neustart überleben.

Design analog zu :mod:`app.db.session_index`:
- **Single-writer** (ein uvicorn-Worker), pro Operation eine frische Verbindung
  im WAL-Modus; SQLite-I/O läuft via ``asyncio.to_thread`` außerhalb der Loop.
- Idempotentes Schema (``CREATE TABLE IF NOT EXISTS``).

Das Repository ist ein Seam: SQLite heute, Postgres/Neon (Phase 2) später ohne
Bruch der Schnittstelle.
"""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active',
    created_at     TEXT
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id    TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    issued_at   TEXT,
    expires_at  TEXT,
    revoked     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
"""


class SqliteAuthRepository:
    """SQLite-Speicher für Konten + Refresh-Token (host-nativ, single-writer)."""

    def __init__(self, db_path: str) -> None:
        self._path = db_path

    # --- Sync-Kern (via to_thread) ----------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_sync(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _count_users_sync(self) -> int:
        # Tolerant gegenüber noch fehlendem Schema (z. B. Tests ohne Lifespan-Init):
        # keine Tabelle ⇒ keine Nutzer ⇒ anonymer Vor-Bootstrap-Betrieb.
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
            return int(row["n"])
        except sqlite3.OperationalError:
            return 0

    def _create_user_sync(self, row: dict) -> None:
        self._init_sync()  # idempotent — Schema sicherstellen (robust ohne Lifespan)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users (user_id, username, password_hash, status, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row["user_id"], row["username"], row["password_hash"],
                 row.get("status", "active"), row.get("created_at")),
            )

    def _get_user_by_username_sync(self, username: str) -> dict | None:
        try:
            with self._connect() as conn:
                r = conn.execute(
                    "SELECT * FROM users WHERE username = ?", (username,)
                ).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(r) if r else None

    def _get_user_by_id_sync(self, user_id: str) -> dict | None:
        try:
            with self._connect() as conn:
                r = conn.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(r) if r else None

    def _store_refresh_sync(self, row: dict) -> None:
        self._init_sync()  # idempotent — Schema sicherstellen (robust ohne Lifespan)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO refresh_tokens (token_id, user_id, issued_at, expires_at, revoked) "
                "VALUES (?, ?, ?, ?, 0)",
                (row["token_id"], row["user_id"], row["issued_at"], row["expires_at"]),
            )

    def _get_refresh_sync(self, token_id: str) -> dict | None:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT * FROM refresh_tokens WHERE token_id = ?", (token_id,)
            ).fetchone()
        return dict(r) if r else None

    def _revoke_refresh_sync(self, token_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token_id = ?", (token_id,)
            )

    # --- Async-Fassade -----------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    async def count_users(self) -> int:
        return await asyncio.to_thread(self._count_users_sync)

    async def create_user(self, row: dict) -> None:
        """Konto anlegen. Wirft ``sqlite3.IntegrityError`` bei Username-Kollision."""
        await asyncio.to_thread(self._create_user_sync, row)

    async def get_user_by_username(self, username: str) -> dict | None:
        return await asyncio.to_thread(self._get_user_by_username_sync, username)

    async def get_user_by_id(self, user_id: str) -> dict | None:
        return await asyncio.to_thread(self._get_user_by_id_sync, user_id)

    async def store_refresh(self, row: dict) -> None:
        await asyncio.to_thread(self._store_refresh_sync, row)

    async def get_refresh(self, token_id: str) -> dict | None:
        return await asyncio.to_thread(self._get_refresh_sync, token_id)

    async def revoke_refresh(self, token_id: str) -> None:
        await asyncio.to_thread(self._revoke_refresh_sync, token_id)

    async def close(self) -> None:
        return None


def build_auth_repo(settings) -> SqliteAuthRepository:
    """Auth-Persistenz auf derselben SQLite-Datei wie der Session-Live-Index.

    Auth MUSS persistieren (Konten sind die Wahrheit), daher immer SQLite — anders
    als der optional abschaltbare Live-Index."""
    return SqliteAuthRepository(settings.session_index_db_path)
