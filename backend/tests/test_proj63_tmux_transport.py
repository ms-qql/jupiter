"""PROJ-63 — TmuxTransport (Spike-Umsetzung: Transport-Abstraktion unterhalb der
EngineDriver, siehe ``app/engine/transport.py``).

Deckt die im Spike verifizierten Kernpunkte ab:
- Naming: Jupiter-Session-ID -> sicherer tmux-Session-Name (keine Injection).
- tmux fehlt -> klarer ``TransportError`` statt Crash.
- Long-lived: `write_line()` überlebt unabhängige, nacheinander folgende
  Öffnen/Schließen-Zyklen (simuliert getrennte Backend-Prozess-Lebenszyklen) OHNE
  dass der CLI-Prozess fälschlich EOF sieht (der eigentliche Spike-Befund).
- Oneshot: `spawn()` erneut aufgerufen (neuer Turn) respawnt sauber, kumulatives
  Log über beide Turns, kein Kollisions-Fehler.
- Stop: `kill()` beendet den Pane-Prozess, keine Waisen, `session_exists()` False danach.
- Backfill: `capture_backfill()` liefert einen bounded Byte-Tail.

Diese Tests spawnen ECHTE tmux-Sessions (tmux 3.4 ist auf diesem Host vorhanden) mit
winzigen Fake-Python-Skripten als CLI-Stand-in (kein echter claude/codex/opencode-
Aufruf, kein API-Kosten) — Muster analog zu ``test_proj48_codex.py`` (Fake-CLI via
``sys.executable``). Jede Session wird im ``finally`` hart beendet.
"""
from __future__ import annotations

import asyncio
import shutil
import sys

import pytest

from app.engine.transport import (
    EXIT_MARKER,
    TmuxTransport,
    TransportError,
    sanitize_tmux_session_name,
    tmux_available,
)

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux ist auf diesem Host nicht installiert"
)


# ===========================================================================
# Naming / Verfügbarkeit
# ===========================================================================

def test_sanitize_tmux_session_name_strips_dangerous_chars():
    assert sanitize_tmux_session_name("abc-123") == "jupiter-abc-123"
    assert sanitize_tmux_session_name("a.b:c d;e$(rm)") == "jupiter-a_b_c_d_e__rm"
    # Nie leer, selbst bei komplett fremdartiger ID.
    assert sanitize_tmux_session_name("???") == "jupiter-session"


def test_tmux_available_true_for_real_binary():
    assert tmux_available("tmux") is True


def test_tmux_available_false_for_missing_binary():
    assert tmux_available("definitely-not-a-real-tmux-binary-xyz") is False


@pytest.mark.asyncio
async def test_spawn_raises_transport_error_when_tmux_missing(tmp_path):
    transport = TmuxTransport(
        "s1", data_dir=str(tmp_path), tmux_bin="definitely-not-a-real-tmux-binary-xyz"
    )
    with pytest.raises(TransportError):
        await transport.spawn(["echo", "hi"], cwd=str(tmp_path), long_lived=False)


# ===========================================================================
# Fake-CLI-Skripte
# ===========================================================================

# Long-lived: liest Zeilen aus stdin in einer Schleife, echot jede als JSON zurück.
# Läuft weiter, bis der Prozess extern beendet wird (kill-session) — wie Claude im
# `-p --input-format stream-json`-Modus, der über viele Turns am Leben bleibt.
FAKE_LONG_LIVED = r'''
import sys, json
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    print(json.dumps({"type": "result", "text": "ECHO:" + line}))
    sys.stdout.flush()
'''

# Oneshot: liest die komplette stdin-Datei einmal, gibt eine JSON-Zeile aus, endet.
FAKE_ONESHOT = r'''
import sys, json
prompt = sys.stdin.read().strip()
print(json.dumps({"type": "result", "text": "TURN:" + prompt}))
'''


def _write_script(tmp_path, name: str, body: str) -> list[str]:
    script = tmp_path / name
    script.write_text(body, encoding="utf-8")
    return [sys.executable, str(script)]


