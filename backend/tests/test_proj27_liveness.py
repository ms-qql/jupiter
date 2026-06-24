"""PROJ-27 — Verifizierter Liveness-Indikator + Reanimieren hängender Sessions.

Deterministisch über injizierte Uhren (Clock) + FakeDriver — ohne echte Claude-Session.
Geprüft werden: der LivenessMonitor (Auto-Versuche/Backoff), der LivenessStore (YAML/
Live-Reload/Fallback), die Zustands-Ableitung ``derive_liveness`` (aktiv/hängt/tot inkl.
legitimer Wartestellung), der Hintergrund-Auswerter ``evaluate_liveness_once`` (Auto-
Reanimierung, Abschaltung, Restart-Orphan-Schutz) und die API (``/reanimate`` +
``/settings/liveness``).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine import liveness, watchdog
from app.engine.base import DeadDriver
from app.engine.liveness import (
    DEFAULTS,
    LIVENESS_ACTIVE,
    LIVENESS_DEAD,
    LIVENESS_HANGING,
    LivenessMonitor,
    LivenessStore,
)
from app.engine.manager import (
    AWAITING_APPROVAL,
    DONE,
    ERROR,
    RUNNING,
    WAITING,
    SessionManager,
)
from app.engine.watchdog import WatchdogMonitor
from app.main import create_app

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


def _app() -> object:
    return create_app(driver_factory=lambda: FakeDriver())


def _hang(rt, idle: float = 1000.0) -> Clock:
    """Versetzt ein Runtime in einen echten Hänger: RUNNING + Fortschritts-Uhr abgelaufen."""
    clk = Clock()
    rt.watchdog = WatchdogMonitor(watchdog.watchdog_store, clock=clk)
    rt.watchdog.note_progress()
    clk.advance(idle)
    rt.state.status = RUNNING
    return clk


# --- LivenessMonitor: Auto-Versuche, Backoff, Reset ------------------------


def test_monitor_attempts_backoff_and_budget():
    clk = Clock()
    m = LivenessMonitor(clock=clk)
    # Erster Versuch sofort erlaubt (kein initialer Backoff).
    assert m.may_auto_attempt(2) is True
    m.record_attempt(30, success=True)
    assert m.auto_attempts == 1
    assert m.last_result == "läuft_wieder"
    # Backoff-Gate: vor Ablauf kein weiterer Versuch.
    assert m.may_auto_attempt(2) is False
    clk.advance(30)
    assert m.may_auto_attempt(2) is True
    m.record_attempt(30, success=False)
    assert m.auto_attempts == 2
    assert m.last_result == "fehlgeschlagen"
    # Budget erschöpft — auch nach beliebigem Backoff-Ablauf kein weiterer Auto-Versuch.
    clk.advance(999)
    assert m.may_auto_attempt(2) is False


def test_monitor_reset_keeps_last_result():
    clk = Clock()
    m = LivenessMonitor(clock=clk)
    m.record_attempt(30, success=False)
    m.reset()
    assert m.auto_attempts == 0
    assert m.may_auto_attempt(2) is True  # frisches Budget
    assert m.last_result == "fehlgeschlagen"  # UI-Rückmeldung bleibt sichtbar


def test_monitor_backoff_zero_allows_immediate_retry():
    clk = Clock()
    m = LivenessMonitor(clock=clk)
    m.record_attempt(0, success=False)
    assert m.may_auto_attempt(2) is True  # backoff 0 → sofort wieder erlaubt


# --- LivenessStore: Datei/Live-Reload/Fallback -----------------------------


def test_store_defaults_without_file(tmp_path):
    store = LivenessStore(str(tmp_path / "fehlt.yaml"))
    assert store.config() == DEFAULTS
    assert store.snapshot()["source"] == "default"


def test_store_save_validates_and_live_reload(tmp_path):
    path = str(tmp_path / "liveness.yaml")
    store = LivenessStore(path)
    snap = store.save(
        {
            "enabled_auto_reanimation": False,
            "progress_timeout_seconds": 60,
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        }
    )
    assert snap["progress_timeout_seconds"] == 60
    assert snap["backoff_seconds"] == 0  # 0 ist erlaubt (kein Backoff)
    assert snap["source"] == path
    assert store.config()["enabled_auto_reanimation"] is False


def test_store_save_rejects_nonpositive_timeout(tmp_path):
    store = LivenessStore(str(tmp_path / "liveness.yaml"))
    with pytest.raises(ValueError):
        store.save(
            {
                "progress_timeout_seconds": 0,  # muss > 0
                "poll_interval_seconds": 5,
                "max_auto_attempts": 1,
                "backoff_seconds": 0,
            }
        )


def test_store_corrupt_file_falls_back(tmp_path):
    path = tmp_path / "liveness.yaml"
    path.write_text("- nicht\n- ein\n- objekt\n", encoding="utf-8")  # Liste statt Mapping
    store = LivenessStore(str(path))
    assert store.config() == DEFAULTS
    assert store.snapshot()["warning"] is not None


# --- derive_liveness: aktiv / hängt / tot ----------------------------------


@pytest.mark.asyncio
async def test_derive_waiting_is_active():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    assert rt.state.status == WAITING
    assert rt.derive_liveness(180) == LIVENESS_ACTIVE


@pytest.mark.asyncio
async def test_derive_awaiting_approval_is_active_despite_idle():
    """Legitime Wartestellung (Decision Card / Watchdog-Pause) ≠ Hänger — auch wenn die
    Fortschritts-Uhr längst abgelaufen wäre."""
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _hang(rt)  # Uhr abgelaufen ...
    rt.state.status = AWAITING_APPROVAL  # ... aber legitim wartend
    assert rt.derive_liveness(180) == LIVENESS_ACTIVE


@pytest.mark.asyncio
async def test_derive_running_without_progress_is_hanging():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _hang(rt, idle=200)
    assert rt.derive_liveness(180) == LIVENESS_HANGING


@pytest.mark.asyncio
async def test_derive_done_is_dead():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    await mgr.stop(rt.state.session_id)
    assert rt.state.status == DONE
    assert rt.derive_liveness(180) == LIVENESS_DEAD


@pytest.mark.asyncio
async def test_to_read_exposes_liveness_fields():
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    data = rt.to_read()
    assert data["liveness"] == LIVENESS_ACTIVE
    assert data["liveness_auto_attempts"] == 0
    assert data["liveness_last_result"] is None


# --- evaluate_liveness_once: Hintergrund-Auswerter -------------------------


@pytest.mark.asyncio
async def test_auto_reanimation_revives_hanging(monkeypatch):
    monkeypatch.setattr(
        liveness,
        "liveness_store",
        StubLivenessStore(
            progress_timeout_seconds=180,
            max_auto_attempts=2,
            backoff_seconds=0,
            enabled_auto_reanimation=True,
        ),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _hang(rt)
    old_driver = rt.driver
    await mgr.evaluate_liveness_once()
    assert rt.liveness.auto_attempts == 1
    assert rt.liveness.last_result == "läuft_wieder"
    assert rt.driver is not old_driver  # frischer Treiber via --resume
    assert rt.derive_liveness(180) == LIVENESS_ACTIVE  # Resume = Fortschritt → aktiv


@pytest.mark.asyncio
async def test_auto_reanimation_disabled_no_attempt(monkeypatch):
    monkeypatch.setattr(
        liveness,
        "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, enabled_auto_reanimation=False),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    _hang(rt)
    await mgr.evaluate_liveness_once()
    assert rt.liveness.auto_attempts == 0  # global aus → kein Auto-Versuch
    assert rt.derive_liveness(180) == LIVENESS_HANGING  # Indikator zeigt trotzdem „hängt"


@pytest.mark.asyncio
async def test_restart_orphan_not_auto_reanimated(monkeypatch):
    """Verwaiste Session nach Backend-Neustart (DeadDriver/ERROR) → „tot", KEIN Auto-
    Versuch (sonst Reanimations-Sturm nach Restart)."""
    monkeypatch.setattr(
        liveness,
        "liveness_store",
        StubLivenessStore(progress_timeout_seconds=180, enabled_auto_reanimation=True),
    )
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="hi")
    rt.driver = DeadDriver(pid=None)
    rt.state.status = ERROR
    await mgr.evaluate_liveness_once()
    assert rt.liveness.auto_attempts == 0
    assert rt.derive_liveness(180) == LIVENESS_DEAD


# --- API: POST /sessions/{id}/reanimate ------------------------------------


def test_reanimate_unknown_session_404():
    client = TestClient(_app())
    assert client.post("/sessions/does-not-exist/reanimate").status_code == 404


def test_reanimate_alive_session_409():
    client = TestClient(_app())
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi"}
    ).json()["session_id"]
    # Frisch (WAITING) = aktiv → keine Reanimierung nötig.
    assert client.post(f"/sessions/{sid}/reanimate").status_code == 409


def test_reanimate_dead_session_succeeds():
    client = TestClient(_app())
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi"}
    ).json()["session_id"]
    client.post(f"/sessions/{sid}/stop")  # → DONE/tot
    resp = client.post(f"/sessions/{sid}/reanimate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["liveness"] == LIVENESS_ACTIVE
    assert body["liveness_last_result"] == "läuft_wieder"


def test_reanimate_respects_session_limit_429(monkeypatch):
    monkeypatch.setattr(settings, "max_parallel_sessions", 1)
    client = TestClient(_app())
    a = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi"}
    ).json()["session_id"]
    client.post(f"/sessions/{a}/stop")  # A terminal (Slot frei)
    b = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "hi"}
    ).json()["session_id"]  # B aktiv → Slot belegt (Limit 1)
    assert b  # B wurde erstellt
    # A reanimieren würde einen NEUEN Slot belegen → Limit greift (kein Bypass).
    assert client.post(f"/sessions/{a}/reanimate").status_code == 429


# --- API: GET/PUT /settings/liveness ---------------------------------------


def test_get_liveness_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    resp = client.get("/settings/liveness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["progress_timeout_seconds"] == 180
    assert body["enabled_auto_reanimation"] is True
    assert body["source"] == "default"


def test_put_liveness_live(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "enabled_auto_reanimation": False,
            "progress_timeout_seconds": 60,
            "tool_in_flight_timeout_seconds": 500,  # PROJ-32
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["progress_timeout_seconds"] == 60
    assert resp.json()["tool_in_flight_timeout_seconds"] == 500  # PROJ-32
    assert liveness.liveness_store.config()["enabled_auto_reanimation"] is False


def test_put_liveness_invalid_422(monkeypatch, tmp_path):
    monkeypatch.setattr(liveness, "liveness_store", LivenessStore(str(tmp_path / "liveness.yaml")))
    client = TestClient(_app())
    resp = client.put(
        "/settings/liveness",
        json={
            "progress_timeout_seconds": 0,  # gt=0 → 422
            "poll_interval_seconds": 5,
            "max_auto_attempts": 1,
            "backoff_seconds": 0,
        },
    )
    assert resp.status_code == 422
