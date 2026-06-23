"""Settings-API — globale Kontext-Schwelle lesen/setzen (PROJ-5).

Single-User-MVP: kein JWT, keine DB. Der Schwellenwert lebt in-memory in
``settings`` (konsistent mit dem No-DB-Ansatz von PROJ-1/2). Jeder Wert wird
auf ``[THRESHOLD_MIN_PCT, THRESHOLD_MAX_PCT]`` geklemmt (Edge-Case: 0/100/Unsinn).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..config import THRESHOLD_MAX_PCT, THRESHOLD_MIN_PCT, clamp_threshold, settings
from ..engine.files import FileService
from ..schemas.settings import (
    ClipboardDirPatch,
    ClipboardDirRead,
    ThresholdSettingPatch,
    ThresholdSettingRead,
)

router = APIRouter(prefix="/settings", tags=["settings"])


def _threshold_payload() -> dict:
    return {
        "threshold_pct": clamp_threshold(settings.context_fill_threshold_pct),
        "min_pct": THRESHOLD_MIN_PCT,
        "max_pct": THRESHOLD_MAX_PCT,
    }


@router.get("/threshold", response_model=ThresholdSettingRead)
async def get_threshold() -> dict:
    return _threshold_payload()


@router.patch("/threshold", response_model=ThresholdSettingRead)
async def set_threshold(payload: ThresholdSettingPatch) -> dict:
    settings.context_fill_threshold_pct = clamp_threshold(payload.threshold_pct)
    return _threshold_payload()


# --- Clipboard-Ordner (PROJ-11) ------------------------------------------

def _files(request: Request) -> FileService:
    return request.app.state.files


@router.get("/clipboard-dir", response_model=ClipboardDirRead)
async def get_clipboard_dir(request: Request) -> dict:
    return {"path": _files(request).clipboard_dir()}


@router.patch("/clipboard-dir", response_model=ClipboardDirRead)
async def set_clipboard_dir(request: Request, payload: ClipboardDirPatch) -> dict:
    try:
        return {"path": _files(request).set_clipboard_dir(payload.path)}
    except ValueError as exc:  # außerhalb der erlaubten Roots
        raise HTTPException(status_code=400, detail=str(exc)) from exc
