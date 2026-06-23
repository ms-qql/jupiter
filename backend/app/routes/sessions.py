"""Session-API — REST (steuern) + WebSocket (Live-Stream). PROJ-1.

MVP single-user: kein JWT; der ``owner`` wird serverseitig gestempelt (#21).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from ..config import clamp_threshold
from ..engine.manager import SessionManager
from ..schemas.sessions import (
    ConstitutionRead,
    DecisionResolve,
    HandoverPreview,
    ResetRequest,
    SessionCreate,
    SessionDetail,
    SessionInput,
    SessionRead,
    ThresholdPatch,
    TranscriptText,
)
from ..schemas.vault import HandoverRequest, VaultWriteResult

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _manager(request: Request) -> SessionManager:
    return request.app.state.manager


@router.post("", response_model=SessionRead, status_code=201)
async def create_session(payload: SessionCreate, request: Request) -> dict:
    try:
        runtime = await _manager(request).create(
            project_path=payload.project_path,
            initial_prompt=payload.initial_prompt,
            model=payload.model,
            permission_mode=payload.permission_mode,
            role=payload.role,
            extra_system_prompt=payload.extra_system_prompt,
        )
    except ValueError as exc:  # ungültiger Pfad / Modell
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:  # claude-Binary nicht gefunden
        raise HTTPException(
            status_code=503, detail="Claude-CLI nicht gefunden — ist `claude` installiert/eingeloggt?"
        ) from exc
    return runtime.to_read()


@router.get("", response_model=list[SessionRead])
async def list_sessions(request: Request) -> list[dict]:
    return [r.to_read() for r in _manager(request).list()]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, request: Request) -> dict:
    runtime = _manager(request).get(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    data = runtime.to_read()
    data["transcript"] = [vars(e) for e in runtime.transcript]
    return data


@router.post("/{session_id}/input", status_code=202)
async def send_input(session_id: str, payload: SessionInput, request: Request) -> dict:
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    try:
        await manager.send_input(session_id, payload.text)
    except RuntimeError as exc:  # pausiert / nicht aktiv
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/{session_id}/decisions/{decision_id}", status_code=202)
async def resolve_decision(
    session_id: str, decision_id: str, payload: DecisionResolve, request: Request
) -> dict:
    """Decision Card entscheiden (PROJ-4): Freigeben / Ablehnen / Mit Kommentar zurück.

    Die wartende Session wird entsperrt und läuft entsprechend weiter oder bricht
    die Aktion ab.
    """
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    try:
        card = manager.resolve_decision(
            session_id,
            decision_id,
            approve=payload.decision == "approve",
            comment=payload.comment,
        )
    except KeyError as exc:  # Card unbekannt (oder bereits aufgelöst/obsolet)
        raise HTTPException(status_code=404, detail="Decision Card nicht gefunden.") from exc
    except ValueError as exc:  # bereits entschieden
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "decision": card.to_read()}


@router.post("/{session_id}/pause")
async def pause_session(session_id: str, request: Request) -> dict:
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    await manager.pause(session_id)
    return {"ok": True}


@router.post("/{session_id}/stop")
async def stop_session(session_id: str, request: Request) -> dict:
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    await manager.stop(session_id)
    return {"ok": True}


@router.get("/{session_id}/constitution", response_model=ConstitutionRead)
async def get_session_constitution(session_id: str, request: Request) -> dict:
    """Effektive Konstitution DIESER Session (PROJ-6, AC: einsehbar)."""
    runtime = _manager(request).get(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    return {
        "role": runtime.state.role,
        "source": runtime.state.constitution_source or "leer",
        "text": runtime.state.effective_constitution,
    }


@router.post("/{session_id}/handover/generate", response_model=HandoverPreview)
async def generate_handover(session_id: str, request: Request) -> dict:
    """Handover-INHALT erzeugen (Vorschau, Hybrid-Gerüst) — schreibt NICHT in den Vault.

    Der zurückgegebene Body geht (ggf. vom Nutzer editiert) an ``POST …/handover``.
    """
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    return manager.generate_handover(session_id)


@router.post("/{session_id}/reset", response_model=SessionRead, status_code=201)
async def reset_session(session_id: str, payload: ResetRequest, request: Request) -> dict:
    """„Session zurücksetzen": alte Session archivieren, Kind-Session mit dem Handover
    als Seed-Kontext frisch starten (Staffelstab, ``parent_session_id`` verweist zurück).
    """
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    try:
        child = await manager.reset(
            session_id,
            seed_context=payload.seed_context,
            initial_prompt=payload.initial_prompt,
        )
    except RuntimeError as exc:  # bereits zurückgesetzt (1 Strang = 1 Nachfolger)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:  # ungültiger Pfad / Modell der Kind-Session
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:  # claude-Binary weg
        raise HTTPException(
            status_code=503, detail="Claude-CLI nicht gefunden — ist `claude` installiert/eingeloggt?"
        ) from exc
    return child.to_read()


@router.patch("/{session_id}/threshold", response_model=SessionRead)
async def set_session_threshold(session_id: str, payload: ThresholdPatch, request: Request) -> dict:
    """Pro-Session-Override der Kontext-Schwelle (None = globale Schwelle nutzen)."""
    runtime = _manager(request).get(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    runtime.state.context_threshold_override_pct = (
        clamp_threshold(payload.threshold_pct) if payload.threshold_pct is not None else None
    )
    # Schwelle geändert → Warn-Status kann sich ändern: Snapshot streamen.
    runtime._broadcast({"kind": "state", **runtime.to_read()})
    return runtime.to_read()


@router.post("/{session_id}/handover", response_model=VaultWriteResult, status_code=201)
async def write_handover(session_id: str, payload: HandoverRequest, request: Request) -> dict:
    """Kuratiertes Handover-Dokument dieser Session in den Vault schreiben (PROJ-2)."""
    runtime = _manager(request).get(session_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    vault = request.app.state.vault
    try:
        result = vault.write(
            type="handover",
            body=payload.body,
            title=payload.title or f"handover-{session_id[:8]}",
            session_id=session_id,
            owner=runtime.state.owner,
            on_exists=payload.on_exists,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PermissionError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"Vault-Schreibfehler: {exc}") from exc
    return vars(result)


@router.get("/{session_id}/transcript", response_model=TranscriptText)
async def get_transcript(session_id: str, request: Request) -> dict:
    manager = _manager(request)
    if manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    return {"text": manager.transcript_text(session_id)}


@router.websocket("/{session_id}/stream")
async def stream_session(websocket: WebSocket, session_id: str) -> None:
    import asyncio

    manager: SessionManager = websocket.app.state.manager
    runtime = manager.get(session_id)
    if runtime is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    queue = runtime.subscribe()
    queue_get: asyncio.Task | None = None
    sock_recv: asyncio.Task | None = None
    try:
        # Sofort einen Zustands-Snapshot senden (inkl. offener Decision Cards),
        # danach live weiterstreamen.
        await websocket.send_json({"kind": "state", **runtime.to_read()})
        while True:
            # Auf das nächste Event ODER eine Socket-Aktion (Disconnect) warten,
            # damit getrennte Clients nicht ewig in queue.get() hängen.
            queue_get = asyncio.ensure_future(queue.get())
            sock_recv = asyncio.ensure_future(websocket.receive())
            done, pending = await asyncio.wait(
                {queue_get, sock_recv}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if sock_recv in done:
                msg = sock_recv.result()  # kann WebSocketDisconnect werfen
                if msg.get("type") == "websocket.disconnect":
                    break
                continue  # Client-Eingaben laufen im MVP über REST → ignorieren
            await websocket.send_json(queue_get.result())
    except WebSocketDisconnect:
        pass
    finally:
        runtime.unsubscribe(queue)
        for task in (queue_get, sock_recv):
            if task is not None and not task.done():
                task.cancel()
