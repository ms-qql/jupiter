"""PROJ-60 — Bugfix: OpenCode-Session hängt lautlos in „Arbeitet", wenn der Prozess

nach einem Tool-Zwischenschritt abbricht, ohne den Turn wirklich zu beenden.

Root Cause: ``GenericCliDriver._read_stdout`` unterdrückte das ``closed``-Event am
Prozessende, sobald IRGENDEIN ``result``-Event im Turn vorkam (``self._saw_result``).
OpenCodes Adapter liefert aber für **jeden** Tool-Zwischenschritt ein result-Event mit
``final: False`` (PROJ-58) — bricht der Prozess danach ab (Provider-Timeout/Crash bei
z. B. `openrouter/z-ai/glm-5.2`, Exit-Code 0, kein finaler ``step_finish``/``reason:
"stop"``), wurde das fälschlich als „Turn normal beendet, Session wartet" gewertet.
Ergebnis: kein `closed`-Event, kein Fehler, die Session bleibt für immer im letzten
Status (`running`/„Arbeitet") — obwohl der Prozess bereits tot ist. Aus Nutzersicht
nicht von einem echten Hänger zu unterscheiden ("Es steht nur oben 'arbeitet'").

Fix: nur ein ``result``-Event mit ``raw["final"]`` wahr (Default ``True`` → Claude/Codex,
die je Turn nur EIN result liefern, unverändert) markiert den Turn als „sauber beendet,
self-resumable". Jeder andere Prozess-Exit emittiert ``closed`` → Session terminiert
sichtbar statt lautlos zu hängen.
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

from app.engine.base import LaunchSpec
from app.engine.generic_cli_driver import GenericCliDriver
from app.engine.registry import EngineProfile

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
async def test_process_death_after_intermediate_result_emits_closed(tmp_path):
    """Vor dem Fix: kein `closed` nach Absturz hinter einem Tool-Zwischenschritt."""
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

    assert drv.is_alive is False
    assert any(e.type == "result" and e.raw.get("final") is False for e in events), events
    assert any(e.type == "system" and e.subtype == "closed" for e in events), (
        "Session muss nach einem Absturz hinter einem Tool-Zwischenschritt terminieren "
        "(closed-Event), statt lautlos im letzten Status hängenzubleiben."
    )


FAKE_CLEAN_TURN_END = r'''
import sys, json
sys.stdin.read()
sid = "ses_OK"
print(json.dumps({"type": "step_start", "sessionID": sid, "part": {"type": "step-start"}}))
print(json.dumps({"type": "tool_use", "sessionID": sid, "part": {"tool": "bash", "state": {"input": {"command": "x"}}}}))
print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {"reason": "tool-calls",
    "tokens": {"total": 50, "input": 40, "output": 5, "reasoning": 0, "cache": {"write": 0, "read": 5}},
    "cost": 0.001}}))
print(json.dumps({"type": "text", "sessionID": sid, "part": {"type": "text", "text": "fertig"}}))
print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {"reason": "stop",
    "tokens": {"total": 80, "input": 60, "output": 10, "reasoning": 0, "cache": {"write": 0, "read": 10}},
    "cost": 0.002}}))
'''


def _clean_profile(tmp_path) -> EngineProfile:
    script = tmp_path / "fake_clean.py"
    script.write_text(FAKE_CLEAN_TURN_END, encoding="utf-8")
    return EngineProfile(
        key="opencode",
        label="Fake OpenCode (sauberes Turn-Ende)",
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
async def test_clean_turn_end_still_suppresses_closed_for_self_resume(tmp_path):
    """Regression: ein ECHTES Turn-Ende (reason=stop) bleibt weiterhin ohne `closed` —
    die Session bleibt self-resumable, wie vor dem Fix (PROJ-56/58 unverändert)."""
    drv = GenericCliDriver(_clean_profile(tmp_path))
    events = []

    async def on_event(e):
        events.append(e)

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="mach was",
    )
    await drv.start(spec, on_event)
    await drv._reader_task

    assert any(e.type == "result" and e.raw.get("final") is True for e in events), events
    assert not any(e.type == "system" and e.subtype == "closed" for e in events), events
