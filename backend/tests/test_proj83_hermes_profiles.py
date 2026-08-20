"""PROJ-83 — Hermes-Profil-Modellwahl (GET/PATCH /settings/hermes-profiles).

Testet die Erkennung der ``jupiter-*``-Profile, das Lesen des aktuellen Modells
sowie das atomare, profilweise Schreiben. Die echte ``~/.hermes/profiles`` wird
nie angerührt — alle Tests arbeiten in einem temporären Verzeichnis.
"""
from __future__ import annotations

import os
import textwrap

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

    def _profile(name: str, model_default: str | None = None, provider: str | None = None,
                 extra: str = "", broken: bool = False) -> None:
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

    _profile("jupiter-backend", "hy3", "opencode-go", "toolsets:\n  - hermes-cli\n")
    _profile("jupiter-requirements", "gpt-5.6-terra", "openai-codex")
    _profile("jupiter-qa")  # kein model-Block
    _profile("jupiter-broken", broken=True)
    _profile("default", "sonnet")  # ausgeschlossen (nicht-abc)
    _profile("jupiter-backoffice", "opus", "anthropic")  # gültiges Modell? opus ∈ VALID_MODELS

    # Ausgeschlossen per _EXCLUDE
    _profile("jupiter", "sonnet")

    monkeypatch.setattr(settings, "hermes_profiles_dir", str(d))
    return d


@pytest.fixture
def client(profiles_dir):
    return TestClient(create_app())


# --- GET ----------------------------------------------------------------


def test_get_lists_abc_profiles_with_models(client):
    res = client.get("/settings/hermes-profiles")
    assert res.status_code == 200
    data = res.json()
    # VALID_MODELS gespiegelt (sortiert)
    assert data["models"] == sorted(svc.available_models()) == sorted(
        ["haiku", "sonnet", "opus", "fable"]
    )
    names = {p["profile"] for p in data["profiles"]}
    # abc-Profile vorhanden; `default` und das ausgeschlossene `jupiter` fehlen
    assert "jupiter-backend" in names
    assert "jupiter-requirements" in names
    assert "jupiter-qa" in names
    assert "default" not in names
    assert "jupiter" not in names
    # aktuelles Modell + Provider gelesen
    backend = next(p for p in data["profiles"] if p["profile"] == "jupiter-backend")
    assert backend["current_model"] == "hy3"
    assert backend["provider"] == "opencode-go"
    # Profil ohne model-Block → current_model None, aber kein Fehler
    qa = next(p for p in data["profiles"] if p["profile"] == "jupiter-qa")
    assert qa["current_model"] is None
    assert qa["error"] is None
    # kaputtes Profil → einzeln als Fehler markiert, Gesamt nicht crash
    broken = next(p for p in data["profiles"] if p["profile"] == "jupiter-broken")
    assert broken["error"] is not None


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


# --- PATCH ---------------------------------------------------------------


def test_patch_writes_model_atomically_and_keeps_rest(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-qa", "model": "opus"}]},
    )
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["saved_model"] == "opus"
    # Datei: nur model.default gesetzt, restliche Keys erhalten
    cfg = yaml.safe_load((profiles_dir / "jupiter-qa" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "opus"
    # jupiter-qa hatte keinen provider → nicht angelegt
    assert "provider" not in cfg.get("model", {})


def test_patch_preserves_other_keys(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-backend", "model": "fable"}]},
    )
    assert res.status_code == 200
    cfg = yaml.safe_load((profiles_dir / "jupiter-backend" / "config.yaml").read_text(encoding="utf-8"))
    # provider + toolsets unverändert erhalten
    assert cfg["model"]["default"] == "fable"
    assert cfg["model"]["provider"] == "opencode-go"
    assert cfg["toolsets"] == ["hermes-cli"]


def test_patch_invalid_model_rejected(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-backend", "model": "gpt-5.6-terra"}]},
    )
    assert res.status_code == 200
    results = res.json()
    assert results[0]["ok"] is False
    assert results[0]["error"] is not None
    assert results[0]["saved_model"] is None
    # Datei unverändert
    cfg = yaml.safe_load((profiles_dir / "jupiter-backend" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "hy3"


def test_patch_non_abc_profile_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "default", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


def test_patch_partial_failure_reports_each(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={
            "models": [
                {"profile": "jupiter-qa", "model": "haiku"},       # ok
                {"profile": "jupiter-backend", "model": "bogus"},  # Fehler
            ]
        },
    )
    assert res.status_code == 200
    results = {r["profile"]: r for r in res.json()}
    assert results["jupiter-qa"]["ok"] is True
    assert results["jupiter-qa"]["saved_model"] == "haiku"
    assert results["jupiter-backend"]["ok"] is False
    # der gültige Eintrag ist tatsächlich gespeichert
    cfg = yaml.safe_load((profiles_dir / "jupiter-qa" / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["model"]["default"] == "haiku"


def test_patch_empty_body_returns_empty_list(client):
    res = client.patch("/settings/hermes-profiles", json={"models": []})
    assert res.status_code == 200
    assert res.json() == []


def test_patch_unknown_profile_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-nonexistent", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


def test_patch_unreadable_profile_rejected(client, profiles_dir):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-broken", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


# --- PROJ-83 BUG-1: Path-Traversal im `profile`-Parameter -----------------


def test_patch_traversal_slash_rejected_and_does_not_escape(client, tmp_path):
    # Ein Verzeichnis AUSSERHALB von profiles_dir mit einer geheimen config.
    escape = tmp_path / "escape_target"
    escape.mkdir()
    secret_file = escape / "config.yaml"
    secret_file.write_text("secret: TOPSECRET\n", encoding="utf-8")

    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-qa/../../escape_target", "model": "opus"}]},
    )
    assert res.status_code == 200
    r = res.json()[0]
    assert r["ok"] is False
    assert r["error"] == "Kein abc-Profil."
    # Die geheime Datei außerhalb wurde weder gelesen noch überschrieben.
    assert secret_file.read_text(encoding="utf-8") == "secret: TOPSECRET\n"


def test_patch_traversal_dotdot_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-qa/..", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


def test_patch_traversal_absolute_rejected(client):
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-/etc/passwd", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False


def test_patch_traversal_uppercase_rejected(client):
    # Format-Regex erlaubt nur Kleinbuchstaben → Großbuchstaben blockiert.
    res = client.patch(
        "/settings/hermes-profiles",
        json={"models": [{"profile": "jupiter-QA", "model": "opus"}]},
    )
    assert res.status_code == 200
    assert res.json()[0]["ok"] is False

