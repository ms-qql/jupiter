"""Session-API — REST (steuern) + WebSocket (Live-Stream). PROJ-1.

PROJ-25: ``owner`` kommt **immer aus dem Token** (``get_current_user``); jeder
Zugriff ist auf die eigenen Sessions beschränkt. Fremde/unbekannte ``session_id``
liefern einheitlich **404** (kein Existenz-Leak fürs ID-Raten).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from ..config import clamp_threshold
from ..deps import CurrentUser, get_current_user
from ..engine.auth import AuthError
from ..engine.manager import (
    EngineUnavailableError,
    SessionActiveError,
    SessionAliveError,
    SessionLimitError,
    SessionManager,
    SessionRuntime,
)
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


def _owned_or_404(manager: SessionManager, session_id: str, user: CurrentUser) -> SessionRuntime:
    """Session DES NUTZERS holen oder 404 — fremde/unbekannte IDs sind ununterscheidbar
    (kein Existenz-Leak fürs ID-Raten, PROJ-25 Red-Team)."""
    runtime = manager.get(session_id)
    if runtime is None or runtime.state.owner != user.user_id:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.")
    return runtime


@router.post("", response_model=SessionRead, status_code=201)
async def create_session(
    payload: SessionCreate, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    try:
        runtime = await _manager(request).create(
            project_path=payload.project_path,
            initial_prompt=payload.initial_prompt,
            model=payload.model,
            permission_mode=payload.permission_mode,
            role=payload.role,
            extra_system_prompt=payload.extra_system_prompt,
            project_name=payload.project_name,
            engine=payload.engine,
            owner=user.user_id,  # PROJ-25: Owner IMMER aus dem Token, nie aus dem Payload.
        )
    except SessionLimitError as exc:  # PROJ-14: Limit aktiver Sessions erreicht.
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except EngineUnavailableError as exc:  # PROJ-18: Engine fehlt CLI/API-Key.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:  # ungültiger Pfad / Modell / unbekannte Engine
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:  # claude-Binary nicht gefunden
        raise HTTPException(
            status_code=503, detail="Claude-CLI nicht gefunden — ist `claude` installiert/eingeloggt?"
        ) from exc
    return runtime.to_read()


@router.get("", response_model=list[SessionRead])
async def list_sessions(request: Request, user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    # PROJ-25: nur die eigenen Sessions (Scope auf owner aus dem Token).
    return [r.to_read() for r in _manager(request).list() if r.state.owner == user.user_id]


@router.get("/limits")
async def session_limits(request: Request, user: CurrentUser = Depends(get_current_user)) -> dict:
    """PROJ-14: Limit-Status für das Cockpit (max + aktuell aktive Sessions).

    ``active``/``max`` sind die GLOBALE VPS-Ressourcen-Obergrenze (single-worker),
    bewusst instanzweit — nur ein gültiges Token ist nötig (PROJ-25)."""
    manager = _manager(request)
    return {"max_parallel_sessions": manager.max_parallel_sessions, "active": manager.active_count()}


@router.post("/cleanup")
async def cleanup_sessions(request: Request, user: CurrentUser = Depends(get_current_user)) -> dict:
    """PROJ-21: alle terminalen Sessions (done/error/verwaist) auf einmal löschen.

    Aktive Sessions werden serverseitig still übersprungen. PROJ-25: nur die eigenen
    Sessions des Nutzers. Statisches Segment, daher VOR ``/{session_id}`` deklariert.
    """
    deleted = await _manager(request).cleanup_terminal(owner=user.user_id)
    return {"deleted": deleted}


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    runtime = _owned_or_404(_manager(request), session_id, user)
    data = runtime.to_read()
    data["transcript"] = [vars(e) for e in runtime.transcript]
    return data


@router.post("/{session_id}/input", status_code=202)
async def send_input(
    session_id: str, payload: SessionInput, request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    try:
        await manager.send_input(session_id, payload.text)
    except RuntimeError as exc:  # pausiert / nicht aktiv
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True}


@router.post("/{session_id}/decisions/{decision_id}", status_code=202)
async def resolve_decision(
    session_id: str, decision_id: str, payload: DecisionResolve, request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Decision Card entscheiden: Freigeben / Ablehnen / Mit Kommentar zurück (PROJ-4)
    bzw. Wissens-Vorschlag Freigeben / Editieren / Verwerfen (PROJ-15).

    Die wartende Session wird entsperrt und läuft entsprechend weiter oder bricht
    die Aktion ab; ein freigegebener Wissens-Vorschlag wird kuratiert in den Vault
    geschrieben.
    """
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    try:
        card = manager.resolve_decision(
            session_id,
            decision_id,
            approve=payload.decision == "approve",
            comment=payload.comment,
            edited_title=payload.edited_title,
            edited_body=payload.edited_body,
        )
    except KeyError as exc:  # Card unbekannt (oder bereits aufgelöst/obsolet)
        raise HTTPException(status_code=404, detail="Decision Card nicht gefunden.") from exc
    except ValueError as exc:  # bereits entschieden
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PermissionError, OSError) as exc:  # PROJ-15: Vault nicht schreibbar → Card bleibt offen
        raise HTTPException(
            status_code=503, detail=f"Wissensnotiz nicht geschrieben (Vault): {exc}"
        ) from exc
    return {"ok": True, "decision": card.to_read()}


