"""PROJ-18 — Weitere Engines (Registry + HTTP-/CLI-Treiber + iFrame/Launch).

Deckt die Akzeptanzkriterien ab:
- Generischer Treiber/Registry, codefrei konfigurierbar (engines.yaml).
- OpenAI (API) als erste Test-Engine und OpenRouter als zweite — **derselbe**
  ``OpenAIDriver`` (OpenAI-API-kompatibel), nur anderer api_base/auth_env.
- Engine-agnostische Session-Sicht; saubere Degradation/Ausgrauen statt Crash.
- Fehlende/fehlkonfigurierte Engine → klare Meldung, Claude bleibt nutzbar.
- Engine-Auswahl in POST /sessions; Claude bleibt Default.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.engine.adapters import (
    VALID_ADAPTERS,
    get_adapter,
    jsonl_parse_line,
    plaintext_parse_line,
)
from app.engine.base import LaunchSpec
from app.engine.manager import SessionManager
from app.engine.openai_driver import OpenAIDriver, _build_usage, _parse_sse_line
from app.engine.registry import (
    CLAUDE_KEY,
    EngineProfile,
    EngineRegistry,
    _builtin_claude,
    engine_registry,
)
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# ===========================================================================
# Hilfen
# ===========================================================================

def _collector():
    """Async Event-Handler (der Treiber ``await``et ihn) + die gesammelte Event-Liste."""
    events: list = []

    async def on_event(e):
        events.append(e)

    return events, on_event


def _registry(tmp_path, yaml_text: str) -> EngineRegistry:
    """Frische Registry über eine temporäre engines.yaml (entkoppelt vom Singleton)."""
    p = tmp_path / "engines.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return EngineRegistry(str(p))


@pytest.fixture()
def use_engines(tmp_path, monkeypatch):
    """Biegt den Modul-Singleton ``engine_registry`` auf eine Test-YAML um (für Route/
    Manager, die den Singleton nutzen) und stellt ihn danach wieder her."""

    def _apply(yaml_text: str):
        p = tmp_path / "engines.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        monkeypatch.setattr(engine_registry, "_path", str(p))
        monkeypatch.setattr(engine_registry, "_mtime", None)
        monkeypatch.setattr(engine_registry, "_loaded_once", False)
        monkeypatch.setattr(engine_registry, "_source", "default")
        monkeypatch.setattr(engine_registry, "_profiles", {CLAUDE_KEY: _builtin_claude()})
        return p

    return _apply


# Zwei Test-Engines, EIN Treiber: OpenAI (1.) und OpenRouter (2., OpenAI-kompatibel).
_TWO_ENGINES_YAML = """
engines:
  - key: openai
    label: "OpenAI (GPT)"
    kind: engine
    driver: openai
    auth_env: OPENAI_API_KEY
    api_base: https://api.openai.com
    api_path: /v1/chat/completions
    models: [gpt-4o-mini]
    default_model: gpt-4o-mini
    context_window: 128000
  - key: openrouter
    label: "OpenRouter"
    kind: engine
    driver: openai
    auth_env: OPENROUTER_API_KEY
    api_base: https://openrouter.ai/api
    api_path: /v1/chat/completions
    models: [openai/gpt-4o-mini]
    default_model: openai/gpt-4o-mini
    context_window: 128000
