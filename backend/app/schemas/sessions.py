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
    role: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Optionale Rolle für den Konstitutions-Override (PROJ-6).",
    )
    extra_system_prompt: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS,
        description="Optionaler Zusatz NACH der Konstitution (kann diese nicht entfernen).",
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


class PendingDecisionRead(BaseModel):
    """Offene Decision Card (PROJ-4) — die 5-Sekunden-Entscheidung."""

    decision_id: str
    session_id: str
    tool_name: str
    action: str            # „Was"
    excerpt: str           # relevanter Ausschnitt (Befehl/Diff)
    rationale: str         # „Warum"
    context: dict          # „Kontext" (Projekt/Phase)
    created_at: str
    state: str
    resolution: str | None = None


class DecisionResolve(BaseModel):
    """Body von POST /sessions/{id}/decisions/{decision_id}."""

    decision: Literal["approve", "deny"]
    comment: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS,
        description="Optionaler Kommentar; bei 'deny' reist er als Begründung zu Claude zurück.",
    )


class SessionRead(BaseModel):
    session_id: str
    owner: str
    project_path: str
    model: str
    permission_mode: str
    role: str | None = None
    constitution_source: str | None = None
    status: str
    created_at: str
    last_activity: str
    tokens_used: int
    context_fill_pct: float
    context_known: bool = False
    context_fill_threshold_pct: int = 85
    threshold_warning: bool = False
    total_cost_usd: float
    num_turns: int
    error: str | None = None
    rate_limit: dict | None = None
    parent_session_id: str | None = None
    child_session_id: str | None = None
    pending_decisions: list[PendingDecisionRead] = []


class PermissionHookRequest(BaseModel):
    """Payload des Claude-Code PreToolUse-Hooks (intern; extra Felder werden ignoriert)."""

    model_config = {"extra": "ignore"}

    session_id: str
    tool_name: str
    tool_input: dict = {}
    tool_use_id: str | None = None
    cwd: str | None = None


class TranscriptEntryRead(BaseModel):
    role: str
    kind: str
    text: str
    ts: str


class SessionDetail(SessionRead):
    transcript: list[TranscriptEntryRead] = []


class TranscriptText(BaseModel):
    text: str


class ConstitutionRead(BaseModel):
    """Effektive Konstitution (einer Session oder einer Rollen-Vorschau)."""

    role: str | None = None
    source: str
    text: str


class ConstitutionOverview(BaseModel):
    """Globale Konstitution + Liste vorhandener Rollen."""

    global_text: str
    roles: list[str]


# --- Context-Management & Handover (PROJ-5) --------------------------------


class HandoverPreview(BaseModel):
    """Vorschau von POST /sessions/{id}/handover/generate (noch nicht geschrieben)."""

    title: str
    body: str


class ResetRequest(BaseModel):
    """Body von POST /sessions/{id}/reset — Staffelstab in eine frische Kind-Session."""

    seed_context: str = Field(
        ..., min_length=1, max_length=MAX_INPUT_CHARS,
        description="Verdichteter Handover (MD) als Seed-Kontext der Kind-Session.",
    )
    initial_prompt: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS,
        description="Optionaler erster Auftrag; ohne Angabe startet die Übernahme automatisch.",
    )


class ThresholdPatch(BaseModel):
    """Body von PATCH /sessions/{id}/threshold — pro-Session-Override der Kontext-Schwelle."""

    threshold_pct: int | None = Field(
        default=None,
        description="Schwelle in % (wird serverseitig geklemmt). None = globale Schwelle nutzen.",
    )
