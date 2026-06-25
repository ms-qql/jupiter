"""Pydantic-v2-Schemas für das in-App Git-Branch-Handling (PROJ-13).

Git ist die Quelle der Wahrheit — kein DB-State, kein JWT (Jupiter-Override).
``project_path`` ist immer ein absoluter, serverseitig gegen die ``allowed_roots``
validierter Pfad eines Git-Repos.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class BranchStatus(BaseModel):
    """Live aus dem Repo gelesener Branch-Status (read-only, pollbar)."""

    path: str                       # validierter Repo-Realpfad
    is_repo: bool                   # False → Aktionen ausgegraut, Angebot „git init?"
    branch: str | None              # aktueller Branch (oder Kurz-Hash bei detached)
    detached: bool                  # True = detached HEAD
    dirty: bool                     # uncommittete Änderungen vorhanden
    ahead: int | None               # Commits vor dem Upstream (None = kein Tracking)
    behind: int | None              # Commits hinter dem Upstream
    branches: list[str]             # lokale Branches


class SwitchRequest(BaseModel):
    project_path: str = Field(..., min_length=1, description="Absoluter Repo-Pfad innerhalb der Roots.")
    branch: str = Field(..., min_length=1, description="Zielbranch (z. B. main oder dev).")


class FeatureBranchRequest(BaseModel):
    project_path: str = Field(..., min_length=1, description="Absoluter Repo-Pfad innerhalb der Roots.")
    feature_id: int = Field(..., ge=1, description="PROJ-Nummer (z. B. 13).")
    slug: str = Field(..., min_length=1, description="Kurz-Titel; wird zu kebab-case slugifiziert.")
    base: str = Field("main", min_length=1, description="Basis-Branch (main oder dev).")


class PromoteRequest(BaseModel):
    project_path: str = Field(..., min_length=1, description="Absoluter Repo-Pfad innerhalb der Roots.")
    source: str = Field(..., min_length=1, description="Quell-Branch (z. B. dev).")
    target: str = Field(..., min_length=1, description="Ziel-Branch (z. B. main).")


class ProjectPathRequest(BaseModel):
    project_path: str = Field(..., min_length=1, description="Absoluter Repo-Pfad innerhalb der Roots.")