"""


# ===========================================================================
# 1) Registry — codefreie Konfiguration, Claude immer da, robuste Degradation
# ===========================================================================

def test_claude_always_present_without_file():
    """Ohne engines.yaml läuft Jupiter nur mit der eingebauten Claude-Engine
    (rückwärtskompatibel zu PROJ-1)."""
    reg = EngineRegistry("/nonexistent/engines.yaml")
    profs = reg.all()
    assert [p.key for p in profs] == [CLAUDE_KEY]
    claude = profs[0]
    assert claude.is_claude
    assert "tools" in claude.capabilities and "resume" in claude.capabilities


def test_loads_openai_first_and_openrouter_second(tmp_path):
    """AC: OpenAI = erste Test-Engine, OpenRouter = zweite — beide über denselben
    `openai`-Treiber, nur anderer api_base/auth_env (kein neuer Code)."""
    reg = _registry(tmp_path, _TWO_ENGINES_YAML)
    keys = [p.key for p in reg.all()]
    assert keys == [CLAUDE_KEY, "openai", "openrouter"]

    openai = reg.require("openai")
    openrouter = reg.require("openrouter")
    # Ein Treiber, zwei Anbieter — der eigentliche Abstraktions-Nachweis.
    assert openai.driver == "openai" and openrouter.driver == "openai"
    assert openai.api_base == "https://api.openai.com"
    assert openrouter.api_base == "https://openrouter.ai/api"
    assert openrouter.auth_env == "OPENROUTER_API_KEY"
    # Der openai-Treiber erzwingt die usage-Capability (Token-/Kontext-Anzeige).
    assert openrouter.has_capability("usage")


def test_reserved_claude_key_is_skipped(tmp_path):
    """Der Schlüssel `claude` ist reserviert — ein YAML-Eintrag darf ihn nicht kapern."""
    reg = _registry(
        tmp_path,
        "engines:\n  - key: claude\n    label: Fake\n    kind: engine\n    driver: openai\n",
    )
    claude = reg.require(CLAUDE_KEY)
    assert claude.label == "Claude Max"  # eingebaut, NICHT der YAML-Eintrag
    assert reg.snapshot()["warning"]


def test_broken_entry_skipped_rest_loads(tmp_path):
    """Ein defekter Eintrag wird übersprungen (mit Warnung), der Rest lädt weiter."""
    reg = _registry(
        tmp_path,
        "engines:\n"
        "  - key: openai\n    label: OpenAI\n    kind: engine\n    driver: openai\n"
        "  - key: kaputt\n    label: Kaputt\n    kind: iframe\n",  # iframe ohne url → ValueError
    )
    keys = [p.key for p in reg.all()]
    assert "openai" in keys and "kaputt" not in keys
    assert reg.snapshot()["warning"]


def test_broken_file_degrades_to_claude(tmp_path):
    """Kaputtes YAML → nur Claude (kein Crash), mit Warnung."""
    p = tmp_path / "engines.yaml"
    p.write_text("engines: [ : : :", encoding="utf-8")
    reg = EngineRegistry(str(p))
    assert [x.key for x in reg.all()] == [CLAUDE_KEY]
    assert reg.snapshot()["warning"]


def test_availability_reports_missing_key(tmp_path, monkeypatch):
    """API-Engine ohne Key → nicht verfügbar + deutscher Setup-Hinweis (Ausgrauen)."""
    reg = _registry(tmp_path, _TWO_ENGINES_YAML)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    available, reason = reg.require("openai").availability()
    assert available is False
    assert "OPENAI_API_KEY" in reason

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert reg.require("openai").availability() == (True, None)


def test_valid_model_per_profile(tmp_path):
    reg = _registry(tmp_path, _TWO_ENGINES_YAML)
    openrouter = reg.require("openrouter")
    assert openrouter.valid_model("openai/gpt-4o-mini") is True
    assert openrouter.valid_model("haiku") is False
    # Leere models-Liste = alles erlauben (defensiver Default).
    assert EngineProfile(key="x", label="X").valid_model("irgendwas") is True


def test_to_read_is_secret_free(tmp_path):
    """GET-/engines-Auszug enthält keine Secrets (kein auth_env, kein bin/argv)."""
    reg = _registry(tmp_path, _TWO_ENGINES_YAML)
    data = reg.require("openai").to_read()
    assert "auth_env" not in data and "bin" not in data and "argv_template" not in data
    assert data["key"] == "openai" and data["driver"] == "openai"
    assert "available" in data and "models" in data


def test_live_reload_on_mtime_change(tmp_path):
    """mtime-Watch: eine geänderte Datei wird ohne Neustart neu geladen (PolicyStore-Muster)."""
    p = tmp_path / "engines.yaml"
    p.write_text(
        "engines:\n  - key: openai\n    label: OpenAI\n    kind: engine\n    driver: openai\n",
        encoding="utf-8",
    )
    reg = EngineRegistry(str(p))
    assert "openrouter" not in [x.key for x in reg.all()]

    p.write_text(_TWO_ENGINES_YAML, encoding="utf-8")
    os.utime(p, (1_000_000_000, 1_000_000_000))  # mtime sicher verändern
    assert "openrouter" in [x.key for x in reg.all()]


# ===========================================================================
# 2) Adapter — Strom-Normalisierung (jsonl / plaintext / Fallback)
# ===========================================================================

def test_plaintext_adapter():
    ev = plaintext_parse_line("Hallo Welt\n")
    assert ev is not None and ev.type == "assistant"
    assert ev.raw["message"]["content"][0]["text"] == "Hallo Welt"
    assert plaintext_parse_line("   \n") is None  # Leerzeilen → ignorieren


def test_jsonl_adapter_text_and_done():
    text_ev = jsonl_parse_line('{"response": "Teil"}')
    assert text_ev.type == "assistant"
    assert text_ev.raw["message"]["content"][0]["text"] == "Teil"

    done_ev = jsonl_parse_line('{"done": true, "text": "fertig"}')
    assert done_ev.type == "result" and done_ev.subtype == "success"


def test_jsonl_adapter_degrades_on_non_json():
    """Edge-Case: keine JSON-Zeile → defensiv als Klartext (kein Crash)."""
    ev = jsonl_parse_line("kein json hier")
    assert ev is not None and ev.type == "assistant"


def test_get_adapter_unknown_falls_back_to_plaintext():
    assert get_adapter("unbekannt") is plaintext_parse_line
    assert get_adapter("jsonl") is jsonl_parse_line
    assert {"claude", "jsonl", "plaintext"} <= set(VALID_ADAPTERS)


# ===========================================================================
# 3) OpenAIDriver — EIN Treiber, zwei Anbieter (OpenAI + OpenRouter)
# ===========================================================================

def test_parse_sse_line():
    assert _parse_sse_line('data: {"choices":[{"delta":{"content":"Hi"}}]}') == ("Hi", None, False)
    assert _parse_sse_line("data: [DONE]") == ("", None, True)
    delta, usage, done = _parse_sse_line('data: {"usage":{"prompt_tokens":5,"completion_tokens":2}}')
    assert usage == {"prompt_tokens": 5, "completion_tokens": 2} and done is False
    assert _parse_sse_line(": openrouter processing") == ("", None, False)  # Kommentarzeile
    assert _parse_sse_line("") == ("", None, False)


def test_build_usage_maps_openai_to_claude_shape():
    u = _build_usage(12, 3)
    assert u == {
        "input_tokens": 12,
        "output_tokens": 3,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }


class _FakeStream:
    def __init__(self, status: int, lines: list[str], body: bytes = b""):
        self.status_code = status
        self._lines = lines
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln

    async def aread(self):
        return self._body


class _FakeClient:
    def __init__(self, rec: dict, status: int, lines: list[str], body: bytes = b""):
        self._rec, self._status, self._lines, self._body = rec, status, lines, body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def stream(self, method, url, json=None, headers=None):
        self._rec.update(method=method, url=url, json=json, headers=headers)
        return _FakeStream(self._status, self._lines, self._body)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "key,api_base,auth_env,model",
    [
        ("openai", "https://api.openai.com", "OPENAI_API_KEY", "gpt-4o-mini"),
        ("openrouter", "https://openrouter.ai/api", "OPENROUTER_API_KEY", "openai/gpt-4o-mini"),
    ],
)
async def test_openai_driver_turn_for_both_providers(monkeypatch, key, api_base, auth_env, model):
    """DERSELBE OpenAIDriver fährt OpenAI UND OpenRouter — nur Profil unterscheidet sich.
    Beweist die Treiber-Abstraktion über zwei Anbieter (das Kern-AC von PROJ-18)."""
    monkeypatch.setenv(auth_env, "secret-123")
    profile = EngineProfile(
        key=key, label=key, kind="engine", driver="openai",
        api_base=api_base, api_path="/v1/chat/completions", auth_env=auth_env,
        context_window=128000, capabilities=["usage", "multi_turn"],
    )
    rec: dict = {}
    sse = [
        'data: {"choices":[{"delta":{"content":"Hal"}}]}',
        'data: {"choices":[{"delta":{"content":"lo"}}]}',
        'data: {"usage":{"prompt_tokens":12,"completion_tokens":3}}',
        "data: [DONE]",
    ]
    driver = OpenAIDriver(profile, client_factory=lambda: _FakeClient(rec, 200, sse))

    events, on_event = _collector()
    spec = LaunchSpec(
        session_id="s1", project_path=PROJECT, model=model,
        permission_mode="default", initial_prompt="Sag Hallo",
    )
    await driver.start(spec, on_event)

    # Richtiger Anbieter-Endpunkt + Key aus der korrekten Env-Variable.
    assert rec["url"] == f"{api_base}/v1/chat/completions"
    assert rec["headers"]["Authorization"] == "Bearer secret-123"

    types = [(e.type, e.subtype) for e in events]
    assert ("system", "init") in types
    assert ("assistant", None) in types
    assert ("result", "success") in types

    assistant = next(e for e in events if e.type == "assistant")
    assert assistant.raw["message"]["content"][0]["text"] == "Hallo"
    result = next(e for e in events if e.type == "result")
    assert result.raw["usage"]["input_tokens"] == 12
    assert result.raw["modelUsage"][model]["contextWindow"] == 128000


@pytest.mark.asyncio
async def test_openai_driver_missing_key_emits_error(monkeypatch):
    """Fehlender Key → system/error mit deutschem Hinweis (kein Crash, Claude bleibt nutzbar)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    profile = EngineProfile(key="openai", label="OpenAI", driver="openai", auth_env="OPENAI_API_KEY")
    driver = OpenAIDriver(profile, client_factory=lambda: _FakeClient({}, 200, []))
    events, on_event = _collector()
    spec = LaunchSpec("s1", PROJECT, "gpt-4o-mini", "default", "Hi")
    await driver.start(spec, on_event)
    errors = [e for e in events if e.type == "system" and e.subtype == "error"]
    assert errors and "OPENAI_API_KEY" in errors[0].raw["message"]


