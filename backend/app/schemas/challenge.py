"""Pydantic-v2-Schemas für die Cross-Agent-Review-/Challenge-API (PROJ-23).

Single-User-MVP: kein JWT/RLS (kommt mit PROJ-25); ``owner`` wird serverseitig
gestempelt. Kein eigenes Persistenz-Schema — Review = Reviewer-Session + In-memory-
Objekt, Audit-Spur im Vault (vgl. ChallengeService).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["hoch", "mittel", "niedrig"]
FindingAction = Literal["übernehmen", "verwerfen", "zurück"]


class ChallengeRequest(BaseModel):
    """Body von POST /sessions/{id}/challenge — eine Challenge auf einem Artefakt starten."""

    artifact_pointer: str = Field(
        ..., min_length=1, max_length=1024,
        description="Vault-relativer Pointer aufs Artefakt, z. B. 'Agentic OS/Jupiter/"
        "Knowledge/contracts/PROJ-22.md' oder mit Zeilenbereich '…#L10-30'.",
    )
    reviewer_engine: str | None = Field(
        default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="Optionale Wunsch-Engine des Reviewers. Ohne Angabe wählt der Server "
        "eine ANDERE verfügbare Engine als der Autor (echte Diversität).",
    )
    focus: str | None = Field(
        default=None, max_length=2000,
        description="Optionaler Prüf-Fokus (z. B. 'Sicherheit', 'Skalierung').",
    )


class FindingRead(BaseModel):
    finding_id: str
    severity: Severity
    location: str
    title: str
    suggestion: str
    state: str
    resolution: FindingAction | None = None


class ReviewRead(BaseModel):
    """Ein Cross-Agent-Review (1 Challenge = 1 Reviewer-Session)."""

    review_id: str
    author_session_id: str
    author_engine: str
    author_model: str
    reviewer_engine: str
    reviewer_model: str
    same_engine: bool
    artifact_pointer: str
    artifact_version: str | None = None
    round: int
    focus: str | None = None
    collected: bool
    incomplete: bool
    stale: bool
    created_at: str
    findings: list[FindingRead] = []


class FindingDecision(BaseModel):
    """Body von POST /reviews/{review_id}/findings/{finding_id}."""

    action: FindingAction
    comment: str | None = Field(
        default=None, max_length=20_000,
        description="Bei 'zurück' der Begründungs-Kommentar an die Autor-Session.",
    )
