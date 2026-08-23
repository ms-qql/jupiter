"""Pydantic-v2-Schemas für die Session-API (PROJ-1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..config import MAX_INPUT_CHARS

ModelName = Literal["haiku", "sonnet", "opus", "fable"]
CLAUDE_MODELS: frozenset[str] = frozenset({"haiku", "sonnet", "opus", "fable"})
# QA-1: `plan` bleibt gesperrt. `bypassPermissions` ist auf Nutzerwunsch wählbar
# (Vollautonomie) — ACHTUNG: umgeht die Decision-Card-Freigaben (siehe config.py).
PermissionMode = Literal["default", "acceptEdits", "bypassPermissions"]


class SessionCreate(BaseModel):
    project_path: str = Field(..., min_length=1, description="Arbeitsverzeichnis der Session.")
    initial_prompt: str = Field(
        ..., max_length=MAX_INPUT_CHARS, description="Erster Auftrag an die Session."
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
    token_savings: Literal["standard", "on", "off"] = Field(
        default="standard",
        description="PROJ-73: globalen Standard verwenden oder für diese Session überschreiben.",
    )
    savings_pilot_task: Literal["code_search", "debugging", "tests", "review", "free_chat"] | None = Field(
        default=None,
        description="PROJ-73: Kennung einer kontrollierten Golden-Task für A/B-Pilotmessung.",
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


class HermesModelOption(BaseModel):
    """Ein im „Neu Hermes"-Dialog wählbares, Hermes-kompatibles Modell (PROJ-85)."""
    engine: str
    model: str
    label: str


class HermesOptionsResponse(BaseModel):
    """GET /sessions/hermes/options — verfügbare Hermes-Modelle (Lese-Pfad)."""
    models: list[HermesModelOption]


class HermesProfileOption(BaseModel):
    """Ein im „Neu Hermes"-Dialog wählbares Hermes-Profil (PROJ-87).

    ``profile`` ist der interne Name (z. B. ``default`` oder ``jupiter-backend``),
    ``label`` die menschenlesbare Bezeichnung. ``engine``/``model`` sind das aus
    der Profil-``config.yaml`` rückübersetzte Standardmodell (``None``, wenn nicht
    auflösbar — der Client lässt das Modell-Dropdown dann ohne Vorauswahl).
    ``error`` markiert ein defektes Profil (nicht startbar, aber sichtbar);
    ``warning`` ist eine strukturelle Hinweismeldung (z. B. fehlendes Default-Home).
    Keine Secrets/Credentials werden gespiegelt.
    """
    profile: str
    label: str
    engine: str | None = None
    model: str | None = None
    error: str | None = None
    warning: str | None = None


class HermesProfilesResponse(BaseModel):
    """GET /sessions/hermes/profiles — alle erkannten Hermes-Profile (PROJ-87).

    ``default`` ist stets enthalten (synthetisch, vorangestellt). ``warning`` ist
    gesetzt, wenn das Profilverzeichnis nicht erreichbar war; die Liste ist dann
    trotzdem nicht leer (mindestens ``default``).
    """
    profiles: list[HermesProfileOption]
    warning: str | None = None


