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
