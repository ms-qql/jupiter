"""Interner Freigabe-Endpoint (PROJ-4) — nur vom PreToolUse-Hook aufgerufen.

Der Hook-Subprozess von Claude Code postet hierher und **blockiert**, bis der Nutzer
im Cockpit entschieden hat. Die Antwort ist bereits der fertige PreToolUse-Hook-Output
(``hookSpecificOutput``), den das Hook-Skript unverändert an Claude zurückgibt.

Sicherheit (MVP): localhost-only + geteiltes Token im Header. Bewusst NICHT unter
``/sessions`` und nicht für den Browser gedacht (kein CORS-Use-Case).
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from ..config import settings
from ..engine.manager import SessionManager
from ..schemas.sessions import PermissionHookRequest

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/permission")
async def permission_prompt(
    payload: PermissionHookRequest,
    request: Request,
    x_jupiter_hook_token: str = Header(default=""),
) -> dict:
    if x_jupiter_hook_token != settings.hook_token:
        raise HTTPException(status_code=403, detail="Ungültiges Hook-Token.")

    manager: SessionManager = request.app.state.manager
    if manager.get(payload.session_id) is None:
        # Unbekannte Session → vorsichtshalber ablehnen (fail-safe).
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Unbekannte Jupiter-Session — blockiert.",
            }
        }

    # decision_id = tool_use_id (erlaubt mehrere parallele Cards je Session).
    decision_id = payload.tool_use_id or f"{payload.session_id}:{payload.tool_name}"
    outcome = await manager.request_decision(
        payload.session_id, decision_id, payload.tool_name, payload.tool_input
    )
    return outcome.to_hook_response()