@pytest.mark.asyncio
async def test_openai_driver_http_401_emits_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "bad")
    profile = EngineProfile(key="openai", label="OpenAI", driver="openai", auth_env="OPENAI_API_KEY")
    driver = OpenAIDriver(
        profile, client_factory=lambda: _FakeClient({}, 401, [], body=b'{"error":"x"}')
    )
    events, on_event = _collector()
    await driver.start(LaunchSpec("s1", PROJECT, "gpt-4o-mini", "default", "Hi"), on_event)
    errors = [e for e in events if e.type == "system" and e.subtype == "error"]
    assert errors and "Authentifizierung" in errors[0].raw["message"]


# ===========================================================================
# 4) GET /engines — engine-agnostischer, secret-freier Überblick
# ===========================================================================

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


def test_engines_endpoint_default_only_claude(client: TestClient):
    """Ohne engines.yaml: nur Claude, als Default an erster Stelle."""
    body = client.get("/engines").json()
    assert body["engines"][0]["key"] == CLAUDE_KEY
    assert body["engines"][0]["available"] is True


def test_engines_endpoint_lists_configured_and_hides_secrets(client, use_engines, monkeypatch):
    use_engines(_TWO_ENGINES_YAML)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    body = client.get("/engines").json()
    by_key = {e["key"]: e for e in body["engines"]}
    assert {"claude", "openai", "openrouter"} <= set(by_key)
    # OpenAI hat einen Key → verfügbar; OpenRouter nicht → ausgegraut + Hinweis.
    assert by_key["openai"]["available"] is True
    assert by_key["openrouter"]["available"] is False
    assert "OPENROUTER_API_KEY" in by_key["openrouter"]["unavailable_reason"]
    # Secret-frei: kein auth_env im API-Response.
    assert all("auth_env" not in e for e in body["engines"])


