"""PROJ-27 — QA: Akzeptanzkriterien + Edge Cases + Red-Team.

Ergänzt die Entwickler-Tests (test_proj27_liveness.py) um:
- das KRITISCHE Finding BUG-1 (False-Positive „hängt" bei legitimer langer Aufgabe) —
  inzwischen durch **PROJ-32** behoben; die Tests verifizieren jetzt den Fix (Tool-
  Aktivität zählt als Fortschritt + In-Flight-Geduld);
- die ehemalige Wurzelursache (Tool-Aufzeichnung zählte nicht als Fortschritt) — jetzt
  als Regressions-Schutz, dass record() die Fortschritts-Uhr setzt;
- Red-Team rund um das Session-Limit (hängende = aktive Session belegt keinen 2. Slot);
- Settings-Validierung (negativ / Nicht-Ganzzahl → 422);
- Automatik global aus → Indikator + manueller Knopf bleiben.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine import liveness, watchdog
from app.engine.liveness import (
    DEFAULTS,
    LIVENESS_ACTIVE,
    LIVENESS_DEAD,
    LIVENESS_HANGING,
    LivenessStore,
)
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


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


def _app() -> object:
    return create_app(driver_factory=lambda: FakeDriver())


# --- BUG-1 (HIGH): False-Positive „hängt" bei legitimer langer Aufgabe ------


def test_bug1_fix_toolcall_counts_as_progress():
    """Fix von BUG-1 (PROJ-32): ein laufender Tool-Call (watchdog.record) setzt die
    Fortschritts-Uhr jetzt zurück und markiert „in-flight" — ein langer Tool-Call gilt
    damit nicht mehr nach `progress_timeout` als Stillstand."""
    clk = Clock()
    m = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    m.note_progress()  # letzter echter Fortschritt bei t=0
    clk.advance(100)
    m.record("Bash", {"command": "npm run build"})  # Tool-Aktivität (manager.py:502)
    assert m.seconds_since_progress() == 0  # PROJ-32: record() setzt die Uhr zurück
    assert m.tool_in_flight is True


@pytest.mark.asyncio
async def test_bug1_long_toolcall_should_stay_active(monkeypatch):
    """Spec (Beschreibung Zeile 23 + Edge Case Zeile 37): eine legitim arbeitende lange
    Aufgabe darf NICHT als „hängt" gewertet werden. Repro: Claude startet einen langen
    Tool-Call (z. B. `npm run build`); das Tool wird aufgezeichnet, produziert aber
    minutenlang keinen Assistenten-Output. Nach PROJ-32: bleibt „aktiv", solange die
    In-Flight-Geduld (600 s) nicht überschritten ist."""
    monkeypatch.setattr(
        liveness, "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, tool_in_flight_timeout_seconds=600),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.note_progress()
    rt.watchdog.record("Bash", {"command": "npm run build"})  # langer Tool-Call beginnt
    clk.advance(200)  # Tool läuft > progress_timeout (180), aber < In-Flight-Geduld (600)
    rt.state.status = RUNNING
    assert rt.derive_liveness(180) == LIVENESS_ACTIVE


# --- Red-Team: Session-Limit (PROJ-14) -------------------------------------


@pytest.mark.asyncio
async def test_reanimate_hanging_alive_session_keeps_one_slot(monkeypatch):
    """Eine hängende Session ist AKTIV (Slot belegt). Ihre Reanimierung darf weder am
    Limit scheitern (kein 2. Slot) noch einen zweiten Slot belegen — sonst würde der
    Limit-Check entweder fälschlich blocken oder das Limit umgangen."""
    monkeypatch.setattr(settings, "max_parallel_sessions", 1)
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.note_progress()
    clk.advance(300)
    rt.state.status = RUNNING  # hängt (alive + idle) → belegt bereits den einzigen Slot
    assert rt.derive_liveness(180) == LIVENESS_HANGING
    assert mgr.active_count() == 1
    # Reanimierung am Limit muss durchgehen (kein 429) und KEINEN neuen Slot belegen.
    result = await mgr.reanimate(rt.state.session_id)
    assert result.state.status == RUNNING
    assert mgr.active_count() == 1


# --- Automatik global aus → Indikator + manueller Knopf bleiben -------------


@pytest.mark.asyncio
async def test_auto_off_keeps_indicator_and_manual_button(monkeypatch):
    """enabled_auto_reanimation=false: KEINE Auto-Reanimierung, aber der Zustand wird
    weiter abgeleitet (Indikator bleibt) und der manuelle Knopf reanimiert weiterhin."""
    monkeypatch.setattr(
        liveness,
        "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, enabled_auto_reanimation=False),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.note_progress()
    clk.advance(300)
    rt.state.status = RUNNING
    await mgr.evaluate_liveness_once()
    assert rt.liveness.auto_attempts == 0  # Automatik aus → kein Auto-Versuch
    assert rt.derive_liveness(180) == LIVENESS_HANGING  # Indikator zeigt weiterhin „hängt"
    # Manueller Knopf funktioniert trotz abgeschalteter Automatik.
    await mgr.reanimate(rt.state.session_id)
    assert rt.liveness.last_result == "läuft_wieder"
    assert rt.derive_liveness(180) == LIVENESS_ACTIVE


# --- API / Settings-Validierung (Red-Team) ---------------------------------


def test_reanimate_failed_resume_returns_503(monkeypatch):
    """Schlägt der Resume fehl (CLI/Treiber wirft), liefert der Endpunkt 503 mit
    deutscher Meldung statt 500/stillem Fehler."""

    class BoomDriver(FakeDriver):
        async def start(self, spec, on_event):  # type: ignore[override]
            raise RuntimeError("claude-Treiber explodiert")

    # Erste Session normal erstellen, dann den Treiber für den Resume „vergiften".
    app = create_app(driver_factory=lambda: FakeDriver())
    client = TestClient(app)
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi"}
    ).json()["session_id"]
    client.post(f"/sessions/{sid}/stop")  # → tot
    # Manager-Treiberfabrik auf den krachenden Treiber umstellen (nur der Resume nutzt sie).
    app.state.manager._driver_factory = lambda: BoomDriver()
    resp = client.post(f"/sessions/{sid}/reanimate")
    assert resp.status_code == 503
    assert "fehlgeschlagen" in resp.json()["detail"].lower()


def test_put_liveness_negative_is_422(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "lv.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "progress_timeout_seconds": -5,  # gt=0 → 422
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 422


def test_put_liveness_non_integer_is_422(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "lv.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "progress_timeout_seconds": 180,
            "poll_interval_seconds": 5,
            "max_auto_attempts": "viele",  # keine Ganzzahl → 422
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 422


def test_reanimate_unknown_is_404_not_500():
    client = TestClient(_app())
    resp = client.post("/sessions/00000000-0000-0000-0000-000000000000/reanimate")
    assert resp.status_code == 404


# --- Sanity: tote/verwaiste Session bleibt tot (kein Auto-Sturm) ------------


@pytest.mark.asyncio
async def test_done_session_is_dead_and_not_auto_reanimated(monkeypatch):
    monkeypatch.setattr(
        liveness,
        "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, enabled_auto_reanimation=True),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    await mgr.stop(rt.state.session_id)  # → DONE
    await mgr.evaluate_liveness_once()
    assert rt.derive_liveness(180) == LIVENESS_DEAD
    assert rt.liveness.auto_attempts == 0  # DONE ist kein Hänger → kein Auto-Versuch
