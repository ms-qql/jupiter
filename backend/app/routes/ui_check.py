"""UI-Check-API (PROJ-14) — lokale Runner-Schicht fuer die native Micro-App."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..engine.ui_check import UiCheckConflict, UiCheckNotFound, UiCheckService
from ..schemas.ui_check import (
    UiCheckRunDetail,
    UiCheckRunsResponse,
    UiCheckStartRequest,
    UiCheckStartResponse,
)

router = APIRouter(prefix="/ui-check", tags=["ui-check"])


def _svc(request: Request) -> UiCheckService:
    return request.app.state.ui_check


@router.get("/runs", response_model=UiCheckRunsResponse)
async def list_runs(request: Request) -> dict:
    return _svc(request).list_runs()


@router.get("/runs/{run_id}", response_model=UiCheckRunDetail)
async def get_run(request: Request, run_id: str) -> dict:
    try:
        return _svc(request).get_run(run_id)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc


@router.post("/runs", response_model=UiCheckStartResponse, status_code=201)
async def start_run(request: Request, payload: UiCheckStartRequest) -> dict:
    try:
        return _svc(request).start_run(payload)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Run-Ordner existiert bereits.") from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs/{run_id}/status", response_model=UiCheckRunDetail)
async def get_status(request: Request, run_id: str) -> dict:
    return await get_run(request, run_id)


@router.post("/runs/{run_id}/cancel", response_model=UiCheckRunDetail)
async def cancel_run(request: Request, run_id: str) -> dict:
    try:
        return _svc(request).cancel_run(run_id)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc


@router.post("/runs/{run_id}/redesign", response_model=UiCheckRunDetail)
async def start_redesign(request: Request, run_id: str) -> dict:
    try:
        return _svc(request).start_redesign(run_id)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runs/{run_id}/artifacts/{kind}")
async def get_artifact(request: Request, run_id: str, kind: str) -> FileResponse:
    try:
        path = _svc(request).artifact_path(run_id, kind)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="Artefakt nicht gefunden.") from exc
    return FileResponse(path)
