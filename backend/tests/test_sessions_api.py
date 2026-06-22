"""API-Tests (TestClient) mit FakeDriver — REST-Vertrag + WebSocket-Smoke."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


@pytest.fixture()
def client() -> TestClient:
    app = create_app(driver_factory=lambda: FakeDriver())
    return TestClient(app)


def _create(client: TestClient, **overrides) -> dict:
    body = {"project_path": PROJECT, "initial_prompt": "Hallo", "model": "haiku"}
    body.update(overrides)
    resp = client.post("/sessions", json=body)
    return resp


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}


def test_cors_allows_frontend_origin(client: TestClient):
    """PROJ-3: Browser-Frontend (Next.js :3000) darf das Backend erreichen."""
    origin = "http://localhost:3000"
    # Preflight (OPTIONS) muss den Origin zurückspiegeln.
    pre = client.options(
        "/sessions",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert pre.headers.get("access-control-allow-origin") == origin
    # Einfache GET-Anfrage trägt den CORS-Allow-Origin-Header.
    resp = client.get("/health", headers={"Origin": origin})
    assert resp.headers.get("access-control-allow-origin") == origin


def test_cors_blocks_unknown_origin(client: TestClient):
    """Fremde Origins erhalten keinen Allow-Origin-Header."""
    resp = client.get("/health", headers={"Origin": "http://evil.example"})
    assert resp.headers.get("access-control-allow-origin") is None


def test_create_session_ok(client: TestClient):
    resp = _create(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] in ("waiting", "running")
    assert data["owner"] == "dev"  # serverseitig gestempelt, kein JWT
    assert data["project_path"] == PROJECT
    assert data["context_fill_pct"] > 0


def test_create_invalid_path_400(client: TestClient):
    resp = _create(client, project_path="/etc")
    assert resp.status_code == 400


def test_create_missing_prompt_422(client: TestClient):
    resp = client.post("/sessions", json={"project_path": PROJECT})
    assert resp.status_code == 422


def test_list_and_get(client: TestClient):
    sid = _create(client).json()["session_id"]
    assert len(client.get("/sessions").json()) == 1
    detail = client.get(f"/sessions/{sid}").json()
    assert detail["session_id"] == sid
    assert any(e["kind"] == "text" for e in detail["transcript"])


def test_get_unknown_404(client: TestClient):
    assert client.get("/sessions/does-not-exist").status_code == 404


def test_input_flow(client: TestClient):
    sid = _create(client).json()["session_id"]
    resp = client.post(f"/sessions/{sid}/input", json={"text": "weiter"})
    assert resp.status_code == 202
    txt = client.get(f"/sessions/{sid}/transcript").json()["text"]
    assert "Du: weiter" in txt


def test_input_unknown_404(client: TestClient):
    assert client.post("/sessions/nope/input", json={"text": "x"}).status_code == 404


def test_stop(client: TestClient):
    sid = _create(client).json()["session_id"]
    assert client.post(f"/sessions/{sid}/stop").json() == {"ok": True}


def test_websocket_sends_state_snapshot(client: TestClient):
    sid = _create(client).json()["session_id"]
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        msg = ws.receive_json()
        assert msg["kind"] == "state"
        assert msg["session_id"] == sid
