"""PROJ-46 — Live-Aktivitäts-Ticker (transient, v. a. Bypass-Mode).

Deckt die serverseitige Sanitisierung des Ziel-Hinweises, den `kind:"activity"`-Broadcast
beim Tool-Start (auch im Bypass, vor jeder Card), die Flüchtigkeit (kein transcript-/Vault-
Eintrag) sowie das Leeren bei terminaler Session ab — alles mit FakeDriver, ohne Subprozess.
"""
from __future__ import annotations

import pytest

from app.engine.events import StreamEvent
from app.engine.manager import (
    DONE,
    SessionManager,
    sanitize_target,
)

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _drain(rt) -> list[dict]:
    q = rt.subscribe()
    out: list[dict] = []
    while not q.empty():
        out.append(q.get_nowait())
    rt.unsubscribe(q)
    return out


# --- sanitize_target -------------------------------------------------------

def test_sanitize_picks_file_path():
    assert sanitize_target("Edit", {"file_path": "/x/main.py"}) == "/x/main.py"


def test_sanitize_picks_command_and_collapses_whitespace():
    assert sanitize_target("Bash", {"command": "npm run build\n  echo ok"}) == "npm run build echo ok"


def test_sanitize_empty_when_no_known_field():
    assert sanitize_target("Read", {}) == ""
    assert sanitize_target("Read", None) == ""


def test_sanitize_clips_to_80_chars():
    out = sanitize_target("Bash", {"command": "x" * 200})
    assert len(out) == 80 and out.endswith("…")


def test_sanitize_field_priority_file_before_command():
    # file_path hat Vorrang vor command (erstes sinnvolles Argument).
    assert sanitize_target("X", {"command": "c", "file_path": "f.py"}) == "f.py"


# --- Tool-Start broadcastet activity (auch im Bypass, vor jeder Card) -------

@pytest.mark.asyncio
async def test_tool_start_broadcasts_activity_in_bypass():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    q = rt.subscribe()
    out = await rt.request_decision("tu1", "Bash", {"command": "ls -la"})
    # Bypass: operativ ohne Card durch — unverändert (rein additiv).
    assert out.behavior == "allow" and out.auto is True
    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    rt.unsubscribe(q)
    act = [m for m in msgs if m.get("kind") == "activity"]
    assert len(act) == 1
    assert act[0]["tool"] == "Bash" and act[0]["target"] == "ls -la" and act[0]["ts"]
    # Letzter Stand am Runtime gehalten.
    assert rt.last_activity["tool"] == "Bash"


@pytest.mark.asyncio
async def test_activity_not_persisted_to_transcript():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    before = len(rt.transcript)
    await rt.request_decision("tu1", "Edit", {"file_path": "a.py"})
    # Flüchtig: der Ticker fügt KEINEN transcript-Eintrag hinzu (kein Persistieren).
    assert len(rt.transcript) == before


@pytest.mark.asyncio
async def test_activity_ring_keeps_last_five():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    for i in range(7):
        await rt.request_decision(f"tu{i}", "Read", {"file_path": f"f{i}.py"})
    assert len(rt._activity_ring) == 5
    # Jüngste zuletzt: f6 ist der letzte Stand.
    assert rt.last_activity["target"] == "f6.py"
    assert rt._activity_ring[0]["target"] == "f2.py"


@pytest.mark.asyncio
async def test_activity_cleared_and_broadcast_empty_on_terminal():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    await rt.request_decision("tu1", "Bash", {"command": "ls"})
    assert rt.last_activity is not None
    q = rt.subscribe()
    # Session terminal (closed) → Ticker leeren + leeren Stand broadcasten.
    await rt.handle_event(StreamEvent("system", "closed", {}))
    assert rt.state.status == DONE
    msgs = []
    while not q.empty():
        msgs.append(q.get_nowait())
    rt.unsubscribe(q)
    cleared = [m for m in msgs if m.get("kind") == "activity"]
    assert cleared and cleared[-1]["tool"] is None
    assert rt.last_activity is None and rt._activity_ring == []
