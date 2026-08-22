"""PROJ-85/86 — Hermes-Session-Backend (Start, Options, direkter Chat-Resume, Liveness).

Testet den schmalen Hermes-Startvertrag (POST /sessions/hermes), den Options-
Lese-Pfad, die serverseitig erzwungenen Bypass/Savings-Werte und — als PROJ-86 —
dass eine Hermes-Session OHNE künstlichen Prompt startet (Status "waiting"),
jeder Turn dieselbe Conversation-ID fortsetzt, fehlende/abgelehnte IDs sichtbar
fehlschlagen, Hermes aus der Liveness-Auto-Reanimation und aus dem manuellen
Reanimieren herausgehalten wird. Die echte Hermes-CLI wird durch einen Fake-Treiber
ersetzt.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.engine.base import EngineDriver, EventHandler, LaunchSpec
from app.engine.events import StreamEvent
from app.engine.registry import engine_registry
from app.main import create_app


@pytest.fixture
def hermes_enabled(monkeypatch):
    """Hermes-Profil für den Test aktivieren (in engines.yaml ist es disabled)."""
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
    """Simuliert die Hermes-CLI im direkten Chat-Modus (PROJ-86):

    - Start mit leerem Prompt → wartet sichtbar (kein Prozess, kein künstlicher Turn).
    - Jede Eingabe = ein Turn, der nach Antwort in ``waiting`` endet und die
      Resume-Ref erst DANN setzt (wie der echte Treiber nach der stdout-Kontrollzeile).
    """

    def __init__(self, profile) -> None:
        self.profile = profile
        self._on: EventHandler | None = None
        self._spec: LaunchSpec | None = None
        self._alive = False
        self.sent: list[str] = []
        self._resume_ref: str | None = None
        self._turn = 0

    @property
    def is_alive(self) -> bool:
        return self._alive

    @property
    def resume_id(self) -> str | None:
        return self._resume_ref

    @property
    def supports_self_resume(self) -> bool:
        # PROJ-86: Hermes setzt selbst fort → Manager löst KEINEN generischen Resume aus.
        return True

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self._on = on_event
        self._spec = spec
        await on_event(StreamEvent("system", "init",
                                   {"session_id": spec.session_id, "model": spec.model}))
        if not spec.initial_prompt or not spec.initial_prompt.strip():
            # PROJ-86: wartet auf die erste echte Nutzereingabe.
            await on_event(StreamEvent("system", "waiting", {"reason": "initial_prompt_empty"}))
            return
        await self._answer(spec.initial_prompt)

    async def send_input(self, text: str) -> None:
        if not self._alive and self._spec is not None:
            self._alive = True
        self.sent.append(text)
        await self._answer(text)

    async def _answer(self, prompt: str) -> None:
        assert self._on is not None and self._spec is not None
        self._turn += 1
        await self._on(StreamEvent("assistant", None,
                                   {"message": {"content": [{"type": "text",
                                                            "text": f"Hermes: {prompt}"}]}}))
        await self._on(StreamEvent("system", "usage",
                                   {"used_tokens": 18600, "window_tokens": 256000}))
        # PROJ-86: Turn fertig → wartet auf nächste Eingabe (KEIN closed/-z-Turn).
        # Hermes liefert pro Turn dieselbe Conversation-ID zurück → stabile Ref.
        self._resume_ref = "hermes-ref-const"
        await self._on(StreamEvent("system", "waiting", {"reason": "turn_complete"}))
        self._alive = False

    async def pause(self) -> None:
        return None

    async def stop(self) -> None:
        self._alive = False
        if self._on is not None:
            await self._on(StreamEvent("system", "closed", {}))


class NoRefHermesDriver(FakeHermesDriver):
    """Hermes liefert KEINE fortsetzbare ID → Turn endet als sichtbarer Fehler."""

    async def _answer(self, prompt: str) -> None:
        assert self._on is not None and self._spec is not None
        await self._on(StreamEvent("assistant", None,
                                   {"message": {"content": [{"type": "text",
                                                            "text": f"Hermes: {prompt}"}]}}))
        # Keine Kontrollzeile → sichtbarer Fehler (kein stiller neuer Chat).
        await self._on(StreamEvent("system", "error",
                                   {"message": "Hermes lieferte keine Conversation-ID."}))
        self._alive = False


def _app(engine_factory):
    return create_app(engine_factory=engine_factory)


def _auth_headers():
    return {}


def _create(client):
    return client.post(
        "/sessions/hermes",
        json={"project_path": "/home/dev/projects",
              "engine": "hermes", "model": "qwen3.5-397b-a17b",
              "title": "Mein Hermes"},
        headers=_auth_headers(),
    )


# --- Startvertrag (Bestand) -------------------------------------------------


def test_resolver_returns_enabled_available_models(hermes_enabled):
    from app.engine.hermes_resolver import hermes_model_options

    opts = hermes_model_options()
    keys = {(o.engine, o.model) for o in opts}
    assert ("hermes", "qwen3.5-397b-a17b") in keys
    assert all(o.engine and o.model for o in opts)


def test_resolve_invocation_translates_claude_to_hermes(hermes_enabled):
    from app.engine.hermes_resolver import resolve_hermes_invocation

    inv = resolve_hermes_invocation("claude", "sonnet")
    assert inv.provider == "anthropic"
    assert inv.model.startswith("claude-")
    with pytest.raises(ValueError):
        resolve_hermes_invocation("claude", "nicht-existent")


def test_options_endpoint(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = client.get("/sessions/hermes/options", headers=_auth_headers())
    assert resp.status_code == 200
    assert "models" in resp.json()


# --- PROJ-86: Start OHNE Prozess/Prompt -------------------------------------


def test_create_hermes_starts_waiting_without_process(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = _create(client)
    assert resp.status_code == 201, resp.text
    s = resp.json()
    assert s["engine"] == "hermes"
    assert s["status"] == "waiting"
    assert s["hermes_resume_ref"] is None
    assert s["context_usage_available"] is False
    assert s["permission_mode"] == "bypassPermissions"
    assert s["savings_enabled"] is True
    assert s["project_name"] == "Mein Hermes"


def test_create_hermes_overrides_client_fields(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    resp = _create(client)
    assert resp.status_code == 201, resp.text
    s = resp.json()
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
    assert s["engine"] == "hermes"
    assert s["permission_mode"] == "bypassPermissions"


def test_create_hermes_extra_forbid(hermes_enabled):
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
    _create(client)
    listing = client.get("/sessions", headers=_auth_headers()).json()
    assert any(s["engine"] == "hermes" for s in listing)


# --- PROJ-86: Turns + Resume ------------------------------------------------


def test_first_turn_sets_ref_and_waits(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    resp = client.post(f"/sessions/{sid}/input", json={"text": "Hallo"}, headers=_auth_headers())
    assert resp.status_code == 202, resp.text
    s = client.get(f"/sessions/{sid}", headers=_auth_headers()).json()
    assert s["status"] == "waiting"
    assert s["hermes_resume_ref"] == "hermes-ref-const"
    assert s["context_usage_available"] is True


def test_three_follow_up_turns_keep_same_ref(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    ref = None
    for text in ("Eins", "Zwei", "Drei"):
        client.post(f"/sessions/{sid}/input", json={"text": text}, headers=_auth_headers())
        s = client.get(f"/sessions/{sid}", headers=_auth_headers()).json()
        assert s["status"] == "waiting", text
        if ref is None:
            ref = s["hermes_resume_ref"]
        else:
            assert s["hermes_resume_ref"] == ref, f"Ref änderte sich bei '{text}'"
        assert s["hermes_resume_ref"].startswith("hermes-ref-")


def test_whitespace_input_returns_422(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    for payload in {"text": "   "}, {"text": "\n\t"}:
        resp = client.post(f"/sessions/{sid}/input", json=payload, headers=_auth_headers())
        assert resp.status_code == 422, resp.text
    # Session bleibt wartend, kein Turn gestartet.
    s = client.get(f"/sessions/{sid}", headers=_auth_headers()).json()
    assert s["status"] == "waiting"
    assert s["hermes_resume_ref"] is None


def test_missing_id_errors_and_keeps_no_ref(hermes_enabled):
    app = _app(lambda p: NoRefHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    client.post(f"/sessions/{sid}/input", json={"text": "Hallo"}, headers=_auth_headers())
    s = client.get(f"/sessions/{sid}", headers=_auth_headers()).json()
    assert s["status"] == "error"
    assert s["hermes_resume_ref"] is None
    assert "Conversation-ID" in (s["error"] or "")


# --- PROJ-86: Liveness / Reanimation ----------------------------------------


def test_hermes_skipped_in_liveness_poller(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    manager = app.state.manager
    import anyio

    anyio.run(manager.evaluate_liveness_once)
    s = client.get(f"/sessions/{sid}", headers=_auth_headers()).json()
    # Hermes wird nicht reanimiert → bleibt wartend, keine Fehler.
    assert s["status"] == "waiting"
    assert s["hermes_resume_ref"] is None


def test_hermes_reanimate_returns_409(hermes_enabled):
    app = _app(lambda p: FakeHermesDriver(p))
    client = TestClient(app)
    sid = _create(client).json()["session_id"]
    resp = client.post(f"/sessions/{sid}/reanimate", headers=_auth_headers())
    assert resp.status_code == 409, resp.text
