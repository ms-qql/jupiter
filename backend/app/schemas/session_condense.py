"""Pydantic-v2-Schemas für die Session-Kondensierung (PROJ-55)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

QueueStatus = Literal["pending", "running", "done", "error"]
Outcome = Literal["condensed", "trivial"]
WorkerStatus = Literal["idle", "draining", "running"]


class QueueItemRead(BaseModel):
    """Ein Warteschlangen-Eintrag (eine Zeile je alter Session)."""

    id: int
    session_filename: str
    session_id: str | None = None
    project: str | None = None
    session_created: str | None = None
    status: QueueStatus
    outcome: Outcome | None = None
    knowledge_paths: str | None = None  # JSON-Array der geschriebenen Notiz-Pfade
    archived_path: str | None = None
    error_message: str | None = None
    worker_session_id: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class WorkerStateRead(BaseModel):
    """Laufzeit-Zustand des Workers (für die UI: Leerlauf · Läuft · nächster Plan-Lauf)."""

    status: WorkerStatus
    draining: bool
    current_id: int | None = None
    next_scheduled_run: str | None = None


class QueueRead(BaseModel):
    """Warteschlange + Worker-Zustand (Polling-Antwort)."""

    items: list[QueueItemRead]
    state: WorkerStateRead


class RunRead(BaseModel):
    """Ein Lauf-Protokoll (Kurzbilanz eines Sweeps)."""

    id: int
    started_at: str | None = None
    finished_at: str | None = None
    checked: int = 0
    condensed: int = 0
    trivial: int = 0
    archived: int = 0
    errors: int = 0
    pruned: int = 0


class SettingsRead(BaseModel):
    """Sweep-Einstellungen (persistiert)."""

    schedule: str
    age_days: int
    retention_days: int
    min_chars: int
    engine: str
    model: str


class SettingsPatch(BaseModel):
    """Teil-Update der Einstellungen (nur gesetzte Felder werden übernommen)."""

    schedule: str | None = Field(default=None, description="Wochenplan 'DOW HH:MM' oder leer.")
    age_days: int | None = Field(default=None, ge=0, le=3650)
    retention_days: int | None = Field(default=None, ge=0, le=3650)
    min_chars: int | None = Field(default=None, ge=0, le=100_000)
    engine: str | None = None
    model: str | None = None
