"""Pydantic-v2-Schemas für die Hermes-Profil-Modellwahl (PROJ-83).

Spiegeln exakt die Frontend-Verträge in ``nextjs_app/lib/types.ts``:
``HermesProfileModel`` / ``HermesProfilesRead`` / ``HermesProfileModelPatch``
/ ``HermesProfileSaveResult``.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HermesProfileModel(BaseModel):
    """Ein erkanntes abc-Hermes-Profil (Präfix ``jupiter-``, eigene config.yaml).

    Enthält bewusst KEINE Secret-Werte/Tokens — nur das Modell.
    """

    profile: str
    label: str
    current_model: str | None = None
    provider: str | None = None
    error: str | None = None


class HermesProfilesRead(BaseModel):
    """GET /settings/hermes-profiles — alle erkannten abc-Profile + Modellbestand."""

    models: list[str] = Field(
        default_factory=list,
        description="Auswählbare Modelle aus Jupiters bestehender Modellverwaltung (PROJ-51).",
    )
    profiles: list[HermesProfileModel] = Field(default_factory=list)
    warning: str | None = None


class HermesProfileModelPatch(BaseModel):
    """Ein zu speichernder Profil-Modell-Eintrag (PATCH /settings/hermes-profiles)."""

    profile: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1, description="Modell-Alias, muss in der Modellverwaltung existieren.")


class HermesProfilesPatch(BaseModel):
    """PATCH /settings/hermes-profiles — Body."""

    models: list[HermesProfileModelPatch] = Field(default_factory=list)


class HermesProfileSaveResult(BaseModel):
    """Profilweises Ergebnis des Speicherns — Teilfehler klar benennbar."""

    profile: str
    ok: bool
    error: str | None = None
    saved_model: str | None = None
