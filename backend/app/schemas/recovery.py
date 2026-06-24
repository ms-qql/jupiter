"""Pydantic-v2-Schemas für die Recovery-API (PROJ-17).

Recovery ist eine read-only Sicht über den Live-Index (PROJ-14) + den Vault
(PROJ-2/PROJ-5): nach einem Reboot/Crash wiederherstellbare Stränge, plus das
Wiederherstellen (Kind-Session mit Seed) bzw. Verwerfen (Vault-Eintrag bleibt).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..config import MAX_INPUT_CHARS

# Quelle des „Hier ging's weiter"-Vorschlags (stärkste zuerst):
# kuratierter Handover > Auto-Session-Log > nur Index-Metadaten.
RecoverySource = Literal["handover", "log", "incomplete"]


class RecoveryCandidate(BaseModel):
    """Ein wiederherstellbarer Strang (verwaist + ohne Nachfolger)."""

    session_id: str = Field(..., description="Verwaiste Vorgänger-Session (Parent).")
    project_path: str
    project_name: str | None = None
    abc_phase: str | None = Field(default=None, description="Weiteste bekannte ABC-Phase.")
    last_handover_at: str | None = Field(
        default=None, description="Zeitpunkt des jüngsten Handovers/letzter Aktivität (ISO)."
    )
    source: RecoverySource
    suggestion: str = Field(..., description="Hier-gehts-weiter: verdichtete offene Punkte.")
    restore_blocked: bool = Field(default=False, description="z. B. Projektpfad existiert nicht mehr.")
    blocked_reason: str | None = None
    warning: str | None = Field(default=None, description="z. B. beschädigter/halber Handover.")


class RecoveryList(BaseModel):
    candidates: list[RecoveryCandidate]


class RecoveryRestoreRequest(BaseModel):
    initial_prompt: str | None = Field(
        default=None,
        max_length=MAX_INPUT_CHARS,
        description="Optionaler Start-Prompt der Nachfolge-Session (sonst Default-Reset-Prompt).",
    )
