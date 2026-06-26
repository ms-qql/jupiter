"""PROJ-47 — Stream-Reader-Stall: verwaister Subprozess & eingefrorene Anzeige.

Wurzelursache (im Code bestätigt): der stdout-Reader (`ClaudeCodeDriver._read_stdout`)
lief ohne Ausnahmebehandlung. Eine einzelne stream-json-Zeile über dem asyncio-Default
von 64 KiB (großer Turn / großes Tool-Result) ließ `readline()` mit ValueError den
Reader LAUTLOS sterben → der Subprozess lief weiter, Jupiter ingestierte nichts mehr,
`result` wurde nie verarbeitet (Status klemmt auf „running/0", später falsch „hängt").

Der Fix: (1) großzügiges StreamReader-Limit, (2) try/except in der Leseschleife —
überlange Zeile loggen + überspringen statt Reader-Tod, (3) jede sonstige Ausnahme
→ Traceback + Fehler-Event (kein stiller Tod), (4) Done-Callback meldet einen
unerwartet beendeten Reader (Reader-Stall-Diagnose) statt ihn verwaisen zu lassen.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from app.engine.claude_driver import ClaudeCodeDriver
from app.engine.events import StreamEvent
from app.engine.manager import RUNNING, WAITING, SessionRuntime, SessionState
from tests.fakes import FakeDriver


class _FakeProc:
    """Minimaler Subprozess-Stub für `_read_stdout` (kein echtes `claude`)."""

    def __init__(self, stdout, *, pid: int, returncode: int | None = 0) -> None:
        self.stdout = stdout
        self.pid = pid
        self.returncode = returncode

    async def wait(self) -> int:
        return self.returncode or 0


class _BoomStream:
    """stdout-Stub, dessen `readline()` eine unerwartete Ausnahme wirft."""

    async def readline(self) -> bytes:
        raise RuntimeError("unerwarteter Lesefehler")


def _driver_with(stdout, *, pid: int, returncode: int | None = 0):
    driver = ClaudeCodeDriver()
    driver._proc = _FakeProc(stdout, pid=pid, returncode=returncode)
    events: list[StreamEvent] = []

    async def on_event(e: StreamEvent) -> None:
        events.append(e)

    driver._on_event = on_event
    return driver, events


def _line(obj: dict) -> str:
    return json.dumps(obj)


# --- AC: Input/große Zeile mitten im Turn killt den Reader nicht ----------

async def test_reader_skips_overlong_line_and_keeps_result():
    """Eine Zeile über dem Limit wird übersprungen — das nachfolgende `result`
    (und der Stream-Abschluss) erreichen den Manager weiterhin."""
    reader = asyncio.StreamReader(limit=1024)
    driver, events = _driver_with(reader, pid=os.getpid(), returncode=0)

    overlong = _line({"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 4000}]}})
    result = _line({
        "type": "result", "subtype": "success", "is_error": False,
        "num_turns": 2, "total_cost_usd": 0.05,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    })
    reader.feed_data((overlong + "\n" + result + "\n").encode("utf-8"))
    reader.feed_eof()

    await driver._read_stdout()

    types = [(e.type, e.subtype) for e in events]
    # Überlange Assistenten-Zeile übersprungen → KEIN assistant-Event …
    assert all(t != "assistant" for t, _ in types)
    # … aber das `result` kam durch (Reader lebte weiter) …
    assert any(t == "result" for t, _ in types)
    # … und der saubere Stream-Abschluss ebenso.
    assert ("system", "closed") in types


# --- AC: `result`-Verarbeitung → korrekter Endzustand --------------------

async def test_result_event_sets_wartet_with_turns_and_cost():
    """Nach `result` (lebender Treiber): running → wartet, Turns/Kosten > 0 —
    kein Steckenbleiben auf „Arbeitet/0"."""
    state = SessionState(
        session_id="s", owner="dev", project_path="/tmp", model="opus", permission_mode="default"
    )
    runtime = SessionRuntime(state, FakeDriver())  # FakeDriver.is_alive == True
    state.status = RUNNING
    await runtime.handle_event(StreamEvent("result", "success", {
        "is_error": False, "num_turns": 3, "total_cost_usd": 0.07,
        "usage": {"input_tokens": 100, "output_tokens": 20},
        "modelUsage": {"opus": {"contextWindow": 200000}},
    }))

    assert state.status == WAITING
    assert state.num_turns == 3
    assert state.total_cost_usd > 0


# --- AC: Kein stiller Tod -------------------------------------------------

async def test_reader_crash_emits_error_event_not_silent():
    """Eine unerwartete Reader-Ausnahme wird NICHT verschluckt: ein Fehler-Event
    geht nach oben (Session wird ERROR), `_read_stdout` kehrt ohne Re-Raise zurück."""
    driver, events = _driver_with(_BoomStream(), pid=os.getpid(), returncode=None)

    await driver._read_stdout()  # darf nicht werfen

    errs = [e for e in events if e.type == "system" and e.subtype == "error"]
    assert errs, "erwartet ein system/error-Event statt lautlosem Reader-Tod"
    assert "Lesefehler" in (errs[0].raw.get("message") or "")


# --- AC: Reader-Stall-Erkennung ------------------------------------------

async def test_done_callback_flags_stall_while_process_alive(caplog):
    """Reader endet regulär, obwohl der Subprozess noch lebt und kein Stop läuft
    → diagnostisch klarer Reader-Stall-Logeintrag (kein stilles Verwaisen)."""
    driver, _ = _driver_with(_BoomStream(), pid=os.getpid(), returncode=None)  # is_alive True
    driver._stopping = False

    async def _noop() -> None:
        return None

    task = asyncio.ensure_future(_noop())
    await task
    with caplog.at_level(logging.ERROR):
        driver._on_reader_done(task)

    assert any("Reader-Stall" in r.getMessage() for r in caplog.records)


async def test_done_callback_logs_reader_exception(caplog):
    """Ein mit Ausnahme beendeter Reader-Task wird mit Logeintrag sichtbar."""
    driver, _ = _driver_with(_BoomStream(), pid=os.getpid(), returncode=None)

    async def _boom() -> None:
        raise RuntimeError("x")

    task = asyncio.ensure_future(_boom())
    try:
        await task
    except RuntimeError:
        pass
    with caplog.at_level(logging.ERROR):
        driver._on_reader_done(task)

    assert any("Ausnahme" in r.getMessage() for r in caplog.records)


async def test_done_callback_silent_on_stop():
    """Beim gewollten Stop (kein Stall) loggt der Done-Callback nichts/keinen Fehler."""
    driver, _ = _driver_with(_BoomStream(), pid=os.getpid(), returncode=0)
    driver._stopping = True

    async def _noop() -> None:
        return None

    task = asyncio.ensure_future(_noop())
    await task
    # is_alive False (returncode gesetzt) + stopping True → kein Reader-Stall.
    driver._on_reader_done(task)  # darf nicht werfen
