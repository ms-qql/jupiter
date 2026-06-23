"""Pydantic-v2-Schemas für die Settings-API (PROJ-5 — Kontext-Schwelle)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ThresholdSettingRead(BaseModel):
    """Globale Kontext-Schwelle + der erlaubte (geklemmte) Bereich."""

    threshold_pct: int
    min_pct: int
    max_pct: int


class ThresholdSettingPatch(BaseModel):
    """Neue globale Schwelle (%) — wird serverseitig auf [min, max] geklemmt."""

    threshold_pct: int = Field(..., description="Neuer globaler Schwellenwert in % (geklemmt).")
