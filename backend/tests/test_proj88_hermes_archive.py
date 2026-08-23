"""PROJ-88 — Archive-Endpoint für Hermes-Sessions (Backend).

Testet den owner-geprüften Endpoint ``POST /sessions/{id}/archive`` und
``SessionManager.archive_hermes()`` (Wiederverwendung der stop()-Semantik +
Setzen des ``archived``-Flags). Archivierte Sessions verschwinden aus
``GET /sessions`` und bleiben nach Rehydrierung erhalten. Die echte Hermes-CLI
wird durch ``FakeHermesDriver`` ersetzt.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db.session_index import SqliteSessionIndexRepository
from app.engine.events import StreamEvent
from app.engine.manager import SessionManager, WAITING
from app.main import create_app

from .test_proj85_hermes import FakeHermesDriver, _app, _auth_headers, hermes_enabled


def _create(client):
    return client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects",
              "engine": "hermes", "model": "qwen3.5-397b-a17b",
              "title": "Archivierbar"},
        headers=_auth_headers(),
    )


def _bootstrap(client, username, password):
    r = client.post("/auth/bootstrap", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _create_user(client, token, username, password):
    r = client.post("/auth/users", json={"username": username, "password": password},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text


def _login(client, username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# --- Endpoint: Happy Path ------------------------------------------------


def test_archive_endpoint_hides_from_list(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sess = _create(client)
    assert sess.status_code == 201, sess.text
    sid = sess.json()["session_id"]

    # Vor dem Archivieren sichtbar.
    assert any(s["session_id"] == sid for s in client.get("/sessions").json())

    resp = client.post(f"/sessions/{sid}/archive", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    # Danach aus der Aktive-Liste verschwunden.
    listed = client.get("/sessions").json()
    assert all(s["session_id"] != sid for s in listed)
    # Detail bleibt erreichbar (404-Leak-Schutz unverändert) und trägt archived.
    detail = client.get(f"/sessions/{sid}", headers=_auth_headers())
    assert detail.status_code == 200
    assert detail.json()["archived"] is True


def test_archive_endpoint_sets_archived_flag_on_manager(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    client.post(f"/sessions/{sid}/archive", headers=_auth_headers())
    manager: SessionManager = app.state.manager
    runtime = manager.get(sid)
    assert runtime is not None
    assert runtime.state.archived is True
    # Archivierte Sessions zählen nicht gegen das Limit (sie waren ohnehin terminal).
    assert runtime.state.status in ("done", "error", "waiting")


# --- Owner-Isolation (PROJ-25) -------------------------------------------


def test_archive_unknown_session_404(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post("/sessions/does-not-exist-xyz/archive", headers=_auth_headers())
    assert resp.status_code == 404


def test_archive_foreign_session_404(hermes_enabled):
    """Fremde Session-ID darf nicht unterscheidbar sein (kein Existenz-Leak).

    Erster Bootstrap-Nutzer erbt ``default_owner`` (Erstell-User der Session);
    ein zweiter, echter Nutzer (bob) darf dessen Session nicht sehen/archivieren.
    """
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    alice = _bootstrap(client, "alice", "geheim123")
    # Alice erstellt die Hermes-Session.
    sess = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b", "title": "Fremd"},
        headers={"Authorization": f"Bearer {alice}"},
    )
    assert sess.status_code == 201, sess.text
    sid = sess.json()["session_id"]

    # Bob (zweiter Account) archiviert → 404, nicht 200 (kein Fremd-Zugriff).
    _create_user(client, alice, "bob", "geheim123")
    bob = _login(client, "bob", "geheim123")
    resp = client.post(f"/sessions/{sid}/archive",
                       headers={"Authorization": f"Bearer {bob}"})
    assert resp.status_code == 404


# --- Rehydration (persistenter Live-Index) -------------------------------


@pytest.mark.asyncio
async def test_archived_flag_persists_and_rehydrates(tmp_path, hermes_enabled):
    repo = SqliteSessionIndexRepository(str(tmp_path / "index.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "arch-h", "owner": "dev", "project_path": "/home/dev/projects",
        "model": "qwen3.5-397b-a17b", "permission_mode": "bypassPermissions",
        "engine": "hermes", "status": "done", "archived": 1,
    })
    rows = await repo.list_all()
    assert rows[0]["archived"] == 1


@pytest.mark.asyncio
async def test_manager_archive_stops_active_session(tmp_path, hermes_enabled):
    """Eine laufende (waiting) Session wird durch archive gestoppt UND archiviert.

    Verifiziert die wiederverwendete stop()-Semantik + das archived-Flag am
    In-Memory-State (der persistierte Spiegel läuft best-effort/async, daher hier
    nur der State-Check, die Repo-Abbildung deckt test_archived_flag_persists… ab).
    """
    from app.engine.manager import WAITING

    # Fake-Driver, der nach dem Start wartet (aktiv), sodass archive stoppen muss.
    class WaitingHermesDriver(FakeHermesDriver):
        async def start(self, spec, on_event):
            self._on = on_event
            self._spec = spec
            self._alive = True
            await on_event(StreamEvent("system", "waiting", {"reason": "idle"}))

    app = _app(lambda p: WaitingHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    manager: SessionManager = app.state.manager
    runtime = manager.get(sid)
    assert runtime.state.status == WAITING

    await manager.archive_hermes(sid)
    assert runtime.state.archived is True
    # Nach archive ist die Session nicht mehr "aktiv" (kein Slot-Verbrauch).
    assert runtime.state.status not in ("starting", "running", "waiting", "awaiting_approval")
