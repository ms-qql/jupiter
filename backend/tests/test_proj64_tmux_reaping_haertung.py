"""PROJ-64 — Reaping-Race-Härtung für den tmux-Transport (BUG-4-Nachfolger, PROJ-63).

Deckt den Live-Vorfall vom 2026-07-07 ab: `POST /sessions` scheiterte mit einem
`503`, obwohl die zugrunde liegende tmux-Session im Hintergrund korrekt lief (der
Nutzer musste manuell reaktivieren + einen Turn fortsetzen). Diese Tests prüfen:

1. Prüf-/Lese-Aufrufe (`has-session` etc.) überstehen einen EINMALIGEN, transienten
   Hänger automatisch (Retry über `tmux_cmd_retries`), ohne dass der Aufrufer je
   einen Fehler sieht.
2. `spawn()`s `new-session`-Aufruf wird NIE blind wiederholt — hängt er, aber die
   Session existiert danach bereits (genau der gemeldete Fall), wird das als
   Erfolg (Attach) behandelt statt als Fehler.
3. Existiert die Session nach dem ersten Hänger noch NICHT, wird GENAU EIN
   weiterer Versuch unternommen (keine Doppel-Session-Gefahr, da `new-session`
   erst nach einem `has-session=false`-Check erneut läuft).
4. Hängt auch der zweite Versuch UND existiert die Session danach immer noch
   nicht, bleibt der bestehende PROJ-63/BUG-2-Fehlerpfad (`TmuxTimeoutError`,
   Unterklasse von `TransportError` → `503` in `routes/sessions.py`) unverändert
   als letzte Absicherung erhalten.
5. `metrics.py::_systemctl_is_active()` (dieselbe Fehlerklasse, im Produktions-
   vorfall als liegen gebliebener `<defunct>`-Zombie beobachtet) degradiert nicht
   mehr bei einem einzelnen Timeout sofort zu `unknown`.
6. QA-BUG-1 (gefunden 2026-07-07, PROJ-64-QA): kollidiert der ZWEITE
   `new-session`-Versuch selbst mit einer inzwischen doch entstandenen Session
   (`rc≠0`, "duplicate session" — KEIN erneuter Timeout), muss auch das als
   Attach-Erfolg erkannt werden, nicht als roher, ungeprüfter Fehler.

Die tmux-spezifischen Tests nutzen ein Fake-`tmux`-Ersatzbinary (POSIX-Shell-
Skript), das gezielt EINEN bestimmten tmux-Subbefehl (per Token-Match in `"$@"`)
N-mal "hängen" lässt (`sleep 3600`, vom `cmd_timeout_seconds`-Timeout gekillt) und
optional den echten Befehl währenddessen im Hintergrund an das echte `tmux`
weiterreicht — exakt das im Produktionsvorfall beobachtete Verhalten: der
Hintergrund-Befehl läuft normal durch, nur die Antwort auf DIESEN Aufruf kommt
nie an. Alle anderen Subbefehle delegiert das Fake-Skript sofort an das echte
`tmux` (kein Einfluss auf Cleanup/Folgeaufrufe).
"""
from __future__ import annotations

import asyncio
import shutil

import pytest

from app.config import settings
from app.engine.metrics import MetricsService
from app.engine.transport import TmuxTimeoutError, TmuxTransport, TransportError

REAL_TMUX = shutil.which("tmux")

pytestmark = pytest.mark.skipif(REAL_TMUX is None, reason="tmux ist auf diesem Host nicht installiert")


