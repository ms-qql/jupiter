"""PROJ-39 — Sidebar-Sektion „Orchestration": Registry-Felder ``group`` + ``icon``.

Der Frontend-Teil (Sidebar-Sektion, Vollbild-Route) ist clientseitig (vitest).
Backend-seitig prüft PROJ-39 nur die kleine Registry-Erweiterung: iFrame-Einträge
tragen ``group`` (Sidebar-Filter) und ein optionales ``icon`` (lucide-Name), die
``GET /engines`` über ``to_read()`` mit ausliefert.
"""
from __future__ import annotations

from app.engine.registry import EngineRegistry

PROJECT = "/home/dev/projects/jupiter"


def _registry(tmp_path, yaml_text: str) -> EngineRegistry:
    p = tmp_path / "engines.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    return EngineRegistry(str(p))


_ORCH_YAML = """
engines:
  - key: paperclip
    label: Paperclip
    kind: iframe
    group: orchestration
    icon: paperclip
    url: https://paperclip.auxevo.tech
    sandbox: "allow-scripts allow-same-origin"
  - key: wayland
    label: Wayland
    kind: iframe
    group: orchestration
    icon: waves
    url: https://wayland.auxevo.tech
"""


def test_iframe_carries_group_and_icon(tmp_path):
    """group + icon werden geparst und über to_read ausgeliefert (für den Sidebar-Filter)."""
    reg = _registry(tmp_path, _ORCH_YAML)
    paperclip = reg.require("paperclip").to_read()
    assert paperclip["kind"] == "iframe"
    assert paperclip["group"] == "orchestration"
    assert paperclip["icon"] == "paperclip"
    assert paperclip["url"] == "https://paperclip.auxevo.tech"

    wayland = reg.require("wayland").to_read()
    assert wayland["group"] == "orchestration" and wayland["icon"] == "waves"


def test_group_icon_default_none_when_absent(tmp_path):
    """Ein iFrame ohne group/icon (z. B. Alt-Eintrag) liefert beide als None — kein Crash."""
    reg = _registry(
        tmp_path,
        "engines:\n  - key: board\n    label: Board\n    kind: iframe\n    url: https://example.com\n",
    )
    board = reg.require("board").to_read()
    assert board["group"] is None and board["icon"] is None


def test_orchestration_entries_are_available(tmp_path):
    """iFrame-Einträge gelten immer als verfügbar (kein Treiber/Key nötig) → nicht ausgegraut."""
    reg = _registry(tmp_path, _ORCH_YAML)
    for key in ("paperclip", "wayland"):
        data = reg.require(key).to_read()
        assert data["available"] is True and data["unavailable_reason"] is None


def test_real_config_has_orchestration_group():
    """Die echte engines.yaml trägt Paperclip+Wayland als group=orchestration (https-URLs)."""
    reg = EngineRegistry(f"{PROJECT}/backend/config/engines.yaml")
    orch = [e for e in reg.all() if e.group == "orchestration"]
    keys = {e.key for e in orch}
    assert {"paperclip", "wayland"} <= keys
    for e in orch:
        assert e.kind == "iframe"
        assert e.url and e.url.startswith("https://"), f"{e.key}: URL muss https sein (Mixed-Content)"