class HermesSessionCreate(BaseModel):
    """POST /sessions/hermes — schmaler Hermes-Startvertrag (PROJ-85/87).

    Titel optional; Projektpfad + Registry-Modellkombination erforderlich. Bypass
    und Token Savings werden serverseitig erzwungen (nie im Payload). ``engine``/
    ``model`` bezeichnen die QUELL-Registry-Kombination; der Manager übersetzt sie
    für genau diese Session in die Hermes-CLI-Argumente. ``profile`` wählt das
    Hermes-Profil (PROJ-87) — Default ``"default"`` für Rückwärtskompatibilität
    beim Rollout zwischen Backend und Frontend.
    """
    # Schmaler Vertrag: unbekannte Felder (z. B. permission_mode, token_savings,
    # initial_prompt) werden abgelehnt, damit ein normaler Client sich nicht als
    # Hermes ausgeben kann (ADR-85-1). Als Klassenattribut gesetzt (Pydantic v2
    # wertet model_config beim Klassenbau aus; eine spätere Zuweisung wirkt nicht).
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None, max_length=120,
        description="Sprechender Titel; ohne Angabe wird der Projektname abgeleitet.",
    )
    project_path: str = Field(..., min_length=1, description="Arbeitsverzeichnis der Session.")
    engine: str = Field(
        ..., pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Engine-Schlüssel aus der Registry (Quelle des Modells).",
    )
    model: str = Field(..., min_length=1, description="Modell aus der gewählten Engine.")
    profile: str = Field(
        default="default", pattern=r"^(default|jupiter-[a-z0-9_-]+)$",
        description="Hermes-Profil (PROJ-87). 'default' oder ein erkanntes jupiter-*-Profil.",
    )

    @model_validator(mode="after")
    def _no_forbidden_fields(self) -> "HermesSessionCreate":
        # Der schmale Vertrag erlaubt KEINE frei setzbaren Sicherheits-/Savings-Werte.
        # Ein Client, der sie mitliefert, bekommt 422 (siehe extra="forbid" oben).
        return self


class SessionRead(BaseModel):
    session_id: str
    owner: str
    project_path: str
    model: str
    permission_mode: str
    engine: str = "claude"  # PROJ-18: welche Engine die Session fährt (Default „claude").
    role: str | None = None
    # PROJ-85: Hermes-Kontext-Snapshot (absolute Werte, nur aus Hermes-Telemetrie).
    # Fehlende Einzelwerte bleiben None (nicht 0); Anzeige-Prozent niemals > 100.
    hermes_resume_ref: str | None = None
    hermes_profile: str = "default"  # PROJ-87: gewähltes Hermes-Profil (Session-Snapshot).
    context_used_tokens: int | None = None
    context_window_tokens: int | None = None
    context_usage_available: bool = False
    constitution_source: str | None = None
    status: str
    created_at: str
    last_activity: str
    tokens_used: int
    # PROJ-19 (#27): kumulative Cache-Tokens — sichtbare Cache-Treffer (read = wiederverwendet).
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    context_fill_pct: float
    context_known: bool = False
    context_fill_threshold_pct: int = 50
    threshold_warning: bool = False
    total_cost_usd: float
    num_turns: int
    error: str | None = None
    rate_limit: dict | None = None
    parent_session_id: str | None = None
    child_session_id: str | None = None
    # PROJ-22 — Multi-Agent-Dispatch (Flotte): Kind → Koordinator + Ticket; der
    # Koordinator führt die Kind-Liste; Vertrag-Pointer wird geteilt.
    parent_coordinator_id: str | None = None
    ticket_id: str | None = None
    child_session_ids: list[str] = []
    contract_pointer: str | None = None
    # M3: am Koordinator eingereihte, noch nicht gestartete Tickets (IDs).
    queued_ticket_ids: list[str] = []
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
    # PROJ-63: "direct" (Default) oder "tmux" — Cockpit-Badge. QA-BUG-3: fehlte hier,
    # obwohl `SessionState.to_read()` es lieferte — Pydantic filtert unbekannte Dict-
    # Schlüssel beim `response_model`-Serialisieren heraus, das Frontend bekam den Wert
    # nie zugestellt.
    transport: str = "direct"
    # PROJ-73: unveränderlicher Savings-Snapshot der Session (keine Promptinhalte/Secrets).
    savings_enabled: bool = False
    savings_source: str = "global"
    savings_profile_version: str | None = None
    savings_modules: list[dict] = Field(default_factory=list)
    savings_degraded: list[str] = Field(default_factory=list)
    savings_provenance: list[dict] = Field(default_factory=list)
    savings_pilot_task: str | None = None
    savings_latency_ms: float | None = None
    savings_pilot_safe: bool | None = None
    # PROJ-79 — Featurezentrierter Koordinator: eine Feature-Ausführung ist selbst eine
    # Koordinator-Session; diese Felder gruppieren die Kind-Sessions im Cockpit.
    is_feature_run: bool = False
    feature_id: str | None = None


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
