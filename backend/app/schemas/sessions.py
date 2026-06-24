"""Pydantic-v2-Schemas für die Session-API (PROJ-1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..config import MAX_INPUT_CHARS

ModelName = Literal["haiku", "sonnet", "opus"]
CLAUDE_MODELS: frozenset[str] = frozenset({"haiku", "sonnet", "opus"})
# QA-1: `plan` bleibt gesperrt. `bypassPermissions` ist auf Nutzerwunsch wählbar
# (Vollautonomie) — ACHTUNG: umgeht die Decision-Card-Freigaben (siehe config.py).
PermissionMode = Literal["default", "acceptEdits", "bypassPermissions"]


class SessionCreate(BaseModel):
    project_path: str = Field(..., min_length=1, description="Arbeitsverzeichnis der Session.")
    initial_prompt: str = Field(
        ..., min_length=1, max_length=MAX_INPUT_CHARS, description="Erster Auftrag an die Session."
    )
    model: str = Field(
        default="sonnet",
        description="Modell. Für Claude: haiku/sonnet/opus. Für andere Engines: ein "
        "im Engine-Profil konfigurierter Modellname (serverseitig geprüft).",
    )
    permission_mode: PermissionMode = "default"
    engine: str = Field(
        default="claude",
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Engine-Schlüssel aus der Registry (PROJ-18). Default 'claude'.",
    )
    role: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Optionale Rolle für den Konstitutions-Override (PROJ-6).",
    )
    extra_system_prompt: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS,
        description="Optionaler Zusatz NACH der Konstitution (kann diese nicht entfernen).",
    )
    project_name: str | None = Field(
        default=None, max_length=120,
        description="Sprechendes Projekt-Label für die Gantt-Zeile (PROJ-8); "
        "ohne Angabe wird der Verzeichnis-Basename genutzt.",
    )

    @model_validator(mode="after")
    def _validate_claude_model(self) -> "SessionCreate":
        """Für die Claude-Engine bleibt die strikte Modell-Whitelist (→ 422, PROJ-1-QA).
        Fremde Engines erlauben beliebige Modellnamen; deren Gültigkeit prüft der
        Manager gegen das Engine-Profil (PROJ-18)."""
        if self.engine == "claude" and self.model not in CLAUDE_MODELS:
            raise ValueError(
                f"Unbekanntes Claude-Modell '{self.model}'. Erlaubt: {sorted(CLAUDE_MODELS)}."
            )
        return self


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
    tool_input: dict = {}   # Roh-Input (Frage-Tools: Frontend rendert Auswahlliste)
    triggering_rule: str | None = None  # PROJ-10: auslösende Policy-Regel (Klartext)
    # normal | phase_transition | deny | knowledge_proposal (PROJ-15) | watchdog_pause (PROJ-16).
    card_type: str = "normal"
    # PROJ-15: editierbarer Inhalt eines Wissens-Vorschlags (knowledge_proposal).
    proposal_title: str | None = None
    proposal_body: str | None = None


class DecisionResolve(BaseModel):
    """Body von POST /sessions/{id}/decisions/{decision_id}."""

    decision: Literal["approve", "deny"]
    comment: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS,
        description="Optionaler Kommentar; bei 'deny' reist er als Begründung zu Claude zurück.",
    )
    # PROJ-15: editierter Inhalt eines Wissens-Vorschlags (bei 'approve' = „Editieren").
    edited_title: str | None = Field(default=None, max_length=200)
    edited_body: str | None = Field(default=None, max_length=MAX_INPUT_CHARS)


class SessionRead(BaseModel):
    session_id: str
    owner: str
    project_path: str
    model: str
    permission_mode: str
    engine: str = "claude"  # PROJ-18: welche Engine die Session fährt (Default „claude").
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
    # PROJ-8 — ABC-Workflow-Gantt.
    project_name: str | None = None
    abc_phase: str | None = None
    abc_phase_reached: str | None = None
    abc_feature: str | None = None
    pending_decisions: list[PendingDecisionRead] = []
    # PROJ-27 — verifizierter Liveness-Indikator + Auto-Reanimierung.
    # liveness: "aktiv" (lebt + Fortschritt/legitime Wartestellung) | "hängt" (lebt, kein
    # Fortschritt) | "tot" (beendet/verwaist). liveness_last_result: "läuft_wieder" |
    # "fehlgeschlagen" | None — Rückmeldung des letzten Reanimations-Versuchs.
    liveness: str = "aktiv"
    liveness_auto_attempts: int = 0
    liveness_last_result: str | None = None


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
