"""Peppermint-Integration + Frontdesk-Triage-Worker (PROJ-67)."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx

from ..config import settings
from ..db.peppermint_queue import (
    ANALYZED, ERROR, NEW, NOTE_ERROR, NOTE_NOT_NEEDED, NOTE_PENDING, NOTE_SYNCED,
    RUNNING, WAITING, PeppermintRepository,
)
from .manager import (
    ACTIVE_STATES,
    DONE as SESSION_DONE,
    ERROR as SESSION_ERROR,
    WAITING as SESSION_WAITING,
    SessionLimitError,
    SessionManager,
    validate_project_path,
)

logger = logging.getLogger(__name__)

DEFAULT_RESOLUTION_PROJECT = "/home/dev/projects/jupiter"
PEPPERMINT_MISSING_CHECK_BATCH = 5
PRIORITY_LABELS = {"low": "Niedrig", "medium": "Mittel", "high": "Hoch", "urgent": "Dringend"}
TYPE_LABELS = {
    "question": "Frage",
    "incident": "Incident",
    "problem": "Problem",
    "feature_request": "Feature Request",
    "other": "Sonstiges",
}
STATUS_LABELS = {
    "open": "Offen",
    "assigned": "Zugewiesen",
    "on_hold": "On Hold",
    "resolved": "Gelöst",
    "closed": "Geschlossen",
}


def _now() -> str:
    return datetime.now().isoformat()


def build_triage_prompt(row: dict) -> str:
    return (
        "/abc-frontdesk-check\n\n"
        "Analysiere dieses Peppermint-Support-Ticket. Keine Codeaenderungen, keine Rueckfragen, "
        "nur Frontdesk-Triage. Gib am Ende einen maschinenlesbaren Block aus.\n\n"
        f"Peppermint-ID: {row.get('peppermint_ticket_id')}\n"
        f"Betreff: {row.get('title') or ''}\n"
        f"Kunde: {row.get('requester_name') or ''} <{row.get('requester_email') or ''}>\n"
        f"Status: {row.get('status') or ''}\n"
        f"Prioritaet: {row.get('priority') or ''}\n\n"
        "Rohinhalt:\n"
        f"{row.get('raw_content') or row.get('description') or ''}\n\n"
        "Abschlussformat exakt:\n"
        "JUPITER_FRONTDESK_RESULT\n"
        "kurzbefund: <ein Satz>\n"
        "eingrenzung: <Frontend/Backend/DB/Modul oder leer>\n"
        "dringlichkeit: <Niedrig|Mittel|Hoch|Dringend>\n"
        "antwortentwurf: <deutscher Antwortentwurf>\n"
        "rueckfragen: <fehlende Informationen oder keine>\n"
    )


def build_resolution_prompt(row: dict) -> str:
    report = row.get("report_text") or ""
    if len(report) > 12000:
        report = report[:12000].rstrip() + "\n\n[Report gekürzt: vollständiger Report im Peppermint Dashboard.]"
    return (
        "Löse dieses analysierte Peppermint-Ticket oder erarbeite den nächsten konkret "
        "umsetzbaren Schritt. Beziehe dich ausdrücklich auf die Ticketnummer aus dem "
        "Analyse-Report.\n\n"
        f"Peppermint-Ticket-ID: {row.get('peppermint_ticket_id')}\n"
        f"Jupiter-Ticket-Datensatz: {row.get('id')}\n"
        f"Betreff: {row.get('title') or '-'}\n"
        f"Kunde: {row.get('requester_name') or '-'} <{row.get('requester_email') or '-'}>\n"
        f"Peppermint-Link: {row.get('ticket_url') or '-'}\n"
        f"Projekt: {row.get('project_label') or row.get('project_path') or '-'}\n"
        f"Priorität: {_label(PRIORITY_LABELS, row.get('manual_priority'))}\n"
        f"Typ: {_label(TYPE_LABELS, row.get('manual_type'))}\n"
        f"Status: {_label(STATUS_LABELS, row.get('manual_status'))}\n\n"
        "Frontdesk-Report:\n"
        f"{report or row.get('short_finding') or '-'}\n\n"
        "Arbeite pragmatisch: prüfe zuerst den Projektkontext, identifiziere die betroffenen "
        "Dateien oder Systeme und liefere eine umsetzbare Lösung bzw. einen klaren nächsten Schritt."
    )


def parse_frontdesk_result(text: str) -> dict:
    tail = text[text.rfind("JUPITER_FRONTDESK_RESULT"):] if "JUPITER_FRONTDESK_RESULT" in text else text

    def field(name: str) -> str | None:
        m = re.search(rf"^\s*(?:{name})\s*:\s*(.+?)\s*$", tail, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None

    return {
        "short_finding": field("kurzbefund"),
        "scope_hint": field("eingrenzung"),
        "urgency": field("dringlichkeit"),
        "customer_reply_draft": field("antwortentwurf"),
        "missing_info_guidance": field("rueckfragen|rückfragen"),
        "report_text": text.strip(),
    }


def _label(labels: dict[str, str], value: str | None) -> str:
    return labels.get(value or "", value or "-")


def _candidate_project_roots() -> list[str]:
    roots: list[str] = []
    for root in settings.allowed_roots:
        real = os.path.realpath(root)
        if real == "/home/dev":
            roots.extend([os.path.realpath("/home/dev/projects"), os.path.realpath("/home/dev/tools")])
        else:
            roots.append(real)
    return list(dict.fromkeys(roots))


def format_internal_note(row: dict) -> str:
    return (
        "Interne Jupiter-Frontdesk-Triage\n\n"
        f"Kurzbefund: {row.get('short_finding') or '-'}\n"
        f"Eingrenzung: {row.get('scope_hint') or '-'}\n"
        f"Dringlichkeit: {row.get('urgency') or '-'}\n\n"
        "Antwortentwurf an den Kunden:\n"
        f"{row.get('customer_reply_draft') or '-'}\n\n"
        "Rückfragen-Guidance:\n"
        f"{row.get('missing_info_guidance') or '-'}"
    )


def save_frontdesk_report(row: dict, result: dict) -> str:
    """Persistiert den fertigen Frontdesk-Report als Markdown-Artefakt."""
    out_dir = Path(settings.peppermint_frontdesk_report_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ticket_id = str(row.get("peppermint_ticket_id") or row.get("id") or "ticket")
    title = str(row.get("title") or "ticket")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{stamp}-{_slug(ticket_id)}-{_slug(title)[:80]}.md"
    path = out_dir / filename
    content = (
        "---\n"
        f"peppermint_ticket_id: \"{ticket_id}\"\n"
        f"title: \"{_yaml_escape(title)}\"\n"
        f"created: \"{datetime.now().isoformat()}\"\n"
        "---\n\n"
        f"# Frontdesk-Check: {title}\n\n"
        "## Ticket\n\n"
        f"- Peppermint-ID: `{ticket_id}`\n"
        f"- Status: {row.get('status') or '-'}\n"
        f"- Priorität: {row.get('priority') or '-'}\n"
        f"- Kunde: {row.get('requester_name') or '-'} <{row.get('requester_email') or '-'}>\n"
        f"- Link: {row.get('ticket_url') or '-'}\n\n"
        "## Kurzbefund\n\n"
        f"{result.get('short_finding') or '-'}\n\n"
        "## Eingrenzung\n\n"
        f"{result.get('scope_hint') or '-'}\n\n"
        "## Dringlichkeit\n\n"
        f"{result.get('urgency') or '-'}\n\n"
        "## Antwortentwurf\n\n"
        f"{result.get('customer_reply_draft') or '-'}\n\n"
        "## Rückfragen-Guidance\n\n"
        f"{result.get('missing_info_guidance') or '-'}\n\n"
        "## Vollständiger Report\n\n"
        f"{result.get('report_text') or '-'}\n"
    )
    path.write_text(content, encoding="utf-8")
    return str(path)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return slug or "ticket"


def _yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class PeppermintClient:
    def __init__(self, base_url: str, token: str = "", email: str = "", password: str = "") -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self._token = token
        self._email = email
        self._password = password

    async def _auth_headers(self) -> dict[str, str]:
        token = self._token or await self._login()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _login(self) -> str:
        if not self._email or not self._password:
            raise RuntimeError("Peppermint-Login ist nicht konfiguriert.")
        async with httpx.AsyncClient(timeout=settings.peppermint_request_timeout_seconds) as client:
            resp = await client.post(
                urljoin(self.base_url, "api/v1/auth/login"),
                json={"email": self._email, "password": self._password},
            )
            resp.raise_for_status()
            data = resp.json()
        token = data.get("token")
        if not token:
            raise RuntimeError("Peppermint-Login lieferte keinen Token.")
        self._token = token
        return token

    async def test_connection(self) -> dict:
        async with httpx.AsyncClient(timeout=settings.peppermint_request_timeout_seconds) as client:
            resp = await client.get(urljoin(self.base_url, "api/v1/auth/profile"), headers=await self._auth_headers())
        return {"ok": resp.status_code == 200, "status_code": resp.status_code}

    async def list_open_tickets(self) -> list[dict]:
        paths = ("api/v1/tickets/all", "api/v1/tickets/open")
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=settings.peppermint_request_timeout_seconds) as client:
            for path in paths:
                try:
                    resp = await client.get(urljoin(self.base_url, path), headers=await self._auth_headers())
                    resp.raise_for_status()
                    data = resp.json()
                    raw = data.get("tickets") if isinstance(data, dict) else data
                    return [self.normalize_ticket(t) for t in (raw or [])]
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
        raise RuntimeError(f"Peppermint-Tickets konnten nicht geladen werden: {last_error}")

    async def get_ticket(self, ticket_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=settings.peppermint_request_timeout_seconds) as client:
            for path in (f"api/v1/ticket/{ticket_id}", f"api/v1/tickets/{ticket_id}"):
                resp = await client.get(urljoin(self.base_url, path), headers=await self._auth_headers())
                if resp.status_code == 200:
                    data = resp.json()
                    return self.normalize_ticket(data.get("ticket") if isinstance(data, dict) else data)
        return None

    async def write_internal_note(self, ticket_id: str, text: str) -> None:
        payloads = (
            ("api/v1/ticket/comment", {"ticketId": ticket_id, "text": text, "comment": text, "internal": True}),
            (f"api/v1/ticket/{ticket_id}/comment", {"text": text, "comment": text, "internal": True}),
        )
        async with httpx.AsyncClient(timeout=settings.peppermint_request_timeout_seconds) as client:
            last = None
            for path, payload in payloads:
                resp = await client.post(urljoin(self.base_url, path), headers=await self._auth_headers(), json=payload)
                if resp.status_code < 400:
                    return
                last = resp.text
        raise RuntimeError(f"Interne Peppermint-Notiz konnte nicht geschrieben werden: {last}")

    def normalize_ticket(self, raw: dict[str, Any]) -> dict:
        ticket_id = raw.get("id") or raw.get("_id") or raw.get("ticket_id")
        client = raw.get("client") or raw.get("requester") or raw.get("user") or {}
        title = raw.get("title") or raw.get("name") or raw.get("summary") or f"Ticket {ticket_id}"
        description = raw.get("description") or raw.get("detail") or raw.get("details") or raw.get("body") or ""
        return {
            "peppermint_ticket_id": str(ticket_id),
            "title": str(title),
            "description": str(description or ""),
            "requester_name": raw.get("name") or client.get("name"),
            "requester_email": raw.get("email") or client.get("email"),
            "status": raw.get("status"),
            "priority": raw.get("priority"),
            "labels": raw.get("labels") or [],
            "ticket_url": urljoin(self.base_url, f"issue/{ticket_id}"),
            "raw": raw,
            "raw_content": _raw_content(raw),
            "peppermint_created_at": raw.get("createdAt") or raw.get("created_at"),
            "peppermint_updated_at": raw.get("updatedAt") or raw.get("updated_at"),
        }


def _raw_content(raw: dict) -> str:
    parts = [
        f"Title: {raw.get('title') or raw.get('name') or ''}",
        f"Description: {raw.get('description') or raw.get('detail') or raw.get('details') or raw.get('body') or ''}",
    ]
    comments = raw.get("comments") or []
    if comments:
        parts.append("Comments:")
        for c in comments:
            parts.append(str(c.get("text") or c.get("comment") or c))
    return "\n".join(p for p in parts if p.strip())


class PeppermintTriageWorker:
    def __init__(self, manager: SessionManager, repo: PeppermintRepository) -> None:
        self._manager = manager
        self._repo = repo
        self._current_id: int | None = None
        self._current_session_id: str | None = None
        self._polling = False
        self._syncing = False

    async def startup(self) -> None:
        await self._repo.init()
        await self._repo.reset_running()

    def state(self) -> dict:
        return {"status": "running" if self._current_id else "idle", "current_ticket_id": self._current_id}

    async def get_settings(self) -> dict:
        return await self._repo.get_settings()

    async def save_settings(self, fields: dict) -> dict:
        fields["updated_at"] = _now()
        return await self._repo.save_settings(fields)

    def client_for(self, cfg: dict | None = None) -> PeppermintClient:
        cfg = cfg or {}
        return PeppermintClient(
            cfg.get("base_url") or settings.peppermint_base_url,
            token=cfg.get("api_token") or settings.peppermint_token,
            email=settings.peppermint_login_email,
            password=settings.peppermint_login_password,
        )

    async def list_tickets(self, filters: dict | None = None, limit: int = 200) -> list[dict]:
        return await self._repo.list_tickets(filters, limit)

    async def get_ticket(self, item_id: int) -> dict | None:
        return await self._repo.get_ticket(item_id)

    async def summary(self) -> dict:
        return await self._repo.summary()

    async def patch_ticket(self, item_id: int, fields: dict) -> dict:
        row = await self._repo.get_ticket(item_id)
        if row is None:
            raise KeyError(item_id)
        clean = {k: v for k, v in fields.items() if v is not None}
        if "project_path" in clean:
            if clean["project_path"]:
                clean["project_path"] = validate_project_path(clean["project_path"])
                clean.setdefault("project_label", os.path.basename(clean["project_path"]) or clean["project_path"])
            else:
                clean["project_path"] = None
                clean.setdefault("project_label", None)
        clean["updated_at"] = _now()
        await self._repo.update_ticket(item_id, **clean)
        return await self._repo.get_ticket(item_id)

    async def set_hidden(self, item_id: int, hidden: bool) -> dict:
        row = await self._repo.get_ticket(item_id)
        if row is None:
            raise KeyError(item_id)
        await self._repo.update_ticket(
            item_id,
            hidden_at=_now() if hidden else None,
            updated_at=_now(),
        )
        return await self._repo.get_ticket(item_id)

    async def set_ignored(self, item_id: int, ignored: bool, reason: str | None = None) -> dict:
        row = await self._repo.get_ticket(item_id)
        if row is None:
            raise KeyError(item_id)
        await self._repo.update_ticket(
            item_id,
            ignored_at=_now() if ignored else None,
            ignored_reason=reason if ignored else None,
            ignored_by=settings.default_owner if ignored else None,
            hidden_at=None if not ignored else row.get("hidden_at"),
            updated_at=_now(),
        )
        return await self._repo.get_ticket(item_id)

    async def project_options(self) -> list[dict]:
        seen: dict[str, dict] = {}

        def add(path: str, label: str | None = None) -> None:
            try:
                real = validate_project_path(path)
            except ValueError:
                return
            seen[real] = {
                "label": label or os.path.basename(real) or real,
                "project_path": real,
                "has_abc": os.path.exists(os.path.join(real, "features", "INDEX.md")),
            }

        add(DEFAULT_RESOLUTION_PROJECT, "Jupiter")
        for runtime in self._manager.list():
            add(runtime.state.project_path, runtime.state.project_name)
        for root in _candidate_project_roots():
            if not os.path.isdir(root):
                continue
            try:
                names = sorted(os.listdir(root))[:200]
            except OSError:
                continue
            for name in names:
                path = os.path.join(root, name)
                if not os.path.isdir(path):
                    continue
                if os.path.isdir(os.path.join(path, ".git")) or os.path.exists(os.path.join(path, "features", "INDEX.md")):
                    add(path)
        return sorted(seen.values(), key=lambda item: item["label"].lower())

    async def ingest_ticket(self, ticket: dict) -> dict:
        return await self._repo.upsert_ticket(ticket, _now(), settings.default_owner)

    async def poll_now(self) -> dict:
        cfg = await self._repo.get_settings()
        await self._repo.save_settings({"last_poll_at": _now(), "last_error": None})
        client = self.client_for(cfg)
        tickets = await client.list_open_tickets()
        rows = [await self.ingest_ticket(t) for t in tickets if t.get("peppermint_ticket_id")]
        seen_ids = {t["peppermint_ticket_id"] for t in tickets if t.get("peppermint_ticket_id")}
        try:
            await self._flag_missing_tickets(client, seen_ids)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Peppermint-Missing-Check fehlgeschlagen: %s", exc)
        await self._repo.save_settings({"last_successful_poll_at": _now(), "last_error": None})
        return {"imported": len(rows), "items": rows}

    async def _flag_missing_tickets(self, client: PeppermintClient, seen_ids: set[str]) -> None:
        """Erkennt Tickets, die lokal noch aktiv sind, aber nicht mehr im Peppermint-Poll auftauchen.

        Nur eine gezielte Einzelabfrage (statt „fehlt in der Liste" = „geloescht") verhindert
        Fehlalarme durch Paginierung/Filterung der Peppermint-API.
        """
        candidates = await self._repo.missing_check_candidates(seen_ids, PEPPERMINT_MISSING_CHECK_BATCH)
        for row in candidates:
            try:
                found = await client.get_ticket(row["peppermint_ticket_id"])
            except Exception:  # noqa: BLE001
                continue
            if found is None:
                await self._repo.update_ticket(row["id"], peppermint_missing_at=_now(), updated_at=_now())

    async def retry_analysis(self, item_id: int) -> dict:
        row = await self._repo.get_ticket(item_id)
        if row is None:
            raise KeyError(item_id)
        await self._repo.update_ticket(
            item_id,
            analysis_status=WAITING,
            error_message=None,
            session_id=None,
            retry_count=int(row.get("retry_count") or 0) + 1,
            updated_at=_now(),
        )
        return await self._repo.get_ticket(item_id)

    async def retry_note_sync(self, item_id: int) -> dict:
        row = await self._repo.get_ticket(item_id)
        if row is None:
            raise KeyError(item_id)
        if row["analysis_status"] != ANALYZED:
            raise ValueError("Nur analysierte Tickets können synchronisiert werden.")
        await self._repo.update_ticket(
            item_id,
            note_sync_status=NOTE_PENDING,
            sync_error_message=None,
            sync_retry_count=int(row.get("sync_retry_count") or 0) + 1,
            updated_at=_now(),
        )
        return await self._repo.get_ticket(item_id)

    async def start_resolution_session(self, item_id: int, force: bool = False) -> dict:
        row = await self._repo.get_ticket(item_id)
        if row is None:
            raise KeyError(item_id)
        if row.get("ignored_at"):
            raise ValueError("Ignorierte Tickets können keine Lösungs-Session starten.")
        if row.get("analysis_status") != ANALYZED:
            raise ValueError("Lösungs-Sessions sind erst nach erfolgreicher Analyse verfügbar.")
        old_session_id = row.get("resolution_session_id")
        old_runtime = self._manager.get(old_session_id) if old_session_id else None
        if not force and old_runtime and old_runtime.state.status in ACTIVE_STATES:
            return row
        project_path = row.get("project_path") or DEFAULT_RESOLUTION_PROJECT
        try:
            real_project = validate_project_path(project_path)
            runtime = await self._manager.create(
                project_path=real_project,
                initial_prompt=build_resolution_prompt(row),
                permission_mode=settings.peppermint_resolution_permission_mode,
                owner=settings.default_owner,
                project_name=f"Peppermint {row.get('peppermint_ticket_id')}",
                ticket_id=f"PEPPERMINT-{row.get('peppermint_ticket_id')}",
            )
        except Exception as exc:  # noqa: BLE001
            await self._repo.update_ticket(item_id, resolution_session_error=str(exc), updated_at=_now())
            raise
        await self._repo.update_ticket(
            item_id,
            resolution_session_id=runtime.state.session_id,
            resolution_session_started_at=_now(),
            resolution_session_error=None,
            updated_at=_now(),
        )
        return await self._repo.get_ticket(item_id)

    async def tick(self) -> None:
        cfg = await self._repo.get_settings()
        if int(cfg.get("active") or 0):
            try:
                await self.poll_now()
            except Exception as exc:  # noqa: BLE001
                await self._repo.save_settings({"last_error": str(exc), "last_poll_at": _now()})
                logger.warning("Peppermint-Poll fehlgeschlagen: %s", exc)
        if self._current_id is not None:
            await self._poll_current()
        else:
            row = await self._repo.next_for_analysis()
            if row:
                await self._start_analysis(row)
        await self._sync_next_note()

    async def _start_analysis(self, row: dict) -> None:
        try:
            runtime = await self._manager.create(
                project_path="/home/dev/projects/jupiter",
                initial_prompt=build_triage_prompt(row),
                model=settings.peppermint_analysis_model,
                permission_mode=settings.peppermint_analysis_permission_mode,
                owner=settings.default_owner,
                project_name="Peppermint Frontdesk",
            )
        except SessionLimitError:
            await self._repo.update_ticket(row["id"], analysis_status=WAITING, updated_at=_now())
            return
        except Exception as exc:  # noqa: BLE001
            await self._repo.update_ticket(row["id"], analysis_status=ERROR, error_message=f"Analyse-Start fehlgeschlagen: {exc}", updated_at=_now())
            return
        self._current_id = row["id"]
        self._current_session_id = runtime.state.session_id
        await self._repo.update_ticket(row["id"], analysis_status=RUNNING, session_id=runtime.state.session_id, updated_at=_now())

    async def _poll_current(self) -> None:
        runtime = self._manager.get(self._current_session_id) if self._current_session_id else None
        if runtime is None:
            await self._finish_analysis(False, error="Analyse-Session verloren.")
            return
        if runtime.state.status in (SESSION_WAITING, SESSION_DONE):
            text = "\n".join(e.text for e in runtime.transcript if e.role == "assistant" and e.kind == "text")
            await self._finish_analysis(True, result=parse_frontdesk_result(text))
        elif runtime.state.status == SESSION_ERROR:
            await self._finish_analysis(False, error=runtime.state.error or "Analyse fehlgeschlagen.")

    async def _finish_analysis(self, success: bool, result: dict | None = None, error: str | None = None) -> None:
        item_id = self._current_id
        if item_id is None:
            return
        if success:
            report_path = None
            if result:
                try:
                    report_path = await asyncio.to_thread(save_frontdesk_report, await self._repo.get_ticket(item_id), result)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Peppermint-Frontdesk-Report konnte nicht gespeichert werden: %s", exc)
            await self._repo.update_ticket(
                item_id,
                analysis_status=ANALYZED,
                note_sync_status=NOTE_PENDING,
                analyzed_at=_now(),
                updated_at=_now(),
                **(result or {}),
            )
        else:
            await self._repo.update_ticket(item_id, analysis_status=ERROR, error_message=error, updated_at=_now())
        if self._current_session_id:
            try:
                await self._manager.stop(self._current_session_id)
            except Exception:  # noqa: BLE001
                pass
        self._current_id = None
        self._current_session_id = None

    async def _sync_next_note(self) -> None:
        if self._syncing:
            return
        row = await self._repo.next_for_note_sync()
        if not row:
            return
        self._syncing = True
        try:
            await self.client_for(await self._repo.get_settings()).write_internal_note(
                row["peppermint_ticket_id"], format_internal_note(row)
            )
            await self._repo.update_ticket(row["id"], note_sync_status=NOTE_SYNCED, sync_error_message=None, note_synced_at=_now(), updated_at=_now())
        except Exception as exc:  # noqa: BLE001
            await self._repo.update_ticket(row["id"], note_sync_status=NOTE_ERROR, sync_error_message=str(exc), updated_at=_now())
        finally:
            self._syncing = False
