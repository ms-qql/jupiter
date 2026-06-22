"""QA + Red-Team-Tests für PROJ-1 (Engine-Treiber).

Schwerpunkt auf der echten Angriffsfläche eines single-user-MVP:
Projekt-Pfad-Scope, Eingabe-Validierung, Session-Lifecycle, Permission-Posture.
(Kein JWT/RLS/Mandant — bewusster MVP-Non-Goal.)
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.engine.manager import validate_project_path
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


# --- Security: Projekt-Pfad-Scope (die zentrale Leitplanke) -----------------

@pytest.mark.parametrize(
    "bad",
    [
        "/etc",                            # komplett außerhalb
        "/home/dev",                       # Elternverzeichnis der Roots
        "/home/dev/projects/../../etc",    # Traversal → /etc
        "/home/dev/projects-evil",         # Prefix-Attacke (kein echtes Unterverz.)
        "/home/dev/tools/../secret",       # Traversal aus tools heraus
    ],
)
def test_path_scope_rejects(client: TestClient, bad: str):
    r = client.post("/sessions", json={"project_path": bad, "initial_prompt": "x"})
    assert r.status_code == 400, f"{bad} hätte abgelehnt werden müssen"


def test_symlink_escape_rejected():
    # Symlink INNERHALB eines erlaubten Roots, der nach außen zeigt → muss scheitern.
    link = "/home/dev/projects/jupiter/backend/.qa_escape_link"
    try:
        if os.path.islink(link) or os.path.exists(link):
            os.remove(link)
        os.symlink("/etc", link)
        with pytest.raises(ValueError):
            validate_project_path(link)
    finally:
        if os.path.islink(link):
            os.remove(link)


def test_allowed_root_accepted():
    assert validate_project_path(PROJECT) == os.path.realpath(PROJECT)


# --- Eingabe-Validierung ----------------------------------------------------

def test_invalid_model_422(client: TestClient):
    r = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "x", "model": "gpt-9"})
    assert r.status_code == 422


def test_invalid_permission_mode_422(client: TestClient):
    r = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "x", "permission_mode": "yolo"},
    )
    assert r.status_code == 422


def test_empty_input_422(client: TestClient):
    sid = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "x"}).json()["session_id"]
    assert client.post(f"/sessions/{sid}/input", json={"text": ""}).status_code == 422


# --- FINDING QA-1: bypassPermissions wird vom Client akzeptiert -------------

def test_bypass_permissions_currently_accepted(client: TestClient):
    """Dokumentiert den Ist-Zustand: Client kann das Safety-Net abschalten.

    Bis PROJ-4 (Decision Cards) + #19 (Watchdog) existiert dann KEIN Schutz.
    Erwartung nach Fix: MVP beschränkt auf {default, acceptEdits} → 422.
    """
    r = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "x", "permission_mode": "bypassPermissions"},
    )
    assert r.status_code == 201  # IST-Zustand (Finding offen)


# --- FINDING QA-2: kein Größenlimit für Eingaben ----------------------------

def test_large_input_has_no_limit(client: TestClient):
    """Spec-Edge-Case nennt 'ggf. Hinweis/Limit' — aktuell unbegrenzt."""
    sid = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "x"}).json()["session_id"]
    r = client.post(f"/sessions/{sid}/input", json={"text": "A" * 500_000})
    assert r.status_code == 202  # IST-Zustand (Finding offen)


# --- Session-Lifecycle / Isolation ------------------------------------------

def test_sessions_are_isolated(client: TestClient):
    a = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "A"}).json()
    b = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "B"}).json()
    assert a["session_id"] != b["session_id"]
    assert len(client.get("/sessions").json()) == 2


def test_input_after_stop_conflict(client: TestClient):
    sid = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "x"}).json()["session_id"]
    client.post(f"/sessions/{sid}/stop")
    r = client.post(f"/sessions/{sid}/input", json={"text": "noch was"})
    assert r.status_code == 409


def test_websocket_unknown_session_closed(client: TestClient):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/sessions/unknown/stream") as ws:
            ws.receive_json()


def test_stop_unknown_session_404(client: TestClient):
    assert client.post("/sessions/nope/stop").status_code == 404
