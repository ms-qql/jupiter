"""PROJ-51 — Engine-/Modellverwaltung in den App-Einstellungen."""
from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from app.engine.registry import CLAUDE_KEY, _builtin_claude, engine_registry
from app.main import create_app

from .fakes import FakeDriver


def _client_with_registry(tmp_path, monkeypatch, yaml_text: str = "") -> TestClient:
    p = tmp_path / "engines.yaml"
    if yaml_text:
        p.write_text(yaml_text, encoding="utf-8")
    monkeypatch.setattr(engine_registry, "_path", str(p))
    monkeypatch.setattr(engine_registry, "_mtime", None)
    monkeypatch.setattr(engine_registry, "_loaded_once", False)
    monkeypatch.setattr(engine_registry, "_source", "default")
    monkeypatch.setattr(engine_registry, "_warning", None)
    monkeypatch.setattr(engine_registry, "_profiles", {CLAUDE_KEY: _builtin_claude()})
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


def _payload() -> dict:
    return {
        "engines": [
            {
                "key": "claude",
                "label": "Claude Max",
                "kind": "engine",
                "driver": "claude",
                "enabled": True,
                "models": ["haiku", "opus", "sonnet"],
                "default_model": "haiku",
                "capabilities": ["usage", "resume", "multi_turn", "tools", "abc"],
            },
            {
                "key": "openai",
                "label": "OpenAI",
                "kind": "engine",
                "driver": "openai",
                "enabled": True,
                "auth_env": "OPENAI_API_KEY",
                "api_base": "https://api.openai.com",
                "api_path": "/v1/chat/completions",
                "models": ["gpt-4o-mini", "gpt-4o"],
                "default_model": "gpt-4o-mini",
                "context_window": 128000,
                "capabilities": ["usage", "multi_turn"],
            },
            {
                "key": "swisscom",
                "label": "Swisscom",
                "kind": "engine",
                "driver": "openai",
                "enabled": False,
                "auth_env": "SWISSCOM_API_KEY",
                "api_base": "https://api.swisscom.com",
                "api_path": "/v1/chat/completions",
                "models": ["swiss-ai-large"],
                "default_model": "swiss-ai-large",
                "context_window": 128000,
                "capabilities": ["usage", "multi_turn"],
            },
        ]
    }


def test_settings_engines_includes_swisscom_placeholder(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)

    body = client.get("/settings/engines").json()
    by_key = {e["key"]: e for e in body["engines"]}

    assert {"claude", "swisscom"} <= set(by_key)
    assert by_key["swisscom"]["enabled"] is False
    assert by_key["swisscom"]["auth_env"] == "SWISSCOM_API_KEY"
    assert "auth_env" in by_key["swisscom"]  # Settings-Sicht, aber nur Variablenname.


def test_put_settings_engines_writes_yaml_and_updates_get_engines(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)

    resp = client.put("/settings/engines", json=_payload())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["engines"][0]["key"] == "claude"
    assert body["engines"][0]["default_model"] == "haiku"

    saved = yaml.safe_load((tmp_path / "engines.yaml").read_text(encoding="utf-8"))
    assert saved["claude"]["default_model"] == "haiku"
    assert [e["key"] for e in saved["engines"]] == ["openai", "swisscom"]
    assert saved["engines"][1]["enabled"] is False

    # Launcher-Sicht bleibt secret-frei und filtert deaktivierte Provider.
    overview = client.get("/engines").json()
    keys = [e["key"] for e in overview["engines"]]
    assert "openai" in keys
    assert "swisscom" not in keys
    assert all("auth_env" not in e and "api_base" not in e for e in overview["engines"])


def test_put_settings_engines_preserves_non_engine_entries(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)
    body = _payload()
    body["engines"].extend(
        [
            {
                "key": "video_summary",
                "label": "Video Summary",
                "kind": "native",
                "enabled": True,
                "models": [],
                "capabilities": [],
                "group": "micro",
                "icon": "film",
            },
            {
                "key": "excalidraw",
                "label": "Excalidraw",
                "kind": "iframe",
                "enabled": True,
                "models": [],
                "capabilities": [],
                "group": "micro",
                "icon": "pentool",
                "url": "https://excalidraw.com",
                "sandbox": "allow-scripts allow-same-origin",
            },
            {
                "key": "gpt-web",
                "label": "ChatGPT Web",
                "kind": "launch",
                "enabled": True,
                "models": [],
                "capabilities": [],
                "target": "https://chat.openai.com",
            },
        ]
    )

    resp = client.put("/settings/engines", json=body)
    assert resp.status_code == 200, resp.text

    saved = yaml.safe_load((tmp_path / "engines.yaml").read_text(encoding="utf-8"))
    by_key = {e["key"]: e for e in saved["engines"]}
    assert by_key["video_summary"] == {
        "key": "video_summary",
        "label": "Video Summary",
        "kind": "native",
        "group": "micro",
        "icon": "film",
    }
    assert by_key["excalidraw"]["kind"] == "iframe"
    assert by_key["excalidraw"]["url"] == "https://excalidraw.com"
    assert by_key["gpt-web"]["kind"] == "launch"
    assert by_key["gpt-web"]["target"] == "https://chat.openai.com"

    overview = client.get("/settings/engines").json()
    returned = {e["key"]: e for e in overview["engines"]}
    assert returned["video_summary"]["kind"] == "native"
    assert returned["excalidraw"]["kind"] == "iframe"
    assert returned["gpt-web"]["kind"] == "launch"


def test_validate_settings_engines_does_not_write_file(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)
    p = tmp_path / "engines.yaml"

    resp = client.post("/settings/engines/validate", json=_payload())
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert not p.exists()


def test_rejects_default_model_not_in_models(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)
    body = _payload()
    body["engines"][1]["default_model"] = "gpt-nicht-da"

    resp = client.put("/settings/engines", json=body)
    assert resp.status_code == 400
    assert "default_model" in resp.json()["detail"]
    assert not (tmp_path / "engines.yaml").exists()


def test_rejects_secret_value_in_auth_env(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)
    body = _payload()
    body["engines"][1]["auth_env"] = "sk-test-secret-value-that-should-not-be-here"

    resp = client.post("/settings/engines/validate", json=body)
    assert resp.status_code == 400
    assert "kein API-Key-Wert" in resp.json()["detail"]


def test_rejects_active_engine_without_models(tmp_path, monkeypatch):
    client = _client_with_registry(tmp_path, monkeypatch)
    body = _payload()
    body["engines"][1]["models"] = []
    body["engines"][1]["default_model"] = None

    resp = client.put("/settings/engines", json=body)
    assert resp.status_code == 400
    assert "mindestens ein Modell" in resp.json()["detail"]
