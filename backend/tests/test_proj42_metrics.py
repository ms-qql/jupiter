"""PROJ-42 — VPS-Admin Metrik-Backend.

Deckt die reine Ampel-Logik (Schwellen + „schlechtester Wert"), den Snapshot-Aufbau
(psutil liest den echten Host — read-only, unkritisch), die systemd-Status-Abbildung
(gemockt) und die beiden Endpunkte via FastAPI-TestClient ab.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.metrics import MetricsService, _status_for, _worst
from app.main import create_app
from app.schemas.metrics import MetricsSnapshot, MetricsStatus

from .fakes import FakeDriver


# --- Reine Logik: Schwellen + schlechtester Wert ------------------------------

@pytest.mark.parametrize(
    "pct,expected",
    [
        (0.0, "green"),
        (74.9, "green"),
        (75.0, "amber"),   # WARN-Grenze inklusiv
        (90.0, "amber"),   # CRIT-Grenze: 90 ist noch gelb
        (90.1, "red"),
        (100.0, "red"),
    ],
)
def test_status_for_schwellen(pct, expected):
    assert _status_for(pct) == expected


def test_worst_nimmt_hoechsten_rang():
    assert _worst(["green", "green"]) == "green"
    assert _worst(["green", "amber", "green"]) == "amber"
    assert _worst(["amber", "red", "green"]) == "red"
    assert _worst([]) == "green"


# --- Snapshot-Aufbau ----------------------------------------------------------

@pytest.fixture
def _no_services(monkeypatch):
    """systemctl im Test deterministisch ausschalten (keine echten Units abfragen)."""
    monkeypatch.setattr(settings, "metrics_services", [])


async def test_tick_baut_validen_snapshot(_no_services):
    svc = MetricsService()
    await svc.tick()
    snap = svc.snapshot()
    # Validiert zugleich das Response-Schema.
    model = MetricsSnapshot.model_validate(snap)
    assert model.overall_status in ("green", "amber", "red")
    assert model.cpu.cores >= 1
    assert model.disk.total_gb > 0
    assert model.services == []


async def test_history_waechst_und_ist_gedeckelt(monkeypatch, _no_services):
    monkeypatch.setattr(settings, "metrics_history_points", 3)
    svc = MetricsService()
    for _ in range(5):
        await svc.tick()
    snap = svc.snapshot()
    # maxlen greift → nie mehr als 3 Punkte.
    assert len(snap["cpu"]["history"]) == 3
    assert len(snap["load"]["history"]) == 3


async def test_netz_rate_ab_zweitem_tick(_no_services):
    svc = MetricsService()
    await svc.tick()  # erster Tick: noch keine Vergleichsbasis
    await svc.tick()
    net = svc.snapshot()["net"]
    assert net["rx_bytes_per_sec"] >= 0.0
    assert net["tx_bytes_per_sec"] >= 0.0


def test_snapshot_vor_erstem_tick_ist_neutral(_no_services):
    """Leer-Stand muss schema-konform sein (Route liefert nie 500 vor dem 1. Tick)."""
    svc = MetricsService()
    model = MetricsSnapshot.model_validate(svc.snapshot())
    assert model.overall_status == "green"
    assert model.uptime_seconds == 0.0


# --- systemd-Status-Abbildung (gemockt) --------------------------------------

async def test_service_failed_macht_gesamt_rot(monkeypatch):
    monkeypatch.setattr(settings, "metrics_services", ["svc-a", "svc-b"])

    async def fake_is_active(unit):
        return "failed" if unit == "svc-b" else "active"

    monkeypatch.setattr(MetricsService, "_systemctl_is_active", staticmethod(fake_is_active))
    svc = MetricsService()
    await svc.tick()
    snap = svc.snapshot()
    names = {s["name"]: s["status"] for s in snap["services"]}
    assert names == {"svc-a": "active", "svc-b": "failed"}
    assert snap["overall_status"] == "red"


async def test_service_unknown_faerbt_ampel_nicht(monkeypatch):
    monkeypatch.setattr(settings, "metrics_services", ["weg"])

    async def fake_is_active(unit):
        return "unknown"

    monkeypatch.setattr(MetricsService, "_systemctl_is_active", staticmethod(fake_is_active))
    svc = MetricsService()
    await svc.tick()
    snap = svc.snapshot()
    # unknown darf die Gesamt-Ampel nicht rot/gelb färben (nur Host zählt).
    assert snap["services"][0]["status"] == "unknown"
    assert snap["overall_status"] in ("green", "amber", "red")


async def test_service_inactive_macht_gesamt_mindestens_amber(monkeypatch):
    """Tech-Design D: ein erwarteter, aber inaktiver Dienst → mindestens gelb."""
    monkeypatch.setattr(settings, "metrics_services", ["ruht"])

    async def fake_is_active(unit):
        return "inactive"

    monkeypatch.setattr(MetricsService, "_systemctl_is_active", staticmethod(fake_is_active))
    svc = MetricsService()
    await svc.tick()
    snap = svc.snapshot()
    assert snap["services"][0]["status"] == "inactive"
    # Host ist im Test gewöhnlich grün → der inaktive Dienst hebt auf gelb.
    assert snap["overall_status"] in ("amber", "red")


class _FakeProc:
    """Minimaler Stub für asyncio-Subprozesse (deterministisch, kein echtes systemctl)."""

    def __init__(self, out: bytes):
        self._out = out
        self.returncode = 0

    async def communicate(self):
        return self._out, b""


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"active\n", "active"),
        (b"inactive\n", "inactive"),
        (b"failed\n", "failed"),
        (b"activating\n", "active"),     # Übergang → nächstliegender stabiler Zustand
        (b"reloading\n", "active"),
        (b"deactivating\n", "inactive"),
        (b"unknown\n", "unknown"),
        (b"", "unknown"),                # leere/unerwartete Ausgabe → unknown, nie Crash
    ],
)
async def test_systemctl_is_active_mapping(monkeypatch, raw, expected):
    async def fake_exec(*args, **kwargs):
        return _FakeProc(raw)

    monkeypatch.setattr(
        "app.engine.metrics.asyncio.create_subprocess_exec", fake_exec
    )
    assert await MetricsService._systemctl_is_active("egal") == expected


async def test_systemctl_timeout_degradiert_zu_unknown(monkeypatch):
    """Hängt `systemctl`, darf der Tick nie blockieren — Timeout → unknown."""

    class _HangProc:
        returncode = None

        async def communicate(self):
            raise AssertionError("communicate sollte vom Timeout abgefangen werden")

        def kill(self):
            self.returncode = -9

    async def fake_exec(*args, **kwargs):
        return _HangProc()

    async def fake_wait_for(coro, timeout):
        coro.close()  # die echte communicate()-Coroutine sauber verwerfen
        raise asyncio.TimeoutError

    monkeypatch.setattr("app.engine.metrics.asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr("app.engine.metrics.asyncio.wait_for", fake_wait_for)
    assert await MetricsService._systemctl_is_active("egal") == "unknown"


# --- Endpunkte ----------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "metrics_services", [])
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


def test_current_endpoint(client):
    res = client.get("/metrics/current")
    assert res.status_code == 200
    MetricsSnapshot.model_validate(res.json())  # Schema-konform


def test_status_endpoint(client):
    res = client.get("/metrics/status")
    assert res.status_code == 200
    model = MetricsStatus.model_validate(res.json())
    assert model.status in ("green", "amber", "red")