@router.post("/{session_id}/reanimate", response_model=SessionRead)
async def reanimate_session(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """PROJ-27: eine hängende/tote Session manuell reaktivieren (``claude --resume``-Pfad).

    404 unbekannt; 409 wenn die Session bereits läuft; 429 wenn das Session-Limit eine
    Reanimierung verbietet (kein Bypass); 503 wenn der Resume/das CLI fehlschlägt.
    """
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    try:
        runtime = await manager.reanimate(session_id)
    except SessionAliveError as exc:  # läuft bereits — nichts zu reanimieren
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SessionLimitError as exc:  # PROJ-14: Limit greift auch beim Reanimieren
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except FileNotFoundError as exc:  # claude-Binary weg
        raise HTTPException(
            status_code=503, detail="Claude-CLI nicht gefunden — ist `claude` installiert/eingeloggt?"
        ) from exc
    except (RuntimeError, OSError) as exc:  # Resume fehlgeschlagen
        raise HTTPException(status_code=503, detail=f"Reanimierung fehlgeschlagen: {exc}") from exc
    return runtime.to_read()


@router.post("/{session_id}/pause")
async def pause_session(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    await manager.pause(session_id)
    return {"ok": True}


@router.post("/{session_id}/stop")
async def stop_session(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    await manager.stop(session_id)
    return {"ok": True}


@router.delete("/{session_id}", status_code=204, response_model=None)
async def delete_session(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> None:
    """PROJ-21: eine terminale Session aus dem Live-Index entfernen (204).

    404 wenn unbekannt/fremd; 409 wenn die Session noch aktiv ist (zuerst stoppen).
    Das Session-Log im Vault bleibt erhalten.
    """
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)  # PROJ-25: kein Fremd-Löschen.
    try:
        await manager.delete(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session nicht gefunden.") from exc
    except SessionActiveError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{session_id}/constitution", response_model=ConstitutionRead)
async def get_session_constitution(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Effektive Konstitution DIESER Session (PROJ-6, AC: einsehbar)."""
    runtime = _owned_or_404(_manager(request), session_id, user)
    return {
        "role": runtime.state.role,
        "source": runtime.state.constitution_source or "leer",
        "text": runtime.state.effective_constitution,
    }


@router.post("/{session_id}/handover/generate", response_model=HandoverPreview)
async def generate_handover(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Handover-INHALT erzeugen (Vorschau, Hybrid-Gerüst) — schreibt NICHT in den Vault.

    Der zurückgegebene Body geht (ggf. vom Nutzer editiert) an ``POST …/handover``.
    """
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    return manager.generate_handover(session_id)


@router.post("/{session_id}/reset", response_model=SessionRead, status_code=201)
async def reset_session(
    session_id: str, payload: ResetRequest, request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """„Session zurücksetzen": alte Session archivieren, Kind-Session mit dem Handover
    als Seed-Kontext frisch starten (Staffelstab, ``parent_session_id`` verweist zurück).
    """
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
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
async def set_session_threshold(
    session_id: str, payload: ThresholdPatch, request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Pro-Session-Override der Kontext-Schwelle (None = globale Schwelle nutzen)."""
    runtime = _owned_or_404(_manager(request), session_id, user)
    runtime.state.context_threshold_override_pct = (
        clamp_threshold(payload.threshold_pct) if payload.threshold_pct is not None else None
    )
    # Schwelle geändert → Warn-Status kann sich ändern: Snapshot streamen.
    runtime._broadcast({"kind": "state", **runtime.to_read()})
    return runtime.to_read()


@router.post("/{session_id}/handover", response_model=VaultWriteResult, status_code=201)
async def write_handover(
    session_id: str, payload: HandoverRequest, request: Request,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Kuratiertes Handover-Dokument dieser Session in den Vault schreiben (PROJ-2)."""
    runtime = _owned_or_404(_manager(request), session_id, user)
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
async def get_transcript(
    session_id: str, request: Request, user: CurrentUser = Depends(get_current_user)
) -> dict:
    manager = _manager(request)
    _owned_or_404(manager, session_id, user)
    return {"text": manager.transcript_text(session_id)}


# PROJ-49 A1: Keepalive-Intervall (s). Deutlich unter üblichen Proxy/Browser-Idle-
# Timeouts (Caddy/60 s), damit eine stille Phase (langer Tool-Lauf ohne Events) die
# WS nicht idle-gekappt wird. Client ignoriert `{"kind":"ping"}`.
_WS_PING_INTERVAL_S = 20.0


@router.websocket("/{session_id}/stream")
async def stream_session(websocket: WebSocket, session_id: str) -> None:
    import asyncio

    manager: SessionManager = websocket.app.state.manager
    auth = websocket.app.state.auth

    # PROJ-25: Browser-WebSockets können keinen Authorization-Header setzen → der
    # Access-Token reist als Query-Param (?access_token=…). Identität wird auch hier
    # serverseitig aus dem Token aufgelöst und der Stream auf den eigenen owner
    # beschränkt. Vor dem Bootstrap (leere Nutzerbasis) bleibt der Stream offen.
    owner: str | None = None
    if await auth.has_users():
        token = websocket.query_params.get("access_token")
        try:
            owner = auth.resolve_access(token).user_id if token else None
        except AuthError:
            owner = None
        if owner is None:
            await websocket.close(code=4401)  # nicht/ungültig authentifiziert
            return

    runtime = manager.get(session_id)
    # Unbekannt ODER fremd → einheitlich 4404 (kein Existenz-Leak fürs ID-Raten).
    if runtime is None or (owner is not None and runtime.state.owner != owner):
        await websocket.close(code=4404)
        return
    await websocket.accept()
    queue = runtime.subscribe()
    queue_get: asyncio.Task | None = None
    sock_recv: asyncio.Task | None = None
    try:
        # PROJ-49 B: Sofort einen Voll-Snapshot senden — Status + offene Decision
        # Cards (aus `to_read()`) UND das aktuelle Transkript. So ist dieser eine
        # Frame nach JEDEM (Re-)Connect die alleinige Wahrheit; verpasste `message`-
        # Chunks während einer Verbindungslücke führen nicht mehr zu dauerhaft
        # fehlendem UI-Inhalt (verlustfreier Resync ohne Server-Event-Puffer).
        snapshot = {"kind": "state", **runtime.to_read()}
        snapshot["transcript"] = [vars(e) for e in runtime.transcript]
        await websocket.send_json(snapshot)
        # Tasks EINMAL anlegen und über Iterationen hinweg halten — so kann ein
        # Keepalive-Timeout feuern, ohne ein laufendes receive() zu zerschneiden.
        queue_get = asyncio.ensure_future(queue.get())
        sock_recv = asyncio.ensure_future(websocket.receive())
        while True:
            # Auf das nächste Event ODER eine Socket-Aktion (Disconnect) warten —
            # mit Timeout, damit eine stille Phase einen Keepalive-Ping auslöst.
            done, _pending = await asyncio.wait(
                {queue_get, sock_recv},
                timeout=_WS_PING_INTERVAL_S,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                # PROJ-49 A1: stille Phase → Ping, damit Proxy/Browser nicht kappen.
                await websocket.send_json({"kind": "ping"})
                continue
            if sock_recv in done:
                msg = sock_recv.result()  # kann WebSocketDisconnect werfen
                if msg.get("type") == "websocket.disconnect":
                    break
                # Client-Eingaben laufen im MVP über REST → ignorieren, neu lauschen.
                sock_recv = asyncio.ensure_future(websocket.receive())
            if queue_get in done:
                await websocket.send_json(queue_get.result())
                queue_get = asyncio.ensure_future(queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        runtime.unsubscribe(queue)
        for task in (queue_get, sock_recv):
            if task is not None and not task.done():
                task.cancel()
