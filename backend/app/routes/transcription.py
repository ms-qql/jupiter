"""Spracheingabe-Transkription (PROJ-20).

Ein Endpunkt nimmt die Audioaufnahme (multipart) entgegen und gibt das Transkript
zurück. Die Engine-Wahl (self-hosted faster-whisper vs. Groq-Cloud) entscheidet der
``TranscriptionService`` anhand der Settings. Kein JWT/DB (Jupiter-Override). Audio
wird NICHT gespeichert.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..config import settings
from ..engine.transcription import TranscriptionError, TranscriptionService
from ..schemas.transcription import TranscriptionResult

router = APIRouter(prefix="/transcription", tags=["transcription"])


def _svc(request: Request) -> TranscriptionService:
    return request.app.state.transcription


@router.post("", response_model=TranscriptionResult)
async def transcribe(
    request: Request,
    audio: UploadFile = File(..., description="Audioaufnahme (z. B. webm/opus)."),
    language: str | None = Form(None, description="ISO-Sprachcode; Default = Server-Setting (de)."),
) -> dict:
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Leere Aufnahme — bitte erneut sprechen.")
    if len(data) > settings.max_audio_bytes:
        mb = settings.max_audio_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Aufnahme zu groß (max. {mb} MB).")
    try:
        outcome = await _svc(request).transcribe(data, language)
    except TranscriptionError as exc:
        # Fachfehler (kein Mikro-/Dienst-/Key-Problem soll 500 sein) → 503 mit Klartext.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"transcript": outcome.transcript, "provider": outcome.provider}
