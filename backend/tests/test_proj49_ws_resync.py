"""PROJ-49 — WebSocket-Stabilität + Event-Replay bei Reconnect.

Deckt die testbaren Akzeptanzkriterien des Delivery-Layers (Backend↔Browser):
- **Replay/Resync:** der Connect-Snapshot trägt den Vollzustand inkl. Transkript,
  sodass ein (Re-)Connect den aktuellen Stand verlustfrei nachlädt.
- **Idempotenz:** jeder erneute Connect liefert denselben Voll-Snapshot (keine
  „leere" Subscription nach Flapping).
- **Frontend-Invariante:** Live-`state`-Broadcasts (z. B. Schwellen-Änderung)
  tragen KEIN `transcript` — nur der Connect-Snapshot. Darauf beruht das
  `liveText`-Reset im Client; ein versehentliches `transcript` in einem Live-Frame
  würde den seit-Snapshot-Strom fälschlich leeren.
- **Keepalive:** Ping in der stillen Phase (separat in test_sessions_api.py).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from .test_sessions_api import _create, client  # noqa: F401 (Fixture-Reexport)


def _drain_to_state(ws, *, allow: tuple[str, ...] = ("message", "activity", "ping")):
    """Frames lesen, bis ein `state`-Frame kommt (transiente Frames überspringen)."""
    for _ in range(10):
        msg = ws.receive_json()
        if msg["kind"] == "state":
            return msg
        assert msg["kind"] in allow, f"unerwarteter Frame: {msg['kind']}"
    raise AssertionError("kein state-Frame erhalten")


def test_snapshot_carries_full_transcript_for_resync(client: TestClient):
    """AC Replay/Resync: der Connect-Snapshot enthält den Transkript-Vollzustand —
    identisch zu dem, was REST `GET /{id}` liefert. So lädt JEDER Reconnect den
    aktuellen Stand nach, ohne Re-Polling."""
    sid = _create(client).json()["session_id"]
    rest = client.get(f"/sessions/{sid}").json()["transcript"]
    assert rest, "Vorbedingung: FakeDriver hat Transkript erzeugt"

    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        snap = ws.receive_json()
        assert snap["kind"] == "state"
        assert snap["session_id"] == sid
        # Vollständig: gleiche Anzahl + identische Texte wie der REST-Vollzustand.
        assert [e["text"] for e in snap["transcript"]] == [e["text"] for e in rest]


def test_reconnect_yields_same_full_snapshot(client: TestClient):
    """AC Stabile-WS/Idempotenz: ein zweiter Connect (= Reconnect nach Flapping)
    liefert wieder den Voll-Snapshot — keine ab-Verbindungszeit „leere" Subscription."""
    sid = _create(client).json()["session_id"]
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws1:
        first = ws1.receive_json()["transcript"]
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws2:
        second = ws2.receive_json()["transcript"]
    assert first and second
    assert [e["text"] for e in first] == [e["text"] for e in second]


def test_live_state_broadcast_omits_transcript(client: TestClient):
    """Frontend-Invariante: NUR der Connect-Snapshot trägt `transcript`. Ein Live-
    `state`-Broadcast (hier: Schwellen-PATCH) darf KEIN `transcript` enthalten —
    sonst würde der Client den seit-Snapshot-Strom (`liveText`) fälschlich leeren."""
    sid = _create(client).json()["session_id"]
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        snap = _drain_to_state(ws)
        assert "transcript" in snap  # Connect-Snapshot trägt es

        # Schwelle ändern → Server broadcastet einen frischen state-Snapshot.
        r = client.patch(f"/sessions/{sid}/threshold", json={"threshold_pct": 55})
        assert r.status_code == 200
        live = _drain_to_state(ws)
        assert "transcript" not in live, "Live-state-Frame darf kein transcript tragen"
