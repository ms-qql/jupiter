"""PROJ-58 — Bugfix: OpenCode-Stdin-Race (falsches „Wartet auf dich" + Transport-Fehler).

Root Cause (siehe Spec):
1. Der ``opencode``-Adapter markierte JEDEN ``step_finish`` (auch Tool-Zwischenschritte,
   ``reason: tool-calls``) als Turn-Ende → der Manager schaltete den Status vorzeitig auf
   „wartet", obwohl OpenCode noch mitten im Turn war.
2. ``GenericCliDriver.send_input`` prüfte nur ``is_alive`` (OS-Prozess lebt), nicht ob
   stdin bereits geschlossen ist (bei ``oneshot``-CLIs passiert das am TURN-START) → eine
   Folge-Eingabe während des laufenden Turns schrieb auf die geschlossene Pipe und ließ
   uvloop einen internen Transport-Fehler werfen, der als roher 409 ans Frontend ging.

Diese Suite deckt beide Fixes ab: der Adapter markiert nur ``reason=="stop"`` als
``final``, der Manager schaltet nur bei ``final`` auf „wartet", und der Treiber lehnt
eine Folge-Eingabe mitten im Turn sauber ab statt zu crashen (ohne einen zweiten,
parallelen Prozess zu spawnen).
"""
from __future__ import annotations

import sys

import pytest

from app.engine.adapters import opencode_parse_line
from app.engine.base import LaunchSpec
from app.engine.generic_cli_driver import GenericCliDriver
from app.engine.registry import EngineProfile


def _collector():
    events: list = []

    async def on_event(e):
        events.append(e)

    return events, on_event


# ===========================================================================
# Adapter: `final` nur bei echtem Turn-Ende (reason == "stop")
# ===========================================================================

def test_intermediate_step_finish_is_not_final():
    line = (
        '{"type":"step_finish","part":{"reason":"tool-calls",'
        '"tokens":{"total":100,"input":80,"output":5,"reasoning":0,"cache":{"write":0,"read":15}},'
        '"cost":0.001}}'
    )
    ev = opencode_parse_line(line)
    assert ev is not None and ev.type == "result"
    assert ev.raw.get("final") is False


def test_terminal_step_finish_is_final():
    ev = opencode_parse_line('{"type":"step_finish","part":{"reason":"stop"}}')
    assert ev is not None and ev.type == "result"
    assert ev.raw.get("final") is True


# ===========================================================================
# Manager: Status bleibt während Tool-Zwischenschritten aktiv, erst der finale
# step_finish schaltet auf WAITING.
# ===========================================================================

FAKE_OPENCODE_MULTISTEP = r'''
import sys, json
sys.stdin.read()
sid = "ses_MULTI"
print(json.dumps({"type": "step_start", "sessionID": sid, "part": {"type": "step-start"}}))
print(json.dumps({"type": "text", "sessionID": sid, "part": {"type": "text", "text": "arbeite..."}}))
print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {"reason": "tool-calls",
    "tokens": {"total": 50, "input": 40, "output": 5, "reasoning": 0, "cache": {"write": 0, "read": 5}},
    "cost": 0.001}}))
print(json.dumps({"type": "text", "sessionID": sid, "part": {"type": "text", "text": "fertig"}}))
print(json.dumps({"type": "step_finish", "sessionID": sid, "part": {"reason": "stop",
    "tokens": {"total": 80, "input": 60, "output": 10, "reasoning": 0, "cache": {"write": 0, "read": 10}},
    "cost": 0.002}}))
'''


def _multistep_profile(tmp_path) -> EngineProfile:
    script = tmp_path / "fake_multistep.py"
    script.write_text(FAKE_OPENCODE_MULTISTEP, encoding="utf-8")
    return EngineProfile(
        key="opencode",
        label="Fake OpenCode (Multi-Step)",
        driver="generic_cli",
        bin=sys.executable,
        argv_template=[str(script), "run", "--format", "json", "-m", "{model}", "--auto"],
        adapter="opencode",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )


@pytest.mark.asyncio
async def test_status_stays_active_through_tool_step_only_waits_at_true_end(tmp_path):
    from app.engine.manager import RUNNING, WAITING, SessionRuntime, SessionState

    prof = _multistep_profile(tmp_path)
    drv = GenericCliDriver(prof)
    state = SessionState(
        session_id="s1", owner="dev", project_path=str(tmp_path),
        model="m", permission_mode="default",
    )
    state.engine = "opencode"
    runtime = SessionRuntime(state, drv, on_done=lambda r: None)

    statuses_at_result: list[tuple[bool, str]] = []

    async def spy(event):
        await runtime.handle_event(event)
        if event.type == "result":
            statuses_at_result.append((bool(event.raw.get("final")), state.status))

    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="mach was",
    )
    await drv.start(spec, spy)
    await drv._reader_task

    assert statuses_at_result == [(False, RUNNING), (True, WAITING)], statuses_at_result


# ===========================================================================
# Treiber: Folge-Eingabe mitten im Turn (stdin bereits zu, Prozess noch aktiv)
# schlägt sauber fehl statt zu crashen — und spawnt KEINEN zweiten Prozess.
# ===========================================================================

FAKE_OPENCODE_WAITS_FOR_SENTINEL = r'''
import sys, time, os, json
sys.stdin.read()
sentinel = sys.argv[-1]
while not os.path.exists(sentinel):
    time.sleep(0.02)
print(json.dumps({"type": "step_finish", "sessionID": "ses_slow", "part": {"reason": "stop",
    "tokens": {"total": 0, "input": 0, "output": 0, "reasoning": 0, "cache": {"write": 0, "read": 0}},
    "cost": 0.0}}))
'''


@pytest.mark.asyncio
async def test_send_input_mid_turn_raises_clean_error_without_second_process(tmp_path):
    sentinel = tmp_path / "go"
    script = tmp_path / "slow_fake.py"
    script.write_text(FAKE_OPENCODE_WAITS_FOR_SENTINEL, encoding="utf-8")
    prof = EngineProfile(
        key="opencode",
        label="Fake OpenCode (langsam)",
        driver="generic_cli",
        bin=sys.executable,
        argv_template=[str(script), str(sentinel)],
        resume_argv_template=[str(script), str(sentinel)],
        adapter="opencode",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )
    drv = GenericCliDriver(prof)
    events, on = _collector()
    spec = LaunchSpec(
        session_id="s1", project_path=str(tmp_path), model="m",
        permission_mode="default", initial_prompt="erste",
    )
    await drv.start(spec, on)

    # Prozess läuft noch (wartet auf das Sentinel-File), stdin ist aber schon zu.
    assert drv.is_alive is True
    first_pid = drv.pid

    with pytest.raises(RuntimeError, match="läuft noch"):
        await drv.send_input("zu früh")

    # Kein paralleler zweiter Prozess wurde gestartet.
    assert drv.pid == first_pid

    sentinel.write_text("go", encoding="utf-8")
    await drv._reader_task
    assert drv.is_alive is False
