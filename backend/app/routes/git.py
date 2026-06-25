"""Git-Branch-Handling-API (PROJ-13).

Ein-Klick-UI-Backend für die abc-Git-Logik: Status sehen, ``main ↔ dev`` wechseln,
Feature-Branches ``specs/PROJ-X-<slug>`` anlegen und ``dev → main`` promoten.
Alles scoped auf ``allowed_roots`` (validiert im ``GitService``), Git als
parametrisierter Subprozess. Kein JWT/DB (Jupiter-Override).

Fehler-Mapping: dirty/Konflikt/„kein Repo" → 409 (bedienbare Situation, keine
500er), Timeout → 504, sonstiger Git-Fehler/Scope-Verletzung → 400.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..engine.git_service import (
    DirtyWorkingTree,
    GitError,
    GitService,
    GitTimeout,
    MergeConflict,
    NotARepo,
)
from ..schemas.git import (
    BranchStatus,
    FeatureBranchRequest,
    PromoteRequest,
    ProjectPathRequest,
    SwitchRequest,
)

router = APIRouter(prefix="/git", tags=["git"])


def _svc(request: Request) -> GitService:
    return request.app.state.git


def _map(exc: GitError) -> HTTPException:
    """Git-Fehler auf bedienbare HTTP-Codes abbilden (keine 500er für Normalfälle)."""
    if isinstance(exc, GitTimeout):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, (DirtyWorkingTree, MergeConflict, NotARepo)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/status", response_model=BranchStatus)
async def status(
    request: Request,
    project_path: str = Query(..., min_length=1, description="Absoluter Repo-Pfad innerhalb der Roots."),
) -> dict:
    try:
        return await _svc(request).status(project_path)
    except GitError as exc:
        raise _map(exc) from exc


@router.post("/switch", response_model=BranchStatus)
async def switch(request: Request, payload: SwitchRequest) -> dict:
    try:
        return await _svc(request).switch(payload.project_path, payload.branch)
    except GitError as exc:
        raise _map(exc) from exc


@router.post("/feature-branch", response_model=BranchStatus)
async def feature_branch(request: Request, payload: FeatureBranchRequest) -> dict:
    try:
        return await _svc(request).create_feature_branch(
            payload.project_path, payload.feature_id, payload.slug, payload.base
        )
    except GitError as exc:
        raise _map(exc) from exc


@router.post("/promote", response_model=BranchStatus)
async def promote(request: Request, payload: PromoteRequest) -> dict:
    try:
        return await _svc(request).promote(
            payload.project_path, payload.source, payload.target
        )
    except GitError as exc:
        raise _map(exc) from exc


@router.post("/stash", response_model=BranchStatus)
async def stash(request: Request, payload: ProjectPathRequest) -> dict:
    try:
        return await _svc(request).stash(payload.project_path)
    except GitError as exc:
        raise _map(exc) from exc


@router.post("/init", response_model=BranchStatus)
async def init(request: Request, payload: ProjectPathRequest) -> dict:
    try:
        return await _svc(request).init(payload.project_path)
    except GitError as exc:
        raise _map(exc) from exc
