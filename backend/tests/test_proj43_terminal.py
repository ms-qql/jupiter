"""PROJ-43 — VPS-Admin Terminal-Backend.

Deckt die reine Erreichbarkeits-Auskunft ``GET /terminal/info`` ab:
- ``terminal_url`` leer → ``enabled=false`` (Feature aus, kein Probe).
- konfiguriert + erreichbar / nicht erreichbar (TCP-Probe gemockt + real).
- URL kommt ausschließlich aus der Config (nie vom Client) und wird getrimmt.

Kein JWT/DB (Jupiter-Override, single-user hinter Tailscale). Sicherheit =
fester Host/Port aus der Config, kurzer Timeout, Fehler abgefangen.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.routes import terminal as terminal_route
from app.schemas.terminal import TerminalInfo

from .fakes import FakeDriver


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


# --- Endpoint: Konfigurations-/Erreichbarkeits-Matrix ------------------------

def test_info_disabled_when_url_empty(client, monkeypatch):
    """Leere URL → enabled=false, kein Probe-Versuch (sauberer „nicht konfiguriert")."""
    monkeypatch.setattr(settings, "terminal_url", "")

    async def _must_not_probe(*args, **kwargs):  # pragma: no cover - darf nicht laufen
        raise AssertionError("Probe darf bei deaktiviertem Terminal nicht laufen")

    monkeypatch.setattr(terminal_route, "_probe_reachable", _must_not_probe)

    resp = client.get("/terminal/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"enabled": False, "url": None, "reachable": False}
    # Response-Schema validieren.
    TerminalInfo.model_validate(body)


def test_info_enabled_and_reachable(client, monkeypatch):
    monkeypatch.setattr(settings, "terminal_url", "https://jupiter.auxevo.tech/vps-terminal/")

    async def _reachable(*args, **kwargs):
        return True

    monkeypatch.setattr(terminal_route, "_probe_reachable", _reachable)

    body = client.get("/terminal/info").json()
    assert body["enabled"] is True
    assert body["reachable"] is True
    assert body["url"] == "https://jupiter.auxevo.tech/vps-terminal/"


def test_info_enabled_but_unreachable(client, monkeypatch):
    """Dienst gestoppt → enabled bleibt true (URL bekannt), nur reachable=false."""
    monkeypatch.setattr(settings, "terminal_url", "https://jupiter.auxevo.tech/vps-terminal/")

    async def _unreachable(*args, **kwargs):
        return False

    monkeypatch.setattr(terminal_route, "_probe_reachable", _unreachable)

    body = client.get("/terminal/info").json()
    assert body["enabled"] is True
    assert body["reachable"] is False
    assert body["url"] == "https://jupiter.auxevo.tech/vps-terminal/"


def test_url_is_trimmed(client, monkeypatch):
    """Versehentliche Whitespace-URL wird getrimmt (und gilt als konfiguriert)."""
    monkeypatch.setattr(settings, "terminal_url", "  https://x.test/t/  ")

    async def _reachable(*args, **kwargs):
        return True

    monkeypatch.setattr(terminal_route, "_probe_reachable", _reachable)

    body = client.get("/terminal/info").json()
    assert body["enabled"] is True
    assert body["url"] == "https://x.test/t/"


def test_whitespace_only_url_counts_as_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "terminal_url", "   ")
    body = client.get("/terminal/info").json()
    assert body == {"enabled": False, "url": None, "reachable": False}


# --- TCP-Probe (real, gegen einen ephemeren Listener) ------------------------

async def test_probe_true_against_live_listener():
    """Lauscht jemand auf dem Port → reachable=true."""
    async def _handle(reader, writer):
        writer.close()

    server = await asyncio.start_server(_handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        assert await terminal_route._probe_reachable("127.0.0.1", port, 1.5) is True
    finally:
        server.close()
        await server.wait_closed()


async def test_probe_false_on_refused_port():
    """Niemand lauscht (Server geschlossen) → reachable=false, keine Exception."""
    server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    server.close()
    await server.wait_closed()
    assert await terminal_route._probe_reachable("127.0.0.1", port, 1.0) is False


async def test_probe_false_on_zero_port():
    """Unkonfigurierter Port (0/negativ) → false ohne Socket-Versuch."""
    assert await terminal_route._probe_reachable("127.0.0.1", 0, 1.0) is False


async def test_probe_false_on_timeout(monkeypatch):
    """Hängt der Connect, darf der Request nie blockieren — Timeout → false."""
    async def _hang(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(terminal_route.asyncio, "open_connection", _hang)
    assert await terminal_route._probe_reachable("127.0.0.1", 7681, 0.05) is False
