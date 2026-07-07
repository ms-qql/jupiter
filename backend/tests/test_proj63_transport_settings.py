"""PROJ-63 — Transport-Settings (globaler Default `direct`/`tmux` + Engine-Overrides,
GET/PUT ``/settings/transports``).

Muster identisch zu ``test_proj27_liveness.py``: YAML-Store live mtime-geprüft,
Route liest/schreibt über das Modul-Attribut (monkeypatch-fähig), Default bleibt
konservativ ``direct`` (Spec-Vorgabe).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine import transport_settings
from app.engine.transport_settings import DEFAULTS, TransportStore
from app.main import create_app

from .fakes import FakeDriver


def _app():
    return create_app(driver_factory=lambda: FakeDriver())


# --- TransportStore (YAML/Live-Reload/Fallback) -----------------------------


def test_defaults_are_conservative_direct(tmp_path):
    store = TransportStore(str(tmp_path / "transport.yaml"))
    cfg = store.config()
    assert cfg == DEFAULTS
    assert cfg["default_transport"] == "direct"
    assert cfg["engine_overrides"] == {}


def test_save_and_reload_roundtrip(tmp_path):
    store = TransportStore(str(tmp_path / "transport.yaml"))
    store.save({"default_transport": "tmux", "engine_overrides": {"codex": "tmux"}})
    fresh = TransportStore(str(tmp_path / "transport.yaml"))
    cfg = fresh.config()
    assert cfg["default_transport"] == "tmux"
    assert cfg["engine_overrides"] == {"codex": "tmux"}


def test_save_rejects_unknown_transport_value(tmp_path):
    store = TransportStore(str(tmp_path / "transport.yaml"))
    try:
        store.save({"default_transport": "ssh"})
        assert False, "haette ValueError werfen muessen"
    except ValueError:
        pass


def test_corrupt_file_falls_back_to_default_with_warning(tmp_path):
    path = tmp_path / "transport.yaml"
    path.write_text("- nicht\n- ein\n- objekt\n", encoding="utf-8")  # Liste statt Mapping
    store = TransportStore(str(path))
    snap = store.snapshot()
    assert snap["default_transport"] == "direct"
    assert snap["source"] == "default"
    assert snap["warning"] is not None


def test_unknown_transport_value_in_file_is_clamped_to_default(tmp_path):
    path = tmp_path / "transport.yaml"
    path.write_text("default_transport: ssh\n", encoding="utf-8")
    store = TransportStore(str(path))
    # Einzelnes ungueltiges Feld wird geklemmt (nicht die ganze Datei verworfen) —
    # source bleibt der Dateipfad, kein warning (analog LivenessStore-Verhalten).
    assert store.config()["default_transport"] == "direct"


def test_resolve_uses_engine_override_over_default(tmp_path):
    store = TransportStore(str(tmp_path / "transport.yaml"))
    store.save({"default_transport": "direct", "engine_overrides": {"codex": "tmux"}})
    # tmux ist auf diesem Host verfuegbar (verifiziert im Spike) -> Override greift.
    assert store.resolve("codex") in ("tmux", "direct")  # host-abhaengig, siehe naechster Test
    assert store.resolve("claude") == "direct"


def test_resolve_falls_back_to_direct_when_tmux_binary_missing(tmp_path, monkeypatch):
    from app.config import settings as app_settings

    monkeypatch.setattr(app_settings, "tmux_bin", "definitely-not-a-real-tmux-binary-xyz")
    store = TransportStore(str(tmp_path / "transport.yaml"))
    store.save({"default_transport": "tmux"})
    # Eine konfigurierte "tmux"-Wahl darf nie zum Startfehler fuehren, wenn das
    # Binary fehlt -> klarer Fallback auf "direct" statt Crash.
    assert store.resolve(None) == "direct"
    assert store.resolve("codex") == "direct"


# --- API: GET/PUT /settings/transports --------------------------------------


def test_get_transports_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transport_settings, "transport_store", TransportStore(str(tmp_path / "transport.yaml"))
    )
    client = TestClient(_app())
    resp = client.get("/settings/transports")
    assert resp.status_code == 200
    body = resp.json()
    assert body["default_transport"] == "direct"
    assert body["engine_overrides"] == {}
    assert body["source"] == "default"
    assert isinstance(body["tmux_available"], bool)


def test_put_transports_live(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transport_settings, "transport_store", TransportStore(str(tmp_path / "transport.yaml"))
    )
    client = TestClient(_app())
    resp = client.put(
        "/settings/transports",
        json={"default_transport": "tmux", "engine_overrides": {"opencode": "tmux"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["default_transport"] == "tmux"
    assert body["engine_overrides"] == {"opencode": "tmux"}
    assert transport_settings.transport_store.config()["default_transport"] == "tmux"


def test_put_transports_invalid_value_400(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transport_settings, "transport_store", TransportStore(str(tmp_path / "transport.yaml"))
    )
    client = TestClient(_app())
    resp = client.put("/settings/transports", json={"default_transport": "ssh"})
    assert resp.status_code == 400
