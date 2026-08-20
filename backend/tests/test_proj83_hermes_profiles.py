"""PROJ-83 Rework — Hermes-Profil-Modellwahl (GET/PATCH /settings/hermes-profiles).

Testet die Erkennung der ``jupiter-*``-Profile, die Rückübersetzung von
``provider``/``default`` in Engine/Modell (Registry-Vokabular) sowie das atomare,
profilweise Schreiben von Engine+Modell. Die echte ``~/.hermes/profiles`` wird
nie angerührt — alle Tests arbeiten in einem temporären Verzeichnis.
"""
from __future__ import annotations

import os

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import settings
from app.engine import hermes_profiles as svc
from app.main import create_app


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    """Einen temporären Profilordner mit einigen ``jupiter-*``-Profilen."""
    d = tmp_path / "profiles"
    d.mkdir()

    def _profile(
        name: str,
        model_default: str | None = None,
        provider: str | None = None,
        extra: str = "",
        broken: bool = False,
    ) -> None:
        p = d / name
        p.mkdir()
        if broken:
            (p / "config.yaml").write_text("::: not valid yaml : :\n  - [", encoding="utf-8")
            return
        body = "model:\n"
        if model_default is not None:
            body += f"  default: {model_default}\n"
        if provider is not None:
            body += f"  provider: {provider}\n"
        body += extra
        (p / "config.yaml").write_text(body, encoding="utf-8")

    # config.yaml-Stand (provider/default) — Rückübersetzung erwartet:
    _profile("jupiter-backend", "hy3", "opencode-go", "toolsets:\n  - hermes-cli\n")
    # → engine="opencode", model="opencode-go/hy3"
    _profile("jupiter-requirements", "gpt-5.6-terra", "openai-codex")
    # → engine="codex", model="gpt-5.6-terra"
    _profile("jupiter-qa")  # kein model-Block → engine/model None
    _profile("jupiter-broken", broken=True)
    _profile("default", "sonnet")  # ausgeschlossen (nicht-abc)
    # Realistischer Hermes-Stand: provider=anthropic, default=claude-<alias>-<ver>.
    _profile("jupiter-backoffice", "claude-opus-5", "anthropic")  # → engine="claude", model="opus"

    # Ausgeschlossen per _EXCLUDE
    _profile("jupiter", "sonnet")

    monkeypatch.setattr(settings, "hermes_profiles_dir", str(d))
    return d


@pytest.fixture
def client(profiles_dir):
    return TestClient(create_app())


# --- GET ----------------------------------------------------------------


def test_get_lists_abc_profiles_with_engine_model(client):
    res = client.get("/settings/hermes-profiles")
    assert res.status_code == 200
    data = res.json()
    # Kein flacher Modellbestand mehr — kommt aus GET /engines.
    assert "models" not in data
    names = {p["profile"] for p in data["profiles"]}
    assert "jupiter-backend" in names
    assert "jupiter-requirements" in names
    assert "jupiter-qa" in names
    assert "default" not in names
    assert "jupiter" not in names

    backend = next(p for p in data["profiles"] if p["profile"] == "jupiter-backend")
    # Rückübersetzung provider/default → engine/model (Registry-Vokabular)
    assert backend["engine"] == "opencode"
    assert backend["model"] == "opencode-go/hy3"
    assert backend["provider"] == "opencode-go"
    assert backend["default"] == "hy3"

    req = next(p for p in data["profiles"] if p["profile"] == "jupiter-requirements")
    assert req["engine"] == "codex"
    assert req["model"] == "gpt-5.6-terra"

    backoffice = next(p for p in data["profiles"] if p["profile"] == "jupiter-backoffice")
    assert backoffice["engine"] == "claude"
    assert backoffice["model"] == "opus"
    assert backoffice["provider"] == "anthropic"
    assert backoffice["default"] == "claude-opus-5"

    # Profil ohne model-Block → engine/model None, aber kein Fehler
    qa = next(p for p in data["profiles"] if p["profile"] == "jupiter-qa")
    assert qa["engine"] is None
    assert qa["model"] is None
    assert qa["error"] is None

    # kaputtes Profil → einzeln als Fehler markiert, Gesamt nicht crash
    broken = next(p for p in data["profiles"] if p["profile"] == "jupiter-broken")
    assert broken["error"] is not None
    assert broken["engine"] is None


def test_get_missing_dir_returns_warning_empty(client, monkeypatch):
    monkeypatch.setattr(settings, "hermes_profiles_dir", "/nope/does/not/exist")
    res = client.get("/settings/hermes-profiles")
    assert res.status_code == 200
    data = res.json()
    assert data["profiles"] == []
    assert data["warning"] is not None


def test_get_label_is_role_name(client):
    data = client.get("/settings/hermes-profiles").json()
    backend = next(p for p in data["profiles"] if p["profile"] == "jupiter-backend")
    assert backend["label"] == "Backend"


