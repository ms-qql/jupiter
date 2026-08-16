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
    # M3: bei vollem Slot eingereihte Tickets (IDs) — rücken automatisch nach.
    queued: list[str] = []


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


# --- PROJ-79: Featurezentrierter Koordinator ---------------------------------


class FeaturePlanItem(BaseModel):
    """Ein internes Arbeitspaket eines Feature-Laufs (nur innerhalb des Eltern-Features
    gültig, z. B. ``PROJ-101.2``). Entspricht einem DispatchPlanItem, trägt aber zusätzlich
    den Schreibbereich, den rollenbezogenen Abschlussbeleg-Typ und die interne Kennung."""

    package_id: str = Field(..., description="Interne Kennung, z. B. „PROJ-101.2”.")
    title: str
    role: str | None = None
    skill: str | None = None
    engine: str = "claude"
    model: str | None = None
    order: int
    dependencies: list[str] = []  # package_ids, auf die dieses Paket wartet
    blocked: bool = False
    blocked_reason: str | None = None
    # Betroffene Dateien/Verzeichnisse — Schreibbereich-Claim (Kollisionsschutz).
    write_scope: list[str] = Field(default_factory=list)
    # Erforderlicher Abschlussbeleg-Typ (Rolle): backend/frontend/qa/architecture/other.
    required_proof: str = "other"


class FeaturePlanRequest(BaseModel):
    project_path: str = Field(..., min_length=1)
    feature_id: str = Field(..., min_length=1, max_length=16, description="„PROJ-101” oder „101”.")


class FeaturePlan(BaseModel):
    """Interner Verteilungsplan für EIN Feature (Human-in-the-Loop, startet NICHTS)."""

    project_path: str
    feature_id: str
    feature_title: str
    items: list[FeaturePlanItem] = []
    warnings: list[str] = []


class FeatureDispatchRequest(BaseModel):
    """Freigegebener Feature-Plan → Dispatch der Feature-Ausführung."""

    project_path: str = Field(..., min_length=1)
    feature_id: str = Field(..., min_length=1, max_length=16)
    items: list[FeaturePlanItem] = Field(..., min_length=1)


class CompletionProof(BaseModel):
    """Strukturierter Abschlussbeleg eines Arbeitspakets (Rolle ergänzt Pflichtfelder).

    Ein bloßer Session-Endstatus ersetzt diesen Beleg niemals — der Scheduler prüft ihn.
    ``package_id`` ist optional im Body (der Pfad ``/packages/{package_id}/complete`` hat
    Vorrang); es muss nur in einem der beiden übergeben werden.
    """

    package_id: str | None = Field(default=None, min_length=1)
    role: str | None = None
    result_state: str = Field(..., pattern=r"^(success|failed)$", description="Ergebniszustand.")
    artifacts: list[str] = Field(default_factory=list, description="Erzeugte/geänderte Artefakte.")
    checks: list[dict] = Field(default_factory=list, description="Durchgeführte Prüfungen + Ergebnis.")
    open_limitations: str | None = Field(default=None, description="Offene Einschränkungen.")


class FeaturePackageRead(BaseModel):
    """Live-Zustand eines internen Arbeitspakets (für die Feature-Ausführungs-Ansicht)."""

    package_id: str
    title: str
    role: str | None = None
    skill: str | None = None
    engine: str
    model: str | None = None
    status: str  # wartet|bereit|läuft|erfolgreich|fehlgeschlagen|übersprungen
    dependencies: list[str] = []
    write_scope: list[str] = []
    required_proof: str = "other"
    session_id: str | None = None
    resume_attempts: int = 0
    last_safe_state: str | None = None
    proof: CompletionProof | None = None


class FeatureRun(BaseModel):
    """Gesamtsicht einer Feature-Ausführung (Elternkopf + Pakete + Blockierung)."""

    feature_id: str
    status: str  # planung|läuft|pausiert|blockiert|fertig|abgebrochen
    coordinator: SessionRead
    packages: list[FeaturePackageRead] = []
    paused: bool = False
    revision: int = 0
    blocker: dict | None = None  # genau eine offene Blockierungs-Decision-Card


class FeatureDecisionRequest(BaseModel):
    """Verarbeitet „erneut versuchen" / „manuell übernehmen" / „Feature abbrechen"."""

    action: str = Field(..., pattern=r"^(retry|manual|abort)$")
    package_id: str | None = Field(default=None, description="Zielpaket (retry/manual).")