def _write_flaky_tmux(tmp_path, *, hang_cmd: str, hang_count: int, mode: str = "noop"):
    """Fake-tmux-Ersatzbinary: hängt (`sleep 3600`) für die ersten `hang_count`
    Aufrufe, deren Argumente `hang_cmd` enthalten; alle anderen Aufrufe (und alle
    Aufrufe danach) gehen sofort an das echte `tmux`. Bei `mode="background"`
    wird der echte Befehl VOR dem Hängen zusätzlich im Hintergrund ausgeführt
    (simuliert: der tmux-Befehl lief tatsächlich durch, nur die Antwort kam nie
    an — der Kern von BUG-4)."""
    counter_file = tmp_path / f"counter-{hang_cmd}.txt"
    counter_file.write_text("0", encoding="utf-8")
    script = tmp_path / f"flaky_tmux_{hang_cmd}.sh"
    background_line = '    "$REAL" "$@" >/dev/null 2>&1 &\n' if mode == "background" else ""
    script.write_text(
        "#!/bin/sh\n"
        f'HANG_CMD="{hang_cmd}"\n'
        f'COUNTER_FILE="{counter_file}"\n'
        f'REAL="{REAL_TMUX}"\n'
        "MATCH=0\n"
        'for a in "$@"; do\n'
        '  if [ "$a" = "$HANG_CMD" ]; then MATCH=1; fi\n'
        "done\n"
        'if [ "$MATCH" = "1" ]; then\n'
        '  N=$(cat "$COUNTER_FILE")\n'
        "  N=$((N+1))\n"
        '  echo "$N" > "$COUNTER_FILE"\n'
        f'  if [ "$N" -le "{hang_count}" ]; then\n'
        f"{background_line}"
        # `exec` statt `sleep 3600` als eigenständiges Kommando: ersetzt den
        # Shell-Prozess durch `sleep` (kein separater Kindprozess) — `proc.kill()`
        # in `_tmux()` trifft dann den tatsächlich schlafenden Prozess direkt,
        # statt einen verwaisten `sleep`-Kindprozess zurückzulassen.
        "    exec sleep 3600\n"
        "  fi\n"
        "fi\n"
        'exec "$REAL" "$@"\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script, counter_file


# ===========================================================================
# 1) `_tmux()`-Retry auf niedriger Ebene (Prüf-/Lese-Aufrufe)
# ===========================================================================

@pytest.mark.asyncio
async def test_tmux_call_retries_transient_timeout_then_succeeds(tmp_path):
    flaky, counter = _write_flaky_tmux(tmp_path, hang_cmd="probe-target", hang_count=1, mode="noop")
    transport = TmuxTransport(
        "proj64-tmux-retry-direct", data_dir=str(tmp_path / "data"),
        tmux_bin=str(flaky), cmd_timeout_seconds=0.3,
    )
    # "probe-target" ist kein echter tmux-Subbefehl — es geht nur darum, dass der
    # EINMALIGE Hänger automatisch überstanden wird (kein TmuxTimeoutError), nicht
    # um den konkreten (Fehler-)Rückgabewert von tmux selbst.
    await asyncio.wait_for(
        transport._tmux("probe-target", check=False, retries=1), timeout=5
    )
    assert int(counter.read_text().strip()) == 2  # 1 Hänger + 1 erfolgreicher Retry


@pytest.mark.asyncio
async def test_tmux_call_gives_up_after_configured_retries(tmp_path):
    flaky, counter = _write_flaky_tmux(tmp_path, hang_cmd="probe-target", hang_count=99, mode="noop")
    transport = TmuxTransport(
        "proj64-tmux-retry-exhausted", data_dir=str(tmp_path / "data"),
        tmux_bin=str(flaky), cmd_timeout_seconds=0.3,
    )
    with pytest.raises(TmuxTimeoutError):
        await asyncio.wait_for(
            transport._tmux("probe-target", check=False, retries=1), timeout=5
        )
    assert int(counter.read_text().strip()) == 2  # Erstversuch + EIN Retry, kein unbegrenztes Haengen


@pytest.mark.asyncio
async def test_session_exists_retries_transient_timeout_transparently(tmp_path):
    """`session_exists()` (genutzt von Liveness/Reanimation) übersteht einen
    einzelnen Hänger automatisch — der Aufrufer sieht nie einen Fehler."""
    real = TmuxTransport("proj64-probe-retry", data_dir=str(tmp_path / "real-data"))
    try:
        await real.spawn(["sleep", "5"], cwd=str(tmp_path), long_lived=False)
        assert await real.session_exists() is True

        flaky, _counter = _write_flaky_tmux(tmp_path, hang_cmd="has-session", hang_count=1, mode="noop")
        probe = TmuxTransport(
            "proj64-probe-retry", data_dir=str(tmp_path / "probe-data"),
            tmux_bin=str(flaky), cmd_timeout_seconds=0.3,
        )
        assert await asyncio.wait_for(probe.session_exists(), timeout=5) is True
    finally:
        await real.kill()
        real.cleanup_files()


# ===========================================================================
# 2)-4) `spawn()` — Attach-statt-Fehler-Pfad für `new-session`
# ===========================================================================

@pytest.mark.asyncio
async def test_spawn_attaches_when_session_exists_despite_timeout(tmp_path):
    """Reproduziert den gemeldeten Produktionsfall (2026-07-07): der `new-session`-
    Aufruf hängt, aber die Session ist tatsächlich schon da (hier: der echte
    Befehl lief im Hintergrund durch) — `spawn()` muss das als Erfolg werten,
    OHNE einen zweiten `new-session`-Versuch zu unternehmen (Doppel-Session-Gefahr)."""
    flaky, counter = _write_flaky_tmux(tmp_path, hang_cmd="new-session", hang_count=1, mode="background")
    transport = TmuxTransport(
        "proj64-attach-success", data_dir=str(tmp_path / "data"),
        tmux_bin=str(flaky), cmd_timeout_seconds=0.3,
    )
    try:
        await asyncio.wait_for(
            transport.spawn(["sleep", "5"], cwd=str(tmp_path), long_lived=False), timeout=10
        )
        assert int(counter.read_text().strip()) == 1  # KEIN zweiter new-session-Versuch
        assert await transport.session_exists() is True
    finally:
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_spawn_retries_new_session_once_if_not_yet_created(tmp_path):
    """Existiert die Session nach dem ersten Hänger NICHT (hier: der echte Befehl
    lief NICHT im Hintergrund — reiner Hänger ohne Wirkung), unternimmt `spawn()`
    genau EINEN weiteren `new-session`-Versuch, der dann durchläuft."""
    flaky, counter = _write_flaky_tmux(tmp_path, hang_cmd="new-session", hang_count=1, mode="noop")
    transport = TmuxTransport(
        "proj64-retry-success", data_dir=str(tmp_path / "data"),
        tmux_bin=str(flaky), cmd_timeout_seconds=0.3,
    )
    try:
        await asyncio.wait_for(
            transport.spawn(["sleep", "5"], cwd=str(tmp_path), long_lived=False), timeout=10
        )
        assert int(counter.read_text().strip()) == 2  # 1 Hänger + 1 erfolgreicher Retry
        assert await transport.session_exists() is True
    finally:
        await transport.kill()
        transport.cleanup_files()


@pytest.mark.asyncio
async def test_spawn_raises_tmux_timeout_error_after_retry_and_attach_check_fail(tmp_path):
    """Regression von PROJ-63/BUG-2: hängt auch der Retry UND existiert die
    Session danach nachweislich immer noch nicht (echter, dauerhafter Hänger),
    bleibt ein klarer Fehler (kein für immer hängender Request) — `routes/
    sessions.py` macht daraus weiterhin einen sauberen 503."""
    flaky, counter = _write_flaky_tmux(tmp_path, hang_cmd="new-session", hang_count=99, mode="noop")
    transport = TmuxTransport(
        "proj64-persistent-hang", data_dir=str(tmp_path / "data"),
        tmux_bin=str(flaky), cmd_timeout_seconds=0.3,
    )
    with pytest.raises(TmuxTimeoutError):
        await asyncio.wait_for(
            transport.spawn(["sleep", "5"], cwd=str(tmp_path), long_lived=False), timeout=10
        )
    assert int(counter.read_text().strip()) == 2  # genau 1 Erstversuch + 1 Retry, keine Endlosschleife


@pytest.mark.asyncio
async def test_spawn_attaches_when_retry_collides_with_now_existing_session(tmp_path):
    """QA-BUG-1-Regression (PROJ-64, gefunden 2026-07-07): kollidiert der ZWEITE
    `new-session`-Versuch nicht mit einem erneuten Timeout, sondern SOFORT mit
    einer inzwischen doch entstandenen Session (`rc≠0`, "duplicate session" — wie
    es echtes `tmux` in genau diesem Fall meldet), darf das NICHT als roher Fehler
    (503) durchschlagen — die Session existiert ja bereits. Deterministisch über
    ein `_tmux`-Monkeypatch nachgebildet (kein Timing-Zufall): Versuch 1 timet aus,
    der `has-session`-Check direkt danach sagt "existiert nicht", Versuch 2
    scheitert sofort mit einem echten `TransportError` ("duplicate session")."""
    transport = TmuxTransport("proj64-retry-collision", data_dir=str(tmp_path / "data"))
    new_session_calls = {"n": 0}
    has_session_calls = {"n": 0}

    async def fake_tmux(*args, check=True, retries=0):
        if args and args[0] == "has-session":
            has_session_calls["n"] += 1
            # 1. Check (nach Versuch 1s Timeout): die Aktion ist noch nicht fertig.
            # 2. Check (nach Versuch 2s Kollision): jetzt existiert sie (per
            # Definition der Kollision — genau das, was echtes tmux mit "duplicate
            # session" signalisiert).
            return (1, "", "") if has_session_calls["n"] == 1 else (0, "", "")
        new_session_calls["n"] += 1
        if new_session_calls["n"] == 1:
            raise TmuxTimeoutError("simulierter Timeout beim ersten new-session-Versuch")
        raise TransportError(
            "tmux new-session ... fehlgeschlagen (Code 1): duplicate session: proj64-retry-collision"
        )

    transport._tmux = fake_tmux  # gezielt nur den Aufruf-Layer isolieren (kein echter Subprozess/Timing)
    await transport._spawn_new_session(("start-server", ";", "new-session", "-d", "-s", "proj64-retry-collision"))
    assert new_session_calls["n"] == 2  # Erstversuch (Timeout) + Retry (Kollision) — kein dritter Versuch
    assert has_session_calls["n"] == 2  # Check nach jedem der beiden fehlgeschlagenen Versuche


# ===========================================================================
# 5) metrics.py::_systemctl_is_active() — dieselbe Fehlerklasse
# ===========================================================================

class _HangProc:
    returncode = None

    async def communicate(self):
        raise AssertionError("communicate() sollte vom Timeout abgefangen werden")

    def kill(self):
        self.returncode = -9


class _OkProc:
    returncode = 0

    def __init__(self, out: bytes):
        self._out = out

    async def communicate(self):
        return self._out, b""


@pytest.mark.asyncio
async def test_systemctl_retries_once_before_degrading(monkeypatch):
    calls = {"n": 0}

    async def fake_exec(*args, **kwargs):
        calls["n"] += 1
        return _HangProc() if calls["n"] == 1 else _OkProc(b"active\n")

    async def fake_wait_for(coro, timeout):
        if calls["n"] == 1:
            coro.close()
            raise asyncio.TimeoutError
        return await coro

    monkeypatch.setattr("app.engine.metrics.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("app.engine.metrics.asyncio.wait_for", fake_wait_for)
    assert await MetricsService._systemctl_is_active("egal") == "active"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_systemctl_gives_up_after_configured_retries(monkeypatch):
    calls = {"n": 0}

    async def fake_exec(*args, **kwargs):
        calls["n"] += 1
        return _HangProc()

    async def fake_wait_for(coro, timeout):
        coro.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr("app.engine.metrics.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("app.engine.metrics.asyncio.wait_for", fake_wait_for)
    assert await MetricsService._systemctl_is_active("egal") == "unknown"
    assert calls["n"] == settings.metrics_systemctl_retries + 1
