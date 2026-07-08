"""PROJ-67 — Peppermint Dashboard Backend."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.config import settings
from app.db.peppermint_queue import ANALYZED, SqlitePeppermintRepository
from app.engine.peppermint import PeppermintClient, parse_frontdesk_result, save_frontdesk_report
from app.main import _peppermint_loop_interval, create_app

from .fakes import FakeDriver


def test_parse_frontdesk_result_reads_required_fields():
    result = parse_frontdesk_result(
        "Text\nJUPITER_FRONTDESK_RESULT\n"
        "kurzbefund: Login kaputt\n"
        "eingrenzung: Backend/Auth\n"
        "dringlichkeit: Hoch\n"
        "antwortentwurf: Wir pruefen das.\n"
        "rueckfragen: Screenshot fehlt\n"
    )
    assert result["short_finding"] == "Login kaputt"
    assert result["scope_hint"] == "Backend/Auth"
    assert result["urgency"] == "Hoch"
    assert result["customer_reply_draft"] == "Wir pruefen das."
    assert result["missing_info_guidance"] == "Screenshot fehlt"


def test_peppermint_client_normalizes_frontend_ticket_shape():
    client = PeppermintClient("http://100.125.96.77:3009/")
    row = client.normalize_ticket({
        "id": 123,
        "title": "Kann mich nicht anmelden",
        "description": "Login endet mit Fehler.",
        "client": {"name": "Max", "email": "max@example.test"},
        "status": "open",
        "priority": "high",
    })
    assert row["peppermint_ticket_id"] == "123"
    assert row["requester_name"] == "Max"
    assert row["ticket_url"].endswith("/issue/123")
    assert "Login endet" in row["raw_content"]


def test_save_frontdesk_report_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_frontdesk_report_dir", str(tmp_path / "frontdesk-check"))
    path = save_frontdesk_report(
        {
            "peppermint_ticket_id": "abc-123",
            "title": "Login geht nicht",
            "status": "needs_support",
            "priority": "high",
            "requester_name": "Max",
            "requester_email": "max@example.test",
            "ticket_url": "http://peppermint/issue/abc-123",
        },
        {
            "short_finding": "Loginproblem",
            "scope_hint": "Backend/Auth",
            "urgency": "Hoch",
            "customer_reply_draft": "Wir pruefen das.",
            "missing_info_guidance": "Bitte Screenshot senden.",
            "report_text": "Volltext",
        },
    )
    assert path.endswith(".md")
    text = (tmp_path / "frontdesk-check").joinpath(path.split("/")[-1]).read_text(encoding="utf-8")
    assert "Frontdesk-Check: Login geht nicht" in text
    assert "Loginproblem" in text
    assert "Peppermint-ID: `abc-123`" in text


async def test_repository_deduplicates_by_peppermint_ticket_id(tmp_path):
    repo = SqlitePeppermintRepository(str(tmp_path / "peppermint.db"))
    await repo.init()
    first = await repo.upsert_ticket(
        {"peppermint_ticket_id": "p-1", "title": "Alt", "description": "A"},
        "2026-07-07T10:00:00",
        "dev",
    )
    second = await repo.upsert_ticket(
        {"peppermint_ticket_id": "p-1", "title": "Neu", "description": "B"},
        "2026-07-07T10:05:00",
        "dev",
    )
    rows = await repo.list_tickets()
    assert first["id"] == second["id"]
    assert len(rows) == 1
    assert rows[0]["title"] == "Neu"
    assert rows[0]["analysis_status"] == "neu"


def test_api_settings_do_not_expose_secret(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    monkeypatch.setattr(settings, "peppermint_login_email", "agent@example.test")
    monkeypatch.setattr(settings, "peppermint_login_password", "super-secret")
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        r = client.patch(
            "/peppermint/settings",
            json={
                "active": True,
                "webhook_secret": "hook-secret",
                "api_token": "peppermint-token-secret",
                "polling_interval_seconds": 30,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["active"] is True
        assert body["webhook_secret_set"] is True
        assert body["login_configured"] is True
        assert body["token_configured"] is True
        assert "hook-secret" not in str(body)
        assert "peppermint-token-secret" not in str(body)
        assert "super-secret" not in str(body)


def test_webhook_rejects_wrong_secret_and_ingests_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        client.patch("/peppermint/settings", json={"webhook_secret": "ok"})
        bad = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "nope"},
            json={"ticket": {"id": 77, "title": "Webhook Ticket", "description": "Text"}},
        )
        assert bad.status_code == 403

        good = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 77, "title": "Webhook Ticket", "description": "Text"}},
        )
        assert good.status_code == 200
        tickets = client.get("/peppermint/tickets").json()["items"]
        assert len(tickets) == 1
        assert tickets[0]["peppermint_ticket_id"] == "77"

        duplicate = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 77, "title": "Webhook Ticket aktualisiert", "description": "Text 2"}},
        )
        assert duplicate.status_code == 200
        tickets = client.get("/peppermint/tickets").json()["items"]
        assert len(tickets) == 1
        assert tickets[0]["title"] == "Webhook Ticket aktualisiert"


def test_sync_note_retry_requires_analyzed_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        client.patch("/peppermint/settings", json={"webhook_secret": "ok"})
        good = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 88, "title": "Noch nicht analysiert", "description": "Text"}},
        )
        assert good.status_code == 200
        item_id = good.json()["ticket_id"]

        retry = client.post(f"/peppermint/tickets/{item_id}/sync-note")
        assert retry.status_code == 409
        assert "Nur analysierte Tickets" in retry.json()["detail"]


def test_proj68_patch_filter_hide_ignore_and_tombstone(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        client.patch("/peppermint/settings", json={"webhook_secret": "ok"})
        created = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 91, "title": "Interner Test", "description": "Nicht relevant"}},
        )
        assert created.status_code == 200
        item_id = created.json()["ticket_id"]

        patched = client.patch(
            f"/peppermint/tickets/{item_id}",
            json={
                "project_path": "/home/dev/projects/jupiter",
                "manual_priority": "high",
                "manual_type": "incident",
                "manual_status": "open",
            },
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["project_path"] == "/home/dev/projects/jupiter"
        assert body["project_label"] == "jupiter"
        assert body["manual_priority"] == "high"
        assert body["manual_type"] == "incident"
        assert body["manual_status"] == "open"

        assert len(client.get("/peppermint/tickets?manual_priority=high").json()["items"]) == 1
        assert len(client.get("/peppermint/tickets?manual_type=incident&manual_status=open").json()["items"]) == 1
        assert len(client.get("/peppermint/tickets?q=hoch").json()["items"]) == 1

        hidden = client.post(f"/peppermint/tickets/{item_id}/hide")
        assert hidden.status_code == 200
        assert hidden.json()["hidden_at"]
        assert client.get("/peppermint/tickets").json()["items"] == []
        assert len(client.get("/peppermint/tickets?include_hidden=true").json()["items"]) == 1

        assert client.post(f"/peppermint/tickets/{item_id}/unhide").status_code == 200
        ignored = client.post(f"/peppermint/tickets/{item_id}/ignore", json={"reason": "Kein Ticket"})
        assert ignored.status_code == 200
        assert ignored.json()["ignored_at"]
        assert ignored.json()["ignored_reason"] == "Kein Ticket"
        assert client.get("/peppermint/tickets").json()["items"] == []
        assert len(client.get("/peppermint/tickets?include_ignored=true").json()["items"]) == 1

        duplicate = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 91, "title": "Interner Test aktualisiert", "description": "Text 2"}},
        )
        assert duplicate.status_code == 200
        assert client.get("/peppermint/tickets").json()["items"] == []
        ignored_items = client.get("/peppermint/tickets?include_ignored=true").json()["items"]
        assert ignored_items[0]["title"] == "Interner Test aktualisiert"
        assert ignored_items[0]["ignored_at"]


def test_proj68_resolution_session_and_project_options(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        options = client.get("/peppermint/project-options")
        assert options.status_code == 200
        assert any(item["project_path"] == "/home/dev/projects/jupiter" for item in options.json()["items"])

        client.patch("/peppermint/settings", json={"webhook_secret": "ok"})
        created = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 92, "title": "Kundenticket", "description": "Bitte lösen"}},
        )
        assert created.status_code == 200
        item_id = created.json()["ticket_id"]

        too_early = client.post(f"/peppermint/tickets/{item_id}/resolution-session")
        assert too_early.status_code == 409
        assert "erst nach erfolgreicher Analyse" in too_early.json()["detail"]

        asyncio.run(app.state.peppermint._repo.update_ticket(  # noqa: SLF001
            item_id,
            analysis_status=ANALYZED,
            report_text="Ticketnummer 92: Problem ist reproduzierbar.",
            short_finding="Problem ist reproduzierbar.",
            manual_priority="urgent",
            manual_type="problem",
            manual_status="open",
            project_path="/home/dev/projects/jupiter",
            project_label="Jupiter",
        ))
        started = client.post(f"/peppermint/tickets/{item_id}/resolution-session")
        assert started.status_code == 200
        body = started.json()
        assert body["resolution_session_id"]
        sessions = client.get("/sessions").json()
        assert any(session["session_id"] == body["resolution_session_id"] for session in sessions)


def test_proj68_resolution_session_force_starts_additional_session(tmp_path, monkeypatch):
    """BUG-1-Fix: bei aktiver verknüpfter Session bleibt der Default ein Reuse, aber
    ``force=true`` startet bewusst eine weitere, neue Session statt das Ticket
    dauerhaft an die erste Session zu binden."""
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        client.patch("/peppermint/settings", json={"webhook_secret": "ok"})
        created = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 93, "title": "Zweite Session", "description": "Bitte lösen"}},
        )
        item_id = created.json()["ticket_id"]
        asyncio.run(app.state.peppermint._repo.update_ticket(  # noqa: SLF001
            item_id,
            analysis_status=ANALYZED,
            report_text="Ticketnummer 93: Problem.",
            project_path="/home/dev/projects/jupiter",
        ))

        first = client.post(f"/peppermint/tickets/{item_id}/resolution-session")
        assert first.status_code == 200
        first_session_id = first.json()["resolution_session_id"]

        reuse = client.post(f"/peppermint/tickets/{item_id}/resolution-session")
        assert reuse.status_code == 200
        assert reuse.json()["resolution_session_id"] == first_session_id

        forced = client.post(f"/peppermint/tickets/{item_id}/resolution-session", json={"force": True})
        assert forced.status_code == 200
        forced_session_id = forced.json()["resolution_session_id"]
        assert forced_session_id != first_session_id

        sessions = {s["session_id"] for s in client.get("/sessions").json()}
        assert {first_session_id, forced_session_id} <= sessions


def test_proj68_missing_peppermint_ticket_is_flagged_and_cleared(tmp_path, monkeypatch):
    """BUG-2-Fix: verschwindet ein Ticket aus dem Peppermint-Poll und ist auch per
    Einzelabfrage nicht mehr abrufbar, wird ``peppermint_missing_at`` gesetzt; taucht
    es wieder auf, wird das Flag beim nächsten Sync automatisch wieder gelöscht."""
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as client:
        client.patch("/peppermint/settings", json={"webhook_secret": "ok"})
        created = client.post(
            "/peppermint/webhook",
            headers={"x-peppermint-secret": "ok"},
            json={"ticket": {"id": 94, "title": "Verschwundenes Ticket", "description": "Text"}},
        )
        item_id = created.json()["ticket_id"]

        class _FakeClientGone:
            async def list_open_tickets(self):
                return []

            async def get_ticket(self, ticket_id):
                return None

        worker = app.state.peppermint
        monkeypatch.setattr(worker, "client_for", lambda cfg=None: _FakeClientGone())
        asyncio.run(worker.poll_now())

        row = client.get(f"/peppermint/tickets/{item_id}").json()
        assert row["peppermint_missing_at"]

        class _FakeClientBack:
            async def list_open_tickets(self):
                return [{
                    "peppermint_ticket_id": "94",
                    "title": "Verschwundenes Ticket wieder da",
                    "description": "Text",
                }]

            async def get_ticket(self, ticket_id):
                return None

        monkeypatch.setattr(worker, "client_for", lambda cfg=None: _FakeClientBack())
        asyncio.run(worker.poll_now())

        row = client.get(f"/peppermint/tickets/{item_id}").json()
        assert row["peppermint_missing_at"] is None
        assert row["title"] == "Verschwundenes Ticket wieder da"


async def test_peppermint_loop_interval_reads_persisted_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "peppermint_db_path", str(tmp_path / "peppermint.db"))
    app = create_app(driver_factory=lambda: FakeDriver())
    await app.state.peppermint.startup()
    await app.state.peppermint.save_settings({"polling_interval_seconds": 123})

    assert await _peppermint_loop_interval(app) == 123.0