def test_get_unresolvable_profile_marked_null(client, profiles_dir):
    # Manuell außerhalb Jupiters gesetzter Stand → engine/model None (nicht verfügbar).
    cfg = profiles_dir / "jupiter-qa" / "config.yaml"
    cfg.write_text("model:\n  provider: some-unknown\n  default: weird/model\n", encoding="utf-8")
    data = client.get("/settings/hermes-profiles").json()
    qa = next(p for p in data["profiles"] if p["profile"] == "jupiter-qa")
    assert qa["engine"] is None
    assert qa["model"] is None
    assert qa["provider"] == "some-unknown"
    assert qa["default"] == "weird/model"


# --- PATCH ---------------------------------------------------------------


def test_patch_writes_engine_model_atomically_and_keeps_rest(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-qa", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    r = results[0]
    assert r["ok"] is True
    assert r["error"] is None
    # Antwort enthält den vollständig zurückübersetzten Eintrag.
    assert r["entry"]["engine"] == "claude"
    assert r["entry"]["model"] == "opus"
    assert r["entry"]["provider"] == "anthropic"
    assert r["entry"]["default"] == "claude-opus-5"
    # Datei: provider + default gemeinsam gesetzt
    cfg = yaml.safe_load((profiles_dir / "jupiter-qa" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["provider"] == "anthropic"
    assert cfg["model"]["default"] == "claude-opus-5"


def test_patch_preserves_other_keys(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-backend", "engine": "claude", "model": "sonnet"}]},
    )
    assert res.status_code == 200
    cfg = yaml.safe_load((profiles_dir / "jupiter-backend" / "config.yaml").read_text(encoding="utf-8"))
    # provider + default überschrieben, toolsets erhalten
    assert cfg["model"]["provider"] == "anthropic"
    assert cfg["model"]["default"] == "claude-sonnet-5"
    assert cfg["toolsets"] == ["hermes-cli"]


def test_patch_invalid_engine_model_rejected(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={
            "profiles": [
                {"profile": "jupiter-backend", "engine": "opencode", "model": "gpt-5.6-terra"}
            ]
        },
    )
    assert res.status_code == 200
    r = res.json()[0]
    assert r["ok"] is False
    assert r["error"] is not None
    assert r["entry"] is None
    # Datei unverändert
    cfg = yaml.safe_load((profiles_dir / "jupiter-backend" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "hy3"
    assert cfg["model"]["provider"] == "opencode-go"


def test_patch_non_abc_profile_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "default", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    r = res.json()[0]
    assert r["ok"] is False
    assert r["entry"] is None


def test_patch_partial_failure_reports_each(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={
            "profiles": [
                {"profile": "jupiter-qa", "engine": "claude", "model": "haiku"},       # ok
                {"profile": "jupiter-backend", "engine": "opencode", "model": "bogus"},  # Fehler
            ]
        },
    )
    assert res.status_code == 200
    results = {r["profile"]: r for r in res.json()}
    assert results["jupiter-qa"]["ok"] is True
    assert results["jupiter-qa"]["entry"]["model"] == "haiku"
    assert results["jupiter-backend"]["ok"] is False
    # der gültige Eintrag ist tatsächlich gespeichert
    cfg = yaml.safe_load((profiles_dir / "jupiter-qa" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "claude-haiku-4.5"


def test_patch_empty_body_returns_empty_list(client):
    res = client.patch("/settings/hermes-profiles", json={"profiles": []})
    assert res.status_code == 200
    assert res.json() == []


def test_patch_unknown_profile_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-nonexistent", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    r = res.json()[0]
    assert r["ok"] is False
    assert r["entry"] is None


def test_patch_unreadable_profile_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-broken", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    r = res.json()[0]
    assert r["ok"] is False
    assert r["entry"] is None


def test_patch_invalid_engine_rejected_by_schema(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-qa", "engine": "openai", "model": "x"}]},
    )
    # engine nicht in {claude, codex, opencode} → 422
    assert res.status_code == 422


# --- PROJ-83 BUG-1: Path-Traversal im `profile`-Parameter -----------------


def test_patch_traversal_slash_rejected_and_does_not_escape(client, tmp_path):
    escape = tmp_path / "escape_target"
    escape.mkdir()
    secret_file = escape / "config.yaml"
    secret_file.write_text("secret: TOPSECRET\n", encoding="utf-8")

    res = client.patch(
        "/settings/hermes-profiles",
        json={
            "profiles": [
                {"profile": "jupiter-qa/../../escape_target", "engine": "claude", "model": "opus"}
            ]
        },
    )
    assert res.status_code == 200
    r = res.json()[0]
    assert r["ok"] is False
    assert r["error"] == "Kein abc-Profil."
    assert secret_file.read_text(encoding="utf-8") == "secret: TOPSECRET\n"


def test_patch_traversal_dotdot_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-qa/..", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


def test_patch_traversal_absolute_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-/etc/passwd", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


def test_patch_traversal_uppercase_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"profiles": [{"profile": "jupiter-QA", "engine": "claude", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False
