"""PROJ-85 — Hermes-Session-Backend (Start, Options, Usage, Resume-ref).

Testet den schmalen Hermes-Startvertrag (POST /sessions/hermes), den Options-
Lese-Pfad (GET /sessions/hermes/options), die serverseitig erzwungenen Bypass/
Savings-Werte, den Hermes-Kontext-Snapshot (nur aus Telemetrie) und die
Resume-Referenz. Die echte Hermes-CLI wird durch einen Fake-Treiber ersetzt.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.base import EngineDriver, EventHandler, LaunchSpec
from app.engine.events import StreamEvent
from app.engine.registry import engine_registry
from app.main import create_app


@pytest.fixture
def hermes_enabled(monkeypatch):
    """Hermes-Profil für den Test aktivieren (in engines.yaml ist es disabled).

    Der Worktree hat ggf. keine eigene engines.yaml → auf die des Haupt-Repos
    zeigen, damit das hermes-Profil überhaupt geladen wird.
    """
    main_yaml = "/home/dev/projects/jupiter/backend/config/engines.yaml"
    if os.path.exists(main_yaml):
        monkeypatch.setattr(engine_registry, "_path", main_yaml)
    engine_registry._loaded_once = False  # erzwingt frisches Laden
    engine_registry._reload_if_changed()
    prof = engine_registry._profiles.get("hermes")
    if prof is None:
        pytest.skip("Kein hermes-Profil in der Registry.")
    monkeypatch.setattr(prof, "enabled", True)
    monkeypatch.setattr(prof, "bin", "hermes")  # reale CLI existiert im PATH
    yield prof
    monkeypatch.setattr(prof, "enabled", False)


class FakeHermesDriver(EngineDriver):
    """Simuliert die Hermes-CLI: emittiert init + Antwort + Usage + Resume-Ref.

    Verhält sich wie ein One-Shot-Treiber: nach dem Start ist der Prozess tot,
    weitere Eingaben lösen über die gespeicherte Resume-Ref einen Folge-Turn aus.
    """

    def __init__(self, profile) -> None:
        self.profile = profile
        self._on: EventHandler | None = None
        self._spec: LaunchSpec | None = None
        self._alive = True
        self.sent: list[str] = []
        self._resume_ref = "hermes-ref-abc123"
        self._turn = 0

    @property
    def is_alive(self) -> bool:
        return self._alive

    @property
    def resume_id(self) -> str | None:
        return self._resume_ref

    @property
    def supports_self_resume(self) -> bool:
        return True

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        self._spec = spec
        await on_event(StreamEvent("system", "init",
                                   {"session_id": spec.session_id, "model": spec.model}))
        if spec.initial_prompt:
            await self._answer(spec.initial_prompt)
        # One-Shot: nach dem Turn ist der Prozess beendet.
        self._alive = False

    async def send_input(self, text: str) -> None:
        if not self._alive:
            # Folge-Turn via Resume-Ref (kein neuer Frischstart).
            self._alive = True
        self.sent.append(text)
        await self._answer(text)

    async def _answer(self, prompt: str) -> None:
        assert self._on is not None and self._spec is not None
        self._turn += 1
        await self._on(StreamEvent("assistant", None,
                                   {"message": {"content": [{"type": "text",
                                                            "text": f"Hermes: {prompt}"}]}}))
        # Usage aus der --usage-file (nur echte Werte).
        await self._on(StreamEvent("system", "usage",
                                   {"used_tokens": 18600, "window_tokens": 256000}))
        # Result/closed wie ein One-Shot-Ende.
        await self._on(StreamEvent("system", "closed", {}))
        self._alive = False

    async def pause(self) -> None:
        return None

    async def stop(self) -> None:
        self._alive = False
        if self._on is not None:
            await self._on(StreamEvent("system", "closed", {}))


def _app(engine_factory):
    app = create_app(engine_factory=engine_factory)
    return app


def _auth_headers():
    # Vor-Bootstrap-Single-User → kein Token nötig (settings.default_owner).
    return {}


def test_resolver_returns_enabled_available_models(hermes_enabled):
    from app.engine.hermes_resolver import hermes_model_options

    opts = hermes_model_options()
    # Hermes-Profil selbst ist enabled+available und hat ein Modell.
    keys = {(o.engine, o.model) for o in opts}
    assert ("hermes", "qwen3.5-397b-a17b") in keys
    # Jede Option ist ein echtes engine/model-Paar.
    assert all(o.engine and o.model for o in opts)


def test_resolve_invocation_translates_claude_to_hermes(hermes_enabled):
    from app.engine.hermes_resolver import resolve_hermes_invocation

    inv = resolve_hermes_invocation("claude", "sonnet")
    assert inv.provider == "anthropic"
    assert inv.model.startswith("claude-")  # PROJ-83-Alias
    # Ungültige Kombination → ValueError (→ 400).
    with pytest.raises(ValueError):
        resolve_hermes_invocation("claude", "nicht-existent")


def test_options_endpoint(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.get("/sessions/hermes/options", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert any(m["engine"] == "hermes" for m in data["models"])


def test_create_hermes_enforces_bypass_and_savings(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects",
              "engine": "hermes", "model": "qwen3.5-397b-a17b",
              "title": "Mein Hermes"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    s = resp.json()
    assert s["engine"] == "hermes"
    assert s["permission_mode"] == "bypassPermissions"
    assert s["savings_enabled"] is True
    assert s["project_name"] == "Mein Hermes"
    # Usage aus der Telemetrie übernommen.
    assert s["context_usage_available"] is True
    assert s["context_used_tokens"] == 18600
    assert s["context_window_tokens"] == 256000
    # Resume-Ref erfasst.
    assert s["hermes_resume_ref"] == "hermes-ref-abc123"


def test_create_hermes_overrides_client_fields(hermes_enabled):
    """Schmaler Vertrag: clientseitige permission_mode/token_savings werden ignoriert
    (nicht im Schema), und selbst wenn sie gesendet würden, gilt serverseitig Bypass +
    Token Savings. Hier prüfen wir, dass die erzwungenen Werte im Response stehen.
    """
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b", "title": "Override-Test"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    s = resp.json()
    # Erzwungen — unabhängig von jeglichem Client-Wunsch (ADR-85-1).
    assert s["permission_mode"] == "bypassPermissions"
    assert s["savings_enabled"] is True


def test_create_hermes_invalid_model_400(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "does-not-exist"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_hermes_invalid_path_400(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/etc", "engine": "hermes",
              "model": "qwen3.5-397b-a17b"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_hermes_accepts_registry_engine(hermes_enabled):
    """BUG-1-Fix: jede vom Options-Endpoint angebotene Registry-Engine (claude/
    codex/opencode/…) ist startbar — der Manager übersetzt sie pro Session in die
    Hermes-CLI. Hier: claude/sonnet wird mit 201 angenommen und als engine='hermes'
    persistiert (Tech Design C: Registry-Modellkombination)."""
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "claude",
              "model": "sonnet"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    s = resp.json()
    assert s["engine"] == "hermes"  # Session läuft unter der Hermes-Engine
    assert s["permission_mode"] == "bypassPermissions"
    assert s["savings_enabled"] is True


def test_create_hermes_extra_forbid(hermes_enabled):
    """BUG-3-Fix: zusätzliche, nicht deklarierte Felder (z. B. permission_mode,
    owner) werden mit 422 abgelehnt — extra='forbid' ist jetzt als Klassenattribut
    wirksam (Pydantic v2)."""
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b", "permission_mode": "default",
              "owner": "attacker"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 422, resp.text


def test_create_hermes_unknown_engine_400(hermes_enabled):
    """Eine wirklich unbekannte Engine (nicht in der Registry) bleibt 400 — der
    Options-Endpoint bietet sie ohnehin nie an."""
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "nicht-registriert",
              "model": "sonnet"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_hermes_appears_in_list(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b"},
        headers=_auth_headers(),
    )
    listing = client.get("/sessions", headers=_auth_headers()).json()
    assert any(s["engine"] == "hermes" for s in listing)


def test_hermes_resume_less_has_no_ref(hermes_enabled, monkeypatch):
    """Ohne Resume-Ref (Engine liefert keine) bleibt die Session sichtbar, aber
    context_usage_available=False und hermes_resume_ref=None (ADR-85-3)."""

    class NoRefDriver(FakeHermesDriver):
        def __init__(self, profile):
            super().__init__(profile)
            self._resume_ref = None

        @property
        def resume_id(self):
            return None

        @property
        def supports_self_resume(self):
            return False

        async def _answer(self, prompt: str) -> None:
            # Keine Usage-Datei → keine Kontext-Telemetrie (ADR-85-3: nie erfinden).
            assert self._on is not None and self._spec is not None
            await self._on(StreamEvent("assistant", None,
                                       {"message": {"content": [{"type": "text",
                                                                        "text": f"Hermes: {prompt}"}]}}))
            await self._on(StreamEvent("system", "closed", {}))
            self._alive = False

    app = _app(lambda p: NoRefDriver(p))
    client = TestClient(app)
    resp = client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects", "engine": "hermes",
              "model": "qwen3.5-397b-a17b"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    s = resp.json()
    # Keine Usage-Datei → Werte bleiben None (nie erfunden).
    assert s["context_usage_available"] is False
    assert s["context_used_tokens"] is None
    assert s["context_window_tokens"] is None
    assert s["hermes_resume_ref"] is None
