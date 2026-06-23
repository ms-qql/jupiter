"""PROJ-10 — Trust-Policy: abgestufter Evaluator, Phasen-Gate, Settings-API.

Deckt die Stufen-/Spezifitäts-Logik, Defekt-Fallback, das bypass-feste Phasen-Gate
und den REST-Vertrag (GET/PUT/preview) ab — mit FakeDriver, ohne echte Claude-Session.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from app.engine import policy
from app.engine.manager import AWAITING_APPROVAL, SessionManager
from app.engine.policy import AUTO_ALLOW, CARD, DENY, PolicyStore
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Evaluator: Stufen, Spezifität, Default, Konflikt ----------------------

def _store(tmp_path, text: str | None = None) -> PolicyStore:
    p = tmp_path / "policy.yaml"
    if text is not None:
        p.write_text(text, encoding="utf-8")
    return PolicyStore(str(p))


def test_default_without_file_is_conservative(tmp_path):
    s = _store(tmp_path)  # keine Datei
    assert s.evaluate("Read").level == AUTO_ALLOW
    assert s.evaluate("Bash").level == CARD
    assert s.snapshot()["source"] == "default"


def test_unknown_tool_defaults_to_card(tmp_path):
    assert _store(tmp_path).evaluate("VölligNeuesTool").level == CARD


def test_rule_matches_tool_and_level(tmp_path):
    s = _store(tmp_path, "rules:\n  - tool: Bash\n    level: auto-allow\n")
    assert s.evaluate("Bash").level == AUTO_ALLOW
    assert s.evaluate("Write").level == CARD  # andere Tools: Default


def test_specific_rule_beats_general(tmp_path):
    s = _store(
        tmp_path,
        "rules:\n"
        "  - tool: Bash\n    level: card\n"
        "  - tool: Bash\n    role: architect\n    level: auto-allow\n",
    )
    assert s.evaluate("Bash", role="architect").level == AUTO_ALLOW  # spezifischer
    assert s.evaluate("Bash", role="qa").level == CARD               # nur allgemeine Regel


def test_deny_wins_conflict_same_specificity(tmp_path):
    s = _store(
        tmp_path,
        "rules:\n  - tool: Bash\n    level: auto-allow\n  - tool: Bash\n    level: deny\n",
    )
    assert s.evaluate("Bash").level == DENY  # restriktivste gewinnt


def test_project_match_is_substring(tmp_path):
    s = _store(tmp_path, "rules:\n  - tool: Bash\n    project: jupiter\n    level: deny\n")
    assert s.evaluate("Bash", project="/home/dev/projects/jupiter").level == DENY
    assert s.evaluate("Bash", project="/home/dev/projects/other").level == CARD


def test_corrupt_file_falls_back_to_default_with_warning(tmp_path):
    s = _store(tmp_path, "rules: [::: kaputt :::\n")  # ungültiges YAML
    assert s.evaluate("Bash").level == CARD
    snap = s.snapshot()
    assert snap["source"] == "default" and snap["warning"]


def test_invalid_level_is_rejected_on_save(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(ValueError):
        s.save([{"match": {"tool": "Bash"}, "level": "vielleicht"}], {"enabled": True, "transitions": []})


def test_save_then_live_reload(tmp_path):
    s = _store(tmp_path)
    assert s.evaluate("Bash").level == CARD
    s.save([{"match": {"tool": "Bash"}, "level": "auto-allow"}], {"enabled": False, "transitions": []})
    assert s.evaluate("Bash").level == AUTO_ALLOW          # neue Regel sofort wirksam
    assert s.phase_gate()["enabled"] is False


def test_rule_text_names_the_match(tmp_path):
    s = _store(tmp_path, "rules:\n  - tool: Bash\n    role: architect\n    level: deny\n")
    d = s.evaluate("Bash", role="architect")
    assert "Bash" in d.rule and "architect" in d.rule  # Nachvollziehbarkeit


# --- Manager: Phasen-Gate (bypass-fest) + Deny -----------------------------

def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _point_store_at(tmp_path, monkeypatch, text: str | None = None) -> None:
    """Globalen policy_store auf eine Test-Datei umbiegen."""
    monkeypatch.setattr(policy, "policy_store", _store(tmp_path, text))


@pytest.mark.asyncio
async def test_phase_gate_fires_even_in_bypass(tmp_path, monkeypatch):
    _point_store_at(tmp_path, monkeypatch)  # Default-Gate: jeder Wechsel
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hi", model="haiku",
        permission_mode="bypassPermissions",
    )
    # 1. Skill setzt Phase architecture (None→architecture = KEIN Übergang).
    out = await mgr.request_decision(
        rt.state.session_id, "tu1", "Skill", {"skill": "abc-architecture", "args": "10"}
    )
    assert out.behavior == "allow" and rt.pending == {}
    assert rt.state.abc_phase == "architecture"

    # 2. Wechsel architecture→frontend → hartes Gate feuert TROTZ Bypass.
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "tu2", "Skill", {"skill": "abc-frontend", "args": "10"})
    )
    await asyncio.sleep(0)
    assert rt.state.status == AWAITING_APPROVAL
    card = rt.pending["tu2"]
    assert card.card_type == "phase_transition"
    assert "architecture" in card.triggering_rule and "frontend" in card.triggering_rule

    mgr.resolve_decision(rt.state.session_id, "tu2", approve=True)
    out2 = await task
    assert out2.behavior == "allow"


@pytest.mark.asyncio
async def test_operative_card_passes_in_bypass(tmp_path, monkeypatch):
    _point_store_at(tmp_path, monkeypatch)
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hi", model="haiku",
        permission_mode="bypassPermissions",
    )
    out = await mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "ls"})
    assert out.behavior == "allow" and out.auto is True and rt.pending == {}


@pytest.mark.asyncio
async def test_card_carries_triggering_rule_and_real_phase(tmp_path, monkeypatch):
    _point_store_at(tmp_path, monkeypatch, "rules:\n  - tool: Bash\n    level: card\n")
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    rt.state.abc_phase = "backend"
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "rm x"})
    )
    await asyncio.sleep(0)
    card = rt.pending["tu1"]
    assert card.card_type == "normal" and card.triggering_rule and "Bash" in card.triggering_rule
    assert card.context["phase"] == "backend"  # PROJ-10-Fix: echte Phase
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=True)
    await task


@pytest.mark.asyncio
async def test_deny_blocks_without_pending_card(tmp_path, monkeypatch):
    _point_store_at(
        tmp_path, monkeypatch,
        "rules:\n  - tool: Bash\n    level: deny\n    reason: Shell gesperrt\n",
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    out = await mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "rm -rf /"})
    assert out.behavior == "deny" and "Shell gesperrt" in out.reason
    assert rt.pending == {}                       # deny blockiert die Session NICHT
    assert rt.state.status != AWAITING_APPROVAL


@pytest.mark.asyncio
async def test_disabled_phase_gate_does_not_fire(tmp_path, monkeypatch):
    _point_store_at(tmp_path, monkeypatch, "phase_gate:\n  enabled: false\n  transitions: []\n")
    mgr = _mgr()
    # Bypass: die operative Skill-Auswertung (Default → card) läuft durch, sodass der
    # Aufruf nicht blockiert — geprüft wird allein, dass das Phasen-Gate AUS bleibt.
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hi", model="haiku",
        permission_mode="bypassPermissions",
    )
    rt.state.abc_phase = "architecture"
    out = await mgr.request_decision(
        rt.state.session_id, "tu1", "Skill", {"skill": "abc-frontend", "args": "10"}
    )
    assert out.behavior == "allow"  # kein hartes Gate trotz Phasenwechsel
    assert all(c.card_type != "phase_transition" for c in rt.pending.values())


# --- REST-Vertrag ----------------------------------------------------------

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "policy_store", _store(tmp_path))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app):
        yield app


@pytest.mark.asyncio
async def test_policy_get_put_preview_roundtrip(client):
    transport = ASGITransport(app=client)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        # Default lesen.
        r = await ac.get("/settings/policy")
        assert r.status_code == 200 and r.json()["source"] == "default"

        # Regel setzen (PUT) → live.
        body = {
            "rules": [{"match": {"tool": "Bash"}, "level": "deny", "reason": "nö"}],
            "phase_gate": {"enabled": True, "transitions": ["frontend"]},
        }
        r = await ac.put("/settings/policy", json=body)
        assert r.status_code == 200
        assert r.json()["rules"][0]["level"] == "deny"

        # Preview spiegelt die neue Regel.
        r = await ac.get("/settings/policy/preview", params={"tool": "Bash"})
        assert r.status_code == 200 and r.json()["level"] == "deny"


@pytest.mark.asyncio
async def test_put_rejects_unknown_phase(client):
    transport = ASGITransport(app=client)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        body = {"rules": [], "phase_gate": {"enabled": True, "transitions": ["xxx"]}}
        r = await ac.put("/settings/policy", json=body)
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_put_rejects_invalid_level(client):
    transport = ASGITransport(app=client)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
        body = {"rules": [{"match": {"tool": "Bash"}, "level": "vielleicht"}], "phase_gate": {"enabled": True, "transitions": []}}
        r = await ac.put("/settings/policy", json=body)
        assert r.status_code == 422  # Pydantic-Literal-Validierung
