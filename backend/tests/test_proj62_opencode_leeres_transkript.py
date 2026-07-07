"""PROJ-62 — Bugfix: OpenCode-Session endet lautlos ohne Transkript und ohne Fehler,
wenn der Turn nur aus Tool-Calls besteht.

Root Cause (zwei Teile, siehe Spec):
1. `SessionManager.handle_event` hängte `tool_use`-Events NIE an `self.transcript` an
   (nur an den flüchtigen Activity-Ticker aus PROJ-46/61) — ein Turn ohne Assistant-Text
   blieb im Transkript komplett leer, obwohl Kosten/Turns/Kontext dafür verbucht wurden.
2. `GenericCliDriver._read_stdout` emittierte beim PROJ-60-Fallback (Prozessende ohne
   echtes Turn-Ende) ein `closed`-Event OHNE jede Fehlermeldung — `state.error` blieb
   `None`, die Session landete unerklärt bei „beendet/nicht steuerbar".

Fix: `tool_use`-Events hinterlassen zusätzlich einen persistenten `TranscriptEntry`
(role="tool"); der stille `closed`-Fallback trägt jetzt `reason="no_final_result"`, aus
dem der Manager — nur falls noch kein Fehler gesetzt ist — einen verständlichen deutschen
Hinweis in `state.error` schreibt.
"""
from __future__ import annotations

import sys

import pytest

from app.engine.base import LaunchSpec
from app.engine.events import StreamEvent
from app.engine.generic_cli_driver import GenericCliDriver
from app.engine.manager import DONE, ERROR, SessionManager
from app.engine.registry import EngineProfile

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


# --- Manager: tool_use-Events landen im Transkript --------------------------

@pytest.mark.asyncio
async def test_tool_use_event_appends_transcript_entry():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    before = len(rt.transcript)
    await rt.handle_event(
        StreamEvent("tool_use", None, {"name": "bash", "input": {"command": "git log --all --oneline"}})
    )
    assert len(rt.transcript) == before + 1
    entry = rt.transcript[-1]
    assert entry.role == "tool"
    assert entry.kind == "tool_use"
    assert "bash" in entry.text and "git log" in entry.text


@pytest.mark.asyncio
async def test_tool_only_turn_leaves_visible_transcript_after_silent_close():
    """Der genaue gemeldete Fall: nur ein Tool-Call, kein Assistant-Text, dann der
    stille PROJ-60-Fallback — das Transkript darf danach NICHT leer sein."""
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    rt.transcript.clear()  # nur den Tool-Only-Turn selbst betrachten
    await rt.handle_event(
        StreamEvent("tool_use", None, {"name": "bash", "input": {"command": "git log --all --oneline | head -30"}})
    )
    await rt.handle_event(StreamEvent("system", "closed", {"reason": "no_final_result"}))
    assert len(rt.transcript) >= 1, "Transkript darf nach einem Tool-Only-Turn nicht leer sein."
    assert any(e.role == "tool" for e in rt.transcript)


@pytest.mark.asyncio
async def test_tool_use_still_updates_activity_ticker():
    """Regression: der bestehende PROJ-46-Ticker bleibt unverändert bestehen —
    dieser Fix fügt den Transkript-Eintrag NUR zusätzlich hinzu."""
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    await rt.handle_event(StreamEvent("tool_use", None, {"name": "bash", "input": {"command": "ls"}}))
    assert rt.last_activity is not None and rt.last_activity["tool"] == "bash"


# --- Manager: stiller closed-Fallback setzt state.error ---------------------

@pytest.mark.asyncio
async def test_silent_closed_fallback_sets_error_reason():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    assert rt.state.error is None
    await rt.handle_event(StreamEvent("system", "closed", {"reason": "no_final_result"}))
    assert rt.state.status == DONE
    assert rt.state.error == "Der Prozess wurde beendet, ohne den Turn regulär abzuschließen."


@pytest.mark.asyncio
async def test_closed_without_reason_leaves_error_none():
    """Ein gewollter Stopp (oder Claude/Codex-Normalfall) trägt keinen Grund —
    darf weiterhin KEINEN Fehler setzen."""
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    await rt.handle_event(StreamEvent("system", "closed", {}))
    assert rt.state.status == DONE
    assert rt.state.error is None


@pytest.mark.asyncio
async def test_silent_closed_fallback_does_not_overwrite_existing_error():
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hallo", model="haiku",
        permission_mode="bypassPermissions",
    )
    await rt.handle_event(StreamEvent("system", "error", {"message": "Echter API-Fehler"}))
    assert rt.state.status == ERROR
    assert rt.state.error == "Echter API-Fehler"
    await rt.handle_event(StreamEvent("system", "closed", {"reason": "no_final_result"}))
    # Status bleibt ERROR (Fallback überschreibt nur DONE, nie ERROR) und der
    # aussagekräftigere Fehler bleibt erhalten statt vom generischen Hinweis ersetzt zu werden.
    assert rt.state.status == ERROR
    assert rt.state.error == "Echter API-Fehler"


# --- Driver: der PROJ-60-Fallback trägt jetzt einen Grund -------------------

FAKE_CRASH_MID_TURN = r'''
import sys, json
sys.stdin.read()
sid = "ses_CRASH"
print(json.dumps({"type": "step_start", "sessionID": sid, "part": {"type": "step-start"}}))
print(json.dumps({"type": "tool_use", "sessionID": sid, "part": {"tool": "bash", "state": {"input": {"command": "x"}}}}))
print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {"reason": "tool-calls",
    "tokens": {"total": 50, "input": 40, "output": 5, "reasoning": 0, "cache": {"write": 0, "read": 5}},
    "cost": 0.001}}))
sys.stdout.flush()
# Abbruch HIER (Provider-Timeout/Crash) -- exit 0, KEIN finaler step_finish(reason=stop).
'''


def _crash_profile(tmp_path) -> EngineProfile:
    script = tmp_path / "fake_crash.py"
    script.write_text(FAKE_CRASH_MID_TURN, encoding="utf-8")
    return EngineProfile(
        key="opencode",
        label="Fake OpenCode (Absturz nach Tool-Zwischenschritt)",
        driver="generic_cli",
        bin=sys.executable,
        argv_template=[str(script)],
        resume_argv_template=[str(script)],
        adapter="opencode",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )


@pytest.mark.asyncio
async def test_driver_silent_close_carries_no_final_result_reason(tmp_path):
    drv = GenericCliDriver(_crash_profile(tmp_path))
    events = []

    async def on_event(e):
        events.append(e)

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="mach was",
    )
    await drv.start(spec, on_event)
    await drv._reader_task

    closed = [e for e in events if e.type == "system" and e.subtype == "closed"]
    assert closed, "closed-Event muss weiterhin emittiert werden (PROJ-60 unverändert)."
    assert closed[0].raw.get("reason") == "no_final_result"
