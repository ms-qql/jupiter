"""PROJ-10 QA — Edge-Cases + dokumentierte Bugs (Red-Team/Verhaltensprüfung).

Ergänzt ``test_proj10_trust_policy.py`` um die Spec-Edge-Cases, die dort nicht
abgedeckt waren: nicht-linearer Phasensprung + Entprellung, sowie zwei mit
``xfail`` festgehaltene Befunde (Bug A: deny-Notiz unsichtbar; Bug B: Phase rückt
bei abgelehntem Gate vor). Die xfail-Tests flippen automatisch auf PASS, sobald
die Bugs gefixt sind (``strict=True`` → würde dann als XPASS-Fehler auffallen).
"""
from __future__ import annotations

import asyncio

import pytest

from app.engine import policy
from app.engine.manager import AWAITING_APPROVAL, SessionManager
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

@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="QA-Bug B: abc_phase rückt bei abgelehntem Phasen-Gate vor "
                                       "(Edge-Case 'Nutzer lehnt ab → bleibt in alter Phase' verletzt).")
async def test_denied_phase_gate_keeps_old_phase(tmp_path, monkeypatch):
    _point(tmp_path, monkeypatch)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku",
                          permission_mode="bypassPermissions")
    rt.state.abc_phase = "architecture"

    task, gated = await _gate(mgr, rt, "a", "abc-frontend")
    assert gated
    mgr.resolve_decision(rt.state.session_id, "a", approve=False, comment="Noch nicht")
    await task
    # Erwartung der Spec: bei Ablehnung bleibt die alte Phase.
    assert rt.state.abc_phase == "architecture"


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="QA-Bug A: deny erzeugt nur ein transientes Event, keine "
                                       "im UI sichtbare Notiz (pending_decisions bleibt leer).")
async def test_deny_surfaces_a_visible_notice(tmp_path, monkeypatch):
    _point(tmp_path, monkeypatch, "rules:\n  - tool: Bash\n    level: deny\n    reason: gesperrt\n")
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    out = await mgr.request_decision(rt.state.session_id, "tu1", "Bash", {"command": "ls"})
    assert out.behavior == "deny"
    # Erwartung: die Ablehnung ist im Cockpit sichtbar (z. B. als kurzlebige Card).
    # Aktuell landet sie NICHT in pending_decisions → unsichtbar.
    assert any(c.card_type == "deny" for c in rt.pending.values())
