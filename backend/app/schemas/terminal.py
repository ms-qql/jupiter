"""Pydantic-v2-Schema für die VPS-Admin-Terminal-API (PROJ-43).

Read-only Auskunft, ob ein ttyd-Terminal-Dienst konfiguriert + gerade erreichbar
ist, plus die einzubettende (gleich-origin) URL. Kein Persistenz-/DB-Bedarf — die
Felder kommen aus der Backend-Config (``terminal_url``) und einem kurzen TCP-Probe.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TerminalInfo(BaseModel):
    """Antwort von ``GET /terminal/info``."""

    enabled: bool = Field(
        ...,
        description="Ist ein Terminal-Dienst konfiguriert (terminal_url gesetzt)? "
        "False → Frontend zeigt „nicht konfiguriert“ statt iFrame.",
    )
    url: str | None = Field(
        None,
        description="Einzubettende https-Adresse (gleiche Origin, aus der Config). "
        "Nur gesetzt, wenn enabled. Nie vom Client bestimmt.",
    )
    reachable: bool = Field(
        ...,
        description="Antwortet der lokale ttyd-Port gerade (kurzer TCP-Connect)? "
        "False → „Terminal nicht erreichbar“ + Retry statt leerer Fläche.",
    )
