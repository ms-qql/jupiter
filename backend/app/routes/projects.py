"""Projekt-/Smart-Launcher-API (PROJ-9).

``GET /projects/suggestion`` liest die ``features/INDEX.md`` eines Projekts und
liefert einen mitdenkenden Session-Start-Vorschlag (nächstes Feature + Phase +
Skill + Modell + Start-Prompt). Read-only, kein DB-State. Pfad-Härtung über
``validate_project_path`` (gleicher Scope wie Session-Start / MD-Reader).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..engine.launcher import LauncherService
from ..schemas.projects import LaunchSuggestion

router = APIRouter(prefix="/projects", tags=["projects"])


def _launcher(request: Request) -> LauncherService:
    return request.app.state.launcher


@router.get("/suggestion", response_model=LaunchSuggestion)
async def suggestion(
    request: Request,
    project_path: str = Query(..., min_length=1, description="Projektpfad innerhalb der erlaubten Roots."),
) -> dict:
    try:
        return _launcher(request).suggest(project_path)
    except ValueError as exc:  # Pfad außerhalb der Roots / kein Verzeichnis
        raise HTTPException(status_code=400, detail=str(exc)) from exc
