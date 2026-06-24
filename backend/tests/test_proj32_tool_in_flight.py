"""PROJ-32 — Fortschritts-Signal aus Tool-Aktivität (kein False-„hängt" bei langen Tools).

Deterministisch über injizierte Uhren (Clock) + FakeDriver. Geprüft werden:
- Watchdog: Tool-Start (record) zählt als Fortschritt + markiert „in-flight"; Assistenten-
  Output/Result (note_progress/feed_usage) löschen den In-Flight-Zustand; die Amok-
  Buchhaltung (Loop-/Schreibrate-Deques) bleibt von der Fortschritts-Uhr unberührt.
- derive_liveness: ein laufendes Tool nutzt die höhere In-Flight-Geduld (langer Build ≠
  Hänger), wird aber bei Überschreiten auch dieser Schwelle doch als „hängt" erkannt;
  Stillstand OHNE laufendes Tool bleibt beim normalen Timeout (Regression).
- Config + API: tool_in_flight_timeout_seconds (Default/Validierung/Round-Trip).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engine import liveness, watchdog
from app.engine.liveness import (
    DEFAULTS,
    LIVENESS_ACTIVE,
    LIVENESS_HANGING,
    LivenessStore,
)
from app.engine.manager import RUNNING, SessionManager
from app.engine.watchdog import WatchdogMonitor
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class Clock:
    """Steuerbare monotone Uhr für deterministische Fortschritts-Tests."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class StubLivenessStore:
    """Minimaler Config-Provider mit überschreibbaren Schwellen."""

    def __init__(self, **over) -> None:
        self._c = {**DEFAULTS, **over}

    def config(self) -> dict:
        return dict(self._c)

    def snapshot(self) -> dict:
        return {**self._c, "source": "stub", "warning": None}


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _app() -> object:
    return create_app(driver_factory=lambda: FakeDriver())


# --- Watchdog: Tool-Start als Fortschritt + In-Flight-Flag -----------------


def test_record_marks_in_flight_and_resets_progress():
    clk = Clock()
    mon = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    mon.note_progress()
    clk.advance(500)  # lange Stille ...
    assert mon.seconds_since_progress() == 500
    mon.record("Bash", {"command": "npm run build"})  # ... Tool startet jetzt
    assert mon.tool_in_flight is True
    assert mon.seconds_since_progress() == 0  # Tool-Start = Fortschritt


def test_note_progress_clears_in_flight():
    clk = Clock()
    mon = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    mon.record("Bash", {"command": "x"})
    assert mon.tool_in_flight is True
    mon.note_progress()  # Modell produziert wieder
    assert mon.tool_in_flight is False


def test_feed_usage_clears_in_flight():
    clk = Clock()
    mon = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    mon.record("Bash", {"command": "x"})
    assert mon.tool_in_flight is True
    mon.feed_usage(100)  # result-Event
    assert mon.tool_in_flight is False


def test_record_preserves_loop_and_write_counters():
    """Amok-Erkennung unberührt: Tool-Start füttert NUR die Fortschritts-Uhr, nicht die
    Loop-(_repeat/_last_fp)- und Schreibrate-(_writes)-Buchhaltung."""
    clk = Clock()
    mon = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    mon.record("Write", {"file_path": "a.txt"})
    mon.record("Write", {"file_path": "a.txt"})  # identisch → Loop-Zähler steigt
    assert mon._repeat == 2  # noqa: SLF001 — White-Box: Schleifen-Zähler intakt
    assert len(mon._writes) == 2  # noqa: SLF001 — Schreibrate-Deque intakt
    # Ein nicht-identischer Aufruf setzt den Schleifen-Zähler zurück (wie gehabt).
    mon.record("Read", {"file_path": "b.txt"})
    assert mon._repeat == 1  # noqa: SLF001


# --- derive_liveness: In-Flight-Geduld -------------------------------------


def _running_with_tool(rt, idle: float) -> None:
    """Versetzt ein Runtime in: RUNNING, ein Tool gestartet (in-flight), seit ``idle`` s nichts mehr."""
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.record("Bash", {"command": "npm run build"})  # in-flight + Uhr auf 0
    clk.advance(idle)
    rt.state.status = RUNNING


@pytest.mark.asyncio
async def test_long_tool_in_flight_is_active(monkeypatch):
    """Langer legitimer Tool-Call (300 s > 180 s Normaltimeout, < 600 s In-Flight) → aktiv."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _running_with_tool(rt, idle=300)
    assert rt.derive_liveness() == LIVENESS_ACTIVE


@pytest.mark.asyncio
async def test_tool_in_flight_beyond_higher_timeout_is_hanging(monkeypatch):
    """Echter Tool-Hänger: auch die höhere In-Flight-Geduld (600 s) überschritten → hängt."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _running_with_tool(rt, idle=700)
    assert rt.derive_liveness() == LIVENESS_HANGING


@pytest.mark.asyncio
async def test_idle_without_tool_still_hangs_at_normal_timeout(monkeypatch):
    """Regression: Stillstand OHNE laufendes Tool wird weiter beim Normaltimeout erkannt."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.note_progress()  # kein Tool in-flight
    clk.advance(300)             # > 180 s Normaltimeout
    rt.state.status = RUNNING
    assert rt.watchdog.tool_in_flight is False
    assert rt.derive_liveness() == LIVENESS_HANGING


# --- Config + API ----------------------------------------------------------


def test_store_includes_tool_in_flight_default(tmp_path):
    store = LivenessStore(str(tmp_path / "fehlt.yaml"))
    assert store.config()["tool_in_flight_timeout_seconds"] == 600


def test_store_rejects_nonpositive_tool_in_flight(tmp_path):
    store = LivenessStore(str(tmp_path / "liveness.yaml"))
    with pytest.raises(ValueError):
        store.save(
            {
                "progress_timeout_seconds": 180,
                "tool_in_flight_timeout_seconds": 0,  # muss > 0
                "poll_interval_seconds": 5,
                "max_auto_attempts": 1,
                "backoff_seconds": 0,
            }
        )


def test_get_liveness_exposes_tool_in_flight(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    body = client.get("/settings/liveness").json()
    assert body["tool_in_flight_timeout_seconds"] == 600


def test_put_liveness_rejects_nonpositive_tool_in_flight(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "progress_timeout_seconds": 180,
            "tool_in_flight_timeout_seconds": 0,  # gt=0 → 422
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 422
