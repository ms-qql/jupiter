"""PROJ-10 QA — Edge-Cases + Regression der zwei behobenen Befunde.

Ergänzt ``test_proj10_trust_policy.py`` um die Spec-Edge-Cases, die dort nicht
abgedeckt waren: nicht-linearer Phasensprung + Entprellung. Die ursprünglich als
``xfail`` festgehaltenen Befunde (QA-Bug A: deny-Notiz unsichtbar; QA-Bug B: Phase
rückt bei abgelehntem Gate vor) sind gefixt → die Tests sichern das Verhalten ab.
"""
from __future__ import annotations

import asyncio

import pytest

from app.engine import policy
from app.engine.manager import AWAITING_APPROVAL, RUNNING, SessionManager
from app.engine.policy import PolicyStore

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _store(tmp_path, text: str | None = None) -> PolicyStore:
    p = tmp_path / "policy.yaml"
    if text is not None:
        p.write_text(text, encoding="utf-8")
    return PolicyStore(str(p))


def _point(tmp_path, monkeypatch, text: str | None = None) -> None:
    monkeypatch.setattr(policy, "policy_store", _store(tmp_path, text))


async def _gate(mgr, rt, tu, skill):
    """Feuert einen Skill-Aufruf, gibt (outcome_task, war_phase_gate) zurück."""
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, tu, "Skill", {"skill": skill, "args": "10"})
    )
    await asyncio.sleep(0)
    card = rt.pending.get(tu)
    gated = card is not None and card.card_type == "phase_transition"
    return task, gated


# --- Edge-Case: nicht-linearer Phasensprung + Entprellung ------------------

@pytest.mark.asyncio
async def test_nonlinear_jumps_gate_each_real_transition(tmp_path, monkeypatch):
    """frontend→backend→frontend: jeder echte Wechsel gated (Default-Gate)."""
    _point(tmp_path, monkeypatch)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "frontend"  # Ausgangsphase gesetzt

    t1, g1 = await _gate(mgr, rt, "a", "abc-backend")   # frontend→backend
    assert g1, "Wechsel frontend→backend muss gaten"
    mgr.resolve_decision(rt.state.session_id, "a", approve=True)
    await t1

    t2, g2 = await _gate(mgr, rt, "b", "abc-frontend")  # backend→frontend
    assert g2, "Rück-Wechsel backend→frontend muss erneut gaten"
    mgr.resolve_decision(rt.state.session_id, "b", approve=True)
    await t2


@pytest.mark.asyncio
async def test_same_phase_twice_is_debounced(tmp_path, monkeypatch):
    """Zweimal derselbe Phasen-Skill → zweiter Aufruf gated NICHT (old==new)."""
    _point(tmp_path, monkeypatch)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "architecture"

    t1, g1 = await _gate(mgr, rt, "a", "abc-frontend")  # architecture→frontend
    assert g1
    mgr.resolve_decision(rt.state.session_id, "a", approve=True)
    await t1

    # Erneut abc-frontend → keine Phasenänderung → kein hartes Gate.
    out = await mgr.request_decision(rt.state.session_id, "b", "Skill",
                                     {"skill": "abc-frontend", "args": "10"})
    assert out.behavior == "allow"
    assert all(c.card_type != "phase_transition" for c in rt.pending.values())


@pytest.mark.asyncio
async def test_specific_transitions_only_gate_listed_targets(tmp_path, monkeypatch):
    """transitions=[deploy] → nur Eintritt in deploy gated, andere Wechsel nicht."""
    _point(tmp_path, monkeypatch, "phase_gate:\n  enabled: true\n  transitions: [deploy]\n")
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "qa"

    # qa→backend ist NICHT in der Liste → kein Gate.
    out = await mgr.request_decision(rt.state.session_id, "a", "Skill",
                                     {"skill": "abc-backend", "args": "10"})
    assert out.behavior == "allow"
    assert all(c.card_type != "phase_transition" for c in rt.pending.values())

    # backend→deploy IST gelistet → Gate.
    _, gated = await _gate(mgr, rt, "b", "abc-deploy")
    assert gated
    mgr.resolve_decision(rt.state.session_id, "b", approve=True)


# --- Dokumentierte Befunde (xfail, strict) ---------------------------------

# --- Regression der behobenen Befunde --------------------------------------

@pytest.mark.asyncio
async def test_denied_phase_gate_keeps_old_phase(tmp_path, monkeypatch):
    """QA-Bug B (fix): abgelehnter Phasen-Übergang lässt die Phase NICHT vorrücken."""
    _point(tmp_path, monkeypatch)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "architecture"

    task, gated = await _gate(mgr, rt, "a", "abc-frontend")
    assert gated
    # Während die Card offen ist, darf die Phase noch nicht umgesprungen sein.
    assert rt.state.abc_phase == "architecture"
    mgr.resolve_decision(rt.state.session_id, "a", approve=False, comment="Noch nicht")
    await task
    assert rt.state.abc_phase == "architecture"  # bleibt in der alten Phase


@pytest.mark.asyncio
async def test_approved_phase_gate_advances_phase(tmp_path, monkeypatch):
    """Gegenprobe: bei Freigabe wird die neue Phase übernommen."""
    _point(tmp_path, monkeypatch)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "architecture"
    task, gated = await _gate(mgr, rt, "a", "abc-frontend")
    assert gated and rt.state.abc_phase == "architecture"  # noch nicht
    mgr.resolve_decision(rt.state.session_id, "a", approve=True)
    await task
    assert rt.state.abc_phase == "frontend"  # erst NACH Freigabe


@pytest.mark.asyncio
async def test_lingering_deny_notice_does_not_freeze_status(tmp_path, monkeypatch):
    _point(tmp_path, monkeypatch,
           "phase_gate:\n  enabled: false\n  transitions: []\n"
           "rules:\n  - tool: Bash\n    level: deny\n  - tool: Write\n    level: card\n")
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    # deny-Notiz (nicht-blockierend) bleibt in pending …
    await mgr.request_decision(rt.state.session_id, "t1", "Bash", {"command": "ls"})
    # … dann eine echte blockierende Card öffnen + freigeben.
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "t2", "Write", {"file_path": "a", "content": "c"})
    )
    await asyncio.sleep(0)
    mgr.resolve_decision(rt.state.session_id, "t2", approve=True)
    await task
    # Erwartung: keine BLOCKIERENDE Entscheidung mehr offen → Status zurück auf RUNNING.
    assert rt.state.status == RUNNING


@pytest.mark.asyncio
async def test_deny_surfaces_a_dismissable_notice(tmp_path, monkeypatch):
    """QA-Bug A (fix): deny erzeugt eine sichtbare, quittierbare Notiz-Card (ohne Blockade)."""
    _point(tmp_path, monkeypatch, "rules:\n  - tool: Bash\n    level: deny\n    reason: gesperrt\n")
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    out = await mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "ls"})
    assert out.behavior == "deny"
    # Sichtbar in pending_decisions, aber NICHT blockierend (Status nicht awaiting).
    card = rt.pending["tu1"]
    assert card.card_type == "deny" and card.state == "resolved"
    assert rt.state.status != AWAITING_APPROVAL
    # „Zur Kenntnis" quittiert sie (future-lose Notiz → einfach entfernen).
    mgr.resolve_decision(rt.state.session_id, "tu1", approve=False)
    assert "tu1" not in rt.pending
