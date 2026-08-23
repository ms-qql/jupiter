"""PROJ-87 — Hermes-Profilwahl im Neue-Session-Dialog (Backend).

Testet die Profil-Liste (GET /sessions/hermes/profiles), die serverseitige
Profilvalidierung beim Start (POST /sessions/hermes), die Weiterreichung der
HERMES_HOME-Umgebung an den Treiber (nur für Nicht-Default) und die Persistenz/
Rehydrierung des gewählten Profils. Die echte Hermes-CLI wird durch einen
Fake-Treiber ersetzt; Profile werden über ein temporäres Verzeichnis simuliert.
"""
from __future__ import annotations

import os

import pytest

from app.db.session_index import SqliteSessionIndexRepository
from app.engine.base import LaunchSpec
from app.engine.hermes_chat_driver import HermesChatDriver
from app.engine.hermes_profiles import (
    discover_profiles,
    list_profiles_for_select,
    profile_home,
    validate_profile,
)
from app.engine.manager import ERROR, SessionManager
from app.engine.registry import engine_registry
from app.main import create_app

from .test_proj85_hermes import FakeHermesDriver, _app, _auth_headers, hermes_enabled


# --- Profilerkennung (hermes_profiles.py) -----------------------------------


def test_default_entry_present_and_first():
    snap = list_profiles_for_select()
    assert snap["entries"][0]["profile"] == "default"
    # default ohne konfiguriertes Profilverzeichnis darf nicht crashen.
    assert "profile" in snap["entries"][0]


def test_discover_excludes_default_and_only_jupiter():
    entries, _ = discover_profiles()
    assert all(e["profile"].startswith("jupiter-") for e in entries)
    assert all(e["profile"] != "default" for e in entries)


def test_validate_profile_default_ok():
    entry = validate_profile("default")
    assert entry["profile"] == "default"


def test_validate_profile_unknown_rejected():
    with pytest.raises(ValueError):
        validate_profile("jupiter-nope-not-there")


def test_validate_profile_bad_format_rejected():
    with pytest.raises(ValueError):
        validate_profile("../escape")
    with pytest.raises(ValueError):
        validate_profile("notjupiter-x")


def test_profile_home_default_is_none():
    # default erbt das CLI-Default-Home → bewusst KEIN explicit HERMES_HOME.
    assert profile_home("default") is None


def test_profile_home_jupiter_returns_profiles_dir(tmp_path, monkeypatch):
    from app import config

    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    (prof_dir / "jupiter-demo").mkdir()
    monkeypatch.setattr(config.settings, "hermes_profiles_dir", str(prof_dir))
    home = profile_home("jupiter-demo")
    assert home is not None
    assert home.endswith(os.path.join("profiles", "jupiter-demo"))


# --- Profil-Endpoint --------------------------------------------------------


