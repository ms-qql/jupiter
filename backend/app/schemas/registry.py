"""Pydantic-v2-Schemas für den Marktplatz/Registry (PROJ-26).

Spiegelt den Frontend-Vertrag (`nextjs_app/lib/types.ts`): RegistryEntry,
RegistryVersion, RegistryEntryDetail, RegistryCatalog, RegistryImportPreview.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RegistryType = Literal["role", "skill", "agent"]
RegistryStatus = Literal["installed", "active", "inactive"]
PolicyLevel = Literal["auto-allow", "card", "deny"]


class RegistryEntryRead(BaseModel):
    """Ein Katalog-Eintrag (GET /registry/catalog)."""

    id: str
    typ: RegistryType
    name: str
    beschreibung: str
    status: RegistryStatus
    version: str
    owner: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    default_policy: PolicyLevel
    verified: bool = False
    limited: bool = False


class RegistryVersionRead(BaseModel):
    """Eine frühere Version eines Eintrags (Rollback-Quelle)."""

    version: str
    created_at: str = ""
    note: str | None = None
    limited: bool = False


class RegistryEntryDetailRead(RegistryEntryRead):
    """Detail eines Eintrags inkl. Definition-Text + Versions-Historie."""

    definition: str = ""
    versions: list[RegistryVersionRead] = Field(default_factory=list)


class RegistryCatalogRead(BaseModel):
    entries: list[RegistryEntryRead] = Field(default_factory=list)


class RegistryImportPreviewRead(BaseModel):
    """Capability-/Policy-Vorschau (POST /registry/import) — noch NICHT aktiv."""

    token: str
    id: str
    typ: RegistryType
    name: str
    beschreibung: str
    version: str
    owner: str | None = None
    schema_version: str
    capabilities: list[str] = Field(default_factory=list)
    default_policy: PolicyLevel
    verified: bool = False
    collision: bool = False
    warnings: list[str] = Field(default_factory=list)


class RegistryRollbackBody(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)


class RegistryImportConfirmBody(BaseModel):
    token: str = Field(..., min_length=1, max_length=64)
