"""Pydantic-v2-Schemas für die Settings-API (PROJ-5 — Kontext-Schwelle, PROJ-10 — Trust-Policy)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ThresholdSettingRead(BaseModel):
    """Globale Kontext-Schwelle + der erlaubte (geklemmte) Bereich."""

    threshold_pct: int
    min_pct: int
    max_pct: int


class ThresholdSettingPatch(BaseModel):
    """Neue globale Schwelle (%) — wird serverseitig auf [min, max] geklemmt."""

    threshold_pct: int = Field(..., description="Neuer globaler Schwellenwert in % (geklemmt).")


class ClipboardDirRead(BaseModel):
    """Aktueller Clipboard-Ordner (PROJ-11) — absoluter Pfad, innerhalb der Roots."""

    path: str


class ClipboardDirPatch(BaseModel):
    """Neuer Clipboard-Ordner — muss innerhalb der allowed_roots liegen."""

    path: str = Field(..., min_length=1, description="Absoluter Ordnerpfad innerhalb der erlaubten Roots.")


# --- PROJ-51: Engine-/Modellverwaltung ------------------------------------


class EngineSettingsEntry(BaseModel):
    """Bearbeitbarer Engine-Registry-Eintrag für /settings/engines.

    Enthält Konfigurationsfelder wie auth_env/api_base, aber nie Secret-Werte.
    """

    key: str
    label: str
    kind: str = "engine"
    driver: str | None = None
    enabled: bool = True
    available: bool = True
    unavailable_reason: str | None = None
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    auth_env: str | None = None
    api_base: str | None = None
    api_path: str | None = None
    url: str | None = None
    sandbox: str | None = None
    target: str | None = None
    group: str | None = None
    icon: str | None = None
    bin: str | None = None
    argv_template: list[str] = Field(default_factory=list)
    resume_argv_template: list[str] = Field(default_factory=list)
    adapter: str | None = None
    prompt_via: str | None = None
    input_format: str | None = None
    oneshot: bool | None = None


class EngineSettingsRead(BaseModel):
    """Vollständige, bearbeitbare Engine-Konfiguration."""

    engines: list[EngineSettingsEntry]
    source: str
    warning: str | None = None


class EngineSettingsPut(BaseModel):
    """Neue Engine-Konfiguration. Speichern validiert serverseitig und schreibt YAML."""

    engines: list[EngineSettingsEntry]


class EngineSettingsValidationRead(BaseModel):
    """Trockenlauf-Ergebnis für eine Engine-Konfiguration."""

    valid: bool
    warnings: list[str] = Field(default_factory=list)
    engines: list[EngineSettingsEntry] = Field(default_factory=list)


# --- PROJ-10: Trust-Policy --------------------------------------------------

PolicyLevel = Literal["auto-allow", "card", "deny"]


class PolicyRuleMatch(BaseModel):
    """Wonach eine Regel matcht — leere Felder = ‚beliebig'."""

    tool: str | None = None
    role: str | None = None
    skill: str | None = None
    project: str | None = None


class PolicyRuleModel(BaseModel):
    """Eine Policy-Regel: Match → Stufe (+ optionaler Klartext-Grund)."""

    match: PolicyRuleMatch = Field(default_factory=PolicyRuleMatch)
    level: PolicyLevel
    reason: str | None = None


class PhaseGateModel(BaseModel):
    """Phasen-Übergangs-Gate (bypass-fest). Leere transitions = jeder Phasenwechsel."""

    enabled: bool = True
    transitions: list[str] = Field(default_factory=list)


class TrustPolicyRead(BaseModel):
    """Vollständige Policy + Herkunft/Warnung (GET /settings/policy)."""

    rules: list[PolicyRuleModel] = Field(default_factory=list)
    phase_gate: PhaseGateModel = Field(default_factory=PhaseGateModel)
    source: str
    warning: str | None = None


class TrustPolicyPut(BaseModel):
    """Neue Policy (PUT /settings/policy) — serverseitig validiert + live übernommen."""

    rules: list[PolicyRuleModel] = Field(default_factory=list)
    phase_gate: PhaseGateModel = Field(default_factory=PhaseGateModel)


class PolicyPreviewRead(BaseModel):
    """Trockenlauf: welche Stufe/Regel würde greifen (GET /settings/policy/preview)."""

    level: PolicyLevel
    rule: str


# --- PROJ-16: Amok-Watchdog + Limits ---------------------------------------


class WatchdogLimitsPut(BaseModel):
    """Die vier konfigurierbaren Watchdog-Limits (PUT /settings/watchdog).

    Alle Zeit-/Zähler-Felder müssen positiv sein (``gt=0`` → 422 bei Verstoß).
    """

    enabled: bool = True
    token_limit: int = Field(..., gt=0, description="Abgerechnete Tokens je Zeitfenster.")
    token_window_seconds: int = Field(..., gt=0, description="Token-Zeitfenster (s).")
    max_idle_seconds: int = Field(..., gt=0, description="Max. Laufzeit ohne Fortschritt (s).")
    max_repeated_calls: int = Field(..., gt=0, description="Identische Tool-Calls in Folge → Schleife.")
    write_limit: int = Field(..., gt=0, description="Writes je Zeitfenster.")
    write_window_seconds: int = Field(..., gt=0, description="Write-Zeitfenster (s).")


