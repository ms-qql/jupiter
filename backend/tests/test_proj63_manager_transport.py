"""PROJ-63 — SessionManager löst den Transport pro Engine auf (Rollout: erst
generic_cli/Codex/OpenCode, jetzt auch Claude). Verwendet FakeDriver (kein echter
Subprozess) — reine Verdrahtungs-/Resolution-Tests, kein tmux nötig.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engine import transport_settings
from app.engine.manager import SessionManager
from app.engine.registry import CLAUDE_KEY, EngineRegistry, _builtin_claude, engine_registry
from app.engine.transport_settings import TransportStore
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"

_GENERIC_CLI_YAML = """
engines:
  - key: fake-codex
    label: "Fake Codex"
    kind: engine
    driver: generic_cli
    bin: /bin/true
    argv_template: ["-"]
    adapter: codex
    prompt_via: stdin
    input_format: text
    oneshot: true
    resume_argv_template: ["-", "resume", "{resume_id}"]
    models: [x]
    default_model: x
"""


@pytest.fixture()
def use_generic_cli_engine(tmp_path, monkeypatch):
    p = tmp_path / "engines.yaml"
    p.write_text(_GENERIC_CLI_YAML, encoding="utf-8")
    monkeypatch.setattr(engine_registry, "_path", str(p))
    monkeypatch.setattr(engine_registry, "_mtime", None)
    monkeypatch.setattr(engine_registry, "_loaded_once", False)
    monkeypatch.setattr(engine_registry, "_source", "default")
    monkeypatch.setattr(engine_registry, "_profiles", {CLAUDE_KEY: _builtin_claude()})


@pytest.fixture()
def transport_store_tmp(tmp_path, monkeypatch):
    store = TransportStore(str(tmp_path / "transport.yaml"))
    monkeypatch.setattr(transport_settings, "transport_store", store)
    return store


def _mgr() -> SessionManager:
    return SessionManager(
        driver_factory=lambda: FakeDriver(), engine_factory=lambda profile: FakeDriver()
    )


@pytest.mark.asyncio
async def test_generic_cli_engine_resolves_tmux_when_configured(
    use_generic_cli_engine, transport_store_tmp
):
    transport_store_tmp.save({"default_transport": "direct", "engine_overrides": {"fake-codex": "tmux"}})
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", engine="fake-codex", model="x")
    assert rt.state.transport == "tmux"
    assert rt.state.to_read()["transport"] == "tmux"


@pytest.mark.asyncio
async def test_generic_cli_engine_defaults_to_direct(use_generic_cli_engine, transport_store_tmp):
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", engine="fake-codex", model="x")
    assert rt.state.transport == "direct"


@pytest.mark.asyncio
async def test_claude_resolves_tmux_when_configured(transport_store_tmp):
    """Rollout-Schritt 5 (PROJ-63): Claude ist jetzt aktiviert — ein Override
    ``claude: tmux`` schaltet Claude-Sessions auf den long-lived-tmux-Transport."""
    transport_store_tmp.save({"engine_overrides": {"claude": "tmux"}})
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    assert rt.state.engine == "claude"
    assert rt.state.transport == "tmux"


@pytest.mark.asyncio
async def test_claude_resolves_tmux_from_global_default(transport_store_tmp):
    """Claude folgt jetzt auch dem globalen tmux-Default (nicht mehr außen vor)."""
    transport_store_tmp.save({"default_transport": "tmux"})
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    assert rt.state.engine == "claude"
    assert rt.state.transport == "tmux"


@pytest.mark.asyncio
async def test_claude_defaults_to_direct_without_override(transport_store_tmp):
    """Ohne tmux-Konfiguration bleibt Claude auf ``direct`` (kein Zwangs-tmux)."""
    transport_store_tmp.save({"default_transport": "direct"})
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", model="haiku")
    assert rt.state.engine == "claude"
    assert rt.state.transport == "direct"


@pytest.mark.asyncio
async def test_resume_keeps_original_transport_even_if_settings_changed_meanwhile(
    use_generic_cli_engine, transport_store_tmp
):
    """Eine laufende Session wechselt nicht mitten im Betrieb den Transport, nur weil
    ein Operator die Settings danach ändert (siehe manager.py: `_resume` nutzt
    `state.transport`, nicht erneut `transport_store.resolve(...)`)."""
    transport_store_tmp.save({"default_transport": "direct"})
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi", engine="fake-codex", model="x")
    assert rt.state.transport == "direct"

    # Operator schaltet danach global auf tmux um.
    transport_store_tmp.save({"default_transport": "tmux"})

    await mgr._resume(rt)
    assert rt.state.transport == "direct"  # unverändert trotz geänderter Settings


# --- QA-BUG-3-Regression: `transport` muss über die ECHTE HTTP-Response ankommen -----
# (nicht nur in `SessionState.to_read()` — Pydantic-`response_model` filtert unbekannte
# Dict-Schlüssel heraus; das hatten weder Backend- noch Frontend-Tests geprüft, weil
# beide Seiten nie den tatsächlichen HTTP-Contract gegeneinander getestet haben.)

@pytest.fixture()
def http_client(use_generic_cli_engine, transport_store_tmp):
    app = create_app(
        driver_factory=lambda: FakeDriver(), engine_factory=lambda profile: FakeDriver()
    )
    return TestClient(app)


def test_post_sessions_response_includes_transport_field(http_client, transport_store_tmp):
    transport_store_tmp.save({"engine_overrides": {"fake-codex": "tmux"}})
    resp = http_client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "hi", "engine": "fake-codex", "model": "x"},
    )
    assert resp.status_code == 201
    assert resp.json()["transport"] == "tmux"


def test_get_sessions_list_response_includes_transport_field(http_client):
    http_client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "hi", "engine": "fake-codex", "model": "x"},
    )
    resp = http_client.get("/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["transport"] == "direct"


def test_get_session_detail_response_includes_transport_field(http_client):
    created = http_client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "hi", "engine": "fake-codex", "model": "x"},
    ).json()
    resp = http_client.get(f"/sessions/{created['session_id']}")
    assert resp.status_code == 200
    assert resp.json()["transport"] == "direct"


# --- QA-BUG-2-Regression: ein fehlgeschlagener tmux-Start liefert eine strukturierte
# 503-Antwort (statt eines rohen, unhandled 500 "Internal Server Error").

def test_post_sessions_transport_error_returns_503_not_raw_500(
    use_generic_cli_engine, transport_store_tmp, monkeypatch
):
    from app.engine import transport as transport_module
    from app.engine.transport import TransportError

    async def _boom(self, *a, **kw):
        raise TransportError("tmux ist nicht verfügbar (Test-Simulation).")

    monkeypatch.setattr(transport_module.TmuxTransport, "spawn", _boom)
    transport_store_tmp.save({"engine_overrides": {"fake-codex": "tmux"}})
    # Echter GenericCliDriver (kein FakeDriver) noetig, damit der `spawn()`-Patch
    # tatsaechlich durchlaufen und TransportError bis zur Route hochgereicht wird.
    app = create_app(driver_factory=lambda: FakeDriver())
    client = TestClient(app)
    resp = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "hi", "engine": "fake-codex", "model": "x"},
    )
    assert resp.status_code == 503
    assert "tmux" in resp.json()["detail"]
