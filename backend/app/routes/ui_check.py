"""UI-Check-API (PROJ-14) — lokale Runner-Schicht fuer die native Micro-App."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError

from ..engine.ui_check import (
    UiCheckBrandingIncomplete,
    UiCheckConflict,
    UiCheckNotFound,
    UiCheckRegistryError,
    UiCheckRegistryGap,
    UiCheckService,
)
from ..schemas.ui_check import (
    UiCheckAssembleRequest,
    UiCheckAssembleResponse,
    UiCheckBrandingProfilesResponse,
    UiCheckImagesRequest,
    UiCheckMockupExportRequest,
    UiCheckRecycleRequest,
    UiCheckRegistryResponse,
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


@router.post("/runs/with-screenshot", response_model=UiCheckStartResponse, status_code=201)
async def start_run_with_screenshot(
    request: Request,
    screenshot: UploadFile = File(...),
    url: str = Form(...),
    mode: str = Form("auto"),
    depth: str = Form("audit"),
    ai_provider: str = Form("claude"),
    ai_model: str = Form(...),
    prompt: str | None = Form(None),
    industry: str | None = Form(None),
    desktop: bool = Form(False),
    full_pipeline: bool = Form(False),
) -> dict:
    try:
        payload = UiCheckStartRequest.model_validate({
            "url": url, "mode": mode, "depth": depth, "ai_provider": ai_provider,
            "ai_model": ai_model, "prompt": prompt, "industry": industry,
            "desktop": desktop, "full_pipeline": full_pipeline,
        })
        return _svc(request).start_run(payload, screenshot.file)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Run-Ordner existiert bereits.") from exc
    finally:
        await screenshot.close()


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


@router.post("/runs/{run_id}/images", response_model=UiCheckRunDetail)
async def start_images(request: Request, run_id: str, payload: UiCheckImagesRequest | None = None) -> dict:
    body = payload or UiCheckImagesRequest()
    try:
        return _svc(request).start_images(run_id, force=body.force, only=body.only)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/runs/{run_id}/mockup-export", response_model=UiCheckRunDetail)
async def start_mockup_export(request: Request, run_id: str, payload: UiCheckMockupExportRequest | None = None) -> dict:
    body = payload or UiCheckMockupExportRequest()
    try:
        return _svc(request).start_mockup_export(run_id, force=body.force)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/runs/{run_id}/recycle", response_model=UiCheckRunDetail)
async def start_recycle(request: Request, run_id: str, payload: UiCheckRecycleRequest | None = None) -> dict:
    body = payload or UiCheckRecycleRequest()
    try:
        return _svc(request).start_recycle(
            run_id, min_total=body.min_total, min_visual=body.min_visual, force=body.force
        )
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/registry", response_model=UiCheckRegistryResponse)
async def get_registry(request: Request) -> dict:
    try:
        return _svc(request).list_registry()
    except UiCheckRegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/branding-profiles", response_model=UiCheckBrandingProfilesResponse)
async def get_branding_profiles(request: Request) -> dict:
    return _svc(request).list_branding_profiles()


@router.post("/assemble", response_model=UiCheckAssembleResponse, status_code=201)
async def start_assemble(request: Request, payload: UiCheckAssembleRequest) -> dict:
    try:
        return _svc(request).start_assemble(payload)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="Branding-Profil nicht gefunden.") from exc
    except UiCheckBrandingIncomplete as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "missing_profile_parts": exc.missing},
        ) from exc
    except UiCheckRegistryGap as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "missing_sections": exc.missing},
        ) from exc
    except UiCheckRegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="Run-Ordner existiert bereits.") from exc


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(request: Request, run_id: str) -> Response:
    try:
        _svc(request).delete_run(run_id)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="UI-Check-Lauf nicht gefunden.") from exc
    except UiCheckConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/runs/{run_id}/artifacts/{kind}")
async def get_artifact(request: Request, run_id: str, kind: str) -> FileResponse:
    try:
        path = _svc(request).artifact_path(run_id, kind)
    except UiCheckNotFound as exc:
        raise HTTPException(status_code=404, detail="Artefakt nicht gefunden.") from exc
    return FileResponse(path)