class WatchdogSettingRead(WatchdogLimitsPut):
    """Aktuelle Watchdog-Limits + Herkunft/Warnung (GET /settings/watchdog)."""

    source: str
    warning: str | None = None


# --- PROJ-52: Provider-Budget-Quoten (Schätz-Limits, UI-editierbar) ---------


class ProviderBudgetLimitsPut(BaseModel):
    """Nutzergepflegte Budget-Schnappschüsse für Claude/Codex/OpenCode (PUT /settings/provider-budgets).

    Pro Provider/Fenster ein Prozentwert (``ge=0``, leer = ``None`` = unbekannt → n/v) und
    ein Reset-Zeitpunkt (ISO 8601, leer = automatisch ``jetzt + Fensterdauer``). Die Werte
    werden in der Sidebar genau so angezeigt; abgelaufene Reset-Zeiten werden als
    *veraltet* markiert. Quelle ist Claudes/Codex' eigene Verbrauchsanzeige (z. B. ``/usage``).
    OpenCode wird i. d. R. live via OpenRouter-API abgefragt; manuelle Werte sind Fallback.
    """

    claude_5h_pct: float | None = Field(None, ge=0, description="Claude 5h-Verbrauch in %.")
    claude_5h_reset_at: str | None = Field(None, description="Claude 5h-Reset (ISO 8601).")
    claude_week_pct: float | None = Field(None, ge=0, description="Claude Wochen-Verbrauch in %.")
    claude_week_reset_at: str | None = Field(None, description="Claude Wochen-Reset (ISO 8601).")
    codex_5h_pct: float | None = Field(None, ge=0, description="Codex 5h-Verbrauch in %.")
    codex_5h_reset_at: str | None = Field(None, description="Codex 5h-Reset (ISO 8601).")
    codex_week_pct: float | None = Field(None, ge=0, description="Codex Wochen-Verbrauch in %.")
    codex_week_reset_at: str | None = Field(None, description="Codex Wochen-Reset (ISO 8601).")
    opencode_5h_pct: float | None = Field(None, ge=0, description="OpenCode Guthaben-Verbrauch in %.")
    opencode_5h_reset_at: str | None = Field(None, description="OpenCode Guthaben-Reset (ISO 8601).")
    opencode_week_pct: float | None = Field(None, ge=0, description="OpenCode Wochen-Verbrauch in %.")
    opencode_week_reset_at: str | None = Field(None, description="OpenCode Wochen-Reset (ISO 8601).")


class ProviderBudgetSettingRead(ProviderBudgetLimitsPut):
    """Aktuelle Schnappschüsse + Herkunft/Warnung + Refresh-Intervall (GET /settings/provider-budgets)."""

    source: str
    warning: str | None = None
    refresh_minutes: int


# --- PROJ-27: Verifizierter Liveness-Indikator + Auto-Reanimierung ----------


class LivenessLimitsPut(BaseModel):
    """Die konfigurierbaren Liveness-Schwellen (PUT /settings/liveness).

    Zeit-/Zähler-Felder müssen positiv sein (``gt=0`` → 422); ``backoff_seconds``
    darf 0 sein (kein Backoff).
    """

    enabled_auto_reanimation: bool = Field(
        default=True, description="Globaler Schalter: Auto-Reanimierung an/aus (Indikator + Knopf bleiben)."
    )
    progress_timeout_seconds: int = Field(..., gt=0, description="Kein Fortschritt seit > X s gilt als haengt.")
    tool_in_flight_timeout_seconds: int = Field(
        ..., gt=0,
        description="Hoehere Geduld, solange ein Tool laeuft (langer Build/Test ist kein Haenger).",
    )
    poll_interval_seconds: int = Field(..., gt=0, description="Frequenz des Hintergrund-Auswerters (s).")
    max_auto_attempts: int = Field(..., gt=0, description="Max. automatische Reanimations-Versuche.")
    backoff_seconds: int = Field(..., ge=0, description="Wartezeit zwischen Auto-Versuchen (s).")


class LivenessSettingRead(LivenessLimitsPut):
    """Aktuelle Liveness-Schwellen + Herkunft/Warnung (GET /settings/liveness)."""

    source: str
    warning: str | None = None


# --- PROJ-63: Tmux-Session-Transport (globaler Default + Engine-Overrides) --


class TransportSettingPut(BaseModel):
    """Transport-Wahl (PUT /settings/transports).

    ``default_transport`` gilt für alle Engines ohne eigenen Eintrag in
    ``engine_overrides``. Beide nur ``"direct"`` oder ``"tmux"`` — Default bleibt
    konservativ ``"direct"``, bis der Spike ausgerollt ist.
    """

    default_transport: str = Field(default="direct", description="'direct' oder 'tmux'.")
    engine_overrides: dict[str, str] = Field(
        default_factory=dict, description="Engine-Key -> 'direct'/'tmux', z. B. {'codex': 'tmux'}."
    )


class TransportSettingRead(TransportSettingPut):
    """Aktuelle Transport-Config + Herkunft/Warnung + tmux-Verfügbarkeit (GET /settings/transports)."""

    source: str
    warning: str | None = None
    tmux_available: bool
