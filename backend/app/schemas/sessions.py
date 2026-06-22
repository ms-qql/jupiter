"""Pydantic-v2-Schemas für die Session-API (PROJ-1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..config import MAX_INPUT_CHARS

ModelName = Literal["haiku", "sonnet", "opus"]
# QA-1: Im MVP nur die sicheren Modi (bypassPermissions/plan gesperrt).
PermissionMode = Literal["default", "acceptEdits"]


class SessionCreate(BaseModel):
    project_path: str = Field(..., min_length=1, description="Arbeitsverzeichnis der Session.")
    initial_prompt: str = Field(
        ..., min_length=1, max_length=MAX_INPUT_CHARS, description="Erster Auftrag an die Session."
    )
    model: ModelName = "sonnet"
    permission_mode: PermissionMode = "default"
    system_prompt_append: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS,
        description="Optionaler System-Prompt-Zusatz (Konstitution #24, PROJ-6).",
    )


class SessionInput(BaseModel):
    text: str = Field(
        ..., min_length=1, max_length=MAX_INPUT_CHARS,
        description="Weitere Eingabe / einzufügender Inhalt.",
    )


class RateLimit(BaseModel):
    status: str | None = None
    resetsAt: int | None = None
    rateLimitType: str | None = None


class SessionRead(BaseModel):
    session_id: str
    owner: str
    project_path: str
    model: str
    permission_mode: str
    status: str
    created_at: str
    last_activity: str
    tokens_used: int
    context_fill_pct: float
    total_cost_usd: float
    num_turns: int
    error: str | None = None
    rate_limit: dict | None = None


class TranscriptEntryRead(BaseModel):
    role: str
    kind: str
    text: str
    ts: str


class SessionDetail(SessionRead):
    transcript: list[TranscriptEntryRead] = []


class TranscriptText(BaseModel):
    text: str