# ===========================================================================
# 5) POST /sessions — Engine-Auswahl; Claude bleibt Default
# ===========================================================================

def _post(client: TestClient, **overrides):
    body = {"project_path": PROJECT, "initial_prompt": "Hallo", "model": "haiku"}
    body.update(overrides)
    return client.post("/sessions", json=body)


def test_create_default_engine_is_claude(client: TestClient):
    resp = _post(client)
    assert resp.status_code == 201
    assert resp.json()["engine"] == "claude"


def test_create_unknown_engine_400(client: TestClient):
    resp = _post(client, engine="gibtsnicht")
    assert resp.status_code == 400


def test_create_missing_key_engine_503(client, use_engines, monkeypatch):
    """Engine ohne API-Key → 503 mit klarer Meldung (Claude bleibt unabhängig nutzbar)."""
    use_engines(_TWO_ENGINES_YAML)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = _post(client, engine="openai", model="gpt-4o-mini")
    assert resp.status_code == 503
    assert "OPENAI_API_KEY" in resp.json()["detail"]


def test_create_iframe_engine_rejected(client, use_engines):
    """iFrame/Launch-Einträge sind keine steuerbaren Sessions → 400."""
    use_engines(
        "engines:\n  - key: board\n    label: Board\n    kind: iframe\n    url: https://example.org\n"
    )
    resp = _post(client, engine="board")
    assert resp.status_code == 400


def test_create_openrouter_session_ok(use_engines, monkeypatch):
    """Vollständiger Pfad: OpenRouter-Session via API startet und erscheint engine-agnostisch
    mit `engine=openrouter` (FakeDriver injiziert über engine_factory)."""
    use_engines(_TWO_ENGINES_YAML)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    app = create_app(
        driver_factory=lambda: FakeDriver(),
        engine_factory=lambda profile: FakeDriver(),
    )
    client = TestClient(app)
    resp = _post(client, engine="openrouter", model="openai/gpt-4o-mini")
    assert resp.status_code == 201
    data = resp.json()
    assert data["engine"] == "openrouter"
    assert data["status"] in ("waiting", "running")
