"""Pydantic-v2-Schemas für die Projekt-/Smart-Launcher-API (PROJ-9)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ModelName = Literal["haiku", "sonnet", "opus"]


class FeatureSuggestion(BaseModel):
    """Ein Feature aus der INDEX.md + die daraus abgeleitete nächste Arbeit.

    Jede Option (Empfehlung wie Alternative) trägt ihre EIGENEN abgeleiteten Felder,
    damit das Frontend beim Umschalten keine Mapping-Logik duplizieren muss.
    """

    id: str = Field(..., description="Feature-ID, z. B. ``PROJ-9``.")
    number: str = Field(..., description="Reine Feature-Nummer, z. B. ``9`` (für Skill-Argumente).")
    title: str = Field("", description="Feature-Titel (ohne Markdown-Link).")
    status: str = Field("", description="INDEX-Status, z. B. ``Architected``.")
    prio: str | None = Field(default=None, description="Priorität, z. B. ``P1``.")
    phase: str | None = Field(default=None, description="Nächste abc-Phase.")
    skill: str | None = Field(default=None, description="Vorgeschlagener abc-Skill.")
    modell: ModelName | None = Field(default=None, description="Empfohlenes Modell (überschreibbar).")
    initial_prompt: str = Field("", description="Vorbelegter Start-Prompt inkl. Skill-Aufruf.")


class LaunchSuggestion(BaseModel):
    """Mitdenkender Session-Start-Vorschlag, abgeleitet aus features/INDEX.md."""

    project_path: str = Field(..., description="Validierter Projekt-Realpfad.")
    abc_erkannt: bool = Field(..., description="True, wenn ein abc-Workflow erkannt wurde; sonst Freitext-Fallback.")
    hinweis: str | None = Field(default=None, description="Optionaler Hinweis (Fallback/Sonderfall).")
    empfehlung: FeatureSuggestion | None = Field(
        default=None, description="Vorausgewählte Empfehlung (None bei Freitext/alle-deployed)."
    )
    alternativen: list[FeatureSuggestion] = Field(
        default_factory=list, description="Weitere offene Features (für manuelle Auswahl)."
    )
    # Default, den „Vorschlag übernehmen" anwendet. Spiegelt die Empfehlung; im
    # Sonderfall „alle deployed" trägt es den /abc-requirements-Vorschlag (ohne Feature).
    naechste_phase: str | None = Field(default=None, description="Phase des Default-Vorschlags.")
    skill: str | None = Field(default=None, description="Skill des Default-Vorschlags.")
    modell: ModelName | None = Field(default=None, description="Modell des Default-Vorschlags.")
    initial_prompt: str | None = Field(default=None, description="Start-Prompt des Default-Vorschlags.")
