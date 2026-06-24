"""Spracheingabe-Transkription (PROJ-20).

Standard ist **self-hosted faster-whisper** (lokal auf dem VPS, kein API-Key, keine
laufenden Kosten); optionaler **Groq-Fallback** (pay-per-use) wird per ``.env``
freigeschaltet und ist eine bewusste Nutzerentscheidung (Audio verlässt dann das
System). Kein DB/JWT (Jupiter-Override). Audio wird NICHT dauerhaft gespeichert —
es lebt nur als Temp-Datei während der Transkription und wird danach gelöscht.

Das eigentliche Whisper-Modell wird **lazy** geladen (erster Aufruf) und im Prozess
gehalten. Der lokale Transkriptions-Aufruf ist über ``local_runner`` injizierbar
(Tests geben einen Fake → kein Modell-Download nötig); analog der Groq-Aufruf über
``groq_runner``.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from ..config import settings

# (audio_path, language) -> erkannter Text. Trennt die Engine vom HTTP-/IO-Pfad.
Runner = Callable[[str, str], Awaitable[str]]

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"
_GROQ_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=15.0)


class TranscriptionError(RuntimeError):
    """Fachlicher Fehler (klare deutsche Meldung fürs Frontend)."""


@dataclass
class TranscriptionOutcome:
    transcript: str
    provider: str  # "faster-whisper" | "groq"


class TranscriptionService:
    """Wählt die Engine anhand der Settings und transkribiert eine Audiodatei."""

    def __init__(
        self,
        local_runner: Runner | None = None,
        groq_runner: Runner | None = None,
    ) -> None:
        self._local_runner = local_runner or self._faster_whisper
        self._groq_runner = groq_runner or self._groq
        self._model = None  # lazy-geladenes faster-whisper-Modell (Cache).

    # --- Settings-Helfer ---------------------------------------------------

    @staticmethod
    def groq_available() -> bool:
        return bool(settings.groq_api_key)

    @staticmethod
    def use_groq() -> bool:
        """Groq nur, wenn bewusst aktiviert UND ein Key konfiguriert ist."""
        return bool(settings.use_groq_transcription and settings.groq_api_key)

    # --- Öffentlicher Pfad -------------------------------------------------

    async def transcribe(self, audio: bytes, language: str | None = None) -> TranscriptionOutcome:
        if not audio:
            raise TranscriptionError("Leere Aufnahme — bitte erneut sprechen.")
        lang = (language or settings.whisper_language or "de").strip() or "de"

        # Audio nur transient als Temp-Datei (faster-whisper/ffmpeg dekodiert webm/opus).
        suffix = ".webm"
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="jupiter-ptt-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(audio)
            if self.use_groq():
                text = await self._groq_runner(path, lang)
                provider = "groq"
            else:
                text = await self._local_runner(path, lang)
                provider = "faster-whisper"
        finally:
            try:
                os.remove(path)  # Audio nie dauerhaft speichern.
            except OSError:
                pass
        return TranscriptionOutcome(transcript=text.strip(), provider=provider)

    # --- Engines -----------------------------------------------------------

    async def _faster_whisper(self, audio_path: str, language: str) -> str:
        """Lokale Transkription. Lazy-Import: fehlt die Lib, klare 503-taugliche Meldung."""
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - Umgebungsfrage
            raise TranscriptionError(
                "Lokale Transkription nicht verfügbar (faster-whisper nicht installiert). "
                "Entweder installieren oder den Groq-Fallback in den Einstellungen aktivieren."
            ) from exc

        # Modell einmalig laden (CPU/int8 — GPU-loser Dev-VPS) und im Prozess halten.
        import anyio

        def _run() -> str:
            if self._model is None:
                self._model = WhisperModel(
                    settings.whisper_model, device="cpu", compute_type="int8"
                )
            segments, _info = self._model.transcribe(audio_path, language=language)
            return "".join(seg.text for seg in segments)

        try:
            return await anyio.to_thread.run_sync(_run)
        except TranscriptionError:
            raise
        except Exception as exc:  # noqa: BLE001 - jede Whisper-/Decode-Panne freundlich melden
            raise TranscriptionError("Transkription fehlgeschlagen (lokales Whisper).") from exc

    async def _groq(self, audio_path: str, language: str) -> str:
        key = settings.groq_api_key
        if not key:
            raise TranscriptionError("Groq ist aktiviert, aber kein API-Key konfiguriert.")
        try:
            with open(audio_path, "rb") as fh:
                files = {"file": ("aufnahme.webm", fh, "audio/webm")}
                data = {"model": GROQ_MODEL, "language": language, "response_format": "json"}
                headers = {"Authorization": f"Bearer {key}"}
                async with httpx.AsyncClient(timeout=_GROQ_TIMEOUT) as client:
                    resp = await client.post(GROQ_URL, headers=headers, data=data, files=files)
            if resp.status_code != 200:
                raise TranscriptionError(
                    f"Groq-Transkription fehlgeschlagen (HTTP {resp.status_code})."
                )
            return str(resp.json().get("text", ""))
        except TranscriptionError:
            raise
        except httpx.HTTPError as exc:
            raise TranscriptionError("Groq nicht erreichbar.") from exc
