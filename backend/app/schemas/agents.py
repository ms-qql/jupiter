"""Pydantic-v2-Schemas für Späher-Agenten (PROJ-19 #26)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..config import MAX_INPUT_CHARS


class ScoutRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS, description="Fazit-Aufgabe für den Späher.")
    query: str | None = Field(
        default=None, max_length=200, description="Optionale Vault-Query → RAG-Ausschnitte als Kontext."
    )
    paths: list[str] = Field(
        default_factory=list, max_length=50, description="Optionale vault-relative Datei-Pointer als Kontext."
    )
    project_path: str | None = Field(default=None, description="Arbeitsverzeichnis des Laufs (Default: Reader-Projekt).")
    model: str | None = Field(
        default=None, description="Modell-Override (Eskalation, z. B. sonnet/opus). Default: günstiges Späher-Modell."
    )
    top_n: int = Field(default=5, ge=1, le=20, description="Maximale Anzahl RAG-Ausschnitte.")


class ScoutResult(BaseModel):
    task: str
    model_used: str
    summary: str = Field(..., description="Verdichtetes Fazit (nur das, keine Rohdaten).")
    sources: list[str] = Field(default_factory=list, description="Herangezogene Vault-Pfade (Nachvollziehbarkeit).")
    context_chars: int = Field(..., description="Größe des eingelesenen Kontexts (Prompt) in Zeichen.")
    usable: bool = Field(..., description="False → Fazit zu dünn/leer; Eskalation empfohlen.")
    note: str | None = Field(default=None, description="Hinweis (z. B. Eskalations-Empfehlung).")