def test_profiles_endpoint_includes_default(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/sessions/hermes/profiles", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "profiles" in data
    profiles = {p["profile"] for p in data["profiles"]}
    assert "default" in profiles
    # Keine Secrets/Credentials in der Antwort.
    for p in data["profiles"]:
        assert set(p.keys()) <= {"profile", "label", "engine", "model", "error", "warning"}


# --- Start mit Profil -------------------------------------------------------


def test_create_hermes_default_profile_is_snapshot(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b", "profile": "default"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    s = resp.json()
    assert s["hermes_profile"] == "default"


def test_create_hermes_unknown_profile_400(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b", "profile": "jupiter-ghost"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400, resp.text
    assert "Profil" in resp.json()["detail"]


def test_create_hermes_bad_format_profile_422(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b", "profile": "../x"},
        headers=_auth_headers(),
    )
    # Schema-Validierung (pattern) → 422, bevor das Backend erreicht wird.
    assert resp.status_code == 422, resp.text


def test_create_hermes_missing_profile_defaults(hermes_enabled):
    # Rückwärtskompatibilität: ohne profile-Feld → default.
    app = _app(lambda p: FakeHermesDriver(p))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["hermes_profile"] == "default"


# --- HERMES_HOME-Weiterreichung an den Treiber ------------------------------


def test_make_driver_sets_hermes_home_for_nondefault(tmp_path, hermes_enabled, monkeypatch):
    from app import config
    from app.engine.manager import SessionState

    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    demo = prof_dir / "jupiter-demo"
    demo.mkdir()
    (demo / "config.yaml").write_text("model:\n  provider: anthropic\n  default: claude-sonnet-5\n")
    monkeypatch.setattr(config.settings, "hermes_profiles_dir", str(prof_dir))

    hermes_profile = engine_registry.get("hermes", include_disabled=True)
    manager = SessionManager()
    state = SessionState(
        session_id="s1", owner="dev", project_path="/home/dev/projects",
        model="claude-sonnet-5", permission_mode="bypassPermissions",
        engine="hermes", status="waiting", hermes_profile="jupiter-demo",
    )
    driver = manager._make_driver(hermes_profile, state)
    assert isinstance(driver, HermesChatDriver)
    assert driver._hermes_home == str(demo)


def test_make_driver_no_hermes_home_for_default(hermes_enabled):
    from app.engine.manager import SessionState

    hermes_profile = engine_registry.get("hermes", include_disabled=True)
    manager = SessionManager()
    state = SessionState(
        session_id="s2", owner="dev", project_path="/home/dev/projects",
        model="claude-sonnet-5", permission_mode="bypassPermissions",
        engine="hermes", status="waiting", hermes_profile="default",
    )
    driver = manager._make_driver(hermes_profile, state)
    assert isinstance(driver, HermesChatDriver)
    assert driver._hermes_home is None


def test_hermes_spec_carries_hermes_home_env(hermes_enabled):
    from app.engine.base import LaunchSpec

    prof = engine_registry.get("hermes", include_disabled=True)
    driver = HermesChatDriver(prof, provider="anthropic", model="claude-sonnet-5")
    driver._spec = LaunchSpec(session_id="x", project_path="/p", model="m",
                              permission_mode="bypassPermissions", initial_prompt="")
    driver.set_hermes_home("/tmp/foo")
    # Folge-Turn-Spec muss HERMES_HOME enthalten.
    spec = driver._spec_with_prompt("hallo")
    assert isinstance(spec, LaunchSpec)
    assert spec.env == {"HERMES_HOME": "/tmp/foo"}
    # Spec ohne Profil → kein env.
    driver2 = HermesChatDriver(prof, provider="anthropic", model="claude-sonnet-5")
    driver2._spec = LaunchSpec(session_id="x", project_path="/p", model="m",
                               permission_mode="bypassPermissions", initial_prompt="")
    spec2 = driver2._spec_with_prompt("hallo")
    assert spec2.env is None


# --- Persistenz + Rehydrierung ----------------------------------------------


@pytest.mark.asyncio
async def test_rehydrate_waiting_hermes_preserves_profile(tmp_path, hermes_enabled):
    repo = SqliteSessionIndexRepository(str(tmp_path / "index.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "hermes-prof", "owner": "dev", "project_path": "/home/dev/projects",
        "model": "gpt-5.6", "permission_mode": "bypassPermissions", "engine": "hermes",
        "status": "waiting", "hermes_resume_ref": "resume-1", "hermes_provider": "openai",
        "hermes_profile": "jupiter-demo",
    })
    manager = SessionManager(repo=repo)
    await manager.rehydrate()
    runtime = manager.get("hermes-prof")
    assert runtime is not None and runtime.state.status == "waiting"
    assert runtime.state.hermes_profile == "jupiter-demo"
    assert isinstance(runtime.driver, HermesChatDriver)
    # Profil ist Session-Snapshot im Response.
    assert runtime.to_read()["hermes_profile"] == "jupiter-demo"


@pytest.mark.asyncio
async def test_persisted_hermes_profile_survives_rehydrate_env(tmp_path, hermes_enabled, monkeypatch):
    from app import config

    prof_dir = tmp_path / "profiles"
    prof_dir.mkdir()
    demo = prof_dir / "jupiter-demo"
    demo.mkdir()
    (demo / "config.yaml").write_text("model:\n  provider: anthropic\n  default: claude-sonnet-5\n")
    monkeypatch.setattr(config.settings, "hermes_profiles_dir", str(prof_dir))

    repo = SqliteSessionIndexRepository(str(tmp_path / "index.db"))
    await repo.init()
    await repo.upsert({
        "session_id": "hermes-rehy", "owner": "dev", "project_path": "/home/dev/projects",
        "model": "claude-sonnet-5", "permission_mode": "bypassPermissions", "engine": "hermes",
        "status": "waiting", "hermes_resume_ref": "resume-2", "hermes_provider": "anthropic",
        "hermes_profile": "jupiter-demo",
    })
    manager = SessionManager(repo=repo)
    await manager.rehydrate()
    runtime = manager.get("hermes-rehy")
    assert runtime is not None
    # Der rehydrierte Treiber muss HERMES_HOME aus dem persistierten Profil ableiten.
    assert runtime.driver._hermes_home == str(demo)


def test_engine_registry_has_hermes(hermes_enabled):
    # Sicherstellen, dass der hermes_enabled-Fixture die Engine schaltet.
    assert engine_registry.get("hermes", include_disabled=True) is not None
