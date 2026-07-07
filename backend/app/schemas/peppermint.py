"""Pydantic-v2-Schemas fuer das Peppermint Dashboard (PROJ-67)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AnalysisStatus = Literal["neu", "wartet", "laeuft", "analysiert", "fehler"]
NoteSyncStatus = Literal["nicht_noetig", "ausstehend", "synchronisiert", "fehler"]


class PeppermintSettingsRead(BaseModel):
    base_url: str
    active: bool
    polling_interval_seconds: int
    webhook_secret_set: bool
    login_configured: bool
    token_configured: bool
    last_poll_at: str | None = None
    last_successful_poll_at: str | None = None
    last_error: str | None = None


class PeppermintSettingsPatch(BaseModel):
    base_url: str | None = Field(None, min_length=8, max_length=500)
    active: bool | None = None
    polling_interval_seconds: int | None = Field(None, ge=15, le=3600)
    webhook_secret: str | None = Field(None, max_length=500)
    api_token: str | None = Field(None, max_length=4000)


class PeppermintStatusRead(BaseModel):
    active: bool
    worker_status: str
    current_ticket_id: int | None = None
    last_poll_at: str | None = None
    last_successful_poll_at: str | None = None
    last_error: str | None = None
    login_configured: bool
    token_configured: bool


class PeppermintTicketRead(BaseModel):
    id: int
    peppermint_ticket_id: str
    title: str
    description: str = ""
    requester_name: str | None = None
    requester_email: str | None = None
    status: str | None = None
    priority: str | None = None
    ticket_url: str | None = None
    analysis_status: AnalysisStatus
    note_sync_status: NoteSyncStatus
    urgency: str | None = None
    short_finding: str | None = None
    scope_hint: str | None = None
    customer_reply_draft: str | None = None
    missing_info_guidance: str | None = None
    report_text: str | None = None
    session_id: str | None = None
    error_message: str | None = None
    sync_error_message: str | None = None
    retry_count: int = 0
    sync_retry_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None
    peppermint_created_at: str | None = None
    peppermint_updated_at: str | None = None
    analyzed_at: str | None = None
    note_synced_at: str | None = None


class PeppermintTicketListRead(BaseModel):
    items: list[PeppermintTicketRead]


class PeppermintSummaryRead(BaseModel):
    new_today: int
    open_tickets: int
    analyzed_tickets: int
    failed_analyses: int
    urgency_distribution: dict[str, int]
    finding_distribution: dict[str, int]


class PeppermintWebhookEvent(BaseModel):
    ticket_id: str | int | None = None
    id: str | int | None = None
    ticket: dict | None = None
    event: str | None = None
    type: str | None = None
