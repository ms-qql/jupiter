"""Persistenz-Schicht (PROJ-14).

Heute nur der **Session-Live-Index** (SQLite-Spiegel der In-Memory-Registry,
damit die Übersicht einen Backend-Neustart übersteht). Das Repository ist ein
abstraktes Seam (:class:`SessionIndexRepository`), auf dem PROJ-17 (Recovery)
und ein späterer Postgres/Neon-Tausch ohne Bruch aufsetzen.
"""
from __future__ import annotations

from .session_index import (
    NullSessionIndexRepository,
    SessionIndexRepository,
    SqliteSessionIndexRepository,
    build_session_index_repo,
)

__all__ = [
    "SessionIndexRepository",
    "SqliteSessionIndexRepository",
    "NullSessionIndexRepository",
    "build_session_index_repo",
]
