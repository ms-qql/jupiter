"""Pydantic-v2-Schemas für die Hermes-Profil-Modellwahl (PROJ-83 Rework).

Spiegeln exakt die Frontend-Verträge in ``nextjs_app/lib/types.ts``:
``HermesProfileModel`` / ``HermesProfilesRead`` / ``HermesProfileModelPatch``
/ ``HermesProfileSaveResult``. Die Anzeige arbeitet mit dem Engine/Modell-
Vokabular aus ``GET /engines`` (``engine`` + ``model``), nicht mit den Rohwerten
der ``config.yaml`` (``provider`` + ``default``). Enthält bewusst KEINE
Secret-Werte/Tokens.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class HermesProfileModel(BaseModel):
    """Ein erkanntes abc-Hermes-Profil (Präfix ``jupiter-``, eigene config.yaml).

    Enthält bewusst KEINE Secret-Werte/Tokens — nur Engine/Modell.
    """

    profile: str
    label: str
    engine: str | None = None
    model: str | None = None
    provider: str | None = None
    default: str | None = None
    error: str | None = None


class HermesProfilesRead(BaseModel):
    """GET /settings/hermes-profiles — alle erkannten abc-Profile (+ Warnung).

    Der Modell-/Engine-Bestand kommt aus ``GET /engines`` (PROJ-18/51), nicht
    aus diesem Endpunkt.
    """

    profiles: list[HermesProfileModel] = Field(default_factory=list)
    warning: str | None = None


class HermesProfileModelPatch(BaseModel):
    """Ein zu speichernder Profil-Eintrag (PATCH /settings/hermes-profiles)."""

    profile: str = Field(..., min_length=1)
    engine: str = Field(
        ...,
        pattern="^(claude|codex|opencode)$",
        description="Erlaubter Engine-Key: claude | codex | opencode.",
    )
    model: str = Field(..., min_length=1, description="Modell dieser Engine aus GET /engines.")


class HermesProfilesPatch(BaseModel):
    """PATCH /settings/hermes-profiles — Body."""

    profiles: list[HermesProfileModelPatch] = Field(default_factory=list)


class HermesProfileSaveResult(BaseModel):
    """Profilweises Ergebnis des Speicherns — Teilfehler klar benennbar."""

    profile: str
    ok: bool
    error: str | None = None
    # Bei ok=true: der vollständig zurückübersetzte Profileintrag (neuer Stand).
    entry: HermesProfileModel | None = None
