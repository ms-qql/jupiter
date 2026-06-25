"""Pydantic-v2-Schemas für die Video-Summary-Micro-App (PROJ-41)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

QueueStatus = Literal["pending", "running", "done", "error"]
WorkerStatus = Literal["idle", "running", "paused"]


class QueueItemRead(BaseModel):
    """Ein Warteschlangen-Eintrag (eine Zeile pro eingereichtem Video)."""

    id: int
    url: str
    owner: str | None = None
    status: QueueStatus
    result_note_path: str | None = None
    result_pdf_path: str | None = None
    error_message: str | None = None
    session_id: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class WorkerStateRead(BaseModel):
    """Laufzeit-Zustand des Workers (für die UI: Leerlauf · Läuft · Pausiert bis …)."""

    status: WorkerStatus
    draining: bool
    paused_until: str | None = None
    next_scheduled_run: str | None = None


class QueueRead(BaseModel):
    """Warteschlange + Worker-Zustand (Polling-Antwort)."""

    items: list[QueueItemRead]
    state: WorkerStateRead


class QueueAddRequest(BaseModel):
    """Eine oder mehrere Video-URLs (Copy-and-Paste-Block erlaubt).

    ``urls`` darf eine Liste sein (Client-vorzerlegt) **oder** ein einzelner String
    (ganzer Paste-Block) — der Server zerlegt zusätzlich an Whitespace/Komma/Semikolon,
    trimmt und dedupliziert."""

    urls: list[str] | str = Field(..., description="URL-Liste oder Paste-Block.")


class QueueAddResult(BaseModel):
    """Ergebnis des Einreihens: was übernommen / abgewiesen / als Duplikat erkannt wurde."""

    added: list[QueueItemRead]
    rejected: list[str]
    duplicates: list[str]
    queue: list[QueueItemRead]


class VideoSummarySettingsRead(BaseModel):
    """Worker-Einstellungen (persistiert, überleben Neustart)."""

    cooldown_minutes: int
    batch_size: int
    schedule: str = Field("", description="Tagesplan HH:MM (24h) oder leer = nur manuell.")


class VideoSummarySettingsPatch(BaseModel):
    """Einstellungen ändern. Felder optional — nur Angegebene werden überschrieben."""

    cooldown_minutes: int | None = Field(None, ge=0, le=1440)
    batch_size: int | None = Field(None, ge=1, le=20)
    schedule: str | None = Field(
        None, description="Tagesplan HH:MM (24h) oder leerer String = kein Plan."
    )
