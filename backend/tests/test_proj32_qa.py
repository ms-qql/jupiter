"""PROJ-32 — QA: Akzeptanzkriterien-Vervollständigung + Red-Team.

Ergänzt die Entwickler-Tests (test_proj32_tool_in_flight.py) um die adversariellen
Checks, die für die Abnahme entscheidend sind:
- AC5: das Füttern der Fortschritts-Uhr aus Tool-Aktivität darf die Amok-Reißleine
  (identische Tool-Schleife / Schreibrate) NICHT maskieren;
- AC1: end-to-end über request_decision wird in-flight gesetzt;
- die In-Flight-Geduld endet sauber, sobald das Tool fertig ist (kein Dauer-Freibrief);
- Schwellen-Grenze (== Timeout → aktiv, > Timeout → hängt);
- Config-Red-Team (String/fehlend → 422).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.engine import liveness, watchdog as wd_mod
from app.engine.liveness import DEFAULTS, LIVENESS_ACTIVE, LIVENESS_HANGING, LivenessStore
from app.engine.manager import RUNNING, SessionManager
from app.engine.watchdog import WatchdogMonitor
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class Clock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class StubLivenessStore:
    def __init__(self, **over) -> None:
        self._c = {**DEFAULTS, **over}

    def config(self) -> dict:
        return dict(self._c)

    def snapshot(self) -> dict:
        return {**self._c, "source": "stub", "warning": None}


class StubWatchdogStore:
    """Watchdog-Limits mit kleinen Schwellen für deterministische Reißleinen-Tests."""

    def __init__(self, **over) -> None:
        self._l = {
            "enabled": True,
            "token_limit": 200_000,
            "token_window_seconds": 60,
            "max_idle_seconds": 180,
            "max_repeated_calls": 3,
            "write_limit": 2,
            "write_window_seconds": 60,
            **over,
        }

    def limits(self) -> dict:
        return dict(self._l)


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _app() -> object:
    return create_app(driver_factory=lambda: FakeDriver())


# --- AC5: Amok-Reißleine bleibt scharf trotz Fortschritts-Fütterung ---------


def test_loop_detection_not_masked_by_progress():
    """Identische Tool-Calls im Hammer-Takt lösen weiterhin die „repeat"-Reißleine aus —
    obwohl record() jetzt die Fortschritts-Uhr füttert (das darf die Loop-Metrik nicht
    aushebeln). Spiegelt den Manager-Ablauf: evaluate() VOR record() je Aufruf."""
    clk = Clock()
    mon = WatchdogMonitor(StubWatchdogStore(max_repeated_calls=3), clock=clk)
    tool, inp = "Bash", {"command": "ls"}
    assert mon.evaluate(tool, inp) is None
    mon.record(tool, inp)  # _repeat=1, + Fortschritt
    assert mon.evaluate(tool, inp) is None
    mon.record(tool, inp)  # _repeat=2, + Fortschritt
    alarm = mon.evaluate(tool, inp)  # prospective=3 → Reißleine
    assert alarm is not None and alarm.metric == "repeat"


def test_write_rate_not_masked_by_progress():
    """Schreibrate-Reißleine bleibt scharf: trotz record()-Fortschrittsfütterung löst das
    Überschreiten von write_limit den „writes"-Alarm aus (verschiedene Inputs → kein
    repeat-Alarm, isoliert die Schreibrate)."""
    clk = Clock()
    mon = WatchdogMonitor(StubWatchdogStore(write_limit=2), clock=clk)
    assert mon.evaluate("Write", {"file_path": "a.txt"}) is None
    mon.record("Write", {"file_path": "a.txt"})
    assert mon.evaluate("Write", {"file_path": "b.txt"}) is None
    mon.record("Write", {"file_path": "b.txt"})
    alarm = mon.evaluate("Write", {"file_path": "c.txt"})  # 3. Write > Limit 2
    assert alarm is not None and alarm.metric == "writes"


# --- AC1: end-to-end über request_decision wird in-flight gesetzt -----------


@pytest.mark.asyncio
async def test_request_decision_marks_in_flight():
    """Der reale Gate-Pfad (request_decision → record) markiert die Session in-flight."""
    mgr = SessionManager(driver_factory=lambda: FakeDriver())
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="hi", permission_mode="bypassPermissions"
    )
    assert rt.watchdog.tool_in_flight is False
    await rt.request_decision("dec-1", "Read", {"file_path": "x.txt"})
    assert rt.watchdog.tool_in_flight is True


# --- In-Flight-Geduld endet sauber + Grenzverhalten ------------------------


@pytest.mark.asyncio
async def test_in_flight_window_ends_after_tool_finishes(monkeypatch):
    """Red-Team: die hohe Geduld gilt NUR während das Tool läuft. Nach Tool-Ende
    (note_progress) greift wieder der Normaltimeout — kein Dauer-Freibrief."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(wd_mod.watchdog_store, clock=clk)
    rt.watchdog.record("Bash", {"command": "npm run build"})  # in-flight
    rt.watchdog.note_progress()  # Tool fertig, Modell produziert wieder → in-flight aus
    clk.advance(200)             # > 180 Normaltimeout, < 600
    rt.state.status = RUNNING
    assert rt.watchdog.tool_in_flight is False
    assert rt.derive_liveness() == LIVENESS_HANGING  # Normaltimeout, NICHT 600


@pytest.mark.asyncio
async def test_in_flight_threshold_boundary(monkeypatch):
    """Grenze: genau == In-Flight-Timeout → noch aktiv; knapp darüber → hängt."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(wd_mod.watchdog_store, clock=clk)
    rt.watchdog.record("Bash", {"command": "x"})
    rt.state.status = RUNNING
    clk.advance(600)
    assert rt.derive_liveness() == LIVENESS_ACTIVE   # == Timeout, nicht > → aktiv
    clk.advance(1)
    assert rt.derive_liveness() == LIVENESS_HANGING  # 601 > 600 → hängt


# --- Config-Red-Team -------------------------------------------------------


def test_put_liveness_rejects_string_tool_in_flight(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "progress_timeout_seconds": 180,
            "tool_in_flight_timeout_seconds": "ewig",  # kein int → 422
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 422


def test_put_liveness_requires_tool_in_flight(monkeypatch, tmp_path):
    """Vertrag: das Limit-Set ist vollständig anzugeben — fehlt das Feld → 422
    (konsistent mit den übrigen Limit-Feldern)."""
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "progress_timeout_seconds": 180,
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 422
