"""Peppermint Dashboard API (PROJ-67)."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request

from ..config import settings
from ..engine.peppermint import PeppermintTriageWorker
from ..schemas.peppermint import (
    PeppermintProjectOptionsRead,
    PeppermintResolutionSessionRequest,
    PeppermintSettingsPatch,
    PeppermintSettingsRead,
    PeppermintStatusRead,
    PeppermintSummaryRead,
    PeppermintTicketIgnoreRequest,
    PeppermintTicketListRead,
    PeppermintTicketPatch,
    PeppermintTicketRead,
    PeppermintWebhookEvent,
)

router = APIRouter(prefix="/peppermint", tags=["peppermint"])
webhook_router = APIRouter(prefix="/peppermint", tags=["peppermint"])


def _worker(request: Request) -> PeppermintTriageWorker:
    return request.app.state.peppermint


def _public_settings(cfg: dict) -> dict:
    return {
        "base_url": cfg.get("base_url"),
        "active": bool(cfg.get("active")),
        "polling_interval_seconds": int(cfg.get("polling_interval_seconds") or 60),
        "webhook_secret_set": bool(cfg.get("webhook_secret") or settings.peppermint_webhook_secret),
        "login_configured": bool(settings.peppermint_login_email and settings.peppermint_login_password),
        "token_configured": bool(cfg.get("api_token") or settings.peppermint_token),
        "last_poll_at": cfg.get("last_poll_at"),
        "last_successful_poll_at": cfg.get("last_successful_poll_at"),
        "last_error": cfg.get("last_error"),
    }


@router.get("/status", response_model=PeppermintStatusRead)
async def status(request: Request) -> dict:
    worker = _worker(request)
    cfg = await worker.get_settings()
    return {
        "active": bool(cfg.get("active")),
        "worker_status": worker.state()["status"],
        "current_ticket_id": worker.state()["current_ticket_id"],
        "last_poll_at": cfg.get("last_poll_at"),
        "last_successful_poll_at": cfg.get("last_successful_poll_at"),
        "last_error": cfg.get("last_error"),
        "login_configured": bool(settings.peppermint_login_email and settings.peppermint_login_password),
        "token_configured": bool(cfg.get("api_token") or settings.peppermint_token),
    }


@router.get("/tickets", response_model=PeppermintTicketListRead)
async def list_tickets(
    request: Request,
    analysis_status: str | None = None,
    urgency: str | None = None,
    status: str | None = None,
    project_path: str | None = None,
    manual_priority: str | None = None,
    manual_type: str | None = None,
    manual_status: str | None = None,
    include_hidden: bool = False,
    include_ignored: bool = False,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    items = await _worker(request).list_tickets(
        {
            "analysis_status": analysis_status,
            "urgency": urgency,
            "status": status,
            "project_path": project_path,
            "manual_priority": manual_priority,
            "manual_type": manual_type,
            "manual_status": manual_status,
            "include_hidden": include_hidden,
            "include_ignored": include_ignored,
            "q": q,
        },
        limit,
    )
    return {"items": items}


@router.get("/tickets/{item_id}", response_model=PeppermintTicketRead)
async def ticket_detail(request: Request, item_id: int) -> dict:
    row = await _worker(request).get_ticket(item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.")
    return row


@router.patch("/tickets/{item_id}", response_model=PeppermintTicketRead)
async def patch_ticket(request: Request, item_id: int, payload: PeppermintTicketPatch) -> dict:
    try:
        return await _worker(request).patch_ticket(item_id, payload.model_dump(exclude_unset=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tickets/{item_id}/hide", response_model=PeppermintTicketRead)
async def hide_ticket(request: Request, item_id: int) -> dict:
    try:
        return await _worker(request).set_hidden(item_id, True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc


@router.post("/tickets/{item_id}/unhide", response_model=PeppermintTicketRead)
async def unhide_ticket(request: Request, item_id: int) -> dict:
    try:
        return await _worker(request).set_hidden(item_id, False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc


@router.post("/tickets/{item_id}/ignore", response_model=PeppermintTicketRead)
async def ignore_ticket(request: Request, item_id: int, payload: PeppermintTicketIgnoreRequest | None = None) -> dict:
    try:
        return await _worker(request).set_ignored(item_id, True, payload.reason if payload else None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc


@router.post("/tickets/{item_id}/restore", response_model=PeppermintTicketRead)
async def restore_ticket(request: Request, item_id: int) -> dict:
    try:
        return await _worker(request).set_ignored(item_id, False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc


@router.post("/tickets/{item_id}/resolution-session", response_model=PeppermintTicketRead)
async def start_resolution_session(
    request: Request, item_id: int, payload: PeppermintResolutionSessionRequest | None = None
) -> dict:
    try:
        return await _worker(request).start_resolution_session(item_id, force=bool(payload and payload.force))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Lösungs-Session konnte nicht gestartet werden: {exc}") from exc


@router.get("/project-options", response_model=PeppermintProjectOptionsRead)
async def project_options(request: Request) -> dict:
    return {"items": await _worker(request).project_options()}


@router.get("/summary", response_model=PeppermintSummaryRead)
async def summary(request: Request) -> dict:
    return await _worker(request).summary()


@router.post("/tickets/{item_id}/analyze", response_model=PeppermintTicketRead)
async def retry_analysis(request: Request, item_id: int) -> dict:
    try:
        return await _worker(request).retry_analysis(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc


@router.post("/tickets/{item_id}/sync-note", response_model=PeppermintTicketRead)
async def retry_note_sync(request: Request, item_id: int) -> dict:
    try:
        return await _worker(request).retry_note_sync(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Ticket nicht gefunden.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/poll-now", response_model=PeppermintTicketListRead)
async def poll_now(request: Request) -> dict:
    try:
        result = await _worker(request).poll_now()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Peppermint-Sync fehlgeschlagen: {exc}") from exc
    return {"items": result["items"]}


@router.get("/settings", response_model=PeppermintSettingsRead)
async def get_settings(request: Request) -> dict:
    return _public_settings(await _worker(request).get_settings())


@router.patch("/settings", response_model=PeppermintSettingsRead)
async def patch_settings(request: Request, payload: PeppermintSettingsPatch) -> dict:
    fields: dict = {}
    if payload.base_url is not None:
        fields["base_url"] = payload.base_url.rstrip("/") + "/"
    if payload.active is not None:
        fields["active"] = 1 if payload.active else 0
    if payload.polling_interval_seconds is not None:
        fields["polling_interval_seconds"] = payload.polling_interval_seconds
    if payload.webhook_secret is not None:
        fields["webhook_secret"] = payload.webhook_secret
    if payload.api_token is not None:
        fields["api_token"] = payload.api_token
    cfg = await _worker(request).save_settings(fields)
    return _public_settings(cfg)


@webhook_router.post("/webhook")
async def webhook(
    request: Request,
    payload: PeppermintWebhookEvent,
    x_peppermint_secret: str | None = Header(None),
    authorization: str | None = Header(None),
) -> dict:
    worker = _worker(request)
    cfg = await worker.get_settings()
    expected = cfg.get("webhook_secret") or settings.peppermint_webhook_secret
    provided = x_peppermint_secret or (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook-Secret ist nicht konfiguriert.")
    if expected and provided != expected:
        raise HTTPException(status_code=403, detail="Ungültiges Webhook-Secret.")
    raw = payload.ticket or {}
    ticket_id = raw.get("id") or payload.ticket_id or payload.id
    if not ticket_id:
        raise HTTPException(status_code=400, detail="Webhook enthält keine Ticket-ID.")
    if raw:
        row = await worker.ingest_ticket(worker.client_for(cfg).normalize_ticket(raw))
    else:
        ticket = await worker.client_for(cfg).get_ticket(str(ticket_id))
        if ticket is None:
            raise HTTPException(status_code=404, detail="Peppermint-Ticket nicht abrufbar.")
        row = await worker.ingest_ticket(ticket)
    return {"ok": True, "ticket_id": row["id"]}
