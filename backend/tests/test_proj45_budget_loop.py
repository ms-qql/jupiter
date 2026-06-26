"""PROJ-45 — Auto-Reanimierungs-Budget: Endlosschleife & False-„hängt" abstellen.

Deterministisch über injizierte Uhr (Clock) + FakeDriver — ohne echte Claude-Session.
Deckt die beiden Wurzelursachen aus der Spec ab:

1. **Budget übersteht Resume-„Fortschritt"** — der unmittelbar nach einem Auto-Versuch
   auftretende ``aktiv``-Zustand (durch das Transkript-Abspiel) setzt das Budget NICHT
   zurück; nur ein echter neuer Turn (``num_turns`` über dem Wasserstand) tut das. Damit
   terminiert ein deterministischer Hänger nach ``max_auto_attempts`` (Belegfall a66fa404).
2. **In-Flight-Geduld über kurze Zwischen-Sätze** (Flag-Hysterese) — ``note_progress``
   löscht ``tool_in_flight`` nicht mehr; nur die echte Turn-Grenze (``feed_usage``) bzw.
   der Resume-Start (``clear_tool_in_flight``) tun das.
"""
from __future__ import annotations

import pytest

from app.engine import liveness, watchdog
from app.engine.liveness import (
    DEFAULTS,
    LIVENESS_ACTIVE,
    LIVENESS_HANGING,
    LivenessMonitor,
)
from app.engine.manager import RUNNING, SessionManager
from app.engine.watchdog import WatchdogMonitor

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class Clock:
    """Steuerbare monotone Uhr für deterministische Fortschritts-/Backoff-Tests."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class StubLivenessStore:
    """Minimaler Config-Provider (config/snapshot) mit überschreibbaren Schwellen."""

    def __init__(self, **over) -> None:
        self._c = {**DEFAULTS, **over}

    def config(self) -> dict:
        return dict(self._c)

    def snapshot(self) -> dict:
        return {**self._c, "source": "stub", "warning": None}


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _hang(rt, idle: float = 1000.0) -> Clock:
    """Versetzt ein Runtime in einen echten Hänger: RUNNING + Fortschritts-Uhr abgelaufen.

    Gibt die injizierte Uhr zurück — derselbe Takt, den ``_resume`` über ``note_progress``
    weiterbenutzt, sodass ein Auto-Versuch die Uhr deterministisch zurücksetzt.
    """
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.note_progress()
    clk.advance(idle)
    rt.state.status = RUNNING
    return clk


# --- AC: Deterministischer Hänger terminiert nach max_auto_attempts ---------


@pytest.mark.asyncio
async def test_deterministic_hang_terminates_at_budget(monkeypatch):
    """Belegfall a66fa404: jeder Resume hängt am SELBEN Turn (num_turns wächst nie).

    Früher nullte der unmittelbar folgende ``aktiv``-Tick das Budget → ``max_auto_attempts``
    griff nie → Endlosschleife. Mit dem Turn-Wasserstand bleibt das Budget bestehen: nach
    genau ``max_auto_attempts`` Versuchen bleibt die Session „hängt", ohne weitere Versuche.
    """
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(
            progress_timeout_seconds=180,
            max_auto_attempts=2,
            backoff_seconds=0,
            enabled_auto_reanimation=True,
        ),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = _hang(rt)
    # num_turns ist nach dem Create fix (derselbe Turn hängt immer wieder) — nie erhöhen.
    frozen_turns = rt.state.num_turns

    # Viele Poll-Ticks: jeweils (a) Hänger-Tick (ggf. Reanimierung), (b) „aktiv"-Tick
    # direkt nach dem Resume (Uhr zurückgesetzt) — genau der Tick, der früher das Budget
    # nullte. Danach Uhr wieder über das Timeout schieben → erneuter Hänger am selben Turn.
    for _ in range(8):
        await mgr.evaluate_liveness_once()           # Hänger-Tick: reanimiert, solange Budget
        assert rt.state.num_turns == frozen_turns    # Resume-Replay erzeugt KEINEN neuen Turn
        await mgr.evaluate_liveness_once()            # „aktiv"-Tick direkt nach Resume
        assert rt.liveness.auto_attempts <= 2         # Budget wird NIE durch Replay genullt
        clk.advance(300)                              # > 180 s → hängt wieder am selben Turn

    assert rt.liveness.auto_attempts == 2             # exakt das Budget ausgeschöpft
    assert rt.derive_liveness(180) == LIVENESS_HANGING  # bleibt „hängt", keine Schleife mehr


@pytest.mark.asyncio
async def test_replay_active_does_not_reset_budget(monkeypatch):
    """Isoliert: ein „aktiv"-Tick OHNE neuen Turn setzt das Budget nicht zurück."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(
            progress_timeout_seconds=180, max_auto_attempts=2,
            backoff_seconds=0, enabled_auto_reanimation=True,
        ),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _hang(rt)
    await mgr.evaluate_liveness_once()                # 1. Auto-Versuch → aktiv (Replay)
    assert rt.liveness.auto_attempts == 1
    assert rt.derive_liveness(180) == LIVENESS_ACTIVE  # Resume = kurzzeitig aktiv
    await mgr.evaluate_liveness_once()                # „aktiv"-Tick, num_turns unverändert
    assert rt.liveness.auto_attempts == 1             # NICHT auf 0 zurückgesetzt


