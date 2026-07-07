"""Peppermint-Dashboard-Persistenz (PROJ-67).

Lokaler SQLite-Spiegel fuer Peppermint-Tickets, Analysezustand und Settings.
Peppermint bleibt Quellsystem; Jupiter speichert nur den robusten Arbeitszustand
fuer Polling, Retry, `abc-frontdesk-check` und internen Notiz-Sync.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Protocol, runtime_checkable

NEW, WAITING, RUNNING, ANALYZED, ERROR = "neu", "wartet", "laeuft", "analysiert", "fehler"
NOTE_PENDING, NOTE_SYNCED, NOTE_ERROR = "ausstehend", "synchronisiert", "fehler"
NOTE_NOT_NEEDED = "nicht_noetig"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS peppermint_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    peppermint_ticket_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    requester_name TEXT,
    requester_email TEXT,
    status TEXT,
    priority TEXT,
    labels_json TEXT NOT NULL DEFAULT '[]',
    ticket_url TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    raw_content TEXT NOT NULL DEFAULT '',
    analysis_status TEXT NOT NULL DEFAULT 'neu',
    note_sync_status TEXT NOT NULL DEFAULT 'nicht_noetig',
    urgency TEXT,
    short_finding TEXT,
    scope_hint TEXT,
    customer_reply_draft TEXT,
    missing_info_guidance TEXT,
    report_text TEXT,
    session_id TEXT,
    error_message TEXT,
    sync_error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    sync_retry_count INTEGER NOT NULL DEFAULT 0,
    owner TEXT,
    peppermint_created_at TEXT,
    peppermint_updated_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    analyzed_at TEXT,
    note_synced_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_peppermint_tickets_analysis_status ON peppermint_tickets(analysis_status);
CREATE INDEX IF NOT EXISTS idx_peppermint_tickets_note_sync_status ON peppermint_tickets(note_sync_status);
CREATE INDEX IF NOT EXISTS idx_peppermint_tickets_status ON peppermint_tickets(status);
CREATE INDEX IF NOT EXISTS idx_peppermint_tickets_created_at ON peppermint_tickets(created_at);

CREATE TABLE IF NOT EXISTS peppermint_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    base_url TEXT NOT NULL DEFAULT 'http://100.125.96.77:3009/',
    active INTEGER NOT NULL DEFAULT 0,
    polling_interval_seconds INTEGER NOT NULL DEFAULT 60,
    webhook_secret TEXT NOT NULL DEFAULT '',
    api_token TEXT NOT NULL DEFAULT '',
    last_poll_at TEXT,
    last_successful_poll_at TEXT,
    last_error TEXT,
    updated_at TEXT
);
"""


@runtime_checkable
class PeppermintRepository(Protocol):
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def reset_running(self) -> None: ...
    async def list_tickets(self, filters: dict | None = None, limit: int = 200) -> list[dict]: ...
    async def get_ticket(self, item_id: int) -> dict | None: ...
    async def get_by_peppermint_id(self, ticket_id: str) -> dict | None: ...
    async def upsert_ticket(self, ticket: dict, now: str, owner: str) -> dict: ...
    async def update_ticket(self, item_id: int, **fields) -> None: ...
    async def next_for_analysis(self) -> dict | None: ...
    async def next_for_note_sync(self) -> dict | None: ...
    async def summary(self) -> dict: ...
    async def get_settings(self) -> dict: ...
    async def save_settings(self, fields: dict) -> dict: ...


