"""Konstitutions-API — Transparenz/Verwaltung (PROJ-6).

Read-only im MVP: globale Konstitution + Rollen-Vorschau. Editiert wird über die
MD-Dateien (später via MD-Reader/-Editor #16).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..engine.constitution import (
    is_valid_role,
    list_roles,
    resolve_constitution,
)
from ..schemas.sessions import ConstitutionOverview, ConstitutionRead

router = APIRouter(prefix="/constitution", tags=["constitution"])


@router.get("", response_model=ConstitutionOverview)
async def get_overview() -> dict:
    resolved = resolve_constitution(None, settings.constitution_dir)
    return {"global_text": resolved.text, "roles": list_roles(settings.constitution_dir)}


@router.get("/{role}", response_model=ConstitutionRead)
async def get_role_constitution(role: str) -> dict:
    if not is_valid_role(role):
        raise HTTPException(status_code=400, detail="Ungültiger Rollenname.")
    resolved = resolve_constitution(role, settings.constitution_dir)
    return {"role": resolved.role, "source": resolved.source, "text": resolved.text}
