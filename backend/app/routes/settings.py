"""Settings-API — globale Kontext-Schwelle (PROJ-5) + Trust-Policy (PROJ-10).

Single-User-MVP: kein JWT, keine DB. Die Schwelle lebt in-memory in ``settings``;
die Trust-Policy in einer YAML-Datei (live editierbar, ``policy_store``), konsistent
mit dem No-DB-/Datei-Ansatz von PROJ-1/2/6.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..config import THRESHOLD_MAX_PCT, THRESHOLD_MIN_PCT, clamp_threshold, settings
from ..engine import liveness, policy, watchdog
from ..engine.abc_phases import ABC_PHASES
from ..engine.files import FileService
from ..engine.registry import engine_registry
from ..schemas.settings import (
    ClipboardDirPatch,
    ClipboardDirRead,
    EngineSettingsPut,
    EngineSettingsRead,
    EngineSettingsValidationRead,
    LivenessLimitsPut,
    LivenessSettingRead,
    PolicyPreviewRead,
    ThresholdSettingPatch,
    ThresholdSettingRead,
    TrustPolicyPut,
    TrustPolicyRead,
    WatchdogLimitsPut,
    WatchdogSettingRead,
)
from ..schemas.transcription import (
    TranscriptionSettingPatch,
    TranscriptionSettingRead,
)
from ..engine.transcription import TranscriptionService

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


# --- Engine-/Modellverwaltung (PROJ-51) ------------------------------------


@router.get("/engines", response_model=EngineSettingsRead)
async def get_engine_settings() -> dict:
    """Bearbeitbare Engine-Konfiguration (secret-frei, aber mit auth_env-Namen)."""
    return engine_registry.settings_snapshot()


@router.post("/engines/validate", response_model=EngineSettingsValidationRead)
async def validate_engine_settings(payload: EngineSettingsPut) -> dict:
    """Trockenlauf: validiert die Engine-Konfiguration ohne YAML zu schreiben."""
    try:
        return engine_registry.validate_settings(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/engines", response_model=EngineSettingsRead)
async def put_engine_settings(payload: EngineSettingsPut) -> dict:
    """Engine-Konfiguration validieren + atomar nach engines.yaml schreiben."""
    try:
        return engine_registry.save_settings(payload.model_dump())
    except (ValueError, OSError) as exc:
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


# --- Liveness + Auto-Reanimierung (PROJ-27) -------------------------------

@router.get("/liveness", response_model=LivenessSettingRead)
async def get_liveness() -> dict:
    """Aktuelle Liveness-Schwellen + Herkunft/Warnung (live aus der Datei)."""
    return liveness.liveness_store.snapshot()


@router.put("/liveness", response_model=LivenessSettingRead)
async def put_liveness(payload: LivenessLimitsPut) -> dict:
    """Schwellen ersetzen — Pydantic erzwingt die Wertebereiche; in YAML geschrieben, **live** aktiv."""
    try:
        return liveness.liveness_store.save(payload.model_dump())
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Spracheingabe / Transkriptions-Quelle (PROJ-20) ----------------------

def _transcription_payload() -> dict:
    return {
        "use_groq": TranscriptionService.use_groq(),
        "groq_available": TranscriptionService.groq_available(),
        "model": settings.whisper_model,
        "language": settings.whisper_language,
    }


@router.get("/transcription", response_model=TranscriptionSettingRead)
async def get_transcription() -> dict:
    """Aktuelle Quelle (lokal/Groq) + ob der Groq-Fallback überhaupt verfügbar ist."""
    return _transcription_payload()


@router.patch("/transcription", response_model=TranscriptionSettingRead)
async def set_transcription(payload: TranscriptionSettingPatch) -> dict:
    """Cloud-Fallback bewusst an/aus. Groq ohne konfigurierten Key → 400 (Setup-Hinweis)."""
    if payload.use_groq and not TranscriptionService.groq_available():
        raise HTTPException(
            status_code=400,
            detail="Kein Groq-API-Key konfiguriert (JUPITER_GROQ_API_KEY in der .env setzen).",
        )
    settings.use_groq_transcription = payload.use_groq
    return _transcription_payload()
