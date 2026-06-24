"""Settings-API — globale Kontext-Schwelle (PROJ-5) + Trust-Policy (PROJ-10).

Single-User-MVP: kein JWT, keine DB. Die Schwelle lebt in-memory in ``settings``;
die Trust-Policy in einer YAML-Datei (live editierbar, ``policy_store``), konsistent
mit dem No-DB-/Datei-Ansatz von PROJ-1/2/6.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..config import THRESHOLD_MAX_PCT, THRESHOLD_MIN_PCT, clamp_threshold, settings
from ..engine import policy, watchdog
from ..engine.abc_phases import ABC_PHASES
from ..engine.files import FileService
from ..schemas.settings import (
    ClipboardDirPatch,
    ClipboardDirRead,
    PolicyPreviewRead,
    ThresholdSettingPatch,
    ThresholdSettingRead,
    TrustPolicyPut,
    TrustPolicyRead,
    WatchdogLimitsPut,
    WatchdogSettingRead,
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


# --- Trust-Policy (PROJ-10) ------------------------------------------------

@router.get("/policy", response_model=TrustPolicyRead)
async def get_policy() -> dict:
    """Aktuelle Trust-Policy + Herkunft/Warnung (live aus der Datei)."""
    return policy.policy_store.snapshot()


@router.put("/policy", response_model=TrustPolicyRead)
async def put_policy(payload: TrustPolicyPut) -> dict:
    """Policy ersetzen — validiert, in YAML geschrieben, **live** übernommen."""
    unknown = [t for t in payload.phase_gate.transitions if t not in ABC_PHASES]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte Phase(n) im Phasen-Gate: {', '.join(unknown)}.",
        )
    try:
        return policy.policy_store.save(
            [r.model_dump() for r in payload.rules],
            payload.phase_gate.model_dump(),
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/policy/preview", response_model=PolicyPreviewRead)
async def preview_policy(
    tool: str,
    role: str | None = None,
    skill: str | None = None,
    project: str | None = None,
) -> dict:
    """Trockenlauf: welche Stufe + Regel würde für den Kontext greifen (Nachvollziehbarkeit)."""
    d = policy.policy_store.evaluate(tool, role=role, skill=skill, project=project)
    return {"level": d.level, "rule": d.rule}


# --- Amok-Watchdog (PROJ-16) ----------------------------------------------

@router.get("/watchdog", response_model=WatchdogSettingRead)
async def get_watchdog() -> dict:
    """Aktuelle Watchdog-Limits + Herkunft/Warnung (live aus der Datei)."""
    return watchdog.watchdog_store.snapshot()


@router.put("/watchdog", response_model=WatchdogSettingRead)
async def put_watchdog(payload: WatchdogLimitsPut) -> dict:
    """Limits ersetzen — Pydantic erzwingt > 0 (422); in YAML geschrieben, **live** aktiv."""
    try:
        return watchdog.watchdog_store.save(payload.model_dump())
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
