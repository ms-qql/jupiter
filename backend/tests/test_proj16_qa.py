"""PROJ-16 — QA: Acceptance Criteria + Edge-Cases am echten Tool-Gate (request_decision).

Ergänzt die Monitor-/Store-/REST-Unit-Tests (test_proj16_watchdog.py) um die
End-to-End-Pausen über die Manager-Maschinerie: Token-/Schreibraten-Riss, der
Korrektur-Pfad („Mit Kommentar korrigieren"), Counter-Reset nach Fortsetzen und der
Edge-Case „Session stirbt während der Watchdog-Pause" (Card wird obsolet).
"""
from __future__ import annotations

import asyncio

import pytest

from app.engine import watchdog
from app.engine.decisions import OBSOLETE
from app.engine.manager import AWAITING_APPROVAL, RUNNING, SessionManager
from app.engine.watchdog import DEFAULTS

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class StubStore:
    """Limits-Provider mit überschreibbaren Werten (nur ``limits()`` nötig)."""

    def __init__(self, **over) -> None:
        self._l = {**DEFAULTS, **over}

    def limits(self) -> dict:
        return dict(self._l)


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


async def _session(monkeypatch, *, permission_mode="default", **limits):
    monkeypatch.setattr(watchdog, "watchdog_store", StubStore(**limits))
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hi", model="haiku",
        permission_mode=permission_mode,
    )
    return mgr, rt


# AC1 — Token-Limit pausiert über das Gate (FakeDriver speist 110 Tokens beim Create).
@pytest.mark.asyncio
async def test_token_limit_pauses_via_gate(monkeypatch):
    mgr, rt = await _session(monkeypatch, token_limit=50)
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "t1", "Read", {"file_path": "x"})
    )
    await asyncio.sleep(0)
    assert rt.state.status == AWAITING_APPROVAL
    card = rt.pending["t1"]
    assert card.card_type == "watchdog_pause" and "Token-Limit" in card.triggering_rule
    mgr.resolve_decision(rt.state.session_id, "t1", approve=True)
    assert (await task).behavior == "allow"


# AC1 — Schreibrate pausiert über das Gate (Bypass, damit Writes nicht an PROJ-10-Cards hängen).
@pytest.mark.asyncio
async def test_write_rate_pauses_via_gate(monkeypatch):
    mgr, rt = await _session(monkeypatch, permission_mode="bypassPermissions", write_limit=2)
    sid = rt.state.session_id
    # 2 Writes auf VERSCHIEDENE Pfade laufen durch (keine Schleife, Rate noch unter Limit).
    assert (await mgr.request_decision(sid, "w1", "Write", {"file_path": "a"})).behavior == "allow"
    assert (await mgr.request_decision(sid, "w2", "Write", {"file_path": "b"})).behavior == "allow"
    task = asyncio.create_task(mgr.request_decision(sid, "w3", "Write", {"file_path": "c"}))
    await asyncio.sleep(0)
    assert rt.pending["w3"].card_type == "watchdog_pause"
    assert "Schreibrate" in rt.pending["w3"].triggering_rule
    mgr.resolve_decision(sid, "w3", approve=True)
    assert (await task).behavior == "allow"


# AC3 + AC6 — „Mit Kommentar korrigieren" = deny+Kommentar; Counter wird zurückgesetzt.
@pytest.mark.asyncio
async def test_correction_path_denies_and_resets_counter(monkeypatch):
    mgr, rt = await _session(monkeypatch, max_repeated_calls=2)
    sid = rt.state.session_id
    assert (await mgr.request_decision(sid, "r1", "Read", {"file_path": "x"})).behavior == "allow"
    task = asyncio.create_task(mgr.request_decision(sid, "r2", "Read", {"file_path": "x"}))
    await asyncio.sleep(0)
    assert rt.pending["r2"].card_type == "watchdog_pause"
    # Korrigieren: deny + Kommentar reist inline zu Claude zurück.
    mgr.resolve_decision(sid, "r2", approve=False, comment="Stopp, anders vorgehen")
    out = await task
    assert out.behavior == "deny" and "anders vorgehen" in out.reason
    assert rt.state.status == RUNNING
    # Counter des ausgelösten Limits ist zurückgesetzt → der nächste identische Call
    # läuft wieder durch (kein sofortiges Re-Trigger).
    assert (await mgr.request_decision(sid, "r3", "Read", {"file_path": "x"})).behavior == "allow"


# AC2 / Edge — Session stirbt während der Watchdog-Pause → Card wird obsolet, kein Hang.
@pytest.mark.asyncio
async def test_pause_card_obsolete_when_session_dies(monkeypatch):
    mgr, rt = await _session(monkeypatch, max_repeated_calls=2)
    sid = rt.state.session_id
    await mgr.request_decision(sid, "r1", "Read", {"file_path": "x"})
    task = asyncio.create_task(mgr.request_decision(sid, "r2", "Read", {"file_path": "x"}))
    await asyncio.sleep(0)
    assert rt.pending["r2"].card_type == "watchdog_pause"
    # Session wird gestoppt (Prozess endet) → offene Card wird hinfällig, Future löst auf.
    await mgr.stop(sid)
    out = await task
    assert out.behavior == "deny"
    assert rt.pending == {} or all(c.state == OBSOLETE for c in rt.pending.values())
