"""PROJ-16 — Amok-Watchdog: Monitor-Metriken, Store (YAML/live/Fallback), Settings-API
und die Pause-am-Tool-Gate-Integration (Watchdog sticht auto-allow).

Deterministisch über einen injizierten Clock + count-basierte Schleifen-Erkennung —
ohne echte Claude-Session (FakeDriver).
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from app.engine import watchdog
from app.engine.manager import AWAITING_APPROVAL, RUNNING, SessionManager
from app.engine.watchdog import DEFAULTS, WatchdogMonitor, WatchdogStore
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


class Clock:
    """Steuerbare monotone Uhr für deterministische Fenster-Tests."""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class StubStore:
    """Minimaler Limits-Provider (nur ``limits()``) mit überschreibbaren Werten."""

    def __init__(self, **over) -> None:
        self._l = {**DEFAULTS, **over}

    def limits(self) -> dict:
        return dict(self._l)


# --- Monitor: vier Limits + Cooldown/Reset ---------------------------------


def test_repeat_is_loop_distinct_is_iteration():
    clk = Clock()
    m = WatchdogMonitor(StubStore(max_repeated_calls=3), clock=clk)
    # 2x identisch → noch kein Alarm, beide aufgezeichnet.
    assert m.evaluate("Read", {"file_path": "a"}) is None
    m.record("Read", {"file_path": "a"})
    assert m.evaluate("Read", {"file_path": "a"}) is None
    m.record("Read", {"file_path": "a"})
    # 3. identischer → Schleife.
    alarm = m.evaluate("Read", {"file_path": "a"})
    assert alarm is not None and alarm.metric == "repeat"
    # Unterschiedlicher Input bricht die Serie (legitime Iteration).
    assert m.evaluate("Read", {"file_path": "b"}) is None


def test_token_window_alarm_and_expiry():
    clk = Clock()
    m = WatchdogMonitor(StubStore(token_limit=100, token_window_seconds=10), clock=clk)
    m.feed_usage(60)            # t=0
    clk.advance(1)
    m.feed_usage(60)            # t=1 → Fenstersumme 120 > 100
    assert m.evaluate("Read", {}).metric == "tokens"
    clk.advance(10)             # t=11 → der t=0-Eintrag fällt aus dem 10-s-Fenster
    assert m.evaluate("Read", {}) is None


def test_idle_alarm():
    clk = Clock()
    m = WatchdogMonitor(StubStore(max_idle_seconds=5), clock=clk)
    clk.advance(6)              # 6 s ohne Fortschritt
    assert m.evaluate("Read", {}).metric == "idle"
    m.note_progress()          # Fortschritt → Uhr zurück
    assert m.evaluate("Read", {}) is None


def test_write_rate_alarm_only_counts_writes():
    clk = Clock()
    m = WatchdogMonitor(StubStore(write_limit=2, write_window_seconds=10), clock=clk)
    m.record("Write", {"file_path": "a"})
    m.record("Write", {"file_path": "b"})
    # prospektiv 3. Write > Limit 2.
    assert m.evaluate("Write", {"file_path": "c"}).metric == "writes"
    # Lese-Tools zählen nicht gegen die Schreibrate.
    assert m.evaluate("Read", {"file_path": "c"}) is None


def test_reset_clears_metric_and_sets_cooldown():
    clk = Clock()
    m = WatchdogMonitor(StubStore(max_repeated_calls=2), clock=clk)
    m.record("Bash", {"command": "x"})
    assert m.evaluate("Bash", {"command": "x"}).metric == "repeat"
    m.reset("repeat")
    # Cooldown unterdrückt sofortiges Re-Trigger (auch eines anderen Limits).
    assert m.evaluate("Bash", {"command": "x"}) is None
    clk.advance(watchdog.COOLDOWN_SECONDS + 1)
    # Nach Cooldown ist der Zähler zurückgesetzt → eine einzelne Wiederholung reißt nicht.
    assert m.evaluate("Bash", {"command": "x"}) is None


def test_disabled_never_alarms():
    m = WatchdogMonitor(StubStore(enabled=False, max_repeated_calls=1), clock=Clock())
    m.record("Bash", {"command": "x"})
    assert m.evaluate("Bash", {"command": "x"}) is None


# --- Store: Defaults, Live-Reload, Defekt-Fallback, Validierung ------------


def test_store_defaults_without_file(tmp_path):
    s = WatchdogStore(str(tmp_path / "wd.yaml"))
    assert s.limits() == DEFAULTS
    assert s.snapshot()["source"] == "default"


def test_store_save_and_live_reload(tmp_path):
    s = WatchdogStore(str(tmp_path / "wd.yaml"))
    snap = s.save({**DEFAULTS, "max_repeated_calls": 7})
    assert snap["max_repeated_calls"] == 7
    assert snap["source"].endswith("wd.yaml")
    # Frischer Store auf dieselbe Datei liest den gespeicherten Wert.
    assert WatchdogStore(str(tmp_path / "wd.yaml")).limits()["max_repeated_calls"] == 7


def test_store_broken_file_falls_back(tmp_path):
    p = tmp_path / "wd.yaml"
    p.write_text("token_limit: [unbalanced", encoding="utf-8")
    s = WatchdogStore(str(p))
    assert s.limits() == DEFAULTS
    assert s.snapshot()["warning"] is not None


def test_store_missing_keys_merge_defaults(tmp_path):
    p = tmp_path / "wd.yaml"
    p.write_text("write_limit: 99\n", encoding="utf-8")
    lim = WatchdogStore(str(p)).limits()
    assert lim["write_limit"] == 99 and lim["token_limit"] == DEFAULTS["token_limit"]


def test_store_save_rejects_nonpositive(tmp_path):
    s = WatchdogStore(str(tmp_path / "wd.yaml"))
    with pytest.raises(ValueError):
        s.save({**DEFAULTS, "token_limit": 0})


# --- Settings-API ----------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "watchdog_store", WatchdogStore(str(tmp_path / "wd.yaml")))
    app = create_app(driver_factory=lambda: FakeDriver())
    return TestClient(app)


def test_get_watchdog_returns_defaults(client):
    r = client.get("/settings/watchdog")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True and body["max_repeated_calls"] == DEFAULTS["max_repeated_calls"]
    assert body["source"] == "default"


def test_put_watchdog_live(client):
    payload = {**DEFAULTS, "write_limit": 12}
    r = client.put("/settings/watchdog", json=payload)
    assert r.status_code == 200 and r.json()["write_limit"] == 12
    assert client.get("/settings/watchdog").json()["write_limit"] == 12


def test_put_watchdog_rejects_nonpositive(client):
    r = client.put("/settings/watchdog", json={**DEFAULTS, "token_window_seconds": 0})
    assert r.status_code == 422  # Pydantic gt=0


# --- Integration: Pause am Tool-Gate (sticht auto-allow) -------------------


def _mgr() -> SessionManager:
    return SessionManager(driver_factory=lambda: FakeDriver())


@pytest.mark.asyncio
async def test_watchdog_pauses_on_loop_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "watchdog_store", StubStore(max_repeated_calls=3))
    mgr = _mgr()
    rt = await mgr.create(project_path=PROJECT, initial_prompt="Hi", model="haiku")
    # Read ist auto-allow → ohne Watchdog liefe es durch; 3. identischer pausiert.
    assert (await mgr.request_decision(rt.state.session_id, "t1", "Read", {"file_path": "x"})).behavior == "allow"
    assert (await mgr.request_decision(rt.state.session_id, "t2", "Read", {"file_path": "x"})).behavior == "allow"
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "t3", "Read", {"file_path": "x"})
    )
    await asyncio.sleep(0)
    assert rt.state.status == AWAITING_APPROVAL
    card = rt.pending["t3"]
    assert card.card_type == "watchdog_pause"
    assert "Schleife" in card.triggering_rule
    # Fortsetzen → Aktion läuft, Session kehrt nach running zurück.
    mgr.resolve_decision(rt.state.session_id, "t3", approve=True)
    out = await task
    assert out.behavior == "allow"
    assert rt.state.status == RUNNING


@pytest.mark.asyncio
async def test_watchdog_overrides_bypass_auto_allow(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "watchdog_store", StubStore(max_repeated_calls=2))
    mgr = _mgr()
    rt = await mgr.create(
        project_path=PROJECT, initial_prompt="Hi", model="haiku",
        permission_mode="bypassPermissions",
    )
    # Im Bypass läuft Bash normal als auto-allow durch …
    assert (await mgr.request_decision(rt.state.session_id, "b1", "Bash", {"command": "ls"})).behavior == "allow"
    # … aber der 2. identische Aufruf wird vom Watchdog TROTZ Bypass pausiert.
    task = asyncio.create_task(
        mgr.request_decision(rt.state.session_id, "b2", "Bash", {"command": "ls"})
    )
    await asyncio.sleep(0)
    assert rt.state.status == AWAITING_APPROVAL
    assert rt.pending["b2"].card_type == "watchdog_pause"
    mgr.resolve_decision(rt.state.session_id, "b2", approve=True)
    assert (await task).behavior == "allow"
