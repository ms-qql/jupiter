"""PROJ-40 — Micro-Apps (Sidebar-Sektion + Excalidraw-Migration + kind=native).

Deckt die backend-seitigen Akzeptanzkriterien ab:
- Registry akzeptiert ``kind: native`` (nativ in Jupiter programmierte Micro-App) —
  ohne url/target-Pflicht, verfügbar, KEINE steuerbare Session.
- ``group``/``icon`` werden kind-unabhängig geparst (Sidebar-Filter „micro").
- Eine native Engine ist (wie iframe/launch) NICHT als Session startbar.
- Migrations-Guard: das getrackte engines.example.yaml führt Excalidraw als
  Micro-App (group=micro, icon) — Vorlage für die (gitignored) Prod-engines.yaml.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.engine.registry import (
    CLAUDE_KEY,
    IFRAME,
    NATIVE,
    VALID_KINDS,
    EngineRegistry,
    _builtin_claude,
    _coerce_profile,
    engine_registry,
)
from app.main import create_app

from .fakes import FakeDriver

EXAMPLE_YAML = os.path.join(
    os.path.dirname(__file__), "..", "config", "engines.example.yaml"
)
PROJECT = "/home/dev/projects/jupiter"


def _registry(tmp_path, yaml_text: str) -> EngineRegistry:
    p = tmp_path / "engines.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return EngineRegistry(str(p))


# --- kind=native ----------------------------------------------------------

def test_native_is_valid_kind():
    assert NATIVE == "native"
    assert NATIVE in VALID_KINDS


def test_native_profile_parses_without_url_or_target():
    """Native App: Code liegt im Frontend → keine url/target-Pflicht (anders als iframe)."""
    prof = _coerce_profile(
        {
            "key": "rechner",
            "label": "Rechner",
            "kind": "native",
            "group": "micro",
            "icon": "pentool",
        }
    )
    assert prof.kind == NATIVE
    assert prof.group == "micro"
    assert prof.icon == "pentool"
    assert prof.url is None and prof.target is None


def test_native_is_available_and_not_a_session():
    prof = _coerce_profile(
        {"key": "rechner", "label": "Rechner", "kind": "native"}
    )
    assert prof.availability() == (True, None)
    assert prof.is_session_engine is False


def test_iframe_still_requires_url_but_native_does_not(tmp_path):
    """Regression: iframe ohne url bleibt ein Fehler; native ohne url ist gültig."""
    reg = _registry(
        tmp_path,
        "engines:\n"
        "  - key: kaputt\n    label: Kaputt\n    kind: iframe\n"  # iframe ohne url → ValueError → übersprungen
        "  - key: rechner\n    label: Rechner\n    kind: native\n    group: micro\n",
    )
    snap = reg.snapshot()
    keys = {e["key"] for e in snap["engines"]}
    assert "rechner" in keys  # native lädt
    assert "kaputt" not in keys  # iframe ohne url fällt raus
    assert snap["warning"]  # und erzeugt eine Warnung


def test_micro_group_on_iframe_is_preserved(tmp_path):
    reg = _registry(
        tmp_path,
        "engines:\n"
        "  - key: whiteboard\n    label: Whiteboard\n    kind: iframe\n"
        "    group: micro\n    icon: pentool\n    url: https://excalidraw.com\n",
    )
    wb = next(e for e in reg.snapshot()["engines"] if e["key"] == "whiteboard")
    assert wb["group"] == "micro"
    assert wb["icon"] == "pentool"
    assert wb["kind"] == IFRAME


# --- POST /sessions: native nicht als Session startbar --------------------

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


@pytest.fixture()
def use_engines(tmp_path, monkeypatch):
    """Biegt den Modul-Singleton ``engine_registry`` auf eine Test-YAML um
    (Muster wie in test_proj18_engines.py)."""

    def _apply(yaml_text: str):
        p = tmp_path / "engines.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        monkeypatch.setattr(engine_registry, "_path", str(p))
        monkeypatch.setattr(engine_registry, "_mtime", None)
        monkeypatch.setattr(engine_registry, "_loaded_once", False)
        monkeypatch.setattr(engine_registry, "_source", "default")
        monkeypatch.setattr(
            engine_registry, "_profiles", {CLAUDE_KEY: _builtin_claude()}
        )
        return p

    return _apply


def test_create_native_engine_rejected(client, use_engines):
    """Eine native Micro-App ist keine steuerbare Engine (wie iframe/launch) → 400."""
    use_engines(
        "engines:\n  - key: rechner\n    label: Rechner\n    kind: native\n    group: micro\n"
    )
    resp = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "Hallo", "model": "haiku", "engine": "rechner"},
    )
    assert resp.status_code == 400


# --- Migrations-Guard: getracktes Example-File ----------------------------

def test_example_yaml_excalidraw_is_microapp(tmp_path):
    """engines.example.yaml (getrackt) führt Excalidraw als Micro-App — die Vorlage
    für die gitignored Prod-engines.yaml. Schützt die Migration vor Regress."""
    reg = EngineRegistry(EXAMPLE_YAML)
    engines = reg.snapshot()["engines"]
    exc = next((e for e in engines if e["key"] == "excalidraw"), None)
    assert exc is not None, "excalidraw fehlt im Example-File"
    assert exc["kind"] == IFRAME
    assert exc["group"] == "micro"
    assert exc["icon"]  # ein Sidebar-Icon ist gesetzt
