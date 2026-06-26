"""Tests für PROJ-25 — Echtes Auth (JWT) + Owner-Scope.

Deckt die Akzeptanzkriterien + Red-Team-Edge-Cases ab:
- Bootstrap (nur bei leerer Nutzerbasis), Login, Refresh-Rotation, Logout, Me, Status.
- Owner IMMER aus dem Token; geschützte Endpunkte verlangen ein gültiges Token.
- Cross-Owner-Isolation: Nutzer B sieht/ändert Sessions von A weder per Liste,
  ID-Raten (404, kein Existenz-Leak) noch Löschen.
- Manipuliertes/abgelaufenes Token → abgelehnt.
- Migration: vor dem Bootstrap (anonym, owner="dev") angelegte Sessions bleiben
  dem ersten Account (user_id="dev") erhalten.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


@pytest.fixture
def client(tmp_path) -> TestClient:
    # `with` löst die Lifespan aus → Auth-Schema (users/refresh_tokens) wird angelegt.
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


def _bootstrap(client: TestClient, username="alice", password="geheim123") -> str:
    r = client.post("/auth/bootstrap", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Status / Bootstrap -----------------------------------------------------

def test_status_empty_then_bootstrap(client: TestClient):
    assert client.get("/auth/status").json() == {"has_users": False}
    token = _bootstrap(client)
    assert token
    assert client.get("/auth/status").json() == {"has_users": True}


def test_bootstrap_sets_owner_to_default_owner(client: TestClient):
    """Migrationsschutz: erstes Konto erbt den Single-User-Owner (default_owner)."""
    token = _bootstrap(client)
    me = client.get("/auth/me", headers=_auth(token)).json()
    assert me["user_id"] == settings.default_owner


def test_bootstrap_twice_forbidden(client: TestClient):
    _bootstrap(client)
    r = client.post("/auth/bootstrap", json={"username": "bob", "password": "geheim123"})
    assert r.status_code == 403


def test_bootstrap_short_password_rejected(client: TestClient):
    r = client.post("/auth/bootstrap", json={"username": "a", "password": "x"})
    assert r.status_code == 400


# --- Login / Refresh / Logout ----------------------------------------------

def test_login_wrong_password(client: TestClient):
    _bootstrap(client, "alice", "geheim123")
    r = client.post("/auth/login", json={"username": "alice", "password": "falsch456"})
    assert r.status_code == 401


def test_login_sets_refresh_cookie_and_refresh_rotates(client: TestClient):
    _bootstrap(client, "alice", "geheim123")
    r = client.post("/auth/login", json={"username": "alice", "password": "geheim123"})
    assert r.status_code == 200
    assert settings.refresh_cookie_name in r.cookies
    # Refresh liest den Cookie (vom TestClient gehalten) → neuer Access-Token.
    r2 = client.post("/auth/refresh")
    assert r2.status_code == 200 and r2.json()["access_token"]


def test_refresh_token_rotation_invalidates_old(client: TestClient):
    """Rotation: ein einmal eingelöster Refresh ist danach ungültig (Diebstahlschutz)."""
    _bootstrap(client, "alice", "geheim123")
    login = client.post("/auth/login", json={"username": "alice", "password": "geheim123"})
    old_refresh = login.cookies[settings.refresh_cookie_name]
    # Einlösen rotiert → neuer Cookie im Client.
    assert client.post("/auth/refresh").status_code == 200
    # Den ALTEN Refresh erneut präsentieren → abgelehnt.
    client.cookies.clear()
    r = client.post("/auth/refresh", cookies={settings.refresh_cookie_name: old_refresh})
    assert r.status_code == 401


def test_logout_revokes_refresh(client: TestClient):
    token = _bootstrap(client, "alice", "geheim123")
    # frischer Login für gültigen Cookie
    client.post("/auth/login", json={"username": "alice", "password": "geheim123"})
    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204
    # Cookie wurde gelöscht → Refresh schlägt fehl.
    client.cookies.clear()
    assert client.post("/auth/refresh").status_code == 401


# --- Geschützte Endpunkte / Token-Prüfung -----------------------------------

def test_protected_requires_token_after_bootstrap(client: TestClient):
    _bootstrap(client)
    assert client.get("/sessions").status_code == 401  # ohne Token
    assert client.get("/vault/files").status_code == 401


def test_tampered_token_rejected(client: TestClient):
    token = _bootstrap(client)
    assert client.get("/sessions", headers=_auth(token + "x")).status_code == 401


def test_expired_token_rejected(client: TestClient):
    _bootstrap(client)
    expired = jwt.encode(
        {
            "sub": settings.default_owner,
            "username": "alice",
            "type": "access",
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/sessions", headers=_auth(expired)).status_code == 401


def test_foreign_secret_token_rejected(client: TestClient):
    _bootstrap(client)
    forged = jwt.encode(
        {"sub": "dev", "username": "x", "type": "access",
         "iat": 0, "exp": 9999999999},
        "ein-voellig-anderes-secret",
        algorithm="HS256",
    )
    assert client.get("/sessions", headers=_auth(forged)).status_code == 401


# --- Owner-Scope / Cross-Owner-Red-Team -------------------------------------

def _create_session(client: TestClient, token: str) -> str:
    r = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "hallo"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["session_id"]


def test_owner_from_token_not_payload(client: TestClient):
    token = _bootstrap(client)
    # Selbst wenn der Client einen owner mitschickt, zählt nur das Token (Payload ignoriert).
    r = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "x", "owner": "angreifer"},
        headers=_auth(token),
    )
    assert r.status_code == 201
    sid = r.json()["session_id"]
    detail = client.get(f"/sessions/{sid}", headers=_auth(token)).json()
    assert detail["owner"] == settings.default_owner


def test_cross_owner_isolation(client: TestClient):
    alice = _bootstrap(client, "alice", "geheim123")
    # Zweiten Nutzer anlegen + einloggen.
    assert client.post(
        "/auth/users", json={"username": "bob", "password": "geheim123"}, headers=_auth(alice)
    ).status_code == 201
    bob = client.post("/auth/login", json={"username": "bob", "password": "geheim123"}).json()["access_token"]

    sid = _create_session(client, alice)

    # Bob sieht Alices Session NICHT in seiner Liste …
    bob_list = client.get("/sessions", headers=_auth(bob)).json()
    assert all(s["session_id"] != sid for s in bob_list)
    # … kann sie per ID-Raten nicht lesen (404, kein Existenz-Leak) …
    assert client.get(f"/sessions/{sid}", headers=_auth(bob)).status_code == 404
    # … nicht löschen …
    assert client.delete(f"/sessions/{sid}", headers=_auth(bob)).status_code == 404
    # … nicht steuern.
    assert client.post(f"/sessions/{sid}/input", json={"text": "hi"}, headers=_auth(bob)).status_code == 404

    # Alice sieht ihre eigene Session weiterhin.
    alice_list = client.get("/sessions", headers=_auth(alice)).json()
    assert any(s["session_id"] == sid for s in alice_list)


# --- Migration: anonyme Vor-Bootstrap-Sessions bleiben dem ersten Konto -----

def test_migration_anonymous_session_survives_bootstrap(client: TestClient):
    # Vor dem Bootstrap: kein Token nötig (anonymer Single-User = default_owner).
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "alt"}
    ).json()["session_id"]
    # Erstes Konto anlegen (user_id = default_owner).
    token = _bootstrap(client)
    # Die alte Session (owner="dev") gehört jetzt dem Bootstrap-Account.
    listed = client.get("/sessions", headers=_auth(token)).json()
    assert any(s["session_id"] == sid for s in listed)


# --- Red-Team-Ergänzungen (QA /abc-qa 2026-06-26) ---------------------------
# Schließen Lücken, die der erste Durchlauf offen ließ: Token-Typ-Verwechslung,
# alg=none, fehlender type-Claim, Live-Stream-WS-Owner-Scope, Rate-Limit.

def _b64url(obj: dict) -> str:
    import base64
    import json

    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def test_refresh_token_not_accepted_as_access(client: TestClient):
    """Typ-Verwechslung: ein gültig signierter REFRESH-Token darf NICHT als
    Access-Bearer durchgehen (``resolve_access`` prüft ``type == "access"``)."""
    _bootstrap(client)
    refresh_like = jwt.encode(
        {"sub": settings.default_owner, "username": "alice", "type": "refresh",
         "jti": "abc", "iat": 0, "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/sessions", headers=_auth(refresh_like)).status_code == 401


def test_alg_none_token_rejected(client: TestClient):
    """``alg=none`` (unsigniert) muss abgelehnt werden — Decode erlaubt nur HS256."""
    _bootstrap(client)
    none_token = (
        _b64url({"alg": "none", "typ": "JWT"})
        + "."
        + _b64url({"sub": settings.default_owner, "type": "access", "iat": 0, "exp": 9999999999})
        + "."
    )
    assert client.get("/sessions", headers=_auth(none_token)).status_code == 401


def test_token_without_type_claim_rejected(client: TestClient):
    """Fehlt der ``type``-Claim, ist es kein gültiger Access-Token → 401."""
    _bootstrap(client)
    no_type = jwt.encode(
        {"sub": settings.default_owner, "username": "alice", "iat": 0, "exp": 9999999999},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/sessions", headers=_auth(no_type)).status_code == 401


def test_ws_stream_owner_scoped(client: TestClient):
    """Live-Stream-WS (`/sessions/{id}/stream`) ist owner-scoped: der Eigentümer
    verbindet (Snapshot), ein fremder Nutzer UND der Tokenlose werden abgewiesen."""
    from starlette.websockets import WebSocketDisconnect

    alice = _bootstrap(client, "alice", "geheim123")
    assert client.post(
        "/auth/users", json={"username": "bob", "password": "geheim123"}, headers=_auth(alice)
    ).status_code == 201
    bob = client.post("/auth/login", json={"username": "bob", "password": "geheim123"}).json()["access_token"]
    sid = _create_session(client, alice)

    # Eigentümerin: verbindet + erhält den State-Snapshot.
    with client.websocket_connect(f"/sessions/{sid}/stream?access_token={alice}") as ws:
        assert ws.receive_json()["kind"] == "state"

    # Fremder Nutzer: Handshake wird abgewiesen (close 4404 → kein Existenz-Leak).
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/sessions/{sid}/stream?access_token={bob}") as ws:
            ws.receive_json()

    # Ohne Token: ebenfalls abgewiesen (close 4401).
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
            ws.receive_json()


def test_login_rate_limited_after_threshold(client: TestClient, monkeypatch):
    """Rate-Limiting (PROJ-25-Härtung): nach 5 Login-Versuchen/Minute/IP → 429.
    (In der globalen conftest-Fixture ist es aus; hier gezielt eingeschaltet.)"""
    _bootstrap(client, "alice", "geheim123")
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    # Fixed-Window-Zähler vor dem Test leeren (Modul-Singleton, sonst Test-Pollution).
    from app import ratelimit

    try:
        ratelimit._limiter.storage.reset()
    except Exception:
        pass
    codes = [
        client.post("/auth/login", json={"username": "alice", "password": "falsch"}).status_code
        for _ in range(7)
    ]
    assert codes.count(401) >= 4, codes  # die ersten Versuche sind echte 401 (falsches PW)
    assert 429 in codes, codes  # ab dem 6. greift der Limiter
