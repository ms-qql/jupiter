"""Pydantic-v2-Schemas für die Koordinator-/Dispatch-API (PROJ-22).

Single-User-MVP: kein JWT/RLS (kommt mit PROJ-25); ``owner`` wird serverseitig
gestempelt. Der Live-Index lebt in-memory (SessionManager) + Vault-Recovery — kein
eigenes Persistenz-Schema (vgl. Tech-Design Abschnitt 0).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import MAX_INPUT_CHARS
from .sessions import SessionRead


class CoordinatorPlanRequest(BaseModel):
    project_path: str = Field(..., min_length=1, description="Projekt, dessen features/INDEX.md gelesen wird.")


class DispatchPlanItem(BaseModel):
    """Ein Ticket + die abgeleitete Zuweisung (Rolle/Skill/Engine) + Reihenfolge."""

    ticket_id: str
    title: str
    status: str
    role: str | None = None
    skill: str | None = None
    engine: str = "claude"
    model: str | None = None
    order: int
    dependencies: list[str] = []
    blocked: bool = False
    blocked_reason: str | None = None


class CoordinatorPlan(BaseModel):
    """Verteilungsplan VOR dem Dispatch (Human-in-the-Loop)."""

    project_path: str
    items: list[DispatchPlanItem] = []
    warnings: list[str] = []


class DispatchRequest(BaseModel):
    """Freigegebener Plan → Dispatch. ``items`` sind die nicht-blockierten Posten."""

    project_path: str = Field(..., min_length=1)
    items: list[DispatchPlanItem] = Field(..., min_length=1)


class CoordinatorFleet(BaseModel):
    """Live-Sicht einer Flotte: Koordinator + Kind-Sessions als Gruppe."""

    coordinator: SessionRead
    children: list[SessionRead] = []
    paused: bool = False
    contract_pointer: str | None = None


class PauseRequest(BaseModel):
    paused: bool = Field(..., description="True = Dispatch pausieren, False = fortsetzen.")


class ReassignRequest(BaseModel):
    """Ein Ticket auf andere Rolle/Engine/Modell umverteilen."""

    ticket_id: str = Field(..., min_length=1, max_length=32)
    role: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    engine: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    model: str | None = Field(default=None, max_length=64)


class ContractRequest(BaseModel):
    """API-Vertrag als Vault-Artefakt ablegen/aktualisieren (Pointer-Quelle)."""

    body: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS, description="Vertrags-MD.")
    title: str | None = Field(default=None, max_length=200)
