"""PROJ-20 — Spracheingabe / Push-to-Talk (Backend).

Isoliert: die echten Whisper-/Groq-Aufrufe werden über injizierte Fake-Runner
ersetzt (kein Modell-Download, kein Netzwerk). Kein JWT/DB (Jupiter-Override).
Geprüft: Engine-Wahl (lokal/Groq), Validierung (leer/zu groß), Fehler-Mapping,
Settings-Endpunkte + Groq-Guard.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.transcription import TranscriptionError, TranscriptionService
from app.main import create_app

from .fakes import FakeDriver

WEBM = b"\x1aE\xdf\xa3" + b"0" * 64  # plausibler webm-Header + Füllbytes


@pytest.fixture(autouse=True)
def _reset_transcription_settings(monkeypatch):
    # Deterministischer Ausgangszustand je Test.
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "use_groq_transcription", False)
    monkeypatch.setattr(settings, "whisper_model", "small")
    monkeypatch.setattr(settings, "whisper_language", "de")


def _client(local_text: str = "hallo welt", groq_text: str = "groq text") -> TestClient:
    """Client mit Fake-Runnern; merkt sich die zuletzt gesehene Sprache."""
    seen: dict[str, str] = {}

    async def fake_local(path: str, language: str) -> str:
        seen["local_lang"] = language
        return local_text

    async def fake_groq(path: str, language: str) -> str:
        seen["groq_lang"] = language
        return groq_text

    app = create_app(driver_factory=lambda: FakeDriver())
    app.state.transcription = TranscriptionService(local_runner=fake_local, groq_runner=fake_groq)
    client = TestClient(app)
    client.seen = seen  # type: ignore[attr-defined]
    return client


def _post_audio(client: TestClient, data: bytes = WEBM, language: str | None = None):
    files = {"audio": ("aufnahme.webm", data, "audio/webm")}
    form = {"language": language} if language is not None else None
    return client.post("/transcription", files=files, data=form)


# --- Happy Path: self-hosted ist der Default ------------------------------

def test_local_transcription_is_default():
    client = _client(local_text="das ist ein test")
    resp = _post_audio(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["transcript"] == "das ist ein test"
    assert body["provider"] == "faster-whisper"
    assert client.seen["local_lang"] == "de"  # Default-Sprache


def test_language_override_is_passed_through():
    client = _client()
    resp = _post_audio(client, language="en")
    assert resp.status_code == 200
    assert client.seen["local_lang"] == "en"


# --- Engine-Wahl: Groq nur bewusst + mit Key ------------------------------

def test_groq_used_when_enabled_and_key_present(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(settings, "use_groq_transcription", True)
    client = _client(groq_text="cloud transkript")
    resp = _post_audio(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "groq"
    assert body["transcript"] == "cloud transkript"


def test_groq_toggle_without_key_stays_local(monkeypatch):
    # use_groq an, aber KEIN Key → fällt auf lokal zurück (kein stiller Cloud-Versand).
    monkeypatch.setattr(settings, "use_groq_transcription", True)
    monkeypatch.setattr(settings, "groq_api_key", "")
    client = _client()
    resp = _post_audio(client)
    assert resp.status_code == 200
    assert resp.json()["provider"] == "faster-whisper"


# --- Validierung ----------------------------------------------------------

def test_empty_audio_rejected():
    client = _client()
    resp = _post_audio(client, data=b"")
    assert resp.status_code == 400


def test_oversized_audio_rejected(monkeypatch):
    monkeypatch.setattr(settings, "max_audio_bytes", 100)
    client = _client()
    resp = _post_audio(client, data=b"0" * 200)
    assert resp.status_code == 413


# --- Fehler-Mapping: Fachfehler → 503 mit Klartext ------------------------

def test_runner_error_maps_to_503():
    async def boom(path: str, language: str) -> str:
        raise TranscriptionError("Lokales Whisper kaputt.")

    app = create_app(driver_factory=lambda: FakeDriver())
    app.state.transcription = TranscriptionService(local_runner=boom)
    client = TestClient(app)
    resp = _post_audio(client)
    assert resp.status_code == 503
    assert "Whisper" in resp.json()["detail"]


# --- Settings-Endpunkte ---------------------------------------------------

def test_get_transcription_settings_default():
    client = _client()
    resp = client.get("/settings/transcription")
    assert resp.status_code == 200
    body = resp.json()
    assert body["use_groq"] is False
    assert body["groq_available"] is False
    assert body["model"] == "small"
    assert body["language"] == "de"


def test_patch_groq_without_key_is_400():
    client = _client()
    resp = client.patch("/settings/transcription", json={"use_groq": True})
    assert resp.status_code == 400


def test_patch_groq_with_key_enables(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk_test")
    client = _client()
    resp = client.patch("/settings/transcription", json={"use_groq": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["use_groq"] is True
    assert body["groq_available"] is True
    # Zustand persistiert im Prozess-Setting → GET spiegelt es.
    assert client.get("/settings/transcription").json()["use_groq"] is True


# --- Service-Ebene: Audio wird nicht dauerhaft gespeichert ----------------

async def test_temp_audio_is_removed_after_transcription(tmp_path, monkeypatch):
    seen_paths: list[str] = []

    async def fake_local(path: str, language: str) -> str:
        seen_paths.append(path)
        assert __import__("os").path.exists(path)  # während des Laufs vorhanden
        return "ok"

    svc = TranscriptionService(local_runner=fake_local)
    outcome = await svc.transcribe(WEBM)
    assert outcome.transcript == "ok"
    # Nach dem Lauf ist die Temp-Datei gelöscht (Datenschutz by default).
    import os

    assert seen_paths and not os.path.exists(seen_paths[0])