class SqlitePeppermintRepository:
    _UPDATABLE = frozenset({
        "title", "description", "requester_name", "requester_email", "status",
        "priority", "labels_json", "ticket_url", "raw_json", "raw_content",
        "analysis_status", "note_sync_status", "urgency", "short_finding",
        "scope_hint", "customer_reply_draft", "missing_info_guidance",
        "report_text", "session_id", "error_message", "sync_error_message",
        "retry_count", "sync_retry_count", "owner", "peppermint_created_at",
        "peppermint_updated_at", "updated_at", "analyzed_at", "note_synced_at",
    })

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
            _ensure_column(conn, "peppermint_settings", "api_token", "TEXT NOT NULL DEFAULT ''")
            conn.execute(
                "INSERT OR IGNORE INTO peppermint_settings "
                "(id, base_url, active, polling_interval_seconds, webhook_secret, api_token) "
                "VALUES (1, 'http://100.125.96.77:3009/', 0, 60, '', '')"
            )

    @staticmethod
    def _dict(row) -> dict | None:
        return dict(row) if row else None

    def _list_tickets_sync(self, filters: dict | None, limit: int) -> list[dict]:
        where, params = [], []
        filters = filters or {}
        for key, col in (
            ("analysis_status", "analysis_status"),
            ("urgency", "urgency"),
            ("status", "status"),
        ):
            val = filters.get(key)
            if val:
                where.append(f"{col} = ?")
                params.append(val)
        q = (filters.get("q") or "").strip()
        if q:
            where.append("(title LIKE ? OR requester_name LIKE ? OR requester_email LIKE ? OR short_finding LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like, like, like])
        sql = "SELECT * FROM peppermint_tickets"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY COALESCE(peppermint_created_at, created_at) DESC, id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 200)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def _get_ticket_sync(self, item_id: int) -> dict | None:
        with self._connect() as conn:
            return self._dict(conn.execute("SELECT * FROM peppermint_tickets WHERE id = ?", (item_id,)).fetchone())

    def _get_by_peppermint_id_sync(self, ticket_id: str) -> dict | None:
        with self._connect() as conn:
            return self._dict(conn.execute("SELECT * FROM peppermint_tickets WHERE peppermint_ticket_id = ?", (ticket_id,)).fetchone())

    def _upsert_ticket_sync(self, ticket: dict, now: str, owner: str) -> dict:
        labels_json = json.dumps(ticket.get("labels") or [], ensure_ascii=False)
        raw_json = json.dumps(ticket.get("raw") or {}, ensure_ascii=False)
        vals = {
            "peppermint_ticket_id": str(ticket["peppermint_ticket_id"]),
            "title": ticket.get("title") or "",
            "description": ticket.get("description") or "",
            "requester_name": ticket.get("requester_name"),
            "requester_email": ticket.get("requester_email"),
            "status": ticket.get("status"),
            "priority": ticket.get("priority"),
            "labels_json": labels_json,
            "ticket_url": ticket.get("ticket_url"),
            "raw_json": raw_json,
            "raw_content": ticket.get("raw_content") or "",
            "owner": owner,
            "peppermint_created_at": ticket.get("peppermint_created_at"),
            "peppermint_updated_at": ticket.get("peppermint_updated_at"),
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO peppermint_tickets (
                    peppermint_ticket_id, title, description, requester_name, requester_email,
                    status, priority, labels_json, ticket_url, raw_json, raw_content, owner,
                    peppermint_created_at, peppermint_updated_at, created_at, updated_at
                ) VALUES (
                    :peppermint_ticket_id, :title, :description, :requester_name, :requester_email,
                    :status, :priority, :labels_json, :ticket_url, :raw_json, :raw_content, :owner,
                    :peppermint_created_at, :peppermint_updated_at, :created_at, :updated_at
                )
                ON CONFLICT(peppermint_ticket_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    requester_name = excluded.requester_name,
                    requester_email = excluded.requester_email,
                    status = excluded.status,
                    priority = excluded.priority,
                    labels_json = excluded.labels_json,
                    ticket_url = excluded.ticket_url,
                    raw_json = excluded.raw_json,
                    raw_content = excluded.raw_content,
                    peppermint_updated_at = excluded.peppermint_updated_at,
                    updated_at = excluded.updated_at
                """,
                vals,
            )
            row = conn.execute(
                "SELECT * FROM peppermint_tickets WHERE peppermint_ticket_id = ?",
                (vals["peppermint_ticket_id"],),
            ).fetchone()
        return dict(row)

    def _update_ticket_sync(self, item_id: int, fields: dict) -> None:
        cols = [c for c in fields if c in self._UPDATABLE]
        if not cols:
            return
        values = [fields[c] for c in cols] + [item_id]
        sql = f"UPDATE peppermint_tickets SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(sql, values)

    def _reset_running_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE peppermint_tickets SET analysis_status = 'wartet', session_id = NULL, "
                "error_message = 'Analyse wurde durch Backend-Neustart unterbrochen.' "
                "WHERE analysis_status = 'laeuft'"
            )

    def _next_sync(self, status: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM peppermint_tickets WHERE analysis_status = ? "
                "ORDER BY created_at ASC, id ASC LIMIT 1",
                (status,),
            ).fetchone()
        return self._dict(row)

    def _next_for_note_sync_sync(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM peppermint_tickets WHERE analysis_status = 'analysiert' "
                "AND note_sync_status IN ('ausstehend', 'fehler') "
                "ORDER BY analyzed_at ASC, id ASC LIMIT 1"
            ).fetchone()
        return self._dict(row)

    def _summary_sync(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM peppermint_tickets").fetchall()
        items = [dict(r) for r in rows]
        return {
            "new_today": sum(1 for r in items if (r.get("created_at") or "")[:10] == _today_prefix()),
            "open_tickets": sum(1 for r in items if (r.get("status") or "").lower() not in {"closed", "done", "completed"}),
            "analyzed_tickets": sum(1 for r in items if r.get("analysis_status") == ANALYZED),
            "failed_analyses": sum(1 for r in items if r.get("analysis_status") == ERROR),
            "urgency_distribution": _counts(r.get("urgency") or "unbekannt" for r in items),
            "finding_distribution": _counts(r.get("short_finding") or "unbekannt" for r in items),
        }

    def _get_settings_sync(self) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM peppermint_settings WHERE id = 1").fetchone()
        return dict(row)

    def _save_settings_sync(self, fields: dict) -> dict:
        allowed = {
            "base_url", "active", "polling_interval_seconds", "webhook_secret",
            "api_token", "last_poll_at", "last_successful_poll_at", "last_error",
            "updated_at",
        }
        cols = [c for c in fields if c in allowed]
        if cols:
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE peppermint_settings SET {', '.join(f'{c} = ?' for c in cols)} WHERE id = 1",
                    [fields[c] for c in cols],
                )
        return self._get_settings_sync()

    async def init(self) -> None: await asyncio.to_thread(self._init_sync)
    async def close(self) -> None: return None
    async def reset_running(self) -> None: await asyncio.to_thread(self._reset_running_sync)
    async def list_tickets(self, filters: dict | None = None, limit: int = 200) -> list[dict]: return await asyncio.to_thread(self._list_tickets_sync, filters, limit)
    async def get_ticket(self, item_id: int) -> dict | None: return await asyncio.to_thread(self._get_ticket_sync, item_id)
    async def get_by_peppermint_id(self, ticket_id: str) -> dict | None: return await asyncio.to_thread(self._get_by_peppermint_id_sync, ticket_id)
    async def upsert_ticket(self, ticket: dict, now: str, owner: str) -> dict: return await asyncio.to_thread(self._upsert_ticket_sync, ticket, now, owner)
    async def update_ticket(self, item_id: int, **fields) -> None: await asyncio.to_thread(self._update_ticket_sync, item_id, fields)
    async def next_for_analysis(self) -> dict | None:
        row = await asyncio.to_thread(self._next_sync, NEW)
        return row or await asyncio.to_thread(self._next_sync, WAITING)
    async def next_for_note_sync(self) -> dict | None: return await asyncio.to_thread(self._next_for_note_sync_sync)
    async def summary(self) -> dict: return await asyncio.to_thread(self._summary_sync)
    async def get_settings(self) -> dict: return await asyncio.to_thread(self._get_settings_sync)
    async def save_settings(self, fields: dict) -> dict: return await asyncio.to_thread(self._save_settings_sync, fields)


def _counts(values) -> dict:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _today_prefix() -> str:
    from datetime import datetime
    return datetime.now().date().isoformat()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def build_peppermint_repo(settings) -> PeppermintRepository:
    return SqlitePeppermintRepository(settings.peppermint_db_path)