# ===========================================================================
# Long-lived: der eigentliche Spike-Befund
# ===========================================================================

@pytest.mark.asyncio
async def test_long_lived_survives_independent_writer_open_close_cycles(tmp_path):
    """Kernbefund des Spikes: zwei GETRENNTE, nacheinander folgende write_line()-
    Aufrufe (jeder öffnet die FIFO, schreibt, schließt wieder — wie ein Backend-
    Neustart zwischen zwei Turns) dürfen den CLI-Prozess NICHT fälschlich per EOF
    beenden. Ohne den `exec 9<>fifo`-Selbst-Open-Trick im Pane-Wrapper würde der
    Prozess nach dem ersten write_line()-Schließen sauber (Exit 0) enden."""
    argv = _write_script(tmp_path, "fake_long_lived.py", FAKE_LONG_LIVED)
    transport = TmuxTransport("spike-claude", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(argv, cwd=str(tmp_path), long_lived=True)
        assert await transport.refresh_liveness() is True

        await transport.write_line(b"turn-1\n")
        line1 = await transport.readline()
        assert b"ECHO:turn-1" in line1

        # Simuliert einen zweiten, komplett unabhängigen Schreiber (z. B. nach
        # einem gedachten Backend-Neustart) — write_line() öffnet/schreibt/schließt
        # erneut. Der Prozess darf davon nichts mitbekommen.
        assert await transport.refresh_liveness() is True
        await transport.write_line(b"turn-2\n")
        line2 = await transport.readline()
        assert b"ECHO:turn-2" in line2

        assert await transport.refresh_liveness() is True
    finally:
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_long_lived_stop_kills_process_no_orphan(tmp_path):
    argv = _write_script(tmp_path, "fake_long_lived.py", FAKE_LONG_LIVED)
    transport = TmuxTransport("spike-stop", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(argv, cwd=str(tmp_path), long_lived=True)
        assert await transport.session_exists() is True
        pid = await transport.pane_pid()
        assert pid is not None

        await transport.kill()

        assert await transport.session_exists() is False
        import os

        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        transport.cleanup_files()


# ===========================================================================
# Oneshot: respawn über mehrere Turns
# ===========================================================================

@pytest.mark.asyncio
async def test_oneshot_respawn_across_turns_appends_cumulative_log(tmp_path):
    argv = _write_script(tmp_path, "fake_oneshot.py", FAKE_ONESHOT)
    prompt1 = tmp_path / "prompt1.txt"
    prompt1.write_text("hello-1", encoding="utf-8")
    prompt2 = tmp_path / "prompt2.txt"
    prompt2.write_text("hello-2", encoding="utf-8")

    transport = TmuxTransport("spike-oneshot", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(
            argv, cwd=str(tmp_path), long_lived=False, stdin_file=str(prompt1)
        )
        rc1 = await transport.wait()
        assert rc1 == 0

        # Turn 2: erneuter spawn() unter demselben Session-Namen respawnt sauber
        # (keine "duplicate session"-Kollision, siehe _ensure_no_stale_session).
        await transport.spawn(
            argv, cwd=str(tmp_path), long_lived=False, stdin_file=str(prompt2)
        )
        rc2 = await transport.wait()
        assert rc2 == 0

        combined = transport.out_path.read_text("utf-8")
        assert "TURN:hello-1" in combined
        assert "TURN:hello-2" in combined
        assert combined.index("TURN:hello-1") < combined.index("TURN:hello-2")
    finally:
        # `remain-on-exit on` haelt die (tote) Pane/Session nach Prozessende am
        # Leben (fuer Diagnose) -> ohne expliziten kill() bliebe eine tmux-Session
        # auf dem Host zurueck, obwohl der Oneshot-Prozess laengst beendet ist.
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_oneshot_exit_code_captured_in_err_log(tmp_path):
    script = tmp_path / "fake_fail.py"
    script.write_text("import sys; sys.exit(3)\n", encoding="utf-8")
    argv = [sys.executable, str(script)]

    transport = TmuxTransport("spike-exitcode", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(argv, cwd=str(tmp_path), long_lived=False)
        rc = await transport.wait()
        assert rc == 3
        assert f"{EXIT_MARKER}:3" in transport.err_path.read_text("utf-8")
    finally:
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_survives_an_instantly_completing_command(tmp_path):
    """QA-BUG-1-Regression: `new-session` + ein SEPARATER `set-option`-Aufruf ließ ein
    Zeitfenster, in dem eine sofort beendete Pane (echte, schnelle Codex-/OpenCode-Turns
    sind das nahezu immer) die Session/den Server schon weg hatte, bevor `set-option`
    lief -> `TransportError` ("no server running"), reproduziert 3/3 mit echten Codex-/
    OpenCode-Läufen. `true` beendet sich schneller als jeder reale CLI-Turnaround —
    haerteste erreichbare Nachbildung ohne echte Engine-Kosten."""
    transport = TmuxTransport("spike-instant", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(["true"], cwd=str(tmp_path), long_lived=False)
        assert await transport.session_exists() is True
        rc = await transport.wait()
        assert rc == 0
    finally:
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_hanging_tmux_call_times_out_instead_of_hanging_forever(tmp_path):
    """Produktionsvorfall (2026-07-07): ein echter Codex-Turn unter `tmux` blieb in
    `TmuxTransport._tmux()`s `communicate()` fuer IMMER haengen (tmux-Server + Codex-
    Prozess liefen im Hintergrund normal weiter, sogar mit korrektem Turn-Abschluss —
    aber `POST /sessions` bekam NIE eine Antwort, kein Log, kein Fehler). Kein
    reproduzierbarer Regressionstest fuer die zugrunde liegende, seltene Reaping-
    Stoerung selbst moeglich (nicht deterministisch) — dieser Test deckt stattdessen
    die Absicherung ab: ein `tmux`-Ersatzbinary, das nie antwortet, darf `spawn()`
    NICHT unbegrenzt haengen lassen, sondern muss nach dem konfigurierten Timeout
    einen klaren `TransportError` werfen (der `routes/sessions.py` zu einer 503 statt
    eines rohen, nie endenden Requests macht)."""
    fake_tmux = tmp_path / "fake_tmux_hangs.sh"
    fake_tmux.write_text("#!/bin/sh\nsleep 3600\n", encoding="utf-8")
    fake_tmux.chmod(0o755)

    transport = TmuxTransport(
        "spike-hang",
        data_dir=str(tmp_path / "data"),
        tmux_bin=str(fake_tmux),
        cmd_timeout_seconds=0.3,
    )
    with pytest.raises(TransportError, match="antwortet nicht"):
        await asyncio.wait_for(
            transport.spawn(["true"], cwd=str(tmp_path), long_lived=False), timeout=5
        )


# ===========================================================================
# Backfill
# ===========================================================================

@pytest.mark.asyncio
async def test_capture_backfill_is_bounded_tail(tmp_path):
    argv = _write_script(tmp_path, "fake_long_lived.py", FAKE_LONG_LIVED)
    transport = TmuxTransport("spike-backfill", data_dir=str(tmp_path / "data"))
    try:
        await transport.spawn(argv, cwd=str(tmp_path), long_lived=True)
        for i in range(5):
            await transport.write_line(f"line-{i}\n".encode())
            await transport.readline()

        full = transport.out_path.read_text("utf-8")
        assert "ECHO:line-0" in full and "ECHO:line-4" in full

        tail = transport.capture_backfill(max_bytes=40).decode("utf-8", errors="replace")
        assert len(tail) <= 40
        assert "ECHO:line-4" in tail
        assert "ECHO:line-0" not in tail  # zu weit zurück für den kleinen Bound
    finally:
        await transport.kill()
        transport.cleanup_files()
