"""Pydantic-v2-Schemas für die Spracheingabe (PROJ-20)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptionResult(BaseModel):
    """Antwort von POST /transcription — Transkript + erzeugende Engine."""

    transcript: str
    provider: str = Field(..., description='"faster-whisper" (lokal) oder "groq" (Cloud).')


class TranscriptionSettingRead(BaseModel):
    """Aktuelle Transkriptions-Quelle + Verfügbarkeit des Groq-Fallbacks."""

    use_groq: bool
    groq_available: bool
    model: str
    language: str


class TranscriptionSettingPatch(BaseModel):
    """Cloud-Fallback (Groq) bewusst an/aus. 400, wenn an ohne konfigurierten Key."""

    use_groq: bool = Field(..., description="True = Groq-Cloud-Fallback nutzen (nur mit Key).")