# --- AC: Echter neuer Fortschritt setzt das Budget zurück -------------------


@pytest.mark.asyncio
async def test_real_new_turn_resets_budget(monkeypatch):
    """Schließt die Session nach einer Reanimierung einen NEUEN Turn ab (num_turns über
    dem Wasserstand), gilt das als substanzieller Fortschritt → Budget frisch. Ein
    späterer, anderer Hänger darf wieder bis ``max_auto_attempts`` auto-reanimiert werden.
    """
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(
            progress_timeout_seconds=180, max_auto_attempts=2,
            backoff_seconds=0, enabled_auto_reanimation=True,
        ),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = _hang(rt)
    await mgr.evaluate_liveness_once()                # Auto-Versuch → auto_attempts=1
    assert rt.liveness.auto_attempts == 1
    watermark = rt.liveness.progress_watermark
    # Session arbeitet real weiter: ein neuer Turn wird abgeschlossen.
    rt.state.num_turns = watermark + 1
    await mgr.evaluate_liveness_once()                # „aktiv"-Tick MIT neuem Turn → Reset
    assert rt.liveness.auto_attempts == 0             # Budget zurückgesetzt
    # Späterer, anderer Hänger → wieder volles Budget nutzbar.
    clk.advance(300)
    await mgr.evaluate_liveness_once()
    assert rt.liveness.auto_attempts == 1             # frischer Versuch erlaubt


# --- AC: In-Flight-Geduld bleibt über kurze Zwischen-Sätze erhalten ---------


@pytest.mark.asyncio
async def test_in_flight_patience_survives_short_message(monkeypatch):
    """Großer Tool-Call → kurzer Assistenten-Zwischensatz (note_progress) → >180 s ohne
    Event: NICHT „hängt" (600 s In-Flight-Geduld gilt weiter). Erst das result-Event
    (feed_usage) schaltet auf den 180 s-Normaltimeout zurück."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.state.status = RUNNING
    rt.watchdog.record("Edit", {"file_path": "big.py"})  # großer Edit beginnt → in-flight
    clk.advance(60)
    rt.watchdog.note_progress()                          # kurzer Zwischensatz
    assert rt.watchdog.tool_in_flight is True            # Hysterese: Geduld bleibt
    clk.advance(200)                                     # > 180 s, < 600 s
    assert rt.derive_liveness() == LIVENESS_ACTIVE       # NICHT vorzeitig „hängt"
    # Turn-Grenze: result-Event beendet die Geduld → wieder strenger 180 s-Timeout.
    rt.watchdog.feed_usage(100)
    assert rt.watchdog.tool_in_flight is False
    clk.advance(200)
    assert rt.derive_liveness() == LIVENESS_HANGING


@pytest.mark.asyncio
async def test_resume_clears_in_flight(monkeypatch):
    """Resume-Start setzt die In-Flight-Geduld zurück: ein frischer Prozess hat kein Tool
    offen, also darf die vor dem Resume gesetzte Hysterese nicht über den Neustart leaken."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.state.status = RUNNING
    rt.watchdog.record("Bash", {"command": "haengt"})    # in-flight
    clk.advance(700)                                     # > 600 s In-Flight-Geduld → hängt
    assert rt.derive_liveness() == LIVENESS_HANGING
    await mgr.reanimate(rt.state.session_id)              # manueller Resume
    assert rt.watchdog.tool_in_flight is False            # Geduld nach Resume zurückgesetzt
